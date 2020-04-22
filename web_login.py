from PyQt5.QtCore import QUrl, pyqtSignal
from PyQt5.QtWidgets import QDialog, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile


class MyWebEngineView(QWebEngineView):
    def __init__(self, user, pwd, *args, **kwargs):
        super(MyWebEngineView, self).__init__(*args, **kwargs)
        self.cookies = {}
        self._user = user
        self._pwd = pwd
        # 绑定cookie被添加的信号槽
        QWebEngineProfile.defaultProfile().cookieStore().cookieAdded.connect(self.onCookieAdd)
        self.loadFinished.connect(self._on_load_finished)

    def _on_load_finished(self):
        self.page().toHtml(self.Callable)

    def Callable(self, html_str):
        self.html = html_str
        self.page().runJavaScript(f"document.getElementsByName('username')[0].value = '{self._user}'")
        self.page().runJavaScript(f"document.getElementsByName('password')[0].value = '{self._pwd}'")

    def onCookieAdd(self, cookie):
        name = cookie.name().data().decode('utf-8')
        value = cookie.value().data().decode('utf-8')
        self.cookies[name] = value

    def get_cookie(self):
        cookie_dict = {}
        for key, value in self.cookies.items():
            if key in ['ylogin', 'phpdisk_info']:
                cookie_dict[key] = value
        return cookie_dict


class LoginWindow(QDialog):
    cookie = pyqtSignal(object)

    def __init__(self, user, pwd):
        super().__init__()
        self._user = user
        self._pwd = pwd
        self.setup()

    def setup(self):
        self.setWindowTitle('滑动滑块，完成登录')
        url = "https://pc.woozooo.com/account.php?action=login&ref=/mydisk.php"
        QWebEngineProfile.defaultProfile().cookieStore().deleteAllCookies()
        self.web = MyWebEngineView(self._user, self._pwd)
        self.web.urlChanged.connect(self.get_cookie)
        self.web.resize(480, 400)
        self.web.load(QUrl(url))
        self.box = QVBoxLayout(self)
        self.box.addWidget(self.web)

    def get_cookie(self):
        home_url = 'https://pc.woozooo.com/mydisk.php'
        if self.web.url().toString() == home_url:
            cookie = self.web.get_cookie()
            if cookie:
                self.cookie.emit(cookie)
                self.reject()
