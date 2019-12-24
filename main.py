#!/usr/bin/env python3

import sys
import os
import re
from time import sleep
from pickle import dump, load
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from Ui_lanzou import Ui_MainWindow
from Ui_share import Ui_Dialog

from lanzou import LanZouCloud

from downloader import Downloader, DownloadManager


def update_settings(_config, up_info):
    """更新配置文件"""
    try:
        with open(_config, "rb") as _file:
            _info = load(_file)
    except Exception:
        _info = {}
    _info.update(up_info)
    with open(_config, "wb") as _file:
        dump(_info, _file)


class LoginDialog(QDialog):
    """登录对话框"""

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._user = ""
        self._pwd = ""
        self._cookie = ""
        self.initUI()
        self.name_ed.textChanged.connect(self.set_user)
        self.pwd_ed.textChanged.connect(self.set_pwd)
        self.cookie_ed.textChanged.connect(self.set_cookie)
        self.btn_ok.clicked.connect(self.clicked_ok)
        self.btn_cancel.clicked.connect(self.clicked_cancel)

    def default_var(self):
        try:
            with open(self._config, "rb") as _file:
                _info = load(_file)
            self._user = _info["user"]
            self._pwd = _info["pwd"]
            self._cookie = _info["cookie"]
        except Exception:
            pass
        self.name_ed.setText(self._user)
        self.pwd_ed.setText(self._pwd)
        self.cookie_ed.setPlainText(self._cookie)

    def initUI(self):
        self.setWindowTitle("登录蓝奏云")
        self.logo = QLabel()
        self.logo.setPixmap(QPixmap("./icon/logo3.gif"))
        self.logo.setStyleSheet("background-color:rgb(0,153,255);")
        self.logo.setAlignment(Qt.AlignCenter)
        self.name_lb = QLabel("&User")
        self.name_ed = QLineEdit()
        self.name_lb.setBuddy(self.name_ed)

        self.pwd_lb = QLabel("&Password")
        self.pwd_ed = QLineEdit()
        self.pwd_ed.setEchoMode(QLineEdit.Password)
        self.pwd_lb.setBuddy(self.pwd_ed)
        
        self.cookie_lb = QLabel("&Cookie")
        self.cookie_ed = QTextEdit()
        self.cookie_ed.setPlaceholderText("如果由于滑动验证，无法使用用户名与密码登录，则需要输入cookie，自行使用浏览器获取，cookie会保持在本地，下次使用。其格式如下：\n\n key1=value1; key2=value2")
        self.cookie_lb.setBuddy(self.cookie_ed)

        self.btn_ok = QPushButton("&OK")
        self.btn_cancel = QPushButton("&Cancel")
        main_layout = QGridLayout()
        main_layout.addWidget(self.logo, 0, 0, 2, 4)
        main_layout.addWidget(self.name_lb, 2, 0)
        main_layout.addWidget(self.name_ed, 2, 1, 1, 3)
        main_layout.addWidget(self.pwd_lb, 3, 0)
        main_layout.addWidget(self.pwd_ed, 3, 1, 1, 3)
        main_layout.addWidget(self.cookie_lb, 4, 0)
        main_layout.addWidget(self.cookie_ed, 4, 1, 2, 3)
        main_layout.addWidget(self.btn_ok, 6, 2)
        main_layout.addWidget(self.btn_cancel, 6, 3)
        self.setLayout(main_layout)
        self.default_var()

    def set_user(self, user):
        self._user = user

    def set_pwd(self, pwd):
        self._pwd = pwd

    def set_cookie(self):
        self._cookie = self.cookie_ed.toPlainText()

    def clicked_cancel(self):
        self.default_var()
        self.close()

    def clicked_ok(self):
        up_info = {"user": self._user, "pwd": self._pwd, "cookie": self._cookie}
        update_settings(self._config, up_info)
        self.close()


