from pickle import load, dump
from lanzou.debug import CONFIG_FILE, DL_DIR

__all__ = ['config']

KEY = 152  # config 加密 key


default_settings = {
    "download_threads": 3,     # 同时三个下载任务
    "timeout": 5,              # 每个请求的超时 s(不包含下载响应体的用时)
    "max_size": 100,           # 单个文件大小上限 MB
    "dl_path": DL_DIR,
    "time_fmt": False,         # 是否使用年月日时间格式
    "to_tray": False,          # 关闭到系统托盘
    "watch_clipboard": False,  # 监听系统剪切板
    "debug": False,            # 调试
    "set_pwd": False,
    "pwd": "",
    "set_desc": False,
    "desc": "",
    "upload_delay": 20,        # 上传大文件延时 0 - 20s
    "allow_big_file": False,
    "upgrade": True
}


def encrypt(key, s):
    b = bytearray(str(s).encode("utf-8"))
    n = len(b)
    c = bytearray(n * 2)
    j = 0
    for i in range(0, n):
        b1 = b[i]
        b2 = b1 ^ key
        c1 = b2 % 19
        c2 = b2 // 19
        c1 = c1 + 46
        c2 = c2 + 46
        c[j] = c1
        c[j + 1] = c2
        j = j + 2
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


def save_config(cf):
    with open(CONFIG_FILE, 'wb') as f:
        dump(cf, f)


class Config:
    """存储登录用户信息"""
    def __init__(self):
        self._users = {}
        self._cookie = ''
        self._name = ''
        self._pwd = ''
        self._work_id = -1
        self._settings = default_settings

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
        except Exception:
            dvar = None
        return dvar

    def update_user(self):
        if self._name:
            self._users[self._name] = (self._cookie, self._name, self._pwd,
                                       self._work_id, self._settings)
            save_config(self)

    def del_user(self, name) -> bool:
        name = self.encode(name)
        if name in self._users:
            del self._users[name]
            return True
        return False

    def change_user(self, name) -> bool:
        name = self.encode(name)
        if name in self._users:
            self.update_user()  # 切换用户前保持目前用户信息
            user = self._users[name]
            self._cookie = user[0]
            self._name = user[1]
            self._pwd = user[2]
            self._work_id = user[3]
            self._settings = user[4]
            save_config(self)
            return True
        return False

    @property
    def users_name(self) -> list:
        return [self.decode(user) for user in self._users]

    def get_user_info(self, name):
        """返回用户名、pwd、cookie"""
        en_name = self.encode(name)
        if en_name in self._users:
            user_info = self._users[en_name]
            return (name, self.decode(user_info[2]), self.decode(user_info[0]))

    def default_path(self):
        path = default_settings['dl_path']
        self._settings.update({'dl_path': path})
        save_config(self)

    @property
    def default_settings(self):
        return default_settings

    @property
    def name(self):
        return self.decode(self._name)

    @property
    def pwd(self):
        return self.decode(self._pwd)

    @property
    def cookie(self):
        return self.decode(self._cookie)

    @cookie.setter
    def cookie(self, cookie):
        self._cookie = self.encode(cookie)
        save_config(self)

    @property
    def work_id(self):
        return self._work_id

    @work_id.setter
    def work_id(self, work_id):
        self._work_id = work_id
        save_config(self)

    def set_cookie(self, cookie):
        self._cookie = self.encode(cookie)
        save_config(self)

    def set_username(self, username):
        self._name = self.encode(username)
        save_config(self)

    @property
    def path(self):
        return self._settings['dl_path']

    @path.setter
    def path(self, path):
        self._settings.update({'dl_path': path})
        save_config(self)

    @property
    def settings(self):
        return self._settings

    @settings.setter
    def settings(self, settings):
        self._settings = settings
        save_config(self)

    def set_infos(self, infos: dict):
        self.update_user()  # 切换用户前保持目前用户信息
        if "name" in infos:
            self._name = self.encode(infos["name"])
        if "pwd" in infos:
            self._pwd = self.encode(infos["pwd"])
        if "cookie" in infos:
            self._cookie = self.encode(infos["cookie"])
        if "path" in infos:
            self._settings.update({'dl_path': infos["path"]})
        if "work_id" in infos:
            self._work_id = infos["work_id"]
        if "settings" in infos:
            self._settings = infos["settings"]
        save_config(self)


# 全局配置对象
try:
    with open(CONFIG_FILE, 'rb') as c:
        config = load(c)
except:
    config = Config()
