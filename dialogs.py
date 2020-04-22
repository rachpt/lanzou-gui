import os
from pickle import dump, load
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QLine, QPoint, QTimer
from PyQt5.QtGui import QIcon, QStandardItem, QStandardItemModel, QPixmap, QFontMetrics, QPainter, QPen
from PyQt5.QtWidgets import (QAbstractItemView, QPushButton, QFileDialog, QLineEdit, QDialog, QLabel, QFormLayout,
                             QTextEdit, QGridLayout, QListView, QDialogButtonBox, QVBoxLayout, QHBoxLayout,
                             QComboBox, QCheckBox, QSizePolicy)

from web_login import LoginWindow
from tools import UserInfo, encrypt, decrypt, UpJob, FileInfos
KEY = 89


def update_settings(config_file: str, up_info: dict, user=None, is_settings=False, action="normal"):
    """更新配置文件"""
    try:
        with open(config_file, "rb") as _file:
            _infos = load(_file)
    except Exception:
        _infos = {}
    try: users = _infos['users']
    except: users = {}
    if is_settings:  # 更新配置
        if user:  # 用户设置
            try: user_info = users[user]
            except: user_info = UserInfo()
            try: settings = user_info.settings
            except: settings = {}
            settings.update(up_info)
            user_info.settings = settings
            users.update({user: user_info})
            _infos.update({"users": users, "choose": encrypt(KEY, user)})
        else:  # 未登录设置
            try: none_user = _infos["none_user"]
            except: none_user = UserInfo()
            none_user.settings.update(up_info)
            _infos.update({"none_user": none_user})
    elif action == "del":  # 删除用户
        try: del _infos["users"][user]
        except: pass
    elif user:  # 添加/更新用户
        user_info = users[user] if user in users else UserInfo()
        user_info.set_infos(up_info)
        users.update({user: user_info})
        _infos.update({"users": users, "choose": encrypt(KEY, user)})
    else:  # 其他
        _infos.update(up_info)
    with open(config_file, "wb") as _file:
        dump(_infos, _file)

def set_file_icon(name):
    suffix = name.split(".")[-1]
    ico_path = "./src/{}.gif".format(suffix)
    if os.path.isfile(ico_path):
        return QIcon(ico_path)
    else:
        return QIcon("./src/file.ico")

btn_style = """
    QPushButton {
        color: white;
        background-color: QLinearGradient(x1: 0, y1: 0, x2: 0, y2: 1,stop: 0 #88d,
            stop: 0.1 #99e, stop: 0.49 #77c, stop: 0.5 #66b, stop: 1 #77c);
        border-width: 1px;
        border-color: #339;
        border-style: solid;
        border-radius: 7;
        padding: 3px;
        font-size: 13px;
        padding-left: 5px;
        padding-right: 5px;
        min-width: 70px;
        min-height: 14px;
        max-height: 14px;
    }
"""
others_style = """
    QLabel {
        font-weight: 400;
        font-size: 14px;
    }
    QLineEdit {
        padding: 1px;
        border-style: solid;
        border: 2px solid gray;
        border-radius: 8px;
    }
    QTextEdit {
        padding: 1px;
        border-style: solid;
        border: 2px solid gray;
        border-radius: 8px;
    }
    #btn_chooseMultiFile, #btn_chooseDir {
        min-width: 90px;
        max-width: 90px;
    }
"""
dialog_qss_style = others_style + btn_style
# https://thesmithfam.org/blog/2009/09/10/qt-stylesheets-tutorial/


class QDoublePushButton(QPushButton):
    """加入了双击事件的按钮"""
    doubleClicked = pyqtSignal()
    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        QPushButton.__init__(self, *args, **kwargs)
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.clicked.emit)
        super().clicked.connect(self.checkDoubleClick)

    def checkDoubleClick(self):
        if self.timer.isActive():
            self.doubleClicked.emit()
            self.timer.stop()
        else:
            self.timer.start(250)


class MyLineEdit(QLineEdit):
    """添加单击事件的输入框，用于设置下载路径"""

    clicked = pyqtSignal()

    def __init__(self, parent):
        super(MyLineEdit, self).__init__(parent)

    def mouseReleaseEvent(self, QMouseEvent):
        if QMouseEvent.button() == Qt.LeftButton:
            self.clicked.emit()


class MyListView(QListView):
    """加入拖拽功能的列表显示器"""
    drop_files = pyqtSignal(object)

    def __init__(self):
        QListView.__init__(self)

        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def dragEnterEvent(self, event):
        m = event.mimeData()
        if m.hasUrls():
            for url in m.urls():
                if url.isLocalFile():
                    event.accept()
                    return
        event.ignore()

    def dropEvent(self, event):
        if event.source():
            QListView.dropEvent(self, event)
        else:
            m = event.mimeData()
            if m.hasUrls():
                urls = [url.toLocalFile() for url in m.urls() if url.isLocalFile()]
                if urls:
                    self.drop_files.emit(urls)
                    event.acceptProposedAction()


class AutoResizingTextEdit(QTextEdit):
    """添加单击事件的自动改变大小的文本输入框，用于显示描述与下载直链
    https://github.com/cameel/auto-resizing-text-edit
    https://gist.github.com/hahastudio/4345418
    """
    clicked = pyqtSignal()
    editingFinished = pyqtSignal()

    def __init__(self, parent = None):
        super(AutoResizingTextEdit, self).__init__(parent)

        # This seems to have no effect. I have expected that it will cause self.hasHeightForWidth()
        # to start returning True, but it hasn't - that's why I hardcoded it to True there anyway.
        # I still set it to True in size policy just in case - for consistency.
        size_policy = self.sizePolicy()
        size_policy.setHeightForWidth(True)
        size_policy.setVerticalPolicy(QSizePolicy.Preferred)
        self.setSizePolicy(size_policy)
        self.textChanged.connect(self.updateGeometry)

        self._changed = False
        self.setTabChangesFocus(True)
        self.textChanged.connect(self._handle_text_changed)

    def setMinimumLines(self, num_lines):
        """ Sets minimum widget height to a value corresponding to specified number of lines
            in the default font. """

        self.setMinimumSize(self.minimumSize().width(), self.lineCountToWidgetHeight(num_lines))

    def heightForWidth(self, width):
        margins = self.contentsMargins()

        if width >= margins.left() + margins.right():
            document_width = width - margins.left() - margins.right()
        else:
            # If specified width can't even fit the margin, there's no space left for the document
            document_width = 0

        # Cloning the whole document only to check its size at different width seems wasteful
        # but apparently it's the only and preferred way to do this in Qt >= 4. QTextDocument does not
        # provide any means to get height for specified width (as some QWidget subclasses do).
        # Neither does QTextEdit. In Qt3 Q3TextEdit had working implementation of heightForWidth()
        # but it was allegedly just a hack and was removed.
        #
        # The performance probably won't be a problem here because the application is meant to
        # work with a lot of small notes rather than few big ones. And there's usually only one
        # editor that needs to be dynamically resized - the one having focus.
        document = self.document().clone()
        document.setTextWidth(document_width)

        return margins.top() + document.size().height() + margins.bottom()

    def sizeHint(self):
        original_hint = super(AutoResizingTextEdit, self).sizeHint()
        return QSize(original_hint.width(), self.heightForWidth(original_hint.width()))

    def mouseReleaseEvent(self, QMouseEvent):
        if QMouseEvent.button() == Qt.LeftButton:
            if not self.toPlainText():
                self.clicked.emit()

    def lineCountToWidgetHeight(self, num_lines):
        """ Returns the number of pixels corresponding to the height of specified number of lines
            in the default font. """

        # ASSUMPTION: The document uses only the default font

        assert num_lines >= 0

        widget_margins  = self.contentsMargins()
        document_margin = self.document().documentMargin()
        font_metrics    = QFontMetrics(self.document().defaultFont())

        # font_metrics.lineSpacing() is ignored because it seems to be already included in font_metrics.height()
        return (
            widget_margins.top()                      +
            document_margin                           +
            max(num_lines, 1) * font_metrics.height() +
            self.document().documentMargin()          +
            widget_margins.bottom()
        )

    def focusOutEvent(self, event):
        if self._changed:
            self.editingFinished.emit()
        super(AutoResizingTextEdit, self).focusOutEvent(event)

    def _handle_text_changed(self):
        self._changed = True


