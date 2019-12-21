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

from downloader import Downloader, DownloadManger


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
        self.initUI()
        self.name_ed.textChanged.connect(self.set_user)
        self.pwd_ed.textChanged.connect(self.set_pwd)
        self.btn_ok.clicked.connect(self.clicked_ok)
        self.btn_cancel.clicked.connect(self.clicked_cancel)

    def default_var(self):
        try:
            with open(self._config, "rb") as _file:
                _info = load(_file)
            self._user = _info["user"]
            self._pwd = _info["pwd"]
        except Exception:
            pass
        self.name_ed.setText(self._user)
        self.pwd_ed.setText(self._pwd)

    def initUI(self):
        self.setWindowTitle("登录蓝奏云")
        self.logo = QLabel()
        self.logo.setPixmap(QPixmap("./icon/logo3.gif"))
        self.logo.setAlignment(Qt.AlignCenter)
        self.name_lb = QLabel("&User")
        self.name_ed = QLineEdit()
        self.name_lb.setBuddy(self.name_ed)

        self.pwd_lb = QLabel("&Password")
        self.pwd_ed = QLineEdit()
        self.pwd_ed.setEchoMode(QLineEdit.Password)
        self.pwd_lb.setBuddy(self.pwd_ed)

        self.btn_ok = QPushButton("&OK")
        self.btn_cancel = QPushButton("&Cancel")
        main_layout = QGridLayout()
        main_layout.addWidget(self.logo, 0, 0, 2, 3)
        main_layout.addWidget(self.name_lb, 2, 0)
        main_layout.addWidget(self.name_ed, 2, 1, 1, 2)
        main_layout.addWidget(self.pwd_lb, 3, 0)
        main_layout.addWidget(self.pwd_ed, 3, 1, 1, 2)
        main_layout.addWidget(self.btn_ok, 4, 1)
        main_layout.addWidget(self.btn_cancel, 4, 2)
        self.setLayout(main_layout)
        self.default_var()

    def set_user(self, user):
        self._user = user

    def set_pwd(self, pwd):
        self._pwd = pwd

    def clicked_cancel(self):
        self.default_var()
        self.close()

    def clicked_ok(self):
        up_info = {"user": self._user, "pwd": self._pwd}
        update_settings(self._config, up_info)
        self.close()


