# -*- coding: utf-8 -*-

import os
import os.path
import sys
import time
import glob
import http.cookiejar
import tempfile
import lz4.block
import datetime
import configparser
import base64
from Crypto.Cipher import AES
from typing import Union

try:
    import json
except ImportError:
    import simplejson as json
try:
    # should use pysqlite2 to read the cookies.sqlite on Windows
    # otherwise will raise the "sqlite3.DatabaseError: file is encrypted or is not a database" exception
    from pysqlite2 import dbapi2 as sqlite3
except ImportError:
    import sqlite3

# external dependencies
import keyring
import pyaes
from pbkdf2 import PBKDF2

__doc__ = 'Load browser cookies into a cookiejar'

class BrowserCookieError(Exception):
    pass


def create_local_copy(cookie_file):
    """Make a local copy of the sqlite cookie database and return the new filename.
    This is necessary in case this database is still being written to while the user browses
    to avoid sqlite locking errors.
    """
    # check if cookie file exists
    if os.path.exists(cookie_file):
        # copy to random name in tmp folder
        tmp_cookie_file = tempfile.NamedTemporaryFile(suffix='.sqlite').name
        open(tmp_cookie_file, 'wb').write(open(cookie_file, 'rb').read())
        return tmp_cookie_file
    else:
        raise BrowserCookieError('Can not find cookie file at: ' + cookie_file)


def windows_group_policy_path():
    # we know that we're running under windows at this point so it's safe to do these imports
    from winreg import ConnectRegistry, HKEY_LOCAL_MACHINE, OpenKeyEx, QueryValueEx, REG_EXPAND_SZ, REG_SZ
    try:
        root = ConnectRegistry(None, HKEY_LOCAL_MACHINE)
        policy_key = OpenKeyEx(root, r"SOFTWARE\Policies\Google\Chrome")
        user_data_dir, type_ = QueryValueEx(policy_key, "UserDataDir")
        if type_ == REG_EXPAND_SZ:
            user_data_dir = os.path.expandvars(user_data_dir)
        elif type_ != REG_SZ:
            return None
    except OSError:
        return None
    return os.path.join(user_data_dir, "Default", "Cookies")


# Code adapted slightly from https://github.com/Arnie97/chrome-cookies
def crypt_unprotect_data(
        cipher_text=b'', entropy=b'', reserved=None, prompt_struct=None, is_key=False
):
    # we know that we're running under windows at this point so it's safe to try these imports
    import ctypes
    import ctypes.wintypes

    class DataBlob(ctypes.Structure):
        _fields_ = [
            ('cbData', ctypes.wintypes.DWORD),
            ('pbData', ctypes.POINTER(ctypes.c_char))
        ]

    blob_in, blob_entropy, blob_out = map(
        lambda x: DataBlob(len(x), ctypes.create_string_buffer(x)),
        [cipher_text, entropy, b'']
    )
    desc = ctypes.c_wchar_p()

    CRYPTPROTECT_UI_FORBIDDEN = 0x01

    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), ctypes.byref(
                desc), ctypes.byref(blob_entropy),
            reserved, prompt_struct, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(
                blob_out)
    ):
        raise RuntimeError('Failed to decrypt the cipher text with DPAPI')

    description = desc.value
    buffer_out = ctypes.create_string_buffer(int(blob_out.cbData))
    ctypes.memmove(buffer_out, blob_out.pbData, blob_out.cbData)
    map(ctypes.windll.kernel32.LocalFree, [desc, blob_out.pbData])
    if is_key:
        return description, buffer_out.raw
    else:
        return description, buffer_out.value