class LoginDialog(QDialog):
    """登录对话框"""

    clicked_ok = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._infos = {}
        self._users = {}
        self._user = ""
        self._del_user = ""
        self._pwd = ""
        self._choose = ""
        self._cookie = {}
        self.initUI()
        self.setStyleSheet(dialog_qss_style)
        self.setMinimumWidth(350)
        # 信号
        self.name_ed.textChanged.connect(self.set_user)
        self.pwd_ed.textChanged.connect(self.set_pwd)
        self.cookie_ed.textChanged.connect(self.set_cookie)

    def default_var(self):
        try:
            with open(self._config, "rb") as _file:
                self._infos = load(_file)
            self._users = self._infos["users"]
            self._choose = decrypt(KEY, self._infos["choose"])
        except: pass

    def update_selection(self):
        if self._infos and "choose" in self._infos:
            user_info = self._infos["users"][self._choose]
            self._user = user_info.name
            self._pwd = user_info.pwd
            self._cookie = user_info.cookie
        self.name_ed.setText(self._user)
        self.pwd_ed.setText(self._pwd)
        if self._cookie:
            try:
                _text = str(";".join([str(k) +'='+ str(v) for k, v in self._cookie.items()]))
                self.cookie_ed.setPlainText(_text)
            except: pass
        else:
            self.cookie_ed.setPlainText("")

    def initUI(self):
        self.setWindowTitle("登录蓝奏云")
        self.setWindowIcon(QIcon("./src/login.ico"))
        logo = QLabel()
        logo.setPixmap(QPixmap("./src/logo3.gif"))
        logo.setStyleSheet("background-color:rgb(0,153,255);")
        logo.setAlignment(Qt.AlignCenter)
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

        hbox = QHBoxLayout()
        hbox.addWidget(self.show_input_cookie_btn)
        hbox.addStretch(1)
        hbox.addWidget(self.ok_btn)
        hbox.addWidget(self.cancel_btn)
        self.default_var()

        user_box = QHBoxLayout()
        self.user_num = 0
        self.user_btns = {}
        for user in self._users.keys():
            user = str(user)
            self.user_btns[user] = QDoublePushButton(user)
            self.user_btns[user].setStyleSheet("QPushButton {border:none;}")
            if user == self._choose:
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
        if self._choose:
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
        self.update_selection()

    def call_del_chose_user(self):
        if self._del_user:
            self.user_num -= 1
            update_settings(self._config, None, self._del_user, action="del")
            self.user_btns[self._del_user].close()
            self._del_user = ""
            if self.user_num <= 1:
                self.del_user_btn.close()

    def delete_chose_user(self):
        user = str(self.sender().text())
        self._del_user = user
        self.del_user_btn.setText(f"删除 <{user}>")

    def choose_user(self):
        user = str(self.sender().text())
        if user != self._choose:
            self.ok_btn.setText("切换用户")
        else:
            self.ok_btn.setText("登录")
        self._choose = user
        self.update_selection()

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
        self._user = str(user)
        if self._user not in self._infos:
            self.ok_btn.setText("添加用户")
            self.cookie_ed.setPlainText("")
        else:
            self._choose = str(user)
            self.update_selection()
            self.ok_btn.setText("切换用户")

    def set_pwd(self, pwd):
        if self._user in self._infos and pwd and pwd != self._infos[self._user]["pwd"]:
            self._cookie = None
        self._pwd = pwd
        if not pwd:
            self.set_cookie()

    def set_cookie(self):
        cookies = self.cookie_ed.toPlainText()
        if cookies:
            try:
                self._cookie = {kv.split("=")[0].strip(" "): kv.split("=")[1].strip(" ") for kv in cookies.split(";")}
            except: self._cookie = None

    def change_cancel_btn(self):
        self.default_var()
        self.update_selection()
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
        update_settings(self._config, up_info, self._user)
        self.clicked_ok.emit()
        self.close()

