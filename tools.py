import re
import requests
from random import choice
from collections import namedtuple


headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:74.0) Gecko/20100101 Firefox/74.0'}
KEY = 152

def get_short_url(url: str):
    """短链接生成器"""
    short_url = ""
    api_infos = ['http://xuewaurl.cn/user/info', 'http://yldwz.cn/user/info', 'http://knurl.cn/user/info']
    apis = ['http://pay.jump-api.cn/tcn/web/test', 'http://pay.jump-api.cn/urlcn/web/test']  # 新浪、腾讯
    try:
        http = requests.get(choice(api_infos), verify=False, headers=headers)
        infos = http.json()

        uid = infos["uid"]
        username = infos["username"]
        token = infos["token"]
        site_id = infos["site_id"]
        role = infos["role"]
        fid = infos["fid"]

        post_data = {
            "uid": uid,
            "username": username,
            "token": token,
            "site_id": site_id,
            "role": role,
            "fid": fid,
            "url_long": url
        }
        for api in apis:
            resp = requests.post(api, data=post_data, verify=False, headers=headers)
            if 'http' in resp.text:
                short_url = resp.text
                break
    except: pass

    if not short_url:
        chinaz_api = 'http://tool.chinaz.com/tools/dwz.aspx'
        post_data = {"longurl":url, "aliasurl":""}
        try:
            html = requests.post(chinaz_api, data=post_data, verify=False, headers=headers).text
            short_url = re.findall('id="shorturl">(http[^<]*?)</span>', html)
            if short_url:
                short_url = short_url[0] 
        except: pass
    return short_url


class UserInfo():
    """存储登录用户信息"""
    def __init__(self, name=None, pwd=None, cookie=None):
        self._username = self.encode(name)
        self._pwd = self.encode(pwd)
        self._cookie = self.encode(cookie)
        self._settings = {}

    def encode(self, var):
        if isinstance(var, dict):
            for k, v in var.items():
                var[k] = encrypt(KEY, str(v))
        elif var:
            var = encrypt(KEY, str(var))
        return var

    def decode(self, var):
        try:
            if isinstance(var, dict):
                dvar = {}  # 新开内存，否则会修改原字典
                for k, v in var.items():
                    dvar[k] = decrypt(KEY, str(v))
            elif var:
                dvar = decrypt(KEY, var)
            else:
                dvar = None
        except:
            dvar = None
        return dvar

    @property
    def name(self):
        return self.decode(self._username)

    @property
    def pwd(self):
        return self.decode(self._pwd)

    @property
    def cookie(self):
        return self.decode(self._cookie)

    @cookie.setter
    def cookie(self, cookie):
        self._cookie = self.encode(cookie)

    @property
    def settings(self):
        return self._settings

    @settings.setter
    def settings(self, settings):
        self._settings = settings

    def set_infos(self, infos: dict):
        if "name" in infos:
            self._username = self.encode(infos["name"])
        if "pwd" in infos:
            self._pwd = self.encode(infos["pwd"])
        if "cookie" in infos:
            self._cookie = self.encode(infos["cookie"])


def encrypt(key, s):
    b = bytearray(str(s).encode("utf-8"))
    n = len(b)
    c = bytearray(n*2)
    j = 0
    for i in range(0, n):
        b1 = b[i]
        b2 = b1 ^ key
        c1 = b2 % 19
        c2 = b2 // 19
        c1 = c1 + 46
        c2 = c2 + 46
        c[j] = c1
        c[j+1] = c2
        j = j+2
    return c.decode("utf-8")


def decrypt(ksa, s):
    c = bytearray(str(s).encode("utf-8"))
    n = len(c)
    if n % 2 != 0:
        return ""
    n = n // 2
    b = bytearray(n)
    j = 0
    for i in range(0, n):
        c1 = c[j]
        c2 = c[j + 1]
        j = j + 2
        c1 = c1 - 46
        c2 = c2 - 46
        b2 = c2 * 19 + c1
        b1 = b2 ^ ksa
        b[i] = b1
    return b.decode("utf-8")


# PyQt5 信号传递数据
DlJob = namedtuple('DlJob', ['name', 'url', 'pwd', 'path', 'info', 'run', 'rate'], defaults=('', '', '', '', None, False, 0))
UpJob = namedtuple('UpJob', ['furl', 'id', 'folder', 'info', 'run', 'rate', 'set_pwd', 'pwd', 'set_desc', 'desc'], defaults=('', -1, '', None, False, 0, False, '', False, ''))