def get_linux_pass(os_crypt_name):
    '''Retrive password used to encrypt cookies from libsecret.
    '''
    # https://github.com/n8henrie/pycookiecheat/issues/12
    my_pass = None

    import secretstorage
    connection = secretstorage.dbus_init()
    collection = secretstorage.get_default_collection(connection)
    secret = None
    
    # we should not look for secret with label. Sometimes label can be different. For example,
    # if Steam is installed before Chromium, Opera or Edge, it will show Steam Secret Storage as label.
    # insted we should look with schema and application
    secret = next(collection.search_items(
        {'xdg:schema': 'chrome_libsecret_os_crypt_password_v2',
            'application': os_crypt_name}), None)
    
    if not secret:
        # trying os_crypt_v1
        secret = next(collection.search_items(
            {'xdg:schema': 'chrome_libsecret_os_crypt_password_v1',
                'application': os_crypt_name}), None)

    if secret:
        my_pass = secret.get_secret()

    connection.close()

    # Try to get pass from keyring, which should support KDE / KWallet
    if not my_pass:
        try:
            import keyring.backends.kwallet
            keyring.set_keyring(keyring.backends.kwallet.DBusKeyring())
            my_pass = keyring.get_password(
                "{} Keys".format(os_crypt_name.capitalize()),
                "{} Safe Storage".format(os_crypt_name.capitalize())
            ).encode('utf-8')
        except RuntimeError:
            pass

    # try default peanuts password, probably won't work
    if not my_pass:
        my_pass = 'peanuts'.encode('utf-8')
    
    return my_pass

def __expand_win_path(path:Union[dict,str]):
    if not isinstance(path,dict):
        path = {'path': path}
    return os.path.join(os.getenv(path['env'], ''), path['path'])

def expand_paths(paths:list, os_name:str):
    '''Expands user paths on Linux, OSX, and windows
    '''

    os_name = os_name.lower()
    assert os_name in ['windows', 'osx', 'linux']

    if not isinstance(paths, list):
        paths = [paths]
    
    if os_name == 'windows':
        paths = map(__expand_win_path, paths)
    else:
        paths = map(os.path.expanduser, paths)
    
    paths = next(filter(os.path.exists, paths), None)
    return paths