class UploadDialog(QDialog):
    """文件上传对话框"""
    new_infos = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.cwd = os.getcwd()
        self._folder_id = -1
        self._folder_name = "LanZouCloud"
        self.set_pwd = False
        self.set_desc = False
        self.pwd = ''
        self.desc = ''
        self.allow_big_file = False
        self.max_size = 100
        self.selected = []
        self.initUI()
        self.set_size()
        self.setStyleSheet(dialog_qss_style)

    def set_pwd_desc_bigfile(self, set_pwd, pwd, set_desc, desc, allow_big_file, max_size):
        self.set_pwd = set_pwd
        self.set_desc = set_desc
        self.pwd = pwd
        self.desc = desc
        self.allow_big_file = allow_big_file
        self.max_size = max_size
        if self.allow_big_file:
            self.btn_chooseMultiFile.setToolTip("")
        else:
            self.btn_chooseMultiFile.setToolTip(f"文件大小上线 {self.max_size}MB")

    def set_values(self, folder_name, folder_id, files):
        self.setWindowTitle("上传文件至 ➩ " + str(folder_name))
        self._folder_id = folder_id
        self._folder_name = folder_name
        if files:
            self.selected = files
            self.show_selected()
        self.exec()

    def initUI(self):
        self.setWindowTitle("上传文件")
        self.setWindowIcon(QIcon("./src/upload.ico"))
        self.logo = QLabel()
        self.logo.setPixmap(QPixmap("./src/logo3.gif"))
        self.logo.setStyleSheet("background-color:rgb(0,153,255);")
        self.logo.setAlignment(Qt.AlignCenter)

        # btn 1
        self.btn_chooseDir = QPushButton("选择文件夹", self)
        self.btn_chooseDir.setObjectName("btn_chooseDir")
        self.btn_chooseDir.setObjectName("btn_chooseDir")
        self.btn_chooseDir.setIcon(QIcon("./src/folder.gif"))

        # btn 2
        self.btn_chooseMultiFile = QPushButton("选择多文件", self)
        self.btn_chooseDir.setObjectName("btn_chooseMultiFile")
        self.btn_chooseMultiFile.setObjectName("btn_chooseMultiFile")
        self.btn_chooseMultiFile.setIcon(QIcon("./src/file.ico"))

        # btn 3
        self.btn_deleteSelect = QPushButton("移除", self)
        self.btn_deleteSelect.setObjectName("btn_deleteSelect")
        self.btn_deleteSelect.setIcon(QIcon("./src/delete.ico"))
        self.btn_deleteSelect.setToolTip("按 Delete 移除选中文件")

        # 列表
        self.list_view = MyListView()
        self.list_view.drop_files.connect(self.add_drop_files)
        self.list_view.setViewMode(QListView.ListMode)
        self.slm = QStandardItem()
        self.model = QStandardItemModel()
        self.list_view.setModel(self.model)
        self.model.removeRows(0, self.model.rowCount())  # 清除旧的选择
        self.list_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.list_view.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.button(QDialogButtonBox.Ok).setText("确定")
        self.buttonBox.button(QDialogButtonBox.Cancel).setText("取消")

        vbox = QVBoxLayout()
        hbox_head = QHBoxLayout()
        hbox_button = QHBoxLayout()
        hbox_head.addWidget(self.btn_chooseDir)
        hbox_head.addStretch(1)
        hbox_head.addWidget(self.btn_chooseMultiFile)
        hbox_button.addWidget(self.btn_deleteSelect)
        hbox_button.addStretch(1)
        hbox_button.addWidget(self.buttonBox)
        vbox.addWidget(self.logo)
        vbox.addLayout(hbox_head)
        vbox.addWidget(self.list_view)
        vbox.addLayout(hbox_button)
        self.setLayout(vbox)
        self.setMinimumWidth(350)

        # 设置信号
        self.btn_chooseDir.clicked.connect(self.slot_btn_chooseDir)
        self.btn_chooseMultiFile.clicked.connect(self.slot_btn_chooseMultiFile)
        self.btn_deleteSelect.clicked.connect(self.slot_btn_deleteSelect)

        self.buttonBox.accepted.connect(self.slot_btn_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.clear_old)
        self.buttonBox.rejected.connect(self.reject)

    def set_size(self):
        if self.selected:
            h = 18 if len(self.selected) > 18 else 10
            w = 40
            for i in self.selected:
                i_len = len(i)
                if i_len > 100:
                    w = 100
                    break
                if i_len > w:
                    w = i_len
            self.resize(120+w*7, h*30)
        else:
            self.resize(400, 300)

    def clear_old(self):
        self.selected = []
        self.model.removeRows(0, self.model.rowCount())
        self.set_size()

    def show_selected(self):
        self.model.removeRows(0, self.model.rowCount())
        for item in self.selected:
            if os.path.isfile(item):
                self.model.appendRow(QStandardItem(QIcon("./src/file.ico"), item))
            else:
                self.model.appendRow(QStandardItem(QIcon("./src/folder.gif"), item))
            self.set_size()

    def backslash(self):
        """Windows backslash"""
        tasks = {}
        for item in self.selected:
            furl = os.path.normpath(item)
            tasks[furl] = UpJob(furl=furl,
                                id=self._folder_id,
                                folder=self._folder_name,
                                set_pwd=self.set_pwd,
                                pwd=self.pwd,
                                set_desc=self.set_desc,
                                desc=self.desc)
        return tasks

    def slot_btn_ok(self):
        tasks = self.backslash()
        if self.selected:
            self.new_infos.emit(tasks)
            self.clear_old()

    def slot_btn_deleteSelect(self):
        _indexes = self.list_view.selectionModel().selection().indexes()
        if not _indexes:
            return
        indexes = []
        for i in _indexes:  # 获取所选行号
            indexes.append(i.row())
        indexes = set(indexes)
        for i in sorted(indexes, reverse=True):
            self.selected.remove(self.model.item(i, 0).text())
            self.model.removeRow(i)
        self.set_size()

    def add_drop_files(self, files):
        for item in files:
            if item not in self.selected:
                self.selected.append(item)
            self.show_selected()

    def slot_btn_chooseDir(self):
        dir_choose = QFileDialog.getExistingDirectory(self, "选择文件夹", self.cwd)  # 起始路径
        if dir_choose == "":
            return
        if dir_choose not in self.selected:
            self.selected.append(dir_choose)
        self.show_selected()

    def slot_btn_chooseMultiFile(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择多文件", self.cwd, "All Files (*)")
        if len(files) == 0:
            return
        for _file in files:
            if _file not in self.selected:
                if os.path.getsize(_file) <= self.max_size * 1048576:
                    self.selected.append(_file)
                elif self.allow_big_file:
                    self.selected.append(_file)
        self.show_selected()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Delete:  # delete
            self.slot_btn_deleteSelect()


class InfoDialog(QDialog):
    """文件信息对话框"""
    get_dl_link = pyqtSignal(str, str)
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.infos = None
        self.initUI()
        self.setStyleSheet(dialog_qss_style)

    def update_ui(self):
        self.tx_dl_link.setPlaceholderText("单击获取")
        self.tx_name.setText(self.infos.name)
        if self.infos.is_file:
            self.setWindowTitle("文件信息")
            self.lb_name.setText("文件名：")
            self.lb_desc.setText("文件描述：")
            self.tx_dl_link.setText("")  # 清空旧的信息
            self.lb_dl_link.setVisible(True)
            self.tx_dl_link.setVisible(True)
        else:
            self.setWindowTitle("文件夹信息")
            self.lb_name.setText("文件夹名：")
            self.lb_desc.setText("文件夹描述：")
            self.lb_dl_link.setVisible(False)
            self.tx_dl_link.setVisible(False)

        if self.infos.size:
            self.tx_size.setText(self.infos.size)
            self.lb_size.setVisible(True)
            self.tx_size.setVisible(True)
        else:
            self.tx_size.setVisible(False)
            self.lb_size.setVisible(False)

        if self.infos.time:
            self.lb_time.setVisible(True)
            self.tx_time.setVisible(True)
            self.tx_time.setText(self.infos.time)
        else:
            self.lb_time.setVisible(False)
            self.tx_time.setVisible(False)

        if self.infos.downs:
            self.lb_dl_count.setVisible(True)
            self.tx_dl_count.setVisible(True)
            self.tx_dl_count.setText(str(self.infos.downs))
        else:
            self.tx_dl_count.setVisible(False)
            self.lb_dl_count.setVisible(False)

        if self.infos.pwd:
            self.tx_pwd.setText(self.infos.pwd)
            self.tx_pwd.setPlaceholderText("")
        else:
            self.tx_pwd.setText("")
            self.tx_pwd.setPlaceholderText("无")

        if self.infos.desc:
            self.tx_desc.setText(self.infos.desc)
            self.tx_desc.setPlaceholderText("")
        else:
            self.tx_desc.setText("")
            self.tx_desc.setPlaceholderText("无")

        self.tx_share_url.setText(self.infos.url)

    def set_values(self, infos):
        self.infos = infos
        self.update_ui()
        self.exec()

    def call_get_dl_link(self):
        url = self.tx_share_url.text()
        pwd = self.tx_pwd.text()
        self.get_dl_link.emit(url, pwd)
        self.tx_dl_link.setPlaceholderText("后台获取中，请稍后！")

    def call_get_short_url(self):
        self.tx_short.setPlaceholderText("后台获取中，请稍后！")
        url = self.tx_share_url.text()
        from tools import get_short_url

        short_url = get_short_url(url)
        if short_url:
            self.tx_short.setText(short_url)
            self.tx_short.setPlaceholderText("")
        else:
            self.tx_short.setText("")
            self.tx_short.setPlaceholderText("生成失败！")

    def clean(self):
        self.tx_short.setText("")
        self.tx_short.setPlaceholderText("单击获取")

    def initUI(self):
        self.setWindowIcon(QIcon("./src/share.ico"))
        self.setWindowTitle("文件信息")
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Close)
        self.buttonBox.button(QDialogButtonBox.Close).setText("关闭")
        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.rejected.connect(self.clean)
        self.buttonBox.rejected.connect(self.closed.emit)

        self.logo = QLabel()
        self.logo.setPixmap(QPixmap("./src/q9.gif"))
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setStyleSheet("background-color:rgb(255,204,51);")

        self.lb_name = QLabel()
        self.lb_name.setText("文件名：")
        self.tx_name = QLineEdit()
        self.tx_name.setReadOnly(True)

        self.lb_size = QLabel()
        self.lb_size.setText("文件大小：")
        self.tx_size = QLabel()

        self.lb_time = QLabel()
        self.lb_time.setText("上传时间：")
        self.tx_time = QLabel()

        self.lb_dl_count = QLabel()
        self.lb_dl_count.setText("下载次数：")
        self.tx_dl_count = QLabel()

        self.lb_share_url = QLabel()
        self.lb_share_url.setText("分享链接：")
        self.tx_share_url = QLineEdit()
        self.tx_share_url.setReadOnly(True)

        self.lb_pwd = QLabel()
        self.lb_pwd.setText("提取码：")
        self.tx_pwd = QLineEdit()
        self.tx_pwd.setReadOnly(True)

        self.lb_short = QLabel()
        self.lb_short.setText("短链接：")
        self.tx_short = AutoResizingTextEdit(self)
        self.tx_short.setPlaceholderText("单击获取")
        self.tx_short.clicked.connect(self.call_get_short_url)
        self.tx_short.setReadOnly(True)

        self.lb_desc = QLabel()
        self.lb_desc.setText("文件描述：")
        self.tx_desc = AutoResizingTextEdit()
        self.tx_desc.setReadOnly(True)

        self.lb_dl_link = QLabel()
        self.lb_dl_link.setText("下载直链：")
        self.tx_dl_link = AutoResizingTextEdit(self)
        self.tx_dl_link.setPlaceholderText("单击获取")
        self.tx_dl_link.clicked.connect(self.call_get_dl_link)
        self.tx_dl_link.setReadOnly(True)

        vbox = QVBoxLayout()
        vbox.addWidget(self.logo)
        vbox.addStretch(1)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.addRow(self.lb_name, self.tx_name)
        form.addRow(self.lb_size, self.tx_size)
        form.addRow(self.lb_time, self.tx_time)
        form.addRow(self.lb_dl_count, self.tx_dl_count)
        form.addRow(self.lb_share_url, self.tx_share_url)
        form.addRow(self.lb_pwd, self.tx_pwd)
        form.addRow(self.lb_short, self.tx_short)
        form.addRow(self.lb_desc, self.tx_desc)
        form.addRow(self.lb_dl_link, self.tx_dl_link)
        vbox.addLayout(form)
        vbox.addStretch(1)
        vbox.addWidget(self.buttonBox)

        self.setLayout(vbox)


