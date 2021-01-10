import os
import re
# import browser_cookie3
# https://github.com/borisbabic/browser_cookie3/pull/70
from lanzou import browser_cookie3_n as browser_cookie3
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QRect, QTimer
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (QDialog, QLabel, QLineEdit, QTextEdit, QPushButton, QFormLayout,
                             QHBoxLayout, QVBoxLayout, QMessageBox, QFileDialog, QTabWidget, QWidget)

from lanzou.gui.others import QDoublePushButton, MyLineEdit, AutoResizingTextEdit
from lanzou.gui.qss import dialog_qss_style, btn_style
from lanzou.debug import logger, SRC_DIR
from lanzou import USE_WEB_ENG

if USE_WEB_ENG:  # 此处不能移动到后面，会抛出异常
    from lanzou.login_assister import LoginWindow


is_windows = True if os.name == 'nt' else False


def get_cookie_from_browser(site='https://pc.woozooo.com'):
    """直接读取浏览器的 cookie 数据库，优先返回 Firefox cookie，最后为 Chrome
    """
    cookie = {}
    domain = re.match(r".*://([^/]+)/?", site)
    domain = domain.groups()[0]
    domain = domain.split(".")
    domain = ".".join(domain[-2:])
    cookies = browser_cookie3.load(domain_name=domain)
    for c in cookies:
        if c.domain in site:
            if c.name in ("ylogin", 'phpdisk_info'):
                cookie[c.name] = c.value

    return cookie