class ChromiumBased:
    '''Super class for all Chromium based browser.
    '''
    def __init__(self, browser:str, cookie_file=None, domain_name="", key_file=None, **kwargs):
        self.salt = b'saltysalt'
        self.iv = b' ' * 16
        self.length = 16
        self.browser = browser
        self.cookie_file = cookie_file
        self.domain_name = domain_name
        self.key_file = key_file
        self.__add_key_and_cookie_file(**kwargs)
    
    def __add_key_and_cookie_file(self, 
            linux_cookies=None, windows_cookies=None, osx_cookies=None,
            windows_keys=None, os_crypt_name=None, osx_key_service=None, osx_key_user=None):

        if sys.platform == 'darwin':
            # running Chromium or it's derivatives on OSX
            import keyring.backends.OS_X
            keyring.set_keyring(keyring.backends.OS_X.Keyring())
            my_pass = keyring.get_password(osx_key_service, osx_key_user)

            # try default peanuts password, probably won't work
            if not my_pass:
                my_pass = 'peanuts'
            my_pass = my_pass.encode('utf-8')

            iterations = 1003  # number of pbkdf2 iterations on mac
            self.key = PBKDF2(my_pass, self.salt,
                              iterations=iterations).read(self.length)
            
            cookie_file = self.cookie_file or expand_paths(osx_cookies,'osx')
        
        elif sys.platform.startswith('linux'):
            my_pass = get_linux_pass(os_crypt_name)

            iterations = 1
            self.key = PBKDF2(my_pass, self.salt,
                              iterations=iterations).read(self.length)
            
            cookie_file = self.cookie_file or expand_paths(linux_cookies, 'linux')

        
        elif sys.platform == "win32":
            key_file = self.key_file or expand_paths(windows_keys,'windows')

            if key_file:
                with open(key_file,'rb') as f:
                    key_file_json = json.load(f)
                    key64 = key_file_json['os_crypt']['encrypted_key'].encode('utf-8')

                    # Decode Key, get rid of DPAPI prefix, unprotect data
                    keydpapi = base64.standard_b64decode(key64)[5:]
                    _, self.key = crypt_unprotect_data(keydpapi, is_key=True)

            # get cookie file from APPDATA
            
            cookie_file = self.cookie_file
            
            if not cookie_file:
                if self.browser.lower() == 'chrome' and windows_group_policy_path():
                    cookie_file = windows_group_policy_path()
                else:
                    cookie_file = expand_paths(windows_cookies,'windows')
        
        else:
            raise BrowserCookieError(
                "OS not recognized. Works on OSX, Windows, and Linux.")
        
        if not cookie_file:
                raise BrowserCookieError('Failed to find {} cookie'.format(self.browser))
        
        self.tmp_cookie_file = create_local_copy(cookie_file)

    def __del__(self):
        # remove temporary backup of sqlite cookie database
        if hasattr(self, 'tmp_cookie_file'):  # if there was an error till here
            os.remove(self.tmp_cookie_file)
    
    def __str__(self):
        return self.browser
    
    def load(self):
        """Load sqlite cookies into a cookiejar
        """
        con = sqlite3.connect(self.tmp_cookie_file)
        cur = con.cursor()
        try:
            # chrome <=55
            cur.execute('SELECT host_key, path, secure, expires_utc, name, value, encrypted_value '
                        'FROM cookies WHERE host_key like "%{}%";'.format(self.domain_name))
        except sqlite3.OperationalError:
            # chrome >=56
            cur.execute('SELECT host_key, path, is_secure, expires_utc, name, value, encrypted_value '
                        'FROM cookies WHERE host_key like "%{}%";'.format(self.domain_name))

        cj = http.cookiejar.CookieJar()
        epoch_start = datetime.datetime(1601, 1, 1)
        for item in cur.fetchall():
            host, path, secure, expires, name = item[:5]
            if item[3] != 0:
                # ensure dates don't exceed the datetime limit of year 10000
                try:
                    offset = min(int(item[3]), 265000000000000000)
                    delta = datetime.timedelta(microseconds=offset)
                    expires = epoch_start + delta
                    expires = expires.timestamp()
                # Windows 7 has a further constraint
                except OSError:
                    offset = min(int(item[3]), 32536799999000000)
                    delta = datetime.timedelta(microseconds=offset)
                    expires = epoch_start + delta
                    expires = expires.timestamp()

            value = self._decrypt(item[5], item[6])
            c = create_cookie(host, path, secure, expires, name, value)
            cj.set_cookie(c)
        con.close()
        return cj

    @staticmethod
    def _decrypt_windows_chromium(value, encrypted_value):

        if len(value) != 0:
            return value

        if encrypted_value == "":
            return ""

        _, data = crypt_unprotect_data(encrypted_value)
        assert isinstance(data, bytes)
        return data.decode()

    def _decrypt(self, value, encrypted_value):
        """Decrypt encoded cookies
        """

        if sys.platform == 'win32':
            try:
                return self._decrypt_windows_chromium(value, encrypted_value)

            # Fix for change in Chrome 80
            except RuntimeError:  # Failed to decrypt the cipher text with DPAPI
                if not self.key:
                    raise RuntimeError(
                        'Failed to decrypt the cipher text with DPAPI and no AES key.')
                # Encrypted cookies should be prefixed with 'v10' according to the
                # Chromium code. Strip it off.
                encrypted_value = encrypted_value[3:]
                nonce, tag = encrypted_value[:12], encrypted_value[-16:]
                aes = AES.new(self.key, AES.MODE_GCM, nonce=nonce)

                # will rise Value Error: MAC check failed byte if the key is wrong,
                # probably we did not got the key and used peanuts
                try:
                    data = aes.decrypt_and_verify(encrypted_value[12:-16], tag)
                except ValueError:
                    raise BrowserCookieError('Unable to get key for cookie decryption')
                return data.decode()

        if value or (encrypted_value[:3] not in [b'v11', b'v10']):
            return value

        # Encrypted cookies should be prefixed with 'v10' according to the
        # Chromium code. Strip it off.
        encrypted_value = encrypted_value[3:]
        encrypted_value_half_len = int(len(encrypted_value) / 2)

        cipher = pyaes.Decrypter(
            pyaes.AESModeOfOperationCBC(self.key, self.iv))
        
        # will rise Value Error: invalid padding byte if the key is wrong,
        # probably we did not got the key and used peanuts
        try:
            decrypted = cipher.feed(encrypted_value[:encrypted_value_half_len])
            decrypted += cipher.feed(encrypted_value[encrypted_value_half_len:])
            decrypted += cipher.feed()
        except ValueError:
            raise BrowserCookieError('Unable to get key for cookie decryption')
        return decrypted.decode("utf-8")

