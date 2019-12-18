#!/usr/bin/env python3

import sys
import os
import re
from time import sleep
from configparser import ConfigParser
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from Ui_lanzou import Ui_MainWindow

from lanzou import LanZouCloud

from downloader import Downloader


class LoginDialog(QDialog):
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
            self._user = self._config.get("login", "username")
            self._pwd = self._config.get("login", "password")
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
        self._config.set("login", "username", self._user)
        self._config.set("login", "password", self._pwd)
        self._config.write(open("config.ini", "w", encoding="utf-8"))
        self.close()


class MainWindow(QMainWindow, Ui_MainWindow, QThread):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)
        self.init_variable()
        self.setWindowTitle("蓝奏云客户端")
        self.setWindowIcon(QIcon("./icon/lanzou-logo2.png"))

        self.center()
        self.extract_share_ui()
        self.disk_ui()
        self.autologin_dialog()

        self.btn_disk_dl.clicked.connect(self.call_downloader)
        self.table_disk.doubleClicked.connect(self.chang_dir)
        self.downloader.download_proc.connect(self.show_download_process)
        self.login.triggered.connect(self.login_dialog.show)
        self.logout.triggered.connect(self.menu_logout)
        self.login.setShortcut("Ctrl+L")
        self.login.setIcon(QIcon("./icon/login.ico"))
        self.logout.setIcon(QIcon("./icon/logout.ico"))
        self.logout.setShortcut("Ctrl+Q")
        self.toolbar.addAction(self.login)
        self.toolbar.addAction(self.logout)

        self.login_dialog.btn_ok.clicked.connect(self.autologin_dialog)

    def init_variable(self):
        self._disk = LanZouCloud()
        self._config = ConfigParser()
        self._config.read("config.ini", encoding="utf-8")
        self._folder_list = {}
        self._file_list = {}
        self._path_list = {}
        self._parent_id = -1
        self._parent_name = ""
        self._work_name = ""
        self._work_id = -1
        self._full_path = ""
        self._stopped = True
        self._mutex = QMutex()
        self.login_dialog = LoginDialog(self._config)
        self.downloader = Downloader(self._disk)

    def _refresh(self, dir_id=-1):
        """刷新当前文件夹和路径信息"""
        self._file_list = self._disk.get_file_list2(dir_id)  # {name-id}
        self._folder_list = self._disk.get_dir_list(dir_id)
        self._path_list = self._disk.get_full_path(dir_id)
        self._work_name = list(self._path_list.keys())[-1]
        self._work_id = self._path_list.get(self._work_name, -1)
        if dir_id != -1:
            self._parent_name = list(self._path_list.keys())[-2]
            self._parent_id = self._path_list.get(self._parent_name, -1)

    def show_download_process(self, msg):
        self.statusbar.showMessage(str(msg), 8000)

    def call_downloader(self, name):
        _indexs = self.table_disk.selectionModel().selection().indexes()
        name = self.model_disk.item(_indexs[0].row(), 0).text()
        self.statusbar.showMessage("准备下载：{}".format(name), 0)
        save_path = self._config.get("path", "save_path")
        isfolder = self._folder_list.get(name, None)
        isfile = self._file_list.get(name, None)
        self.downloader.setVal(isfile, isfolder, save_path)

    def menu_logout(self):
        self._disk.logout()
        self.tabWidget.setCurrentIndex(0)
        self.disk_tab.setEnabled(False)
        self.upload_tab.setEnabled(False)
        self.tabWidget.removeTab(2)
        self.tabWidget.removeTab(1)
        self.statusbar.showMessage("已经退出登录！", 5000)

    def autologin_dialog(self):
        """登录网盘"""
        self._disk.logout()
        try:
            username = self._config.get("login", "username")
            password = self._config.get("login", "password")
            if not username or not password:
                self.statusbar.showMessage("登录失败: 没有用户或密码", 3000)
                raise Exception("没有用户或密码")
            if self._disk.login(username, password) != LanZouCloud.SUCCESS:
                self.statusbar.showMessage("登录失败: 用户名或密码错误", 7000)
                raise Exception("登录失败")
            self.statusbar.showMessage("登录成功！", 5000)

            self.tabWidget.insertTab(1, self.disk_tab, "我的蓝奏云")
            self.tabWidget.insertTab(2, self.upload_tab, "上传文件")
            self.disk_tab.setEnabled(True)
            self.upload_tab.setEnabled(True)
            # 设置当前显示 tab
            self.tabWidget.setCurrentIndex(1)
            # 刷新文件列表
            self._refresh(self._work_id)
            self.show_file()
        except Exception:
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
        if self._work_id != -1:
            self.model_disk.appendRow(
                [QStandardItem(folder_ico, ".."), QStandardItem(""), QStandardItem("")]
            )
        for folder, _ in self._folder_list.items():
            self.model_disk.appendRow(
                [
                    QStandardItem(folder_ico, folder),
                    QStandardItem(""),
                    QStandardItem(""),
                ]
            )
        for file_name, f_info in self._file_list.items():
            self.model_disk.appendRow(
                [
                    QStandardItem(self.set_file_icon(file_name), file_name),
                    QStandardItem("{}".format(f_info[1])),
                    QStandardItem("{}".format(f_info[2])),
                ]
            )

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

        model.setHorizontalHeaderLabels(["文件名/夹", "大小", "时间"])
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
        table.horizontalHeader().resizeSection(1, 60)
        table.horizontalHeader().resizeSection(2, 80)
        # 设置第一列宽度自动调整，充满屏幕
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        # 表格填充
        # table.horizontalHeader().setStretchLastSection(True)
        # table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def show_file(self):
        self.list_file_folder()

    def chang_dir(self, dir_name):
        # 文件名
        dir_name = self.model_disk.item(dir_name.row(), 0).text()
        """切换工作目录"""
        if self._work_name == "Recovery" and dir_name not in [".", ".."]:
            print("ERROR : 回收站模式下仅支持 > cd ..")
            return None
        if dir_name == "..":  # 返回上级路径
            self._refresh(self._parent_id)
            self.show_file()
        elif dir_name == ".":
            pass
        elif dir_name in self._folder_list.keys():
            folder_id = self._folder_list[dir_name]
            self._refresh(folder_id)
            self.show_file()
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

    def disk_ui(self):
        self.model_disk = QStandardItemModel(1, 3)
        self.config_tableview("disk")
        self.btn_disk_delect.setIcon(QIcon("./icon/delete.png"))

    def _down_by_url(self, url):
        """通过url下载"""
        save_path = self._config.get("path", "save_path")
        if self._disk.is_file_url(url):
            code = self._disk.download_file(url, "", save_path, self._show_progress)
            if code == LanZouCloud.LACK_PASSWORD:
                pwd = input("输入该文件的提取码 : ") or ""
                code2 = self._disk.download_file(
                    url, str(pwd), save_path, self._show_progress
                )
                self._print_error(code2)
            else:
                self._print_error(code)
        elif self._disk.is_folder_url(url):
            code = self._disk.download_dir(url, "", save_path, self._show_progress)
            if code == LanZouCloud.LACK_PASSWORD:
                pwd = input("输入该文件夹的提取码 : ") or ""
                code2 = self._disk.download_dir(
                    url, str(pwd), save_path, self._show_progress
                )
                self._print_error(code2)
            else:
                self._print_error(code)
        else:
            print("ERROR : 该链接无效")

    def list_share_url_file(self):
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

        if self._disk.is_file_url(share_url):
            file_infos = self._disk.get_share_file_info(share_url, pwd)
        elif self._disk.is_folder_url(share_url):
            file_infos = self._disk.get_share_folder_info(share_url, pwd)
        else:
            self.statusbar.showMessage("{} 为非法链接！".format(share_url), 0)
            return
        self.model_share.removeRows(0, self.model_share.rowCount())
        if file_infos["code"] == LanZouCloud.FILE_CANCELLED:
            self.statusbar.showMessage("文件不存在！", 0)
        elif file_infos["code"] == LanZouCloud.URL_INVALID:
            self.statusbar.showMessage("链接非法！", 0)
        elif file_infos["code"] == LanZouCloud.PASSWORD_ERROR:
            self.statusbar.showMessage("提取码 [{}] 错误！".format(pwd), 0)
        elif file_infos["code"] == LanZouCloud.LACK_PASSWORD:
            self.statusbar.showMessage("请在链接后面跟上提取码，空格分割！", 0)
        elif file_infos["code"] == LanZouCloud.FAILED:
            self.statusbar.showMessage("网络错误！", 0)
        elif file_infos["code"] == LanZouCloud.SUCCESS:
            self.statusbar.showMessage("提取信息成功！", 0)
            for key, infos in file_infos["info"].items():
                self.model_share.appendRow(
                    [
                        QStandardItem(self.set_file_icon(key), key),
                        QStandardItem(infos[1]),
                        QStandardItem(infos[2]),
                    ]
                )

    def extract_share_ui(self):
        self.model_share = QStandardItemModel(1, 3)
        self.config_tableview("share")
        self.line_share_url.setPlaceholderText("蓝奏云链接，如有提取码，放后面，空格或汉字等分割，回车键提取")
        self.line_share_url.returnPressed.connect(self.list_share_url_file)
        self.btn_extract.clicked.connect(self.list_share_url_file)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    form = MainWindow()
    form.show()
    sys.exit(app.exec())
