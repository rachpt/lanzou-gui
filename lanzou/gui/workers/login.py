from PyQt6.QtCore import QThread, pyqtSignal, QMutex
from lanzou.api import LanZouCloud
from lanzou.debug import logger


class LoginLuncher(QThread):
    '''登录线程'''
    code = pyqtSignal(bool, str, int)
    update_cookie = pyqtSignal(object)
    update_username = pyqtSignal(object)

    def __init__(self, parent=None):
        super(LoginLuncher, self).__init__(parent)
        self._disk = None
        self.username = ""
        self.password = ""
        self.cookie = None

    def set_disk(self, disk):
        self._disk = disk

    def set_values(self, username, password, cookie=None):
        self.username = username
        self.password = password
        self.cookie = cookie
        self.start()

    def run(self):
        try:
            if self.cookie:
                res = self._disk.login_by_cookie(self.cookie)
                if res == LanZouCloud.SUCCESS:
                    if not self.username:
                        username = self._disk.get_user_name()
                        if isinstance(username, str):
                            self.update_username.emit(username)
                        logger.debug(f"login by Cookie: username={username}")
                    self.code.emit(True, "<font color='#00CC00'>通过<b>Cookie</b>登录<b>成功</b>！ ≧◉◡◉≦</font>", 5000)
                    return None
                logger.debug(f"login by Cookie err: res={res}")
            if (not self.username or not self.password) and not self.cookie:
                logger.debug("login err: No UserName、No cookie")
                self.code.emit(False, "<font color='red'>登录失败: 没有用户或密码</font>", 3000)
            else:
                res = self._disk.login(self.username, self.password)
                if res == LanZouCloud.SUCCESS:
                    self.code.emit(True, "<font color='#00CC00'>登录<b>成功</b>！ ≧◉◡◉≦</font>", 5000)
                    _cookie = self._disk.get_cookie()
                    self.update_cookie.emit(_cookie)
                else:
                    logger.debug(f"login err: res={res}")
                    self.code.emit(False, "<font color='red'>登录失败，可能是用户名或密码错误！</font>", 8000)
                    self.update_cookie.emit(None)
        except TimeoutError:
            self.code.emit(False, "<font color='red'>网络超时！</font>", 3000)
        except Exception as e:
            logger.error(f"LoginLuncher error: e={e}")


class LogoutWorker(QThread):
    '''登出'''
    succeeded = pyqtSignal()
    msg = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super(LogoutWorker, self).__init__(parent)
        self._disk = None
        self.update_ui = True
        self._mutex = QMutex()
        self._is_work = False

    def set_disk(self, disk):
        self._disk = disk

    def set_values(self, update_ui=True):
        self.update_ui = update_ui
        self.start()

    def __del__(self):
        self.wait()

    def stop(self):
        self._mutex.lock()
        self._is_work = False
        self._mutex.unlock()

    def run(self):
        if not self._is_work:
            self._mutex.lock()
            self._is_work = True
            try:
                res = self._disk.logout()
                if res == LanZouCloud.SUCCESS:
                    if self.update_ui:
                        self.succeeded.emit()
                    self.msg.emit("已经退出登录！", 4000)
                else:
                    self.msg.emit("失败，请重试！", 5000)
            except TimeoutError:
                self.msg.emit("网络超时，请稍后重试！", 6000)
            except Exception as e:
                logger.error(f"LogoutWorker error: e={e}")
            self._is_work = False
            self._mutex.unlock()
        else:
            self.msg.emit("后台正在运行，请稍后重试！", 3100)