class Chrome(ChromiumBased):
    def __init__(self, cookie_file=None, domain_name="", key_file=None):
        args = {
            'linux_cookies':[
                    '~/.config/google-chrome/Default/Cookies',
                    '~/.config/google-chrome-beta/Default/Cookies'
                ],
            'windows_cookies':[
                    {'env':'APPDATA', 'path':'..\\Local\\Google\\Chrome\\User Data\\Default\\Cookies'},
                    {'env':'LOCALAPPDATA', 'path':'Google\\Chrome\\User Data\\Default\\Cookies'},
                    {'env':'APPDATA', 'path':'Google\\Chrome\\User Data\\Default\\Cookies'}
                ],
            'osx_cookies': ['~/Library/Application Support/Google/Chrome/Default/Cookies'],
            'windows_keys': [
                    {'env':'APPDATA', 'path':'..\\Local\\Google\\Chrome\\User Data\\Local State'},
                    {'env':'LOCALAPPDATA', 'path':'Google\\Chrome\\User Data\\Local State'},
                    {'env':'APPDATA', 'path':'Google\\Chrome\\User Data\\Local State'}
                ],
            'os_crypt_name':'chrome',
            'osx_key_service' : 'Chrome Safe Storage',
            'osx_key_user' : 'Chrome'
        }

        super().__init__(browser='Chrome', cookie_file=cookie_file, domain_name=domain_name, key_file=key_file, **args)

class Chromium(ChromiumBased):
    def __init__(self, cookie_file=None, domain_name="", key_file=None):
        args = {
            'linux_cookies':['~/.config/chromium/Default/Cookies'],
            'windows_cookies':[
                    {'env':'APPDATA', 'path':'..\\Local\\Chromium\\User Data\\Default\\Cookies'},
                    {'env':'LOCALAPPDATA', 'path':'Chromium\\User Data\\Default\\Cookies'},
                    {'env':'APPDATA', 'path':'Chromium\\User Data\\Default\\Cookies'}
            ],
            'osx_cookies': ['~/Library/Application Support/Chromium/Default/Cookies'],
            'windows_keys': [
                    {'env':'APPDATA', 'path':'..\\Local\\Chromium\\User Data\\Local State'},
                    {'env':'LOCALAPPDATA', 'path':'Chromium\\User Data\\Local State'},
                    {'env':'APPDATA', 'path':'Chromium\\User Data\\Local State'}
            ],
            'os_crypt_name':'chromium',
            'osx_key_service' : 'Chromium Safe Storage',
            'osx_key_user' : 'Chromium'
        }
        super().__init__(browser='Chromium', cookie_file=cookie_file, domain_name=domain_name, key_file=key_file, **args)

class Opera(ChromiumBased):
    def __init__(self, cookie_file=None, domain_name="", key_file=None):
        args = {
            'linux_cookies': ['~/.config/opera/Cookies'],
            'windows_cookies':[
                    {'env':'APPDATA', 'path':'..\\Local\\Opera Software\\Opera Stable\\Cookies'},
                    {'env':'LOCALAPPDATA', 'path':'Opera Software\\Opera Stable\\Cookies'},
                    {'env':'APPDATA', 'path':'Opera Software\\Opera Stable\\Cookies'}
            ],
            'osx_cookies': ['~/Library/Application Support/com.operasoftware.Opera/Cookies'],
            'windows_keys': [
                    {'env':'APPDATA', 'path':'..\\Local\\Opera Software\\Opera Stable\\Local State'},
                    {'env':'LOCALAPPDATA', 'path':'Opera Software\\Opera Stable\\Local State'},
                    {'env':'APPDATA', 'path':'Opera Software\\Opera Stable\\Local State'}
            ],
            'os_crypt_name':'chromium',
            'osx_key_service' : 'Opera Safe Storage',
            'osx_key_user' : 'Opera'
        }

        super().__init__(browser='Opera', cookie_file=cookie_file, domain_name=domain_name, key_file=key_file, **args)