class RenameDialog(QDialog):
    out = pyqtSignal(object)

    def __init__(self, parent=None):
        super(RenameDialog, self).__init__(parent)
        self.infos = []
        self.min_width = 400
        self.initUI()
        self.update_text()
        self.setStyleSheet(dialog_qss_style)

    def set_values(self, infos=None):
        self.infos = infos or []
        self.update_text()  # 更新界面

    def initUI(self):
        self.setWindowIcon(QIcon("./src/desc.ico"))
        self.lb_name = QLabel()
        self.lb_name.setText("文件夹名：")
        self.lb_name.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_name = QLineEdit()
        self.lb_desc = QLabel()
        self.tx_desc = QTextEdit()
        self.lb_desc.setText("描　　述：")
        self.lb_desc.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.button(QDialogButtonBox.Ok).setText("确定")
        self.buttonBox.button(QDialogButtonBox.Cancel).setText("取消")

        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.grid.addWidget(self.lb_name, 1, 0)
        self.grid.addWidget(self.tx_name, 1, 1)
        self.grid.addWidget(self.lb_desc, 2, 0)
        self.grid.addWidget(self.tx_desc, 2, 1, 5, 1)
        self.grid.addWidget(self.buttonBox, 7, 1, 1, 1)
        self.setLayout(self.grid)
        self.buttonBox.accepted.connect(self.btn_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def update_text(self):
        num= len(self.infos)
        if num == 1:
            self.lb_name.setVisible(True)
            self.tx_name.setVisible(True)
            infos = self.infos[0]
            self.buttonBox.button(QDialogButtonBox.Ok).setToolTip("")  # 去除新建文件夹影响
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)  # 去除新建文件夹影响
            self.setWindowTitle("修改文件夹名与描述")
            self.tx_name.setText(str(infos.name))
            if infos.desc:
                self.tx_desc.setText(str(infos.desc))
                self.tx_desc.setToolTip('原描述：' + str(infos.desc))
            else:
                self.tx_desc.setText("无")
                self.tx_desc.setToolTip('')
            self.tx_desc.setPlaceholderText("无")
            self.min_width = len(str(infos.name)) * 8
            if infos.is_file:
                self.setWindowTitle("修改文件描述")
                self.tx_name.setFocusPolicy(Qt.NoFocus)
                self.tx_name.setReadOnly(True)
            else:
                self.tx_name.setFocusPolicy(Qt.StrongFocus)
                self.tx_name.setReadOnly(False)
        elif num > 1:
            self.lb_name.setVisible(False)
            self.tx_name.setVisible(False)
            self.setWindowTitle(f"批量修改{num}个文件(夹)的描述")
            self.tx_desc.setText('')
            self.tx_desc.setPlaceholderText("建议160字数以内。")

        else:
            self.setWindowTitle("新建文件夹")
            self.tx_name.setText("")
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
            self.buttonBox.button(QDialogButtonBox.Ok).setToolTip("请先输入文件名！")
            self.tx_name.textChanged.connect(self.slot_new_ok_btn)
            self.tx_name.setPlaceholderText("不支持空格，如有会被自动替换成 _")
            self.tx_name.setFocusPolicy(Qt.StrongFocus)
            self.tx_name.setReadOnly(False)
            self.tx_desc.setPlaceholderText("可选项，建议160字数以内。")
        if self.min_width < 400:
            self.min_width = 400
        self.resize(self.min_width, 200)

    def slot_new_ok_btn(self):
        """新建文件夹槽函数"""
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)
        self.buttonBox.button(QDialogButtonBox.Ok).setToolTip("")

    def btn_ok(self):
        new_name = self.tx_name.text()
        new_des = self.tx_desc.toPlainText()
        if not self.infos:  # 在 work_id 新建文件夹
            if new_name:
                self.out.emit(("new", new_name, new_des))
            else:
                return
        if len(self.infos) == 1:
            if new_name != self.infos[0].name or new_des != self.infos[0].desc:
                self.infos[0].new_des = new_des
                self.infos[0].new_name = new_name
                self.out.emit(("change", self.infos))
        else:
            if new_des:
                for infos in self.infos:
                    infos.new_des = new_des
                self.out.emit(("change", self.infos))