class UploadDialog(QDialog):
    """文件上传对话框"""

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._user = ""
        self._pwd = ""
        self.initUI()
        self.btn_upload.clicked.connect(self.clicked_upload)
        self.btn_cancel.clicked.connect(self.clicked_cancel)

    def initUI(self):
        self.setWindowTitle("上传文件")
        self.logo = QLabel()
        self.logo.setPixmap(QPixmap("./icon/logo3.gif"))
        self.logo.setAlignment(Qt.AlignCenter)
        self.name_lb = QLabel("&Files")
        self.name_ed = QLineEdit()
        self.name_lb.setBuddy(self.name_ed)

        self.pwd_lb = QLabel("&Path")
        self.pwd_ed = QLineEdit()
        self.pwd_lb.setBuddy(self.pwd_ed)

        self.btn_upload = QPushButton("&Upload")
        self.btn_cancel = QPushButton("&Cancel")
        main_layout = QGridLayout()
        main_layout.addWidget(self.logo, 0, 0, 2, 3)
        main_layout.addWidget(self.name_lb, 2, 0)
        main_layout.addWidget(self.name_ed, 2, 1, 1, 2)
        main_layout.addWidget(self.pwd_lb, 3, 0)
        main_layout.addWidget(self.pwd_ed, 3, 1, 1, 2)
        main_layout.addWidget(self.btn_upload, 4, 1)
        main_layout.addWidget(self.btn_cancel, 4, 2)
        self.setLayout(main_layout)

    def clicked_cancel(self):
        self.close()

    def clicked_upload(self):
        self.close()


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
        line_h = 26  # 行高
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
        min_width = int(len(self.infos[0]) * 7.4)
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
        self.setWindowTitle("修改文件夹名与描述")
        self.lb_name = QLabel()
        self.lb_name.setText("文件夹名：")
        self.lb_name.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_name = QLineEdit()
        self.tx_name.setText(self.infos[0])
        if self.infos[1]:
            # 文件无法重命名，有大小表示文件
            self.tx_name.setFocusPolicy(Qt.NoFocus)
            self.tx_name.setReadOnly(True)
        self.lb_desc = QLabel()
        self.lb_desc.setText("描　　述：")
        self.lb_desc.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_desc = QTextEdit()
        self.tx_desc.setText(self.infos[6])

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
        min_width = len(self.infos[0]) * 8
        if min_width < 340:
            min_width = 340
        self.resize(min_width, 200)
        self.buttonBox.accepted.connect(self.btn_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
    
    def btn_ok(self):
        new_name = self.tx_name.text()
        new_desc = self.tx_desc.toPlainText()
        if  new_name != self.infos[0] or new_desc != self.infos[6]:
            self.new_infos.emit(((self.infos[0],new_name),(self.infos[6],new_desc)))


class SetPwdDialog(QDialog):
    new_infos = pyqtSignal(object)
    def __init__(self, infos, parent=None):
        super(SetPwdDialog, self).__init__(parent)
        self.infos = infos
        self.initUI()
    def initUI(self):
        self.setWindowTitle("修改文件/文件夹名提取码")
        self.lb_oldpwd = QLabel()
        self.lb_oldpwd.setText("当前提取码：")
        self.lb_oldpwd.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_oldpwd = QLineEdit()
        self.tx_oldpwd.setText(self.infos[5] if self.infos[5] else "无")
        # 只读
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
        if  new_pwd != self.infos[5]:
            self.new_infos.emit((self.infos[3], new_pwd))


class MoveFileDialog(QDialog):
    new_infos = pyqtSignal(object)
    def __init__(self, infos, all_dirs, parent=None):
        super(MoveFileDialog, self).__init__(parent)
        self.infos = infos
        self.dirs = all_dirs
        self.selected = ''
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
        self.lb_new_path.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.tx_new_path = QComboBox()
        self.tx_new_path.addItem("id：{}，name：{}".format(-1, "根目录"))
        for i in self.dirs:
            self.tx_new_path.addItem("id：{}，name：{}".format(i["folder_id"], i["folder_name"]))

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
        self.tx_new_path.activated[str].connect(self.selected_item)
        self.buttonBox.accepted.connect(self.btn_ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.setMinimumWidth(280)

    def selected_item(self, text):
        self.selected = text.split("，")[0].split("：")[1]

    def btn_ok(self):
        self.new_infos.emit((self.infos[3], self.selected, self.infos[0]))


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
        self.btn_disk_dl.clicked.connect(self.disk_call_downloader)
        self.table_disk.doubleClicked.connect(self.chang_dir)

        self.create_left_menus()

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
        self.upload_dialog = UploadDialog(self._config)
        self.upload.triggered.connect(self.upload_dialog.show)
        # self.download.triggered.connect(self.menu_logout)
        self.upload.setShortcut("Ctrl+U")
        self.upload.setIcon(QIcon("./icon/upload.ico"))
        # self.upload.setIcon(QIcon("./icon/logout.ico"))
        # self.logout.setShortcut("Ctrl+Q")
        self.toolbar.addAction(self.upload)
        # self.toolbar.addAction(self.logout)

    def init_variable(self):
        self._disk = LanZouCloud()
        self._config = "./config.pkl"
        self._folder_list = {}
        self._file_list = {}
        self._path_list = {}
        self._parent_id = -1
        self._parent_name = ""
        self._work_name = ""
        self._work_id = -1
        self._full_path = ""
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

    def _refresh(self, dir_id=-1):
        """刷新当前文件夹和路径信息"""
        self._file_list = self._disk.get_file_list2(dir_id)  # {name-[id,...]}
        self._folder_list = self._disk.get_dir_list(dir_id)
        self._path_list = self._disk.get_full_path(dir_id)
        self._work_name = list(self._path_list.keys())[-1]
        self._work_id = self._path_list.get(self._work_name, -1)
        if dir_id != -1:
            self._parent_name = list(self._path_list.keys())[-2]
            self._parent_id = self._path_list.get(self._parent_name, -1)

    def show_download_process(self, msg):
        self.statusbar.showMessage(str(msg), 8000)

    def disk_call_downloader(self):
        _indexs = self.table_disk.selectionModel().selection().indexes()
        indexs = []
        for i in _indexs:
            indexs.append(i.row())
        indexs = set(indexs)
        tasks = []
        isurl = None
        save_path = self.settings["path"]
        for index in indexs:
            name = self.model_disk.item(index, 0).text()
            if name == "...":
                continue
            isfolder = self._folder_list.get(name, None)
            isfile = self._file_list.get(name, None)
            tasks.append([isfile, isfolder, isurl, name, save_path])
        self.download_manger_disk = DownloadManger(self._disk, tasks, self)
        self.download_manger_disk.download_mgr_msg.connect(self.show_download_process)
        self.download_manger_disk.downloaders_msg.connect(self.show_download_process)
        self.download_manger_disk.start()

    def share_call_downloader(self):
        _indexs = self.table_share.selectionModel().selection().indexes()
        indexs = []
        for i in _indexs:
            indexs.append(i.row())
        indexs = set(indexs)
        tasks = []
        isfolder = None
        isfile = None
        save_path = self.settings["path"]
        for index in indexs:
            name = self.model_share.item(index, 0).text()
            _info = self.share_file_infos["info"][name]
            isurl = (_info[0], _info[4])  # (url, size, date, desc, pwd)
            tasks.append([isfile, isfolder, isurl, name, save_path])
        self.download_manger_share = DownloadManger(self._disk, tasks, self)
        self.download_manger_share.download_mgr_msg.connect(self.show_download_process)
        self.download_manger_share.downloaders_msg.connect(self.show_download_process)
        self.download_manger_share.start()

    def menu_logout(self):
        self._disk.logout()
        self.toolbar.removeAction(self.logout)
        self.tabWidget.setCurrentIndex(0)
        self.disk_tab.setEnabled(False)
        self.upload_tab.setEnabled(False)
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
            if not username or not password:
                self.statusbar.showMessage("登录失败: 没有用户或密码", 3000)
                raise Exception("没有用户或密码")
            if self._disk.login(username, password) != LanZouCloud.SUCCESS:
                self.statusbar.showMessage("登录失败: 用户名或密码错误", 7000)
                raise Exception("登录失败")
            self.statusbar.showMessage("登录成功！", 8000)
            self.login_menu()

            self.tabWidget.insertTab(1, self.disk_tab, "我的蓝奏云")
            self.tabWidget.insertTab(2, self.upload_tab, "上传文件")
            self.disk_tab.setEnabled(True)
            self.upload_tab.setEnabled(True)
            # 设置当前显示 tab
            self.tabWidget.setCurrentIndex(1)
            # 刷新文件列表
            self._refresh(self._work_id)
            self.list_file_folder()
        except Exception as exp:
            self.tabWidget.setCurrentIndex(0)
            self.tabWidget.removeTab(2)
            self.tabWidget.removeTab(1)
            self.disk_tab.setEnabled(False)
            self.upload_tab.setEnabled(False)

    def set_file_icon(self, name):
        suffix = name.split(".")[-1]
        ico_path = "./icon/{}.gif".format(suffix)
        if os.path.isfile(ico_path):
            return QIcon(ico_path)
        else:
            return QIcon("./icon/zip.gif")

    def list_file_folder(self):
        """列出文件"""
        self.model_disk.removeRows(0, self.model_disk.rowCount())
        self.show_full_path()
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

        model.setHorizontalHeaderLabels(["文件名/夹", "大小", "时间", "ID", "下载数", "密码", "描述", "链接"])
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
        # 表格填充
        # table.horizontalHeader().setStretchLastSection(True)
        # table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
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
        self.left_menu_move = self.left_menus.addAction("移动")
        self.left_menu_move.setIcon(QIcon("./icon/move.ico"))
        self.left_menu_set_pwd = self.left_menus.addAction("设置访问密码")
        self.left_menu_set_pwd.setIcon(QIcon("./icon/password.ico"))


    def rename_set_desc(self, infos):
        """重命名"""
        name = infos[0][0]
        new_name = infos[0][1]
        desc = infos[1][0]
        new_desc = infos[1][1]
        if self._work_name == 'Recovery':
            print('ERROR : 回收站模式下无法使用此操作')
            return None
        fid = self._folder_list.get(name, None)[0]
        if fid is None:
            print('ERROR : 文件夹不存在:{}'.format(name))
        else:
            res = self._disk.rename_dir(fid, str(new_name), str(new_desc))
            if res == LanZouCloud.SUCCESS:
                self.statusbar.showMessage("修改成功！", 4000)
            elif res == LanZouCloud.FAILED:
                self.statusbar.showMessage("失败：文件夹id数大于7位 或者 网络错误！", 4000)
            self._refresh(self._work_id)
            self.list_file_folder()

    def set_passwd(self, infos):
        """设置文件(夹)提取码"""
        fid = infos[0]
        if not fid:
            print('ERROR : 文件(夹)不存在:{}'.format(infos[0]))
            return None
        new_pass = infos[1]
        if 2 <= len(new_pass) <= 6 or new_pass == "":
            res = self._disk.set_share_passwd(fid, new_pass)
            print(res)
            if res == LanZouCloud.SUCCESS:
                self.statusbar.showMessage("提取码变更成功！♬", 3000)
            else:
                self.statusbar.showMessage("提取码变更失败❀╳❀:{}".format(res), 4000)
            self._refresh(self._work_id)
            self.list_file_folder()
        else:
            self.statusbar.showMessage("提取码为2-6位字符,关闭请输入空！", 4000)

    def move_file(self, info):
        old_fid = info[0]
        new_fid = info[1]
        if self._disk.move_file(old_fid, new_fid) == LanZouCloud.SUCCESS:
            self._refresh(self._work_id)
            self.list_file_folder()
            self.statusbar.showMessage("{} 移动成功！".format(info[2]), 4000)
        else:
            self.statusbar.showMessage("移动文件{}失败！".format(info[2]), 4000)

    def generateMenu(self, pos):
        row_num = -1
        for i in self.sender().selectionModel().selection().indexes():
            row_num = i.row()
        _model = self.sender().model()
        # 通过 第二列 size 判断是文件还是文件夹，从而设置不同的显示菜单名
        if _model.item(row_num, 1).text():
            self.left_menu_rename_set_desc.setText("修改文件描述")
        else:
            self.left_menu_rename_set_desc.setText("修改文件夹名与描述")
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
            else:
                return

    def get_share_infomation(self, infos):
        """显示分享信息"""
        if self._work_name == "Recovery":
            print("ERROR : 回收站模式下无法使用此操作")
            return None
        # infos: 文件名，大小，日期，ID/url，下载次数(dl_count)，提取码(pwd)，描述(desc)，链接(share-url)
        _infos = infos[0:3]
        _infos.append(infos[4])
        if re.match(r"[\d]+", infos[3]):
            # 登录 文件信息
            if self._file_list.get(infos[0], None):
                # 下载直链
                d_url = self._disk.get_direct_url2(infos[3])
                _infos.append(infos[7])  # 分享链接
                _infos.append(infos[5] if infos[5] else "无")  # 提取码
                _infos.append("{}".format(d_url["direct_url"] or "无"))
            elif self._folder_list.get(infos[0], None):
                _infos.append(infos[7])  # 分享链接
                _infos.append(infos[5] if infos[5] else "无")  # 提取码
                _infos.append("无")
            else:
                print("ERROR : 文件(夹)不存在:{}".format(infos[0]))
        else:
            # 分享链接文件信息
            _infos.append(infos[7])  # share url
            d_url = self._disk.get_direct_url(infos[7], infos[5])
            _infos.append(infos[6] if infos[6] else "无")  # 提取码
            _infos.append("{}".format(d_url["direct_url"] or "无"))  # 下载直链

        info_dialog = InfoDialog(_infos)
        info_dialog.setWindowModality(Qt.ApplicationModal)
        info_dialog.exec()

    def chang_dir(self, dir_name):
        # 文件名
        dir_name = self.model_disk.item(dir_name.row(), 0).text()
        """切换工作目录"""
        if self._work_name == "Recovery" and dir_name not in [".", ".."]:
            print("ERROR : 回收站模式下仅支持 > cd ..")
            return None
        if dir_name == "..":  # 返回上级路径
            self._refresh(self._parent_id)
            self.list_file_folder()
        elif dir_name == ".":
            pass
        elif dir_name in self._folder_list.keys():
            folder_id = self._folder_list[dir_name][0]
            self._refresh(folder_id)
            self.list_file_folder()
        else:
            pass
            # print("ERROR : 该文件夹不存在: {}".format(dir_name))

    def show_full_path(self):
        """路径框显示当前路径"""
        if self._work_name == "/":
            self._full_path = "/"
        elif self._work_name != "/" and self._parent_name == "/":
            self._full_path = "/{}".format(self._work_name)
        else:
            text = "{}/{}".format(self._parent_name, self._work_name)
            self._full_path = self._full_path.split(self._parent_name)[0] + text
        self.line_location.setText(self._full_path)

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
        self.btn_share_dl.clicked.connect(self.share_call_downloader)
        self.btn_share_dl.setIcon(QIcon("./icon/downloader.ico"))
        self.btn_share_select_all.setIcon(QIcon("./icon/select-all.ico"))
        self.btn_share_select_all.clicked.connect(lambda: self.select_all_btn("share"))
        self.table_share.clicked.connect(lambda: self.select_all_btn("share", "cancel"))

        # 添加文件下载路径选择器
        self.line_dl_path = MyLineEdit(self.share_tab)
        self.line_dl_path.setObjectName("line_dl_path")
        self.horizontalLayout_share.insertWidget(2, self.line_dl_path)
        self.line_dl_path.setText(self.settings["path"])
        self.line_dl_path.clicked.connect(self.set_dl_path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    form = MainWindow()
    form.show()
    sys.exit(app.exec())