class Edge(ChromiumBased):
    def __init__(self, cookie_file=None, domain_name="", key_file=None):
        args = {
            'linux_cookies': [
                '~/.config/microsoft-edge/Default/Cookies',
                '~/.config/microsoft-edge-dev/Default/Cookies'
            ],
            'windows_cookies':[
                    {'env':'APPDATA', 'path':'..\\Local\\Microsoft\\Edge\\User Data\\Default\\Cookies'},
                    {'env':'LOCALAPPDATA', 'path':'Microsoft\\Edge\\User Data\\Default\\Cookies'},
                    {'env':'APPDATA', 'path':'Microsoft\\Edge\\User Data\\Default\\Cookies'}
            ],
            'osx_cookies': ['~/Library/Application Support/Microsoft Edge/Default/Cookies'],
            'windows_keys': [
                    {'env':'APPDATA', 'path':'..\\Local\\Microsoft\\Edge\\User Data\\Local State'},
                    {'env':'LOCALAPPDATA', 'path':'Microsoft\\Edge\\User Data\\Local State'},
                    {'env':'APPDATA', 'path':'Microsoft\\Edge\\User Data\\Local State'}
            ],
            'os_crypt_name':'chromium',
            'osx_key_service' : 'Microsoft Edge Safe Storage',
            'osx_key_user' : 'Microsoft Edge'
        }

        super().__init__(browser='Edge', cookie_file=cookie_file, domain_name=domain_name, key_file=key_file, **args)

class Firefox:
    def __init__(self, cookie_file=None, domain_name=""):
        self.tmp_cookie_file = None
        cookie_file = cookie_file or self.find_cookie_file()
        self.tmp_cookie_file = create_local_copy(cookie_file)
        # current sessions are saved in sessionstore.js
        self.session_file = os.path.join(
            os.path.dirname(cookie_file), 'sessionstore.js')
        self.session_file_lz4 = os.path.join(os.path.dirname(
            cookie_file), 'sessionstore-backups', 'recovery.jsonlz4')
        # domain name to filter cookies by
        self.domain_name = domain_name

    def __del__(self):
        # remove temporary backup of sqlite cookie database
        if self.tmp_cookie_file:
            os.remove(self.tmp_cookie_file)

    def __str__(self):
        return 'firefox'

    @staticmethod
    def get_default_profile(user_data_path):
        config = configparser.ConfigParser()
        profiles_ini_path = glob.glob(os.path.join(
            user_data_path + '**', 'profiles.ini'))
        fallback_path = user_data_path + '**'

        if not profiles_ini_path:
            return fallback_path

        profiles_ini_path = profiles_ini_path[0]
        config.read(profiles_ini_path)

        profile_path = None
        for section in config.sections():
            if section.startswith('Install'):
                profile_path = config[section].get('Default')
                break
            # in ff 72.0.1, if both an Install section and one with Default=1 are present, the former takes precedence
            elif config[section].get('Default') == '1' and not profile_path:
                profile_path = config[section].get('Path')

        for section in config.sections():
            # the Install section has no relative/absolute info, so check the profiles
            if config[section].get('Path') == profile_path:
                absolute = config[section].get('IsRelative') == '0'
                return profile_path if absolute else os.path.join(os.path.dirname(profiles_ini_path), profile_path)

        return fallback_path

    @staticmethod
    def find_cookie_file():
        cookie_files = []

        if sys.platform == 'darwin':
            user_data_path = os.path.expanduser(
                '~/Library/Application Support/Firefox')
        elif sys.platform.startswith('linux'):
            user_data_path = os.path.expanduser('~/.mozilla/firefox')
        elif sys.platform == 'win32':
            user_data_path = os.path.join(
                os.environ.get('APPDATA'), 'Mozilla', 'Firefox')
            # legacy firefox <68 fallback
            cookie_files = glob.glob(os.path.join(os.environ.get('PROGRAMFILES'), 'Mozilla Firefox', 'profile', 'cookies.sqlite')) \
                or glob.glob(os.path.join(os.environ.get('PROGRAMFILES(X86)'), 'Mozilla Firefox', 'profile', 'cookies.sqlite'))
        else:
            raise BrowserCookieError(
                'Unsupported operating system: ' + sys.platform)

        cookie_files = glob.glob(os.path.join(Firefox.get_default_profile(user_data_path), 'cookies.sqlite')) \
            or cookie_files

        if cookie_files:
            return cookie_files[0]
        else:
            raise BrowserCookieError('Failed to find Firefox cookie')

    @staticmethod
    def __create_session_cookie(cookie_json):
        expires = str(int(time.time()) + 3600 * 24 * 7)
        # return create_cookie(cookie_json.get('host', ''), cookie_json.get('path', ''), False, expires,
        #                      cookie_json.get('name', ''), cookie_json.get('value', ''))
        return create_cookie(cookie_json.get('host', ''), cookie_json.get('path', ''),
                             cookie_json.get('secure', False), expires,
                             cookie_json.get('name', ''), cookie_json.get('value', ''))

    def __add_session_cookies(self, cj):
        if not os.path.exists(self.session_file):
            return
        try:
            json_data = json.loads(
                open(self.session_file, 'rb').read().decode())
        except ValueError as e:
            print('Error parsing firefox session JSON:', str(e))
        else:
            for window in json_data.get('windows', []):
                for cookie in window.get('cookies', []):
                    if self.domain_name == '' or self.domain_name in cookie.get('host', ''):
                        cj.set_cookie(Firefox.__create_session_cookie(cookie))

    def __add_session_cookies_lz4(self, cj):
        if not os.path.exists(self.session_file_lz4):
            return
        try:
            file_obj = open(self.session_file_lz4, 'rb')
            file_obj.read(8)
            json_data = json.loads(lz4.block.decompress(file_obj.read()))
        except ValueError as e:
            print('Error parsing firefox session JSON LZ4:', str(e))
        else:
            for cookie in json_data.get('cookies', []):
                if self.domain_name == '' or self.domain_name in cookie.get('host', ''):
                    cj.set_cookie(Firefox.__create_session_cookie(cookie))

    def load(self):
        con = sqlite3.connect(self.tmp_cookie_file)
        cur = con.cursor()
        cur.execute('select host, path, isSecure, expiry, name, value from moz_cookies '
                    'where host like "%{}%"'.format(self.domain_name))

        cj = http.cookiejar.CookieJar()
        for item in cur.fetchall():
            c = create_cookie(*item)
            cj.set_cookie(c)
        con.close()

        self.__add_session_cookies(cj)
        self.__add_session_cookies_lz4(cj)

        return cj


