from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (QDialog, QLabel, QLineEdit, QTextEdit, QPushButton, QFormLayout,
                             QHBoxLayout, QVBoxLayout, QMessageBox)

from lanzou.gui.utils import dialog_qss_style, btn_style
from lanzou.gui.others import QDoublePushButton, MyLineEdit
from lanzou.gui.web_login import LoginWindow


class LoginDialog(QDialog):
    """登录对话框"""

    clicked_ok = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._cookie_assister = ''
        self._infos = {}
        self._users = {}
        self._user = ""
        self._user_old = ""
        self._del_user = ""
        self._pwd = ""
        self._cookie = {}
        self.initUI()
        self.setStyleSheet(dialog_qss_style)
        self.setMinimumWidth(350)
        # 信号
        self.name_ed.textChanged.connect(self.set_user)
        self.pwd_ed.textChanged.connect(self.set_pwd)
        self.cookie_ed.textChanged.connect(self.set_cookie)

    def update_selection(self, user):
        if self._infos and "choose" in self._infos:
            user_info = self._infos["users"][user]
            self._user = user_info.name
            self._pwd = user_info.pwd
            self._cookie = user_info.cookie
        self.name_ed.setText(self._user)
        self.pwd_ed.setText(self._pwd)
        try: text = ";".join([str(k) +'='+ str(v) for k, v in self._cookie.items()])
        except: text = ''
        self.cookie_ed.setPlainText(text)

    def initUI(self):
        self.setWindowTitle("登录蓝奏云")
        self.setWindowIcon(QIcon("./src/login.ico"))
        logo = QLabel()
        logo.setPixmap(QPixmap("./src/logo3.gif"))
        logo.setStyleSheet("background-color:rgb(0,153,255);")
        logo.setAlignment(Qt.AlignCenter)
        self.assister_lb = QLabel("登录辅助程序")
        self.assister_lb.setAlignment(Qt.AlignCenter)
        self.assister_ed = MyLineEdit(self)
        self.assister_lb.setBuddy(self.assister_ed)

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
        notice = "如果由于滑动验证，无法使用用户名与密码登录，则需要输入用户名和cookie，自行使用浏览器获取，\n" + \
            "cookie会保存在本地，下次使用。其格式如下：\n ylogin=value1; PHPSESSID=value2; phpdisk_info=value3"
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
        self.form.addRow(self.assister_lb, self.assister_ed)

        hbox = QHBoxLayout()
        hbox.addWidget(self.show_input_cookie_btn)
        hbox.addStretch(1)
        hbox.addWidget(self.ok_btn)
        hbox.addWidget(self.cancel_btn)
        # self.default_var()

        user_box = QHBoxLayout()
        self.user_num = 0
        self.user_btns = {}
        for user in self._users.keys():
            user = str(user)
            self.user_btns[user] = QDoublePushButton(user)
            self.user_btns[user].setStyleSheet("QPushButton {border:none;}")
            if user == self._user_old:
                self.user_btns[user].setStyleSheet("QPushButton {background-color:rgb(0,153,2);}")
            self.user_btns[user].setToolTip(f"点击选中，双击切换至用户：{user}")
            self.user_btns[user].doubleClicked.connect(self.choose_user)
            self.user_btns[user].clicked.connect(self.delete_chose_user)
            user_box.addWidget(self.user_btns[user])
            self.user_num += 1
            user_box.addStretch(1)

        vbox = QVBoxLayout()
        vbox.addWidget(logo)
        vbox.addStretch(1)
        if self._user_old:
            vbox.addWidget(lb_line_1)
            vbox.addLayout(user_box)
            vbox.addWidget(lb_line_2)
            if self.user_num > 1:
                self.del_user_btn = QPushButton("删除账户")
                self.del_user_btn.setIcon(QIcon("src/delete.ico"))
                self.del_user_btn.setStyleSheet("QPushButton {max-width: 180px;}")
                self.del_user_btn.clicked.connect(self.call_del_chose_user)
                vbox.addWidget(self.del_user_btn)
            vbox.addStretch(1)
        vbox.addLayout(self.form)
        vbox.addStretch(1)
        vbox.addLayout(hbox)
        self.setLayout(vbox)
        self.update_selection(self._user_old)

    def call_del_chose_user(self):
        if self._del_user:
            if self._del_user != self._user_old:
                self.user_num -= 1
                update_settings(self._config, None, self._del_user, action="del")
                self.user_btns[self._del_user].close()
                self._del_user = ""
                if self.user_num <= 1:
                    self.del_user_btn.close()
                return
            else:
                title = '不能删除'
                msg = '不能删除当前登录账户，请先切换用户！'
        else:
            title = '请选择账户'
            msg = '请单击选择需要删除的账户\n\n注意不能删除当前账户(绿色)'
        message_box = QMessageBox(self)
        message_box.setStyleSheet(btn_style)
        message_box.setWindowTitle(title)
        message_box.setText(msg)
        message_box.setStandardButtons(QMessageBox.Close)
        buttonC = message_box.button(QMessageBox.Close)
        buttonC.setText('关闭')
        message_box.exec()

    def delete_chose_user(self):
        user = str(self.sender().text())
        self._del_user = user
        if self.del_user_btn:
            self.del_user_btn.setText(f"删除 <{user}>")

    def choose_user(self):
        user = self.sender().text()
        if user != self._user_old:
            self.ok_btn.setText("切换用户")
        else:
            self.ok_btn.setText("登录")
        self.update_selection(user)

    def change_show_input_cookie(self):
        if self.form.rowCount() < 3:
            self.form.addRow(self.cookie_lb, self.cookie_ed)
            self.show_input_cookie_btn.setText("隐藏Cookie输入框")
        else:
            if self.cookie_ed.isVisible():
                self.cookie_lb.setVisible(False)
                self.cookie_ed.setVisible(False)
                self.show_input_cookie_btn.setText("显示Cookie输入框")
            else:
                self.cookie_lb.setVisible(True)
                self.cookie_ed.setVisible(True)
                self.show_input_cookie_btn.setText("隐藏Cookie输入框")

    def set_user(self, user):
        self._user = user
        if not user:
            return
        if 'users' not in self._infos or user not in self._infos['users']:
            self.ok_btn.setText("添加用户")
            self.cookie_ed.setPlainText("")
        elif user != self._user_old:
            self.update_selection(user)
            self.ok_btn.setText("切换用户")
        else:
            self.update_selection(user)
            self.ok_btn.setText("登录")

    def set_pwd(self, pwd):
        if 'users' in self._infos and self._user in self._infos['users']:
            if pwd and pwd != self._infos['users'][self._user].pwd:  # 改变密码，cookie作废
                self.cookie_ed.setPlainText("")
                self._cookie = None
            if not pwd:  # 输入空密码，表示删除对pwd的存储，并使用以前的cookie
                self._cookie = self._infos['users'][self._user].cookie
                try: text = ";".join([str(k) +'='+ str(v) for k, v in self._cookie.items()])
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
        # self.default_var()
        self.update_selection(self._user_old)
        self.close()

    def change_ok_btn(self):
        if self._user and self._pwd:
            if 'users' in self._infos and self._user not in self._infos['users']:
                self._cookie = None
        if self._cookie:
            up_info = {"name": self._user, "pwd": self._pwd, "cookie": self._cookie}
            update_settings(self._config, up_info, self._user)
            self.clicked_ok.emit()
            self.close()
        else:
            self.web = LoginWindow(self._user, self._pwd)
            self.web.cookie.connect(self.get_cookie_by_web)
            self.web.setWindowModality(Qt.ApplicationModal)
            self.web.exec()

    def get_cookie_by_web(self, cookie):
        self._cookie = cookie
        up_info = {"name": self._user, "pwd": self._pwd, "cookie": self._cookie}
        self._config.set_infos(up_info)
        self.clicked_ok.emit()
        self.close()
