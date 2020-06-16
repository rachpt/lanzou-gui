import sys
from PyQt5.QtCore import QUrl, pyqtSignal
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout
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
        self.urlChanged.connect(self._on_load_finished)

    def _on_load_finished(self):
        self.page().toHtml(self.Callable)

    def Callable(self, html_str):
        try:
            self.html = html_str
            js = """var l_name=document.getElementsByName('username');
                    if (l_name.length > 0) {{
                        l_name[0].value = '{}';
                    }};
                    var l_pwd=document.getElementsByName('password');
                    if (l_pwd.length > 0) {{
                        l_pwd[0].value = '{}';
                    }};""".format(self._user, self._pwd)
            self.page().runJavaScript(js)
        except: pass
        # except Exception as e:
        #     print("Err:", e)

    def onCookieAdd(self, cookie):
        name = cookie.name().data().decode('utf-8')
        value = cookie.value().data().decode('utf-8')
        self.cookies[name] = value

    def get_cookie(self):
        cookie_dict = {}
        for key, value in self.cookies.items():
            if key in ('ylogin', 'phpdisk_info'):
                cookie_dict[key] = value
        return cookie_dict


class LoginWindow(QDialog):
    cookie = pyqtSignal(object)

    def __init__(self, user=None, pwd=None, gui=False):
        super().__init__()
        self._user = user
        self._pwd = pwd
        self._base_url = 'https://pc.woozooo.com/'
        self._gui = gui
        self.setup()

    def setup(self):
        self.setWindowTitle('滑动滑块，完成登录')
        url = self._base_url + 'account.php?action=login&ref=/mydisk.php'
        QWebEngineProfile.defaultProfile().cookieStore().deleteAllCookies()
        self.web = MyWebEngineView(self._user, self._pwd)
        self.web.urlChanged.connect(self.get_cookie)
        self.web.resize(480, 400)
        self.web.load(QUrl(url))
        self.box = QVBoxLayout(self)
        self.box.addWidget(self.web)

    def get_cookie(self):
        home_url = self._base_url + 'mydisk.php'
        if self.web.url().toString() == home_url:
            cookie = self.web.get_cookie()
            if cookie:
                if self._gui:
                    try: print(";".join([f'{k}={v}' for k, v in cookie.items()]), end='')
                    except: pass
                else:
                    self.cookie.emit(cookie)
                self.reject()


if __name__ == "__main__":
    if len(sys.argv) == 3:
        username, password = sys.argv[1], sys.argv[2]
        app = QApplication(sys.argv)
        form = LoginWindow(username, password, gui=True)
        form.show()
        sys.exit(app.exec())