class SetPwdDialog(QDialog):
    new_infos = pyqtSignal(object)

    def __init__(self, parent=None):
        super(SetPwdDialog, self).__init__(parent)
        self.infos = []
        self.initUI()
        self.update_text()
        self.setStyleSheet(dialog_qss_style)

    def set_values(self, infos):
        self.infos = infos
        self.update_text()  # 更新界面

    def set_tip(self):  # 用于提示状态
        self.setWindowTitle("请稍等……")

    def initUI(self):
        self.setWindowTitle("请稍等……")
        self.setWindowIcon(QIcon("./src/password.ico"))
        self.lb_oldpwd = QLabel()
        self.lb_oldpwd.setText("当前提取码：")
        self.lb_oldpwd.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_oldpwd = QLineEdit()
        # 当前提取码 只读
        self.tx_oldpwd.setFocusPolicy(Qt.NoFocus)
        self.tx_oldpwd.setReadOnly(True)
        self.lb_newpwd = QLabel()
        self.lb_newpwd.setText("新的提取码：")
        self.lb_newpwd.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_newpwd = QLineEdit()

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.button(QDialogButtonBox.Ok).setText("确定")
        self.buttonBox.button(QDialogButtonBox.Cancel).setText("取消")

        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.grid.addWidget(self.lb_oldpwd, 1, 0)
        self.grid.addWidget(self.tx_oldpwd, 1, 1)
        self.grid.addWidget(self.lb_newpwd, 2, 0)
        self.grid.addWidget(self.tx_newpwd, 2, 1)
        self.grid.addWidget(self.buttonBox, 3, 0, 1, 2)
        self.setLayout(self.grid)
        self.buttonBox.accepted.connect(self.btn_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.accepted.connect(self.set_tip)
        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.rejected.connect(self.set_tip)
        self.setMinimumWidth(280)

    def update_text(self):
        num = len(self.infos)
        if num == 1:
            self.tx_oldpwd.setVisible(True)
            self.lb_oldpwd.setVisible(True)
            infos = self.infos[0]
            if infos.has_pwd:
                self.tx_oldpwd.setText(str(infos.pwd))
                self.tx_oldpwd.setPlaceholderText("")
            else:
                self.tx_oldpwd.setText("")
                self.tx_oldpwd.setPlaceholderText("无")

            if isinstance(infos, FileInfos):  # 文件  通过size列判断是否为文件
                self.setWindowTitle("修改文件提取码")
                self.tx_newpwd.setPlaceholderText("2-6位字符,关闭请留空")
                self.tx_newpwd.setMaxLength(6)  # 最长6个字符
            else:  # 文件夹
                self.setWindowTitle("修改文件夹名提取码")
                self.tx_newpwd.setPlaceholderText("2-12位字符,关闭请留空")
                self.tx_newpwd.setMaxLength(12)  # 最长12个字符
        elif num > 1:
            self.tx_oldpwd.setVisible(False)
            self.lb_oldpwd.setVisible(False)
            self.setWindowTitle(f"批量修改{num}个文件(夹)的提取码")
            self.tx_newpwd.setPlaceholderText("2-12位字符,关闭请留空")
            self.tx_newpwd.setMaxLength(12)  # 最长12个字符
            self.tx_newpwd.setText('')
            for infos in self.infos:
                if isinstance(infos, FileInfos):  # 文件
                    self.tx_newpwd.setPlaceholderText("2-6位字符,文件无法关闭")
                    self.tx_newpwd.setMaxLength(6)  # 最长6个字符
                    break

    def btn_ok(self):
        new_pwd = self.tx_newpwd.text()
        for infos in self.infos:
            infos.new_pwd = new_pwd
        self.new_infos.emit(self.infos)  # 最后一位用于标示文件还是文件夹


class MoveFileDialog(QDialog):
    '''移动文件对话框'''
    new_infos = pyqtSignal(object)

    def __init__(self, parent=None):
        super(MoveFileDialog, self).__init__(parent)
        self.infos = None
        self.dirs = {}
        self.initUI()
        self.setStyleSheet(dialog_qss_style)

    def update_ui(self):
        names = "\n".join([i.name for i in self.infos])
        names_tip = "\n".join([i.name for i in self.infos])
        self.tx_name.setText(names)
        self.tx_name.setToolTip(names_tip)

        self.tx_new_path.clear()
        f_icon = QIcon("./src/folder.gif")
        for f_name, fid in self.dirs.items():
            if len(f_name) > 50:  # 防止文件夹名字过长？
                f_name = f_name[:47] + "..."
            self.tx_new_path.addItem(f_icon, "id：{:>8}，name：{}".format(fid, f_name))

    def set_values(self, infos, all_dirs_dict):
        self.infos = infos
        self.dirs = all_dirs_dict
        self.update_ui()
        self.exec()

    def initUI(self):
        self.setWindowTitle("移动文件(夹)")
        self.setWindowIcon(QIcon("./src/move.ico"))
        self.lb_name = QLabel()
        self.lb_name.setText("文件(夹)名：")
        self.lb_name.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_name = AutoResizingTextEdit()
        self.tx_name.setFocusPolicy(Qt.NoFocus)  # 只读
        self.tx_name.setReadOnly(True)
        self.lb_new_path = QLabel()
        self.lb_new_path.setText("目标文件夹：")
        self.lb_new_path.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_new_path = QComboBox()

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.button(QDialogButtonBox.Ok).setText("确定")
        self.buttonBox.button(QDialogButtonBox.Cancel).setText("取消")

        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.grid.addWidget(self.lb_name, 1, 0)
        self.grid.addWidget(self.tx_name, 1, 1)
        self.grid.addWidget(self.lb_new_path, 2, 0)
        self.grid.addWidget(self.tx_new_path, 2, 1)
        self.grid.addWidget(self.buttonBox, 3, 0, 1, 2)
        self.setLayout(self.grid)
        self.buttonBox.accepted.connect(self.btn_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.setMinimumWidth(280)

    def btn_ok(self):
        new_id = self.tx_new_path.currentText().split("，")[0].split("：")[1]
        for index in range(len(self.infos)):
            self.infos[index].new_id = int(new_id)
        self.new_infos.emit(self.infos)


class DeleteDialog(QDialog):
    new_infos = pyqtSignal(object)

    def __init__(self, infos, parent=None):
        super(DeleteDialog, self).__init__(parent)
        self.infos = infos
        self.out = []
        self.initUI()
        self.setStyleSheet(dialog_qss_style)

    def initUI(self):
        self.setWindowTitle("确认删除")
        self.setWindowIcon(QIcon("./src/delete.ico"))
        self.layout = QVBoxLayout()
        self.list_view = QListView()
        self.list_view.setViewMode(QListView.ListMode)
        # 列表
        self.slm = QStandardItem()
        self.model = QStandardItemModel()
        max_len = 10
        count = 0
        for info in self.infos:
            if info.is_file:  # 文件
                self.model.appendRow(QStandardItem(set_file_icon(info.name), info.name))
            else:
                self.model.appendRow(QStandardItem(QIcon("./src/folder.gif"), info.name))
            self.out.append({'fid': info.id, 'is_file': info.is_file, 'name': info.name})  # id，文件标示, 文件名
            count += 1
            if max_len < len(info.name):  # 使用最大文件名长度
                max_len = len(info.name)
        self.list_view.setModel(self.model)

        self.lb_name = QLabel("尝试删除以下{}个文件(夹)：".format(count))
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.button(QDialogButtonBox.Ok).setText("确定")
        self.buttonBox.button(QDialogButtonBox.Cancel).setText("取消")

        self.layout.addWidget(self.lb_name)
        self.layout.addWidget(self.list_view)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

        self.buttonBox.accepted.connect(self.btn_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.setMinimumWidth(400)
        self.resize(int(max_len*8), int(count*34+60))

    def btn_ok(self):
        self.new_infos.emit(self.out)


class AboutDialog(QDialog):
    check_update = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super(AboutDialog, self).__init__(parent)
        self._ver = ''
        self._github = 'https://github.com/rachpt/lanzou-gui'
        self._api_url = 'https://github.com/zaxtyson/LanZouCloud-API'
        self._gitee = 'https://gitee.com/rachpt/lanzou-gui'
        self._home_page = 'https://rachpt.cn/lanzou-gui/'
        self.initUI()
        self.setStyleSheet(others_style)

    def set_values(self, version):
        self._ver = version
        self.lb_name_text.setText(f"{version}  (点击检查更新)")  # 更新版本

    def show_update(self, ver, msg):
        self.lb_new_ver = QLabel("新版")  # 检测新版
        self.lb_new_ver_msg = QLabel()
        self.lb_new_ver_msg.setOpenExternalLinks(True)
        self.lb_new_ver_msg.setWordWrap(True)
        if ver != '0':
            self.lb_name_text.setText(f"{self._ver}  ➡  {ver}")
        self.lb_new_ver_msg.setText(msg)
        self.lb_new_ver_msg.setMinimumWidth(700)
        if self.form.rowCount() < 5:
            self.form.insertRow(1, self.lb_new_ver, self.lb_new_ver_msg)

    def initUI(self):
        self.setWindowTitle("关于 lanzou-gui")
        about = f'本项目使用PyQt5实现图形界面，可以完成蓝奏云的大部分功能<br/> \
    得益于 <a href="{self._api_url}">API</a> 的功能，可以间接突破单文件最大 100MB 的限制，同时增加了批量上传/下载的功能<br/> \
Python 依赖见<a href="{self._github }/blob/master/requirements.txt">requirements.txt</a>，\
<a href="{self._github}/releases">releases</a> 有打包好了的 Windows 可执行程序，但可能不是最新的'
        project_url = f'<a href="{self._home_page}">主页</a> | <a href="{self._github}">repo</a> | \
                        <a href="{self._gitee}">mirror repo</a>'
        self.logo = QLabel()  # logo
        self.logo.setPixmap(QPixmap("./src/logo2.gif"))
        self.logo.setStyleSheet("background-color:rgb(255,255,255);")
        self.logo.setAlignment(Qt.AlignCenter)
        self.lb_name = QLabel("版本")  # 版本
        self.lb_name_text = QPushButton("")  # 版本
        self.lb_name_text.setToolTip("点击检查更新")
        ver_style = "QPushButton {border:none; background:transparent;font-weight:bold;color:blue;}"
        self.lb_name_text.setStyleSheet(ver_style)
        self.lb_name_text.clicked.connect(lambda: self.check_update.emit(self._ver, True))
        self.lb_about = QLabel("关于")  # about
        self.lb_about_text = QLabel()
        self.lb_about_text.setText(about)
        self.lb_about_text.setOpenExternalLinks(True)
        self.lb_author = QLabel("作者")  # author
        self.lb_author_mail = QLabel("<a href='mailto:rachpt@126.com'>rachpt</a>")
        self.lb_author_mail.setOpenExternalLinks(True)
        self.lb_update = QLabel("项目")  # 更新
        self.lb_update_url = QLabel(project_url)
        self.lb_update_url.setOpenExternalLinks(True)
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Close)
        self.buttonBox.button(QDialogButtonBox.Close).setText("关闭")
        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.setStyleSheet(btn_style)

        self.line = QLine(QPoint(), QPoint(550, 0))
        self.lb_line = QLabel()
        self.lb_line.setText('<html><hr /></html>')

        vbox = QVBoxLayout()
        vbox.addWidget(self.logo)
        vbox.addStretch(1)
        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignRight)
        self.form.setFormAlignment(Qt.AlignLeft)
        self.form.setHorizontalSpacing(40)
        self.form.setVerticalSpacing(15)
        self.form.addRow(self.lb_name, self.lb_name_text)
        self.form.addRow(self.lb_update, self.lb_update_url)
        self.form.addRow(self.lb_author, self.lb_author_mail)
        self.form.addRow(self.lb_about, self.lb_about_text)
        vbox.addLayout(self.form)
        vbox.addStretch(1)
        vbox.addWidget(self.lb_line)
        donate = QLabel()
        donate.setText("<b>捐助我</b>&nbsp;如果你愿意")
        donate.setAlignment(Qt.AlignCenter)
        hbox = QHBoxLayout()
        hbox.addStretch(2)
        for it in ["wechat", "alipay", "qqpay"]:
            lb = QLabel()
            lb.setPixmap(QPixmap(f"./src/{it}.jpg"))
            hbox.addWidget(lb)
        hbox.addStretch(1)
        hbox.addWidget(self.buttonBox)
        vbox.addWidget(donate)
        vbox.addLayout(hbox)
        self.setLayout(vbox)
        self.setMinimumWidth(720)

    def paintEvent(self, event):
        QDialog.paintEvent(self, event)
        if not self.line.isNull():
            painter = QPainter(self)
            pen = QPen(Qt.red, 3)
            painter.setPen(pen)
            painter.drawLine(self.line)


class SettingDialog(QDialog):
    saved = pyqtSignal()

    def __init__(self, config_file: str, default_settings: dict, parent=None):
        super(SettingDialog, self).__init__(parent)
        self.cwd = os.getcwd()
        self._config_file = config_file
        self._default_settings = default_settings
        self._user = None
        self.download_threads = 3
        self.max_size = 100
        self.timeout = 5
        self.dl_path = None
        self.time_fmt = False
        self.to_tray = False
        self.watch_clipboard = False
        self.debug = False
        self.set_pwd = False
        self.set_desc = False
        self.upload_delay = 0
        self.allow_big_file = False
        self.pwd = ""
        self.desc = ""
        self.initUI()
        self.set_values()
        self.setStyleSheet(dialog_qss_style)

    def open_dialog(self, user=None):
        """"打开前先更新一下显示界面"""
        if user:
            self._user = user
            self.setWindowTitle(f"设置 <{user}>")
        else:
            self.setWindowTitle("设置")
        self.set_values()
        self.exec()

    def read_values(self):
        """读取配置信息"""
        try:
            with open(self._config_file, "rb") as _file:
                configs = load(_file)
            if self._user:
                users = configs["users"]
                settings = users[self._user].settings
            else:
                settings = configs["settings"]
        except Exception:
            settings = self._default_settings
        return settings

    def show_values(self):
        """控件显示值"""
        self.download_threads_var.setText(str(self.download_threads))
        self.max_size_var.setText(str(self.max_size))
        self.timeout_var.setText(str(self.timeout))
        self.dl_path_var.setText(str(self.dl_path))
        self.time_fmt_box.setChecked(self.time_fmt)
        self.to_tray_box.setChecked(self.to_tray)
        self.watch_clipboard_box.setChecked(self.watch_clipboard)
        self.debug_box.setChecked(self.debug)
        self.set_pwd_box.setChecked(self.set_pwd)
        self.set_pwd_var.setEnabled(self.set_pwd)
        self.set_pwd_var.setText(self.pwd)
        self.set_desc_box.setChecked(self.set_desc)
        self.set_desc_var.setEnabled(self.set_desc)
        self.set_desc_var.setText(self.desc)
        self.upload_delay_var.setText(str(self.upload_delay))
        self.big_file_box.setChecked(self.allow_big_file)
        self.big_file_box.setText(f"允许上传超过 {self.max_size}MB 的大文件")
        self.big_file_box.setDisabled(True)

    def set_values(self, reset=False):
        """设置控件对应变量初始值"""
        settings = self._default_settings if reset else self.read_values()
        self.download_threads = settings["download_threads"]
        self.max_size = settings["max_size"]
        self.timeout = settings["timeout"]
        self.dl_path = settings["dl_path"]
        self.time_fmt = settings["time_fmt"]
        self.to_tray = settings["to_tray"] if "to_tray" in settings else False  # 兼容
        self.watch_clipboard = settings["watch_clipboard"] if "watch_clipboard" in settings else False  # 兼容
        self.debug = settings["debug"] if "debug" in settings else False  # 兼容
        self.set_pwd = settings["set_pwd"] if "set_pwd" in settings else False  # 兼容
        self.pwd = settings["pwd"] if "pwd" in settings else ""  # 兼容
        self.set_desc = settings["set_desc"] if "set_desc" in settings else False  # 兼容
        self.desc = settings["desc"] if "desc" in settings else ""  # 兼容
        self.upload_delay = settings["upload_delay"] if "upload_delay" in settings else 0  # 兼容
        self.show_values()

    def get_values(self) -> dict:
        """读取输入控件的值"""
        if self.download_threads_var.text():
            self.download_threads = int(self.download_threads_var.text())
        if self.max_size_var.text():
            self.max_size = int(self.max_size_var.text())
        if self.timeout_var.text():
            self.timeout = int(self.timeout_var.text())
        if self.upload_delay_var.text():
            self.upload_delay = int(self.upload_delay_var.text())
        self.dl_path = str(self.dl_path_var.text())
        self.pwd = str(self.set_pwd_var.toPlainText())
        self.desc = str(self.set_desc_var.toPlainText())
        return {"download_threads": self.download_threads,
                "max_size": self.max_size,
                "timeout": self.timeout,
                "dl_path": self.dl_path,
                "time_fmt": self.time_fmt,
                "to_tray": self.to_tray,
                "watch_clipboard": self.watch_clipboard,
                "debug": self.debug,
                "set_pwd": self.set_pwd,
                "pwd": self.pwd,
                "set_desc": self.set_desc,
                "desc": self.desc,
                "upload_delay": self.upload_delay,
                "allow_big_file": self.allow_big_file}

    def initUI(self):
        self.setWindowTitle("设置")
        logo = QLabel()  # logo
        logo.setPixmap(QPixmap("./src/logo2.gif"))
        logo.setStyleSheet("background-color:rgb(255,255,255);")
        logo.setAlignment(Qt.AlignCenter)
        self.download_threads_lb = QLabel("同时下载文件数")  # about
        self.download_threads_var = QLineEdit()
        self.download_threads_var.setPlaceholderText("范围：1-9")
        self.download_threads_var.setToolTip("范围：1-9")
        self.download_threads_var.setInputMask("D")
        self.max_size_lb = QLabel("分卷大小(MB)")
        self.max_size_var = QLineEdit()
        self.max_size_var.setPlaceholderText("普通用户最大100，vip用户根据具体情况设置")
        self.max_size_var.setToolTip("普通用户最大100，vip用户根据具体情况设置")
        self.max_size_var.setInputMask("D99")
        self.timeout_lb = QLabel("请求超时(秒)")
        self.timeout_var = QLineEdit()
        self.timeout_var.setPlaceholderText("范围：1-99")
        self.timeout_var.setToolTip("范围：1-99")
        self.timeout_var.setInputMask("D9")
        self.upload_delay_lb = QLabel("上传延时(秒)")
        self.upload_delay_var = QLineEdit()
        self.upload_delay_var.setPlaceholderText("范围：1-99")
        self.upload_delay_var.setToolTip("范围：1-99")
        self.upload_delay_var.setInputMask("D9")
        self.dl_path_lb = QLabel("下载保存路径")
        self.dl_path_var = MyLineEdit(self)
        self.dl_path_var.clicked.connect(self.set_download_path)
        self.time_fmt_box = QCheckBox("使用[年-月-日]时间格式")
        self.to_tray_box = QCheckBox("关闭到系统托盘")
        self.watch_clipboard_box = QCheckBox("监听系统剪切板")
        self.debug_box = QCheckBox("开启调试日志")
        self.set_pwd_box = QCheckBox("上传文件自动设置密码")
        self.set_pwd_var = AutoResizingTextEdit()
        self.set_pwd_var.setPlaceholderText(" 2-8 位数字或字母")
        self.set_pwd_var.setToolTip("2-8 位数字或字母")
        self.set_desc_box = QCheckBox("上传文件自动设置描述")
        self.set_desc_var = AutoResizingTextEdit()
        self.big_file_box = QCheckBox(f"允许上传超过 {self.max_size}MB 的大文件")

        self.time_fmt_box.toggle()
        self.time_fmt_box.stateChanged.connect(self.change_time_fmt)
        self.to_tray_box.stateChanged.connect(self.change_to_tray)
        self.watch_clipboard_box.stateChanged.connect(self.change_watch_clipboard)
        self.debug_box.stateChanged.connect(self.change_debug)
        self.set_pwd_box.stateChanged.connect(self.change_set_pwd)
        self.set_pwd_var.editingFinished.connect(self.check_pwd)
        self.set_desc_box.stateChanged.connect(self.change_set_desc)
        self.big_file_box.stateChanged.connect(self.change_big_file)

        buttonBox = QDialogButtonBox()
        buttonBox.setOrientation(Qt.Horizontal)
        buttonBox.setStandardButtons(QDialogButtonBox.Reset | QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttonBox.button(QDialogButtonBox.Reset).setText("重置")
        buttonBox.button(QDialogButtonBox.Save).setText("保存")
        buttonBox.button(QDialogButtonBox.Cancel).setText("取消")
        buttonBox.button(QDialogButtonBox.Reset).clicked.connect(lambda: self.set_values(reset=True))
        buttonBox.button(QDialogButtonBox.Save).clicked.connect(self.slot_save)
        buttonBox.rejected.connect(self.reject)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)
        form.addRow(self.download_threads_lb, self.download_threads_var)
        form.addRow(self.timeout_lb, self.timeout_var)
        form.addRow(self.upload_delay_lb, self.upload_delay_var)
        form.addRow(self.max_size_lb, self.max_size_var)
        form.addRow(self.dl_path_lb, self.dl_path_var)

        vbox = QVBoxLayout()
        vbox.addWidget(logo)
        vbox.addStretch(1)
        vbox.addLayout(form)
        vbox.addStretch(1)
        hbox = QHBoxLayout()
        hbox.addWidget(self.time_fmt_box)
        hbox.addWidget(self.to_tray_box)
        hbox.addWidget(self.watch_clipboard_box)
        hbox.addWidget(self.debug_box)
        vbox.addLayout(hbox)
        vbox.addStretch(1)
        hbox_2 = QHBoxLayout()
        hbox_2.addWidget(self.set_pwd_box)
        hbox_2.addWidget(self.set_pwd_var)
        vbox.addLayout(hbox_2)
        vbox.addStretch(1)
        hbox_3 = QHBoxLayout()
        hbox_3.addWidget(self.set_desc_box)
        hbox_3.addWidget(self.set_desc_var)
        vbox.addLayout(hbox_3)
        vbox.addWidget(self.big_file_box)
        vbox.addStretch(2)
        vbox.addWidget(buttonBox)
        self.setLayout(vbox)
        self.setMinimumWidth(500)

    def change_time_fmt(self, state):
        if state == Qt.Checked:
            self.time_fmt = True
        else:
            self.time_fmt = False

    def change_to_tray(self, state):
        if state == Qt.Checked:
            self.to_tray = True
        else:
            self.to_tray = False

    def change_watch_clipboard(self, state):
        if state == Qt.Checked:
            self.watch_clipboard = True
        else:
            self.watch_clipboard = False

    def change_debug(self, state):
        if state == Qt.Checked:
            self.debug = True
        else:
            self.debug = False

    def change_big_file(self, state):
        if state == Qt.Checked:
            self.allow_big_file = True
        else:
            self.allow_big_file = False

    def change_set_pwd(self, state):
        if state == Qt.Checked:
            self.set_pwd = True
            self.set_pwd_var.setDisabled(False)
        else:
            self.set_pwd = False
            self.set_pwd_var.setDisabled(True)

    def change_set_desc(self, state):
        if state == Qt.Checked:
            self.set_desc = True
            self.set_desc_var.setDisabled(False)
        else:
            self.set_desc = False
            self.set_desc_var.setDisabled(True)

    def check_pwd(self):
        pwd = self.set_pwd_var.toPlainText()
        pwd = ''.join(list(filter(str.isalnum, pwd)))
        if len(pwd) < 2:
            pwd = ""
        self.set_pwd_var.setText(pwd[:8])

    def set_download_path(self):
        """设置下载路径"""
        dl_path = QFileDialog.getExistingDirectory(self, "选择文件下载保存文件夹", self.cwd)
        dl_path = os.path.normpath(dl_path)  # windows backslash
        if dl_path == self.dl_path or dl_path == ".":
            return
        self.dl_path_var.setText(dl_path)
        self.dl_path = dl_path

    def slot_save(self):
        """保存槽函数"""
        update_settings(self._config_file, self.get_values(), self._user, is_settings=True)
        self.saved.emit()
        self.close()


class RecFolderDialog(QDialog):
    out = pyqtSignal(object)

    def __init__(self, files, parent=None):
        super(RecFolderDialog, self).__init__(parent)
        self.files = files
        self.initUI()
        self.setStyleSheet(others_style)

    def initUI(self):
        self.setWindowTitle("查看回收站文件夹内容")
        self.form = QVBoxLayout()
        for item in iter(self.files):
            ico = QPushButton(set_file_icon(item.name), item.name)
            ico.setStyleSheet("QPushButton {border:none; background:transparent; color:black;}")
            ico.adjustSize()
            it = QLabel(f"<font color='#CCCCCC'>({item.size})</font>")
            hbox = QHBoxLayout()
            hbox.addWidget(ico)
            hbox.addStretch(1)
            hbox.addWidget(it)
            self.form.addLayout(hbox)

        self.form.setSpacing(10)
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Close)
        self.buttonBox.button(QDialogButtonBox.Close).setText("关闭")
        self.buttonBox.setStyleSheet(btn_style)
        self.buttonBox.rejected.connect(self.reject)

        vbox = QVBoxLayout()
        vbox.addLayout(self.form)
        vbox.addStretch(1)
        vbox.addWidget(self.buttonBox)
        self.setLayout(vbox)