class UploadDialog(QDialog):
    """文件上传对话框"""
    new_infos = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.cwd = os.getcwd()
        self.selected = []
        self.max_len = 400
        self.initUI()
        self.set_size()

    def initUI(self):
        self.setWindowTitle("上传文件")
        self.logo = QLabel()
        self.logo.setPixmap(QPixmap("./icon/logo3.gif"))
        self.logo.setStyleSheet("background-color:rgb(0,153,255);")
        self.logo.setAlignment(Qt.AlignCenter)

        # btn 1
        self.btn_chooseDir = QPushButton("选择文件夹", self)
        self.btn_chooseDir.setObjectName("btn_chooseDir")
        self.btn_chooseDir.setIcon(QIcon("./icon/folder_open.gif"))

        # btn 2
        self.btn_chooseMutiFile = QPushButton("选择多文件", self)
        self.btn_chooseMutiFile.setObjectName("btn_chooseMutiFile")
        self.btn_chooseMutiFile.setIcon(QIcon("./icon/file.ico"))

        # btn 3
        self.btn_deleteSelect = QPushButton("删除", self)
        self.btn_deleteSelect.setObjectName("btn_deleteSelect")
        self.btn_deleteSelect.setIcon(QIcon("./icon/delete.ico"))

        # 列表
        self.list_view = QListView(self)
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

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(self.logo, 1, 0, 1, 3)
        grid.addWidget(self.btn_chooseDir, 2, 0)
        grid.addWidget(self.btn_chooseMutiFile, 2, 2)
        grid.addWidget(self.list_view, 3, 0, 2, 3)
        grid.addWidget(self.btn_deleteSelect, 5, 0)
        grid.addWidget(self.buttonBox, 5, 1, 1, 2)
        self.setLayout(grid)

        self.setMinimumWidth(350)

        # 设置信号
        self.btn_chooseDir.clicked.connect(self.slot_btn_chooseDir)
        self.btn_chooseMutiFile.clicked.connect(self.slot_btn_chooseMutiFile)
        self.btn_deleteSelect.clicked.connect(self.slot_btn_deleteSelect)

        self.buttonBox.accepted.connect(self.slot_btn_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.clear_old)
        self.buttonBox.rejected.connect(self.reject)

    def set_size(self):
        rows = self.model.rowCount()
        for i in range(rows):
            m_len = int(len(self.model.item(i, 0).text()) * 8)
            if m_len > self.max_len:
                self.max_len = m_len
        self.resize(self.max_len, 250+rows*28)

    def clear_old(self):
        self.selected = []
        self.model.removeRows(0, self.model.rowCount())
        self.set_size()

    def slot_btn_ok(self):
        if self.selected:
            self.new_infos.emit(self.selected)
            self.clear_old()

    def slot_btn_deleteSelect(self):
        _indexs = self.list_view.selectionModel().selection().indexes()
        if not _indexs:
            return
        indexs = []
        for i in _indexs:  # 获取所选行号
            indexs.append(i.row())
        indexs = set(indexs)
        for i in sorted(indexs, reverse=True):
            self.selected.remove(self.model.item(i, 0).text())
            self.model.removeRow(i)
        self.set_size()

    def slot_btn_chooseDir(self):
        dir_choose = QFileDialog.getExistingDirectory(self, "选择文件夹", self.cwd)  # 起始路径

        if dir_choose == "":
            return
        if dir_choose not in self.selected:
            self.selected.append(dir_choose)
            self.model.appendRow(QStandardItem(QIcon("./icon/folder_open.gif"), dir_choose))
            self.set_size()

    def slot_btn_chooseMutiFile(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择多文件", self.cwd, "All Files (*)")
        if len(files) == 0:
            return

        for _file in files:
            if _file not in self.selected:
                self.selected.append(_file)
                self.model.appendRow(QStandardItem(QIcon("./icon/file.ico"), _file))
        self.set_size()


class InfoDialog(QDialog, Ui_Dialog):
    """文件信息对话框"""

    def __init__(self, infos, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.infos = infos
        self.initUI()

    def initUI(self):
        self.setWindowTitle("文件信息")
        self.logo.setPixmap(QPixmap("./icon/q9.gif"))
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setStyleSheet("background-color:rgb(255,204,51);")
        self.tx_name.setText(self.infos[0])
        self.tx_name.setReadOnly(True)
        if self.infos[1]:
            self.tx_size.setText(self.infos[1])
        else:
            self.tx_size.hide()
            self.lb_size.hide()
        if self.infos[2]:
            self.tx_time.setText(self.infos[2])
        else:
            self.lb_time.hide()
            self.tx_time.hide()
        if self.infos[3]:
            self.tx_dl_count.setText(self.infos[3])
        else:
            self.tx_dl_count.hide()
            self.lb_dl_count.hide()
        self.tx_share_url.setText(self.infos[4])
        self.tx_share_url.setReadOnly(True)
        line_h = 28  # 行高
        self.tx_share_url.setMinimumHeight(line_h)
        self.tx_share_url.setMaximumHeight(line_h)
        self.lb_share_url.setMinimumHeight(line_h)
        self.lb_share_url.setMaximumHeight(line_h)
        self.lb_name.setMinimumHeight(line_h)
        self.lb_name.setMaximumHeight(line_h)
        self.tx_name.setMinimumHeight(line_h)
        self.tx_name.setMaximumHeight(line_h)
        self.lb_pwd.setMinimumHeight(line_h)
        self.lb_pwd.setMaximumHeight(line_h)
        self.tx_pwd.setMinimumHeight(line_h)
        self.tx_pwd.setMaximumHeight(line_h)
        self.tx_pwd.setText(self.infos[5])
        self.tx_pwd.setReadOnly(True)
        self.tx_dl_link.setText(self.infos[6])
        min_width = int(len(self.infos[0]) * 7.8)
        if self.infos[6] == "无":
            if min_width < 380:
                min_width = 380
            min_height = 260
            dl_link_height = line_h
        else:
            if min_width < 480:
                min_width = 480
            min_height = 420
            dl_link_height = 120
            self.setMinimumSize(QSize(min_width, min_height))
        self.resize(min_width, min_height)
        self.tx_dl_link.setMinimumHeight(dl_link_height)
        self.tx_dl_link.setMaximumHeight(dl_link_height)
        self.lb_dl_link.setMinimumHeight(dl_link_height)
        self.lb_dl_link.setMaximumHeight(dl_link_height)


class RenameDialog(QDialog):
    new_infos = pyqtSignal(object)

    def __init__(self, infos, parent=None):
        super(RenameDialog, self).__init__(parent)
        self.infos = infos
        self.initUI()

    def initUI(self):
        self.lb_name = QLabel()
        self.lb_name.setText("文件夹名：")
        self.lb_name.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_name = QLineEdit()
        self.lb_desc = QLabel()
        self.tx_desc = QTextEdit()
        if self.infos:
            self.setWindowTitle("修改文件夹名与描述")
            self.tx_name.setText(self.infos[0])
            self.tx_desc.setText(self.infos[6])
            min_width = len(self.infos[0]) * 8
            if self.infos[1]:
                # 文件无法重命名，有大小表示文件
                self.tx_name.setFocusPolicy(Qt.NoFocus)
                self.tx_name.setReadOnly(True)
        else:
            min_width = 400
            self.setWindowTitle("新建文件夹")
        self.lb_desc.setText("描　　述：")
        self.lb_desc.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.grid.addWidget(self.lb_name, 1, 0)
        self.grid.addWidget(self.tx_name, 1, 1)
        self.grid.addWidget(self.lb_desc, 2, 0)
        self.grid.addWidget(self.tx_desc, 2, 1, 5, 1)
        self.grid.addWidget(self.buttonBox, 7, 1, 1, 1)
        self.setLayout(self.grid)
        if min_width < 340:
            min_width = 340
        self.resize(min_width, 200)
        self.buttonBox.accepted.connect(self.btn_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def btn_ok(self):
        new_name = self.tx_name.text()
        new_desc = self.tx_desc.toPlainText()
        if not self.infos and new_name:
            self.new_infos.emit((new_name, new_desc))
            return
        if new_name != self.infos[0] or new_desc != self.infos[6]:
            self.new_infos.emit(((self.infos[0], new_name), (self.infos[6], new_desc)))


class SetPwdDialog(QDialog):
    new_infos = pyqtSignal(object)

    def __init__(self, infos, parent=None):
        super(SetPwdDialog, self).__init__(parent)
        self.infos = infos
        self.initUI()

    def initUI(self):
        if self.infos[1]:  # 通过size列判断是否为文件
            self.setWindowTitle("修改文件提取码")
        else:
            self.setWindowTitle("修改文件夹名提取码")
        self.lb_oldpwd = QLabel()
        self.lb_oldpwd.setText("当前提取码：")
        self.lb_oldpwd.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_oldpwd = QLineEdit()
        self.tx_oldpwd.setText(self.infos[5] or "无")
        # 当前提取码 只读
        self.tx_oldpwd.setFocusPolicy(Qt.NoFocus)
        self.tx_oldpwd.setReadOnly(True)
        self.lb_newpwd = QLabel()
        self.lb_newpwd.setText("新的提取码：")
        self.lb_newpwd.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_newpwd = QLineEdit()
        self.tx_newpwd.setMaxLength(6)  # 最长6个字符
        self.tx_newpwd.setPlaceholderText("2-6位字符,关闭请留空")

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

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
        self.buttonBox.rejected.connect(self.reject)
        self.setMinimumWidth(280)

    def btn_ok(self):
        new_pwd = self.tx_newpwd.text()
        if new_pwd != self.infos[5]:
            self.new_infos.emit((self.infos[3], new_pwd, self.infos[1]))  # 最后一位用于标示文件还是文件夹


class MoveFileDialog(QDialog):
    new_infos = pyqtSignal(object)

    def __init__(self, infos, all_dirs, parent=None):
        super(MoveFileDialog, self).__init__(parent)
        self.infos = infos
        self.dirs = all_dirs
        self.initUI()

    def initUI(self):
        self.setWindowTitle("移动文件")
        self.lb_name = QLabel()
        self.lb_name.setText("文件路径：")
        self.lb_name.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_name = QLineEdit()
        self.tx_name.setText(self.infos[0])
        # 只读
        self.tx_name.setFocusPolicy(Qt.NoFocus)
        self.tx_name.setReadOnly(True)
        self.lb_new_path = QLabel()
        self.lb_new_path.setText("目标文件夹：")
        self.lb_new_path.setAlignment(
            Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter
        )
        self.tx_new_path = QComboBox()
        f_icon = QIcon("./icon/folder_open.gif")
        self.tx_new_path.addItem(f_icon, "id：{}，name：{}".format(-1, "根目录"))
        for i in self.dirs:
            f_name = i["folder_name"]
            if len(f_name) > 1000:  # 防止文件夹名字过长？
                f_name = f_name[:998] + "..."
            self.tx_new_path.addItem(f_icon, "id：{}，name：{}".format(i["folder_id"], f_name))

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

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
        selected = self.tx_new_path.currentText().split("，")[0].split("：")[1]
        self.new_infos.emit((self.infos[3], selected, self.infos[0]))


class DeleteDialog(QDialog):
    new_infos = pyqtSignal(object)

    def __init__(self, infos, parent=None):
        super(DeleteDialog, self).__init__(parent)
        self.infos = infos
        self.out = []
        self.initUI()

    def set_file_icon(self, name):
        suffix = name.split(".")[-1]
        ico_path = "./icon/{}.gif".format(suffix)
        if os.path.isfile(ico_path):
            return QIcon(ico_path)
        else:
            return QIcon("./icon/file.ico")

    def initUI(self):
        self.setWindowTitle("确认删除")
        self.layout = QVBoxLayout()
        self.list_view = QListView()
        self.list_view.setViewMode(QListView.ListMode)
        # 列表
        self.slm = QStandardItem()
        self.model = QStandardItemModel()
        max_len = 10
        count = 0
        for i in self.infos:
            if i[2]:  # 有大小，是文件
                self.model.appendRow(QStandardItem(self.set_file_icon(i[0]), i[0]))
            else:
                self.model.appendRow(QStandardItem(QIcon("./icon/folder_open.gif"), i[0]))
            self.out.append((i[1], i[2]))
            count += 1
            if max_len < len(i[0]):
                max_len = len(i[0])
        self.list_view.setModel(self.model)

        self.lb_name = QLabel("尝试删除以下{}个文件(夹)：".format(count))
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

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


class MyLineEdit(QLineEdit):
    """添加单击事件的输入框"""

    clicked = pyqtSignal()

    def __init__(self, parent):
        super(MyLineEdit, self).__init__(parent)

    def mouseReleaseEvent(self, QMouseEvent):
        if QMouseEvent.button() == Qt.LeftButton:
            self.clicked.emit()


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)
        self.init_variable()
        self.init_menu()
        self.setWindowTitle("蓝奏云客户端")
        self.setWindowIcon(QIcon("./icon/lanzou-logo2.png"))

        self.center()
        self.extract_share_ui()
        self.disk_ui()
        self.autologin_dialog()
        self.table_disk.doubleClicked.connect(self.chang_dir)

        self.create_left_menus()
        self._disk.set_rar_tool("/usr/bin/rar")

    def init_menu(self):
        self.login.triggered.connect(self.show_login_dialog)
        self.logout.triggered.connect(self.menu_logout)
        self.login.setShortcut("Ctrl+L")
        self.login.setIcon(QIcon("./icon/login.ico"))
        self.logout.setShortcut("Ctrl+Q")
        self.logout.setIcon(QIcon("./icon/logout.ico"))
        self.toolbar.addAction(self.login)
        self.download.setShortcut("Ctrl+J")
        self.download.setIcon(QIcon("./icon/download.ico"))
        self.delete.setShortcut("Ctrl+D")
        self.delete.setIcon(QIcon("./icon/delete.ico"))
        self.how.setShortcut("Ctrl+H")
        self.how.setIcon(QIcon("./icon/help.ico"))
        self.about.setShortcut("Ctrl+A")
        self.about.setIcon(QIcon("./icon/about.ico"))

    def login_menu(self):
        self.toolbar.addAction(self.logout)
        self.upload_dialog = UploadDialog()
        self.upload.triggered.connect(self.upload_dialog.show)
        self.upload_dialog.new_infos.connect(self.call_upload)
        self.upload.setIcon(QIcon("./icon/upload.ico"))
        self.upload.setShortcut("Ctrl+U")
        self.toolbar.addAction(self.upload)
        # self.download.triggered.connect(self.download_dialog.show)
        # self.download.setIcon(QIcon("./icon/logout.ico"))
        # self.download.setShortcut("Ctrl+J")
        # self.toolbar.addAction(self.download)

    def init_variable(self):
        self._disk = LanZouCloud()
        self._config = "./config.pkl"
        self._folder_list = {}
        self._file_list = {}
        self._path_list = {}
        self._path_list_old = {}
        self.locs = {}
        self._parent_id = -1
        self._parent_name = ""
        self._work_name = ""
        self._work_id = -1
        # self._stopped = True
        # self._mutex = QMutex()
        self.load_settings()

    def show_login_dialog(self):
        """显示登录对话框"""
        login_dialog = LoginDialog(self._config)
        login_dialog.btn_ok.clicked.connect(self.autologin_dialog)
        login_dialog.setWindowModality(Qt.ApplicationModal)
        login_dialog.exec()

    def load_settings(self):
        try:
            with open(self._config, "rb") as _file:
                self.settings = load(_file)
        except Exception:
            dl_path = os.path.dirname(os.path.abspath(__file__)) + os.sep + "downloads"
            self.settings = {"user": "", "pwd": "", "path": dl_path}
            with open(self._config, "wb") as _file:
                dump(self.settings, _file)

    def _refresh(self, dir_id=-1, r_files=True, r_folders=True):
        """刷新当前文件夹和路径信息"""
        if r_files:
            self._file_list = self._disk.get_file_list2(dir_id)  # {name-[id,...]}
        if r_folders:
            self._folder_list = self._disk.get_dir_list(dir_id)
        self._path_list = self._disk.get_full_path(dir_id)
        self._work_name = list(self._path_list.keys())[-1]
        self._work_id = self._path_list.get(self._work_name, -1)
        if dir_id != -1:
            self._parent_name = list(self._path_list.keys())[-2]
            self._parent_id = self._path_list.get(self._parent_name, -1)

    def show_download_process(self, msg):
        self.statusbar.showMessage(str(msg), 8000)

    def call_downloader(self, tab):
        if tab == "disk":
            listview = self.table_disk
            model = self.model_disk
        elif tab == "share":
            listview = self.table_share
            model = self.model_share
        indexs = []
        tasks = []
        _indexs = listview.selectionModel().selection().indexes()
        for i in _indexs:  # 获取所选行号
            indexs.append(i.row())
        indexs = set(indexs)
        save_path = self.settings["path"]
        for index in indexs:
            name = model.item(index, 0).text()  # 用于folder创建文件夹
            url = model.item(index, 7).text()  # 分享链接
            pwd = model.item(index, 5).text()  # 提取码，没有为空串
            if tab == "disk" and name == "..":
                continue
            tasks.append([name, url, pwd, save_path])
        self.download_manager = DownloadManager(self._disk, tasks, self)
        self.download_manager.download_mgr_msg.connect(self.show_download_process)
        self.download_manager.downloaders_msg.connect(self.show_download_process)
        self.download_manager.start()

    def menu_logout(self):
        self._disk.logout()
        self.toolbar.removeAction(self.logout)
        self.tabWidget.setCurrentIndex(0)
        self.disk_tab.setEnabled(False)
        self.rec_tab.setEnabled(False)
        self.tabWidget.removeTab(2)
        self.tabWidget.removeTab(1)
        self.statusbar.showMessage("已经退出登录！", 5000)

    def autologin_dialog(self):
        """登录网盘"""
        self.load_settings()
        self._disk.logout()
        self.toolbar.removeAction(self.logout)
        try:
            username = self.settings["user"]
            password = self.settings["pwd"]
            cookie = self.settings["cookie"]
            if (not username or not password) and not cookie:
                self.statusbar.showMessage("登录失败: 没有用户或密码", 3000)
                raise Exception("没有用户或密码")
            res = self._disk.login(username, password, cookie=cookie)
            if res == LanZouCloud.LOGIN_ERROR:
                self.statusbar.showMessage("无法使用用户名与密码登录，请使用Cookie！", 8000)
                raise Exception("登录失败")
            elif res != LanZouCloud.SUCCESS:
                self.statusbar.showMessage("登录失败，可能是用户名或密码错误！", 8000)
                raise Exception("登录失败")
            self.statusbar.showMessage("登录成功！", 8000)
            self.login_menu()

            self.tabWidget.insertTab(1, self.disk_tab, "我的蓝奏云")
            self.tabWidget.insertTab(2, self.rec_tab, "回收站")
            self.disk_tab.setEnabled(True)
            self.rec_tab.setEnabled(True)
            # 设置当前显示 tab
            self.tabWidget.setCurrentIndex(1)
            # 刷新文件列表
            self.refresh_dir(self._work_id)
        except Exception as exp:
            print(exp)
            self.tabWidget.setCurrentIndex(0)
            self.tabWidget.removeTab(2)
            self.tabWidget.removeTab(1)
            self.disk_tab.setEnabled(False)
            self.rec_tab.setEnabled(False)

    def set_file_icon(self, name):
        suffix = name.split(".")[-1]
        ico_path = "./icon/{}.gif".format(suffix)
        if os.path.isfile(ico_path):
            return QIcon(ico_path)
        else:
            return QIcon("./icon/file.ico")

    def list_file_folder(self):
        """列出文件"""
        self.model_disk.removeRows(0, self.model_disk.rowCount())
        folder_ico = QIcon("./icon/folder_open.gif")
        pwd_ico = QIcon("./icon/keys.ico")
        if self._work_id != -1:
            self.model_disk.appendRow(
                [
                    QStandardItem(folder_ico, ".."),
                    QStandardItem(""),
                    QStandardItem(""),
                    QStandardItem(""),
                    QStandardItem(""),
                    QStandardItem(""),
                    QStandardItem(""),
                    QStandardItem(""),
                ]
            )
        for folder, f_info in self._folder_list.items():
            if f_info[4]:
                self.model_disk.appendRow(
                    [
                        QStandardItem(folder_ico, folder),
                        QStandardItem(pwd_ico, "{}".format(f_info[1])),
                        QStandardItem("{}".format(f_info[2])),
                        QStandardItem("{}".format(f_info[0])),
                        QStandardItem("{}".format(f_info[3])),
                        QStandardItem("{}".format(f_info[4])),
                        QStandardItem("{}".format(f_info[5])),
                        QStandardItem("{}".format(f_info[6])),
                    ]
                )
            else:
                self.model_disk.appendRow(
                    [
                        QStandardItem(folder_ico, folder),
                        QStandardItem("{}".format(f_info[1])),
                        QStandardItem("{}".format(f_info[2])),
                        QStandardItem("{}".format(f_info[0])),
                        QStandardItem("{}".format(f_info[3])),
                        QStandardItem("{}".format(f_info[4])),
                        QStandardItem("{}".format(f_info[5])),
                        QStandardItem("{}".format(f_info[6])),
                    ]
                )
        for file_name, f_info in self._file_list.items():
            if f_info[4]:
                self.model_disk.appendRow(
                    [
                        QStandardItem(self.set_file_icon(file_name), file_name),
                        QStandardItem(pwd_ico, "{}".format(f_info[1])),
                        QStandardItem("{}".format(f_info[2])),
                        QStandardItem("{}".format(f_info[0])),
                        QStandardItem("{}".format(f_info[3])),
                        QStandardItem("{}".format(f_info[4])),
                        QStandardItem("{}".format(f_info[5])),
                        QStandardItem("{}".format(f_info[6])),
                    ]
                )
            else:
                self.model_disk.appendRow(
                    [
                        QStandardItem(self.set_file_icon(file_name), file_name),
                        QStandardItem("{}".format(f_info[1])),
                        QStandardItem("{}".format(f_info[2])),
                        QStandardItem("{}".format(f_info[0])),
                        QStandardItem("{}".format(f_info[3])),
                        QStandardItem("{}".format(f_info[4])),
                        QStandardItem("{}".format(f_info[5])),
                        QStandardItem("{}".format(f_info[6])),
                    ]
                )
        for r in range(self.model_disk.rowCount()):
            self.model_disk.item(r, 1).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.model_disk.item(r, 2).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def center(self):
        screen = QDesktopWidget().screenGeometry()
        size = self.geometry()

        new_left = int((screen.width() - size.width()) / 2)
        new_top = int((screen.height() - size.height()) / 2)

        self.move(new_left, new_top)

    def config_tableview(self, tab):
        if tab == "share":
            model = self.model_share
            table = self.table_share
        elif tab == "disk":
            model = self.model_disk
            table = self.table_disk

        model.setHorizontalHeaderLabels(
            ["文件名/夹", "大小", "时间", "ID", "下载数", "密码", "描述", "链接"]
        )
        table.setModel(model)
        # 是否显示网格线
        table.setShowGrid(False)
        # 禁止编辑表格
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # 隐藏水平表头
        table.verticalHeader().setVisible(False)
        # 设置表头可以自动排序
        table.setSortingEnabled(True)
        table.setMouseTracking(False)
        # 设置表头的背景色为绿色
        table.horizontalHeader().setStyleSheet(
            "QHeaderView::section{background:lightgray}"
        )
        # 设置 不可选择单个单元格，只可选择一行。
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        # 设置第二三列的宽度
        table.horizontalHeader().resizeSection(1, 70)
        table.horizontalHeader().resizeSection(2, 80)
        table.horizontalHeader().resizeSection(4, 40)
        table.horizontalHeader().resizeSection(5, 50)
        table.horizontalHeader().resizeSection(6, 90)
        # 设置第一列宽度自动调整，充满屏幕
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.setContextMenuPolicy(Qt.CustomContextMenu)  # 允许右键产生子菜单
        table.customContextMenuRequested.connect(self.generateMenu)  # 右键菜单
        table.hideColumn(8)
        table.hideColumn(7)
        table.hideColumn(6)
        table.hideColumn(5)
        table.hideColumn(4)
        table.hideColumn(3)

    def create_left_menus(self):
        self.left_menus = QMenu()
        self.left_menu_share_url = self.left_menus.addAction("外链分享地址")
        self.left_menu_share_url.setIcon(QIcon("./icon/share.ico"))
        self.left_menu_rename_set_desc = self.left_menus.addAction("修改文件夹名与描述")
        self.left_menu_rename_set_desc.setIcon(QIcon("./icon/desc.ico"))
        self.left_menu_set_pwd = self.left_menus.addAction("设置访问密码")
        self.left_menu_set_pwd.setIcon(QIcon("./icon/password.ico"))
        self.left_menu_move = self.left_menus.addAction("移动")
        self.left_menu_move.setIcon(QIcon("./icon/move.ico"))

    def rename_set_desc(self, infos):
        """重命名与修改简介"""
        name = infos[0][0]
        new_name = infos[0][1]
        desc = infos[1][0]
        new_desc = infos[1][1]
        if self._work_name == "Recovery":
            print("ERROR : 回收站模式下无法使用此操作")
            return None
        fid = self._folder_list.get(name, None)[0]
        if fid is None:
            print("ERROR : 文件夹不存在:{}".format(name))
        else:
            res = self._disk.rename_dir(fid, str(new_name), str(new_desc))
            if res == LanZouCloud.SUCCESS:
                self.statusbar.showMessage("修改成功！", 4000)
            elif res == LanZouCloud.FAILED:
                self.statusbar.showMessage("失败：文件夹id数大于7位 或者 网络错误！", 4000)
            # 只更新文件夹列表
            self.refresh_dir(self._work_id, r_files=False, r_folders=True, r_path=False)

    def set_passwd(self, infos):
        """设置文件(夹)提取码"""
        fid = infos[0]
        if not fid:
            print("ERROR : 文件(夹)不存在:{}".format(infos[0]))
            return None
        new_pass = infos[1]
        if 2 <= len(new_pass) <= 6 or new_pass == "":
            if infos[2]:
                isFile = True
                isFolder = False
            else:
                isFile = False
                isFolder = True
            res = self._disk.set_share_passwd(fid, new_pass, isFile=isFile, isFolder=isFolder)
            if res == LanZouCloud.SUCCESS:
                self.statusbar.showMessage("提取码变更成功！♬", 3000)
            else:
                self.statusbar.showMessage("提取码变更失败❀╳❀:{}".format(res), 4000)
            self.refresh_dir(self._work_id, r_files=isFile, r_folders=isFolder, r_path=False)
        else:
            self.statusbar.showMessage("提取码为2-6位字符,关闭请输入空！", 4000)

    def move_file(self, info):
        """移动文件至新的文件夹"""
        file_id = info[0]
        folder_id = info[1]
        if self._disk.move_file(file_id, folder_id) == LanZouCloud.SUCCESS:
            # 此处仅更新文件夹，并显示
            self.refresh_dir(self._work_id, False, True, False)
            self.statusbar.showMessage("{} 移动成功！".format(info[2]), 4000)
        else:
            self.statusbar.showMessage("移动文件{}失败！".format(info[2]), 4000)

    def call_mkdir(self):
        """弹出新建文件夹对话框"""
        mkdir_dialog = RenameDialog(None)
        mkdir_dialog.new_infos.connect(self.mkdir)
        mkdir_dialog.exec()

    def mkdir(self, infos):
        """创建文件夹"""
        if self._work_name == 'Recovery':
            print('ERROR : 回收站模式下无法使用此操作')
            return None
        name = infos[0]
        desc = infos[1]
        if name in self._folder_list.keys():
            self.statusbar.showMessage("文件夹已存在：{}".format(name), 7000)
        else:
            res = self._disk.mkdir(self._work_id, name, desc)
            if res == LanZouCloud.MKDIR_ERROR:
                self.statusbar.showMessage("创建文件夹失败：{}".format(name), 7000)
            else:
                sleep(1)  # 不暂停一下无法获取新建文件夹
                self.statusbar.showMessage("成功创建文件夹：{}".format(name), 7000)
                # 此处仅更新文件夹，并显示
                self.refresh_dir(self._work_id, False, True, False)

    def remove_files(self, infos):
        if not infos:
            return
        for i in infos:
            if i[1]:
                isfile = True
                isfolder = False
            else:
                isfile = False
                isfolder = True
            self._disk.delete(i[0], isfile, isfolder)
        self.refresh_dir(self._work_id)

    def call_remove_files(self):
        indexs = []
        infos = []
        _indexs = self.table_disk.selectionModel().selection().indexes()
        if not _indexs:
            return
        for i in _indexs:  # 获取所选行号
            indexs.append(i.row())
        indexs = set(indexs)
        for index in indexs:
            name = self.model_disk.item(index, 0).text()  # 用于提示删除的文件名
            id = self.model_disk.item(index, 3).text()  # 文件(夹)id
            file = self.model_disk.item(index, 1).text()  # 标示文件
            if name == "..":
                continue
            infos.append([name, id, file])
        delete_dialog = DeleteDialog(infos)
        delete_dialog.new_infos.connect(self.remove_files)
        delete_dialog.exec()

    def generateMenu(self, pos):
        """右键菜单"""
        row_num = self.sender().selectionModel().selection().indexes()
        if not row_num:  # 如果没有选中行，什么也不做
            return
        row_num = row_num[0].row()
        _model = self.sender().model()
        # 通过 第4列文件 ID 判断是登录界面还是提取界面
        if _model.item(row_num, 3).text():
            self.left_menu_rename_set_desc.setEnabled(True)
            self.left_menu_set_pwd.setEnabled(True)
            # 通过第2列 size 判断是否为文件夹，文件夹不能移动，设置不同的显示菜单名
            if _model.item(row_num, 1).text():
                self.left_menu_rename_set_desc.setText("修改文件描述")
                self.left_menu_move.setEnabled(True)
            else:
                self.left_menu_rename_set_desc.setText("修改文件夹名与描述")
                self.left_menu_move.setDisabled(True)
        else:
            self.left_menu_rename_set_desc.setDisabled(True)
            self.left_menu_move.setDisabled(True)
            self.left_menu_set_pwd.setDisabled(True)
        if _model.item(row_num, 0).text() != "..":
            action = self.left_menus.exec_(self.sender().mapToGlobal(pos))
            infos = []
            for i in range(8):
                infos.append(_model.item(row_num, i).text())
            if action == self.left_menu_share_url:
                self.get_share_infomation(infos)
            elif action == self.left_menu_move:
                all_dirs = self._disk.get_all_folders(infos[3])
                move_file_dialog = MoveFileDialog(infos, all_dirs)
                move_file_dialog.new_infos.connect(self.move_file)
                move_file_dialog.exec()
            elif action == self.left_menu_set_pwd:
                set_pwd_dialog = SetPwdDialog(infos)
                set_pwd_dialog.new_infos.connect(self.set_passwd)
                set_pwd_dialog.exec()
            elif action == self.left_menu_rename_set_desc:
                rename_dialog = RenameDialog(infos)
                rename_dialog.new_infos.connect(self.rename_set_desc)
                rename_dialog.exec()

    def get_share_infomation(self, infos):
        """显示分享信息"""
        if self._work_name == "Recovery":
            print("ERROR : 回收站模式下无法使用此操作")
            return None
        # infos: 文件名，大小，日期，ID/url，下载次数(dl_count)，提取码(pwd)，描述(desc)，链接(share-url)
        _infos = infos[0:3]  # 文件名+大小+日期
        _infos.append(infos[4])  # 下载次数
        _infos.append(infos[7])  # 分享链接
        _infos.append(infos[5] or "无")  # 提取码

        # 通过分享链接 获取文件下载直链
        d_url = self._disk.get_direct_url(infos[7], infos[5])
        _infos.append("{}".format(d_url["direct_url"] or "无"))  # 下载直链

        info_dialog = InfoDialog(_infos)
        info_dialog.setWindowModality(Qt.ApplicationModal)
        info_dialog.exec()

    def chang_dir(self, dir_name):
        """双击切换工作目录"""
        # 文件名
        dir_name = self.model_disk.item(dir_name.row(), 0).text()
        if self._work_name == "Recovery" and dir_name not in [".", ".."]:
            print("ERROR : 回收站模式下仅支持 > cd ..")
            return None
        if dir_name == "..":  # 返回上级路径
            self.refresh_dir(self._parent_id)
        elif dir_name == ".":
            pass
        elif dir_name in self._folder_list.keys():
            folder_id = self._folder_list[dir_name][0]
            self.refresh_dir(folder_id)
        else:
            pass
            # print("ERROR : 该文件夹不存在: {}".format(dir_name))

    def refresh_dir(self, folder_id=-1, r_files=True, r_folders=True, r_path=True):
        """更新目录列表"""
        self._refresh(folder_id, r_files, r_folders)
        self.list_file_folder()
        if r_path:
            self.show_full_path()

    def call_change_dir(self, folder_id=-1):
        """按钮调用"""
        def callfunc():
            self.refresh_dir(folder_id)

        return callfunc

    def call_upload(self, infos):
        """上传文件(夹)"""
        if self._work_name == 'Recovery':
            print('ERROR : 回收站模式下无法使用此操作')
            return None
        for f in infos:
            if not os.path.exists(f):
                msg = 'ERROR : 文件不存在:{}'.format(f)
                return None
            if os.path.isdir(f):
                msg = 'INFO : 文件夹批量上传:{}'.format(f)
                self._disk.upload_dir(f, self._work_id, None)
            else:
                self._disk.upload_file(f, self._work_id, None)
        if infos:
            self.refresh_dir(self._work_id, True, True, False)

    def show_full_path(self):
        """路径框显示当前路径"""
        index = 1
        for name in self._path_list_old.items():
            self.locs[index].clicked.disconnect()
            self.disk_loc.removeWidget(self.locs[index])
            self.locs[index].deleteLater()
            self.locs[index] = None
            del self.locs[index]
            index += 1
        index = 1
        for name, id in self._path_list.items():
            self.locs[index] = QPushButton(name, self.disk_tab)
            self.locs[index].setIcon(QIcon("./icon/folder_open.gif"))
            self.disk_loc.insertWidget(index, self.locs[index])
            # wd = self.locs[index].fontMetrics().width(name)
            # self.locs[index].setMaxLength(name)  # 设置按钮宽度
            self.locs[index].clicked.connect(self.call_change_dir(id))
            index += 1
        self._path_list_old = self._path_list

    def select_all_btn(self, page, action="reverse"):
        if page == "disk":
            btn = self.btn_disk_select_all
            table = self.table_disk
        elif page == "share":
            btn = self.btn_share_select_all
            table = self.table_share
        else:
            return
        if action == "reverse":
            if btn.text() == "全选":
                table.selectAll()
                btn.setText("取消")
                btn.setIcon(QIcon("./icon/select-none.ico"))
            elif btn.text() == "取消":
                table.clearSelection()
                btn.setText("全选")
                btn.setIcon(QIcon("./icon/select-all.ico"))
        elif action == "cancel":
            btn.setText("全选")
            btn.setIcon(QIcon("./icon/select-all.ico"))
        else:
            table.selectAll()
            btn.setText("取消")
            btn.setIcon(QIcon("./icon/select-none.ico"))

    def disk_ui(self):
        self.model_disk = QStandardItemModel(1, 8)
        self.config_tableview("disk")
        self.btn_disk_delete.setIcon(QIcon("./icon/delete.ico"))
        self.btn_disk_dl.setIcon(QIcon("./icon/downloader.ico"))
        self.btn_disk_select_all.setIcon(QIcon("./icon/select-all.ico"))
        self.btn_disk_select_all.clicked.connect(lambda: self.select_all_btn("disk"))
        self.table_disk.clicked.connect(lambda: self.select_all_btn("disk", "cancel"))
        self.btn_disk_dl.clicked.connect(lambda: self.call_downloader("disk"))
        self.btn_disk_mkdir.setIcon(QIcon("./icon/add-folder.ico"))
        self.btn_disk_mkdir.clicked.connect(self.call_mkdir)
        self.btn_disk_delete.clicked.connect(self.call_remove_files)

    def list_share_url_file(self):
        self.btn_share_select_all.setDisabled(True)
        self.btn_share_dl.setDisabled(True)
        self.table_share.setDisabled(True)
        line_share_text = self.line_share_url.text().strip()
        patn = re.findall(
            r"(https?://www.lanzous.com/[bi][a-z0-9]+)[^0-9a-z]*([a-z0-9]+)?",
            line_share_text,
        )
        if patn:
            share_url = patn[0][0]
            pwd = patn[0][1]
        else:
            share_url = line_share_text
            pwd = ""

        self.model_share.removeRows(0, self.model_share.rowCount())
        if self._disk.is_file_url(share_url):
            self.share_file_infos = self._disk.get_share_file_info(share_url, pwd)
        elif self._disk.is_folder_url(share_url):
            self.share_file_infos = self._disk.get_share_folder_info(share_url, pwd)
        else:
            self.statusbar.showMessage("{} 为非法链接！".format(share_url), 0)
            self.share_file_infos = {}
            return

        if self.share_file_infos["code"] == LanZouCloud.FILE_CANCELLED:
            self.statusbar.showMessage("文件不存在！", 0)
        elif self.share_file_infos["code"] == LanZouCloud.URL_INVALID:
            self.statusbar.showMessage("链接非法！", 0)
        elif self.share_file_infos["code"] == LanZouCloud.PASSWORD_ERROR:
            self.statusbar.showMessage("提取码 [{}] 错误！".format(pwd), 0)
        elif self.share_file_infos["code"] == LanZouCloud.LACK_PASSWORD:
            self.statusbar.showMessage("请在链接后面跟上提取码，空格分割！", 0)
        elif self.share_file_infos["code"] == LanZouCloud.FAILED:
            self.statusbar.showMessage("网络错误！", 0)
        elif self.share_file_infos["code"] == LanZouCloud.SUCCESS:
            self.statusbar.showMessage("提取信息成功！", 0)
            for key, infos in self.share_file_infos["info"].items():
                self.model_share.appendRow(
                    [
                        QStandardItem(self.set_file_icon(key), key),
                        QStandardItem("{}".format(infos[1])),
                        QStandardItem("{}".format(infos[2])),
                        QStandardItem("{}".format(infos[0])),
                        QStandardItem("{}".format(infos[3])),
                        QStandardItem("{}".format(infos[4])),
                        QStandardItem("{}".format(infos[5])),
                        QStandardItem("{}".format(infos[6])),
                    ]
                )
            self.table_share.setDisabled(False)
            self.btn_share_select_all.setDisabled(False)
            self.btn_share_dl.setDisabled(False)

    def set_dl_path(self):
        """设置下载路径"""
        dl_path = QFileDialog.getExistingDirectory()
        if dl_path == self.settings["path"]:
            return
        if dl_path == "":
            dl_path = os.path.dirname(os.path.abspath(__file__)) + os.sep + "downloads"
            up_info = {"path": dl_path}
        else:
            up_info = {"path": dl_path}
        update_settings(self._config, up_info)
        self.load_settings()
        self.line_dl_path.setText(self.settings["path"])

    def extract_share_ui(self):
        self.btn_share_select_all.setDisabled(True)
        self.btn_share_dl.setDisabled(True)
        self.table_share.setDisabled(True)
        self.model_share = QStandardItemModel(1, 8)
        self.config_tableview("share")
        self.line_share_url.setPlaceholderText("蓝奏云链接，如有提取码，放后面，空格或汉字等分割，回车键提取")
        self.line_share_url.returnPressed.connect(self.list_share_url_file)
        self.btn_extract.clicked.connect(self.list_share_url_file)
        self.btn_share_dl.clicked.connect(lambda: self.call_downloader("share"))
        self.btn_share_dl.setIcon(QIcon("./icon/downloader.ico"))
        self.btn_share_select_all.setIcon(QIcon("./icon/select-all.ico"))
        self.btn_share_select_all.clicked.connect(lambda: self.select_all_btn("share"))
        self.table_share.clicked.connect(lambda: self.select_all_btn("share", "cancel"))

        # 添加文件下载路径选择器
        self.line_dl_path = MyLineEdit(self.share_tab)
        self.line_dl_path.setObjectName("line_dl_path")
        self.horizontalLayout_share_2.insertWidget(2, self.line_dl_path)
        self.line_dl_path.setText(self.settings["path"])
        self.line_dl_path.clicked.connect(self.set_dl_path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    form = MainWindow()
    form.show()
    sys.exit(app.exec())