def create_cookie(host, path, secure, expires, name, value):
    """Shortcut function to create a cookie
    """
    return http.cookiejar.Cookie(0, name, value, None, False, host, host.startswith('.'), host.startswith('.'), path,
                                 True, secure, expires, False, None, None, {})

def chrome(cookie_file=None, domain_name="", key_file=None):
    """Returns a cookiejar of the cookies used by Chrome. Optionally pass in a
    domain name to only load cookies from the specified domain
    """
    return Chrome(cookie_file, domain_name, key_file).load()

def chromium(cookie_file=None, domain_name="", key_file=None):
    """Returns a cookiejar of the cookies used by Chromium. Optionally pass in a
    domain name to only load cookies from the specified domain
    """
    return Chromium(cookie_file, domain_name, key_file).load()

def opera(cookie_file=None, domain_name="", key_file=None):
    """Returns a cookiejar of the cookies used by Opera. Optionally pass in a
    domain name to only load cookies from the specified domain
    """
    return Opera(cookie_file, domain_name, key_file).load()

def edge(cookie_file=None, domain_name="", key_file=None):
    """Returns a cookiejar of the cookies used by Microsoft Egde. Optionally pass in a
    domain name to only load cookies from the specified domain
    """
    return Edge(cookie_file, domain_name, key_file).load()

def firefox(cookie_file=None, domain_name=""):
    """Returns a cookiejar of the cookies and sessions used by Firefox. Optionally
    pass in a domain name to only load cookies from the specified domain
    """
    return Firefox(cookie_file, domain_name).load()


def load(domain_name=""):
    """Try to load cookies from all supported browsers and return combined cookiejar
    Optionally pass in a domain name to only load cookies from the specified domain
    """
    cj = http.cookiejar.CookieJar()
    for cookie_fn in [chrome, chromium, opera, edge, firefox]:
        try:
            for cookie in cookie_fn(domain_name=domain_name):
                cj.set_cookie(cookie)
        except BrowserCookieError:
            pass
        if cj:
            break
    return cj


if __name__ == '__main__':
    print(load())