class CaptchaDialog(QDialog):
    captcha = pyqtSignal(object)

    def __init__(self, parent=None):
        super(CaptchaDialog, self).__init__(parent)
        self.img_path = os.getcwd() + os.sep + 'captcha.png'
        self.initUI()
        self.setStyleSheet(others_style)

    def show_img(self):
        self.captcha_pixmap = QPixmap(self.img_path)
        self.captcha_lb.setPixmap(self.captcha_pixmap)

    def handle(self, img_data):
        with open(self.img_path, 'wb') as f:
            f.write(img_data)
            f.flush()
        self.show_img()

    def on_ok(self):
        captcha = self.code.text()
        self.captcha.emit(captcha)
        if os.path.isfile(self.img_path):
            os.remove(self.img_path)

    def initUI(self):
        self.setWindowTitle("请输入下载验证码")

        self.captcha_lb = QLabel()
        self.captcha_pixmap = QPixmap(self.img_path)
        self.captcha_lb.setPixmap(self.captcha_pixmap)

        self.code = QLineEdit()
        self.code.setPlaceholderText("在此输入验证码")

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Reset|QDialogButtonBox.Ok|QDialogButtonBox.Close)
        self.buttonBox.button(QDialogButtonBox.Reset).setText("显示图片")
        self.buttonBox.button(QDialogButtonBox.Ok).setText("确定")
        self.buttonBox.button(QDialogButtonBox.Close).setText("关闭")
        self.buttonBox.setStyleSheet(btn_style)
        self.buttonBox.button(QDialogButtonBox.Reset).clicked.connect(self.show_img)
        self.buttonBox.accepted.connect(self.on_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        vbox = QVBoxLayout()
        vbox.addWidget(self.captcha_lb)
        vbox.addStretch(1)
        vbox.addWidget(self.code)
        vbox.addStretch(1)
        vbox.addWidget(self.buttonBox)
        self.setLayout(vbox)
        self.setMinimumWidth(260)