class LoginDialog(QDialog):
    """登录对话框"""

    clicked_ok = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self._cwd = os.getcwd()
        self._config = config
        self._cookie_assister = 'login_assister.exe'
        self._user = ""
        self._pwd = ""
        self._cookie = {}
        self._del_user = ""
        self.initUI()
        self.setStyleSheet(dialog_qss_style)
        self.setMinimumWidth(380)
        self.name_ed.setFocus()
        # 信号
        self.name_ed.textChanged.connect(self.set_user)
        self.pwd_ed.textChanged.connect(self.set_pwd)
        self.cookie_ed.textChanged.connect(self.set_cookie)

    def update_selection(self, user):
        """显示已经保存的登录用户信息"""
        user_info = self._config.get_user_info(user)
        if user_info:
            self._user = user_info[0]
            self._pwd = user_info[1]
            self._cookie = user_info[2]
        # 更新控件显示内容
        self.name_ed.setText(self._user)
        self.pwd_ed.setText(self._pwd)
        try: text = ";".join([f'{k}={v}' for k, v in self._cookie.items()])
        except: text = ''
        self.cookie_ed.setPlainText(text)

    def initUI(self):
        self.setWindowTitle("登录蓝奏云")
        self.setWindowIcon(QIcon(SRC_DIR + "login.ico"))
        logo = QLabel()
        logo.setPixmap(QPixmap(SRC_DIR + "logo3.gif"))
        logo.setStyleSheet("background-color:rgb(0,153,255);")
        logo.setAlignment(Qt.AlignCenter)

        self.tabs = QTabWidget()
        self.auto_tab = QWidget()
        self.hand_tab = QWidget()

        # Add tabs
        self.tabs.addTab(self.auto_tab,"自动获取Cookie")
        self.tabs.addTab(self.hand_tab,"手动输入Cookie")
        self.auto_get_cookie_ok = AutoResizingTextEdit("🔶点击👇自动获取浏览器登录信息👇")
        self.auto_get_cookie_ok.setReadOnly(True)
        self.auto_get_cookie_btn = QPushButton("自动读取浏览器登录信息")
        auto_cookie_notice = '支持浏览器：Chrome, Chromium, Opera, Edge, Firefox'
        self.auto_get_cookie_btn.setToolTip(auto_cookie_notice)
        self.auto_get_cookie_btn.clicked.connect(self.call_auto_get_cookie)
        self.auto_get_cookie_btn.setStyleSheet("QPushButton {min-width: 210px;max-width: 210px;}")

        self.name_lb = QLabel("&U 用户")
        self.name_lb.setAlignment(Qt.AlignCenter)
        self.name_ed = QLineEdit()
        self.name_lb.setBuddy(self.name_ed)

        self.pwd_lb = QLabel("&P 密码")
        self.pwd_lb.setAlignment(Qt.AlignCenter)
        self.pwd_ed = QLineEdit()
        self.pwd_ed.setEchoMode(QLineEdit.Password)
        self.pwd_lb.setBuddy(self.pwd_ed)

        self.cookie_lb = QLabel("&Cookie")
        self.cookie_ed = QTextEdit()
        notice = "由于滑动验证的存在，需要输入cookie，cookie请使用浏览器获取\n" + \
            "cookie会保存在本地，下次使用。其格式如下：\n ylogin=value1; phpdisk_info=value2"
        self.cookie_ed.setPlaceholderText(notice)
        self.cookie_lb.setBuddy(self.cookie_ed)

        self.show_input_cookie_btn = QPushButton("显示Cookie输入框")
        self.show_input_cookie_btn.setToolTip(notice)
        self.show_input_cookie_btn.setStyleSheet("QPushButton {min-width: 110px;max-width: 110px;}")
        self.show_input_cookie_btn.clicked.connect(self.change_show_input_cookie)
        self.ok_btn = QPushButton("登录")
        self.ok_btn.clicked.connect(self.change_ok_btn)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.change_cancel_btn)
        lb_line_1 = QLabel()
        lb_line_1.setText('<html><hr />切换用户</html>')
        lb_line_2 = QLabel()
        lb_line_2.setText('<html><hr /></html>')

        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignRight)
        self.form.addRow(self.name_lb, self.name_ed)
        self.form.addRow(self.pwd_lb, self.pwd_ed)
        if is_windows:
            def set_assister_path():
                """设置辅助登录程序路径"""
                assister_path = QFileDialog.getOpenFileName(self, "选择辅助登录程序路径",
                                                            self._cwd, "EXE Files (*.exe)")
                if not assister_path[0]:
                    return None
                assister_path = os.path.normpath(assister_path[0])  # windows backslash
                if assister_path == self._cookie_assister:
                    return None
                self.assister_ed.setText(assister_path)
                self._cookie_assister = assister_path

            self.assister_lb = QLabel("登录辅助程序")
            self.assister_lb.setAlignment(Qt.AlignCenter)
            self.assister_ed = MyLineEdit(self)
            self.assister_ed.setText(self._cookie_assister)
            self.assister_ed.clicked.connect(set_assister_path)
            self.assister_lb.setBuddy(self.assister_ed)
            self.form.addRow(self.assister_lb, self.assister_ed)

        hbox = QHBoxLayout()
        hbox.addWidget(self.show_input_cookie_btn)
        hbox.addStretch(1)
        hbox.addWidget(self.ok_btn)
        hbox.addWidget(self.cancel_btn)

        user_box = QHBoxLayout()
        self.user_num = 0
        self.user_btns = {}
        for user in self._config.users_name:
            user = str(user)  # TODO: 可能需要删掉
            self.user_btns[user] = QDoublePushButton(user)
            self.user_btns[user].setStyleSheet("QPushButton {border:none;}")
            if user == self._config.name:
                self.user_btns[user].setStyleSheet("QPushButton {background-color:rgb(0,153,2);}")
                self.tabs.setCurrentIndex(1)
            self.user_btns[user].setToolTip(f"点击选中，双击切换至用户：{user}")
            self.user_btns[user].doubleClicked.connect(self.choose_user)
            self.user_btns[user].clicked.connect(self.delete_chose_user)
            user_box.addWidget(self.user_btns[user])
            self.user_num += 1
            user_box.addStretch(1)

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(logo)
        vbox = QVBoxLayout()
        if self._config.name:
            vbox.addWidget(lb_line_1)
            user_box.setAlignment(Qt.AlignCenter)
            vbox.addLayout(user_box)
            vbox.addWidget(lb_line_2)
            if self.user_num > 1:
                self.del_user_btn = QPushButton("删除账户")
                self.del_user_btn.setIcon(QIcon(SRC_DIR + "delete.ico"))
                self.del_user_btn.setStyleSheet("QPushButton {min-width: 180px;max-width: 180px;}")
                self.del_user_btn.clicked.connect(self.call_del_chose_user)
                vbox.addWidget(self.del_user_btn)
            else:
                self.del_user_btn = None
            vbox.addStretch(1)

        vbox.addLayout(self.form)
        vbox.addStretch(1)
        vbox.addLayout(hbox)
        vbox.setAlignment(Qt.AlignCenter)

        self.hand_tab.setLayout(vbox)
        auto_cookie_vbox = QVBoxLayout()
        auto_cookie_vbox.addWidget(self.auto_get_cookie_ok)
        auto_cookie_vbox.addWidget(self.auto_get_cookie_btn)
        auto_cookie_vbox.setAlignment(Qt.AlignCenter)
        self.auto_tab.setLayout(auto_cookie_vbox)
        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)
        self.update_selection(self._config.name)

    def call_del_chose_user(self):
        if self._del_user:
            if self._del_user != self._config.name:
                self.user_num -= 1
                self._config.del_user(self._del_user)
                self.user_btns[self._del_user].close()
                self._del_user = ""
                if self.user_num <= 1:
                    self.del_user_btn.close()
                    self.del_user_btn = None
                return
            else:
                title = '不能删除'
                msg = '不能删除当前登录账户，请先切换用户！'
        else:
            title = '请选择账户'
            msg = '请单击选择需要删除的账户\n\n注意不能删除当前账户(绿色)'
        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Critical)
        message_box.setStyleSheet(btn_style)
        message_box.setWindowTitle(title)
        message_box.setText(msg)
        message_box.setStandardButtons(QMessageBox.Close)
        buttonC = message_box.button(QMessageBox.Close)
        buttonC.setText('关闭')
        message_box.exec()

    def delete_chose_user(self):
        """更改单击选中需要删除的用户"""
        user = str(self.sender().text())
        self._del_user = user
        if self.del_user_btn:
            self.del_user_btn.setText(f"删除 <{user}>")

    def choose_user(self):
        """切换用户"""
        user = self.sender().text()
        if user != self._config.name:
            self.ok_btn.setText("切换用户")
        else:
            self.ok_btn.setText("登录")
        self.update_selection(user)

    def change_show_input_cookie(self):
        row_c = 4 if is_windows else 3
        if self.form.rowCount() < row_c:
            self.org_height = self.height()
            self.form.addRow(self.cookie_lb, self.cookie_ed)
            self.show_input_cookie_btn.setText("隐藏Cookie输入框")
            self.change_height = None
            self.adjustSize()
        else:
            if not self.change_height:
                self.change_height = self.height()
            if self.cookie_ed.isVisible():
                self.cookie_lb.setVisible(False)
                self.cookie_ed.setVisible(False)
                self.show_input_cookie_btn.setText("显示Cookie输入框")
                start_height, end_height = self.change_height, self.org_height
            else:
                self.cookie_lb.setVisible(True)
                self.cookie_ed.setVisible(True)
                self.show_input_cookie_btn.setText("隐藏Cookie输入框")
                start_height, end_height = self.org_height, self.change_height
            gm = self.geometry()
            x, y = gm.x(), gm.y()
            wd = self.width()
            self.animation = QPropertyAnimation(self, b'geometry')
            self.animation.setDuration(400)
            self.animation.setStartValue(QRect(x, y, wd, start_height))
            self.animation.setEndValue(QRect(x, y, wd, end_height))
            self.animation.start()

    def set_user(self, user):
        self._user = user
        if not user:
            return None
        if user not in self._config.users_name:
            self.ok_btn.setText("添加用户")
            self.cookie_ed.setPlainText("")
        elif user != self._config.name:
            self.update_selection(user)
            self.ok_btn.setText("切换用户")
        else:
            self.update_selection(user)
            self.ok_btn.setText("登录")

    def set_pwd(self, pwd):
        if self._user in self._config.users_name:
            user_info = self._config.get_user_info(self._user)
            if pwd and pwd != user_info[1]:  # 改变密码，cookie作废
                self.cookie_ed.setPlainText("")
                self._cookie = None
            if not pwd:  # 输入空密码，表示删除对pwd的存储，并使用以前的cookie
                self._cookie = user_info[2]
                try: text = ";".join([f'{k}={v}' for k, v in self._cookie.items()])
                except: text = ''
                self.cookie_ed.setPlainText(text)
        self._pwd = pwd

    def set_cookie(self):
        cookies = self.cookie_ed.toPlainText()
        if cookies:
            try:
                self._cookie = {kv.split("=")[0].strip(" "): kv.split("=")[1].strip(" ") for kv in cookies.split(";")}
            except: self._cookie = None

    def change_cancel_btn(self):
        self.update_selection(self._config.name)
        self.close()

    def change_ok_btn(self):
        if self._user and self._pwd:
            if self._user not in self._config.users_name:
                self._cookie = None
        if self._cookie:
            up_info = {"name": self._user, "pwd": self._pwd, "cookie": self._cookie, "work_id": -1}
            if self.ok_btn.text() == "切换用户":
                self._config.change_user(self._user)
            else:
                self._config.set_infos(up_info)
            self.clicked_ok.emit()
            self.close()
        elif USE_WEB_ENG:
            self.web = LoginWindow(self._user, self._pwd)
            self.web.cookie.connect(self.get_cookie_by_web)
            self.web.setWindowModality(Qt.ApplicationModal)
            self.web.exec()
        elif os.path.isfile(self._cookie_assister):
            try:
                result = os.popen(f'{self._cookie_assister} {self._user} {self._pwd}')
                cookie = result.read()
                try:
                    self._cookie = {kv.split("=")[0].strip(" "): kv.split("=")[1].strip(" ") for kv in cookie.split(";")}
                except: self._cookie = None
                if not self._cookie:
                    return None
                up_info = {"name": self._user, "pwd": self._pwd, "cookie": self._cookie, "work_id": -1}
                self._config.set_infos(up_info)
                self.clicked_ok.emit()
                self.close()
            except: pass
        else:
            title = '请使用 Cookie 登录或是选择 登录辅助程序'
            msg = '没有输入 Cookie，或者没有找到登录辅助程序！\n\n' + \
                  '推荐使用浏览器获取 cookie 填入 cookie 输入框\n\n' + \
                  '如果不嫌文件体积大，请下载登录辅助程序：\n' + \
                  'https://github.com/rachpt/lanzou-gui/releases'
            message_box = QMessageBox(self)
            message_box.setIcon(QMessageBox.Critical)
            message_box.setStyleSheet(btn_style)
            message_box.setWindowTitle(title)
            message_box.setText(msg)
            message_box.setStandardButtons(QMessageBox.Close)
            buttonC = message_box.button(QMessageBox.Close)
            buttonC.setText('关闭')
            message_box.exec()

    def get_cookie_by_web(self, cookie):
        """使用辅助登录程序槽函数"""
        self._cookie = cookie
        self._close_dialog()

    def call_auto_get_cookie(self):
        """自动读取浏览器cookie槽函数"""
        try:
            self._cookie = get_cookie_from_browser()
        except Exception as e:
            logger.error(f"Browser_cookie3 Error: {e}")
            self.auto_get_cookie_ok.setPlainText(f"❌获取失败，错误信息\n{e}")
        else:
            if self._cookie:
                self._user = self._pwd = ''
                self.auto_get_cookie_ok.setPlainText("✅获取成功即将登录……")
                QTimer.singleShot(2000, self._close_dialog)
            else:
                self.auto_get_cookie_ok.setPlainText("❌获取失败\n请提前使用支持的浏览器登录蓝奏云，读取前完全退出浏览器！\n支持的浏览器与顺序：\nchrome, chromium, opera, edge, firefox")

    def _close_dialog(self):
        """关闭对话框"""
        up_info = {"name": self._user, "pwd": self._pwd, "cookie": self._cookie}
        self._config.set_infos(up_info)
        self.clicked_ok.emit()
        self.close()
