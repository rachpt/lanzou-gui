#!/usr/bin/env python3

import sys
import os
from pickle import dump, load

from PyQt5.QtCore import Qt, QCoreApplication, QTimer, QUrl
from PyQt5.QtGui import QIcon, QStandardItem, QStandardItemModel, QDesktopServices
from PyQt5.QtWidgets import (QMainWindow, QApplication, QAbstractItemView, QHeaderView, QMenu, QAction, QLabel,
                             QPushButton, QFileDialog, QDesktopWidget)

from Ui_lanzou import Ui_MainWindow
from lanzou.api import LanZouCloud

from workers import (DownloadManager, GetSharedInfo, UploadWorker, LoginLuncher, DescPwdFetcher, ListRefresher,
                     RemoveFilesWorker, GetMoreInfoWorker, GetAllFoldersWorker, RenameMkdirWorker, SetPwdWorker, LogoutWorker)
from dialogs import (update_settings, LoginDialog, UploadDialog, InfoDialog, RenameDialog, SettingDialog,
                     SetPwdDialog, MoveFileDialog, DeleteDialog, MyLineEdit, AboutDialog)


qssStyle = '''
    QPushButton {
        background-color: rgba(255, 130, 71, 100);
    }
    #table_share {
        background-color: rgba(255, 255, 255, 150);
    }
    #disk_tab {
        background-color: rgba(255, 255, 255, 150);
    }
    #table_disk {
        background-color: rgba(255, 255, 255, 150);
    }
    #tableView_rec {
        background-color: rgba(255, 255, 255, 150);
    }
    QTabWidget::pane {
        border: 1px;
        /* background:transparent;  # 完全透明 */
        background-color: rgba(255, 255, 255, 100);
    }
    QTabWidget::tab-bar {
        background:transparent;
        subcontrol-position:center;
    }
    QTabBar::tab {
        min-width:120px;
        min-height:30px;
        background:transparent;
    }
    QTabBar::tab:selected {
        color: rgb(153, 50, 204);
        background:transparent;
        font-weight:bold;
    }
    QTabBar::tab:!selected {
        color: rgb(28, 28, 28);
        background:transparent;
    }
    QTabBar::tab:hover {
        color: rgb(0, 0, 205);
        background:transparent;
    }
    #MainWindow {
        border-image:url(./background.png);
    }
    #statusbar {
        font: 14px;
        color: white;
    }
    #msg_label {
        font: 14px;
        color: white;
        background:transparent;
    }
'''


class MainWindow(QMainWindow, Ui_MainWindow):
    __version__ = 'v0.0.8'

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)
        self.init_default_settings()
        self.init_variables()
        self.init_workers()
        self.init_menu()
        self.setWindowTitle("蓝奏云客户端 - {}".format(self.__version__))

        self.set_window_at_center()
        self.init_extract_share_ui()
        self.init_disk_ui()
        self.call_login_luncher()

        self.create_left_menus()

        self.setStyleSheet(qssStyle)
        self.tabWidget.setStyleSheet("QTabBar{ background-color: #AEEEEE; }")

    def init_menu(self):
        self.login.triggered.connect(self.show_login_dialog)  # 登录
        self.login.setIcon(QIcon("./icon/login.ico"))
        self.login.setShortcut("Ctrl+L")
        self.toolbar.addAction(self.login)
        self.logout.triggered.connect(lambda: self.logout_worker.set_values(self._disk))  # 登出
        self.logout.setIcon(QIcon("./icon/logout.ico"))
        self.logout.setShortcut("Ctrl+Q")    # 登出快捷键
        self.download.setShortcut("Ctrl+J")  # 以下还未使用
        self.download.setIcon(QIcon("./icon/download.ico"))
        self.download.setEnabled(False)  # 暂时不用
        self.delete.setShortcut("Ctrl+D")
        self.delete.setIcon(QIcon("./icon/delete.ico"))
        self.delete.setEnabled(False)  # 暂时不用
        # self.how.setShortcut("Ctrl+H")
        self.how.setIcon(QIcon("./icon/help.ico"))
        self.how.triggered.connect(self.open_wiki_url)
        # self.about.setShortcut("Ctrl+O")
        self.about.setIcon(QIcon("./icon/about.ico"))
        self.about.triggered.connect(self.about_dialog.exec)
        self.upload.setIcon(QIcon("./icon/upload.ico"))
        self.upload.setShortcut("Ctrl+U")  # 上传快捷键
        # 添加设置菜单，暂时放这里
        self.setting_menu = QAction(self)  # 设置菜单
        self.setting_menu.setObjectName("setting_menu")
        self.setting_menu.setText("设置")
        self.files.addAction(self.setting_menu)
        self.setting_menu.setIcon(QIcon("./icon/about.ico"))
        self.setting_menu.triggered.connect(self.setting_dialog.open_dialog)
        self.setting_menu.setShortcut("Ctrl+P")  # 设置快捷键

    def init_default_settings(self):
        """初始化默认设置"""
        if os.name == 'nt':
            rar_tool = "./rar.exe"
        else:
            rar_tool = "/usr/bin/rar"
        download_threads = 3   # 同时三个下载任务
        max_size = 100         # 单个文件大小上限 MB
        timeout = 5            # 每个请求的超时 s(不包含下载响应体的用时)
        guise_suffix = '.dll'  # 不支持的文件伪装后缀
        rar_part_name = 'abc'  # rar 分卷文件后缀 *.abc01.rar
        time_fmt = False       # 是否使用年月日时间格式
        dl_path = os.path.dirname(os.path.abspath(__file__)) + os.sep + "downloads"
        self._default_settings = {"rar_tool": rar_tool, "download_threads": download_threads,
                    "max_size": max_size, "guise_suffix": guise_suffix, "dl_path": dl_path,
                    "timeout": timeout, "rar_part_name": rar_part_name, "time_fmt": time_fmt}

    def init_variables(self):
        self._disk = LanZouCloud()
        self._config_file = "./config.pkl"
        self._folder_list = {}
        self._file_list = {}
        self._path_list = {}
        self._path_list_old = {}
        self._locs = {}
        self._parent_id = -1  # --> ..
        self._work_name = ""  # share disk rec, not use now
        self._work_id = -1    # disk folder id
        self._old_work_id = self._work_id  # 用于上传完成后判断是否需要更新disk界面
        self.load_settings()

    def update_lanzoucloud_settings(self):
        """更新LanzouCloud实例设置"""
        self._disk.set_rar_tool(self.configs["settings"]["rar_tool"])
        self._disk.set_guise_suffix(self.configs["settings"]["guise_suffix"])
        self._disk.set_rar_part_name(self.configs["settings"]["rar_part_name"])
        self._disk.set_timeout(self.configs["settings"]["timeout"])
        self._disk.set_max_size(self.configs["settings"]["max_size"])
        self.download_threads = self.configs["settings"]["download_threads"]
        self.time_fmt = self.configs["settings"]["time_fmt"]
        # self.time_fmt = True

    def init_workers(self):
        # 登录器
        self.login_luncher = LoginLuncher(self._disk)
        self.login_luncher.code.connect(self.login_update_ui)
        self.login_luncher.update_cookie.connect(self.call_update_cookie)
        # 登出器
        self.logout_worker = LogoutWorker()
        self.logout_worker.successed.connect(self.call_logout_update_ui)
        # 下载器
        self.download_manager = DownloadManager()
        self.download_manager.downloaders_msg.connect(self.show_status)
        self.download_manager.download_mgr_msg.connect(self.show_status)
        self.download_manager.finished.connect(lambda: self.show_status("所有下载任务已完成！", 7000))
        # 获取更多信息，直链、下载次数等
        self.more_info_worker = GetMoreInfoWorker()
        self.more_info_worker.msg.connect(self.show_status)
        self.more_info_worker.infos.connect(self.show_info_dialog)
        # 登录文件列表更新器
        self.list_refresher = ListRefresher(self._disk)
        self.list_refresher.err_msg.connect(self.show_status)
        self.list_refresher.infos.connect(self.update_lists)
        # 获取所有文件夹fid，并移动
        self.all_folders_worker = GetAllFoldersWorker()
        self.all_folders_worker.msg.connect(self.show_status)
        self.all_folders_worker.infos.connect(self.show_move_file_dialog)
        self.all_folders_worker.moved.connect(lambda: self.list_refresher.set_values(self._work_id, False, True, False)) # 更新文件列表
        # 重命名、修改简介、新建文件夹
        self.rename_mkdir_worker = RenameMkdirWorker()
        self.rename_mkdir_worker.msg.connect(self.show_status)
        self.rename_mkdir_worker.update.connect(self.list_refresher.set_values)  # 更新界面
        # 设置文件(夹)提取码
        self.set_pwd_worker = SetPwdWorker()
        self.set_pwd_worker.msg.connect(self.show_status)
        self.set_pwd_worker.update.connect(self.list_refresher.set_values)  # 更新界面
        # 删除文件(夹)
        self.remove_files_worker = RemoveFilesWorker(self._disk)
        self.remove_files_worker.msg.connect(self.show_status)  # 显示错误提示
        self.remove_files_worker.finished.connect(lambda: self.list_refresher.set_values(self._work_id))  # 更新界面
        # 上传器，信号在登录更新界面设置
        self.upload_dialog = UploadDialog()
        self.upload_dialog.new_infos.connect(self.call_upload)
        # 文件描述与提取码更新器
        self.desc_pwd_fetcher = DescPwdFetcher()
        self.desc_pwd_fetcher.desc.connect(self.call_update_desc_pwd)
        self.desc_pwd_fetcher.tasks.connect(self.call_download_manager_thread)  # 连接下载管理器线程
        # 设置 tab
        self.tabWidget.setCurrentIndex(0)
        self.tabWidget.removeTab(2)
        self.tabWidget.removeTab(1)
        self.disk_tab.setEnabled(False)
        self.rec_tab.setEnabled(False)
        # 状态栏
        self._msg_label = QLabel()
        self._msg_label.setObjectName("msg_label")
        self.statusbar.addWidget(self._msg_label)
        # 重命名、修改简介与新建文件夹对话框
        self.rename_dialog = RenameDialog()
        self.rename_dialog.out.connect(self.call_rename_mkdir_worker)
        # 修改设置 提取码对话框
        self.set_pwd_dialog = SetPwdDialog()
        self.set_pwd_dialog.new_infos.connect(self.set_passwd)
        # 菜单栏关于
        self.about_dialog = AboutDialog()
        self.about_dialog.set_values(self.__version__)
        # 菜单栏设置
        self.setting_dialog = SettingDialog(self._config_file, self._default_settings)
        self.setting_dialog.saved.connect(lambda: self.load_settings(ref_ui=True))

    def show_login_dialog(self):
        """显示登录对话框"""
        login_dialog = LoginDialog(self._config_file)
        login_dialog.clicked_ok.connect(self.call_login_luncher)
        login_dialog.setWindowModality(Qt.ApplicationModal)
        login_dialog.exec()

    def show_upload_dialog(self):
        """显示上传文件对话框"""
        self.upload_dialog.set_values(list(self._path_list.keys())[-1])
        self.upload_dialog.exec()

    def load_settings(self, ref_ui=False):
        """加载用户设置"""
        try:
            with open(self._config_file, "rb") as _file:
                self.configs = load(_file)
        except Exception:
            self.configs = {"user": "", "pwd": "", "cookie": "", "settings": self._default_settings}
            with open(self._config_file, "wb") as _file:
                dump(self.configs, _file)
        # 兼容以前的平配置文件
        if "settings" not in self.configs or not self.configs["settings"]:
            self.configs.update({"settings": self._default_settings})
            update_settings(self._config_file, {"settings": self._default_settings})
        self.update_lanzoucloud_settings()
        if ref_ui and self.tabWidget.currentIndex() == 1:  # 更新文件界面的时间
            self.show_file_and_folder_lists()

    def call_download_manager_thread(self, tasks):
        self.download_manager.set_values(tasks, self.configs["settings"]["dl_path"], self.download_threads)
        self.download_manager.start()

    def call_downloader(self):
        tab_page = self.tabWidget.currentIndex()
        if tab_page == 0:
            listview = self.table_share
            model = self.model_share
        elif tab_page == 1:
            listview = self.table_disk
            model = self.model_disk
        else:
            return
        infos = []
        _indexes = listview.selectionModel().selection().indexes()
        for i in _indexes:  # 获取所选行号
            info = model.item(i.row(), 0).data()
            if info and info not in infos:
                infos.append(info)
        if not infos:
            return
        self.desc_pwd_fetcher.set_values(self._disk, infos, download=True)

    def call_logout_update_ui(self):
        """菜单栏、工具栏登出"""
        self.toolbar.removeAction(self.logout)
        self.tabWidget.setCurrentIndex(0)
        self.disk_tab.setEnabled(False)
        self.rec_tab.setEnabled(False)
        self.tabWidget.removeTab(2)
        self.tabWidget.removeTab(1)
        self.toolbar.removeAction(self.logout)  # 登出工具
        self.logout.setEnabled(False)
        self.toolbar.removeAction(self.upload)  # 上传文件工具栏
        self.upload.setEnabled(False)
        self.upload.triggered.disconnect(self.show_upload_dialog)

    def login_update_ui(self, success, msg, duration):
        """根据登录是否成功更新UI"""
        if success:
            self.show_status(msg, duration)
            self.tabWidget.insertTab(1, self.disk_tab, "我的蓝奏云")
            self.tabWidget.insertTab(2, self.rec_tab, "回收站")
            self.disk_tab.setEnabled(True)
            self.rec_tab.setEnabled(True)
            # 更新快捷键与工具栏
            self.toolbar.addAction(self.logout)  # 添加登出工具栏
            self.toolbar.addAction(self.upload)  # 添加上传文件工具栏
            # 菜单栏槽
            self.logout.setEnabled(True)
            self.upload.setEnabled(True)
            self.upload.triggered.connect(self.show_upload_dialog)
            # 设置当前显示 tab
            self.tabWidget.setCurrentIndex(1)
            QCoreApplication.processEvents()  # 重绘界面
            # 刷新文件列表
            self.list_refresher.set_values(self._work_id)
        else:
            self.show_status(msg, duration)
            self.tabWidget.setCurrentIndex(0)
            self.tabWidget.removeTab(2)
            self.tabWidget.removeTab(1)
            self.disk_tab.setEnabled(False)
            self.rec_tab.setEnabled(False)
            # 更新快捷键与工具栏
            self.toolbar.removeAction(self.logout)  # 登出工具栏
            self.toolbar.removeAction(self.upload)  # 上传文件工具栏
            self.logout.setEnabled(False)
            self.upload.setEnabled(False)

    def call_login_luncher(self):
        """登录网盘"""
        self.load_settings()
        self.logout_worker.set_values(self._disk, update_ui=False)
        self.toolbar.removeAction(self.logout)
        try:
            username = self.configs["user"]
            password = self.configs["pwd"]
            cookie = self.configs["cookie"]
            self.login_luncher.set_values(username, password, cookie)
            self.login_luncher.start()
        except Exception as exp:
            print(exp)
            pass

    def call_update_cookie(self, cookie):
        """更新cookie至config文件"""
        up_info = {"cookie": cookie}
        update_settings(self._config_file, up_info)

    def set_file_icon(self, name):
        suffix = name.split(".")[-1]
        ico_path = "./icon/{}.gif".format(suffix)
        if os.path.isfile(ico_path):
            return QIcon(ico_path)
        else:
            return QIcon("./icon/file.ico")

    def show_file_and_folder_lists(self):
        """显示文件和文件夹列表"""
        self.model_disk.removeRows(0, self.model_disk.rowCount())  # 清理旧的内容
        file_count = len(self._file_list.keys())
        folder_count = len(self._folder_list.keys())
        name_header = ["文件夹{}个".format(folder_count), ] if folder_count else []
        if file_count:
            name_header.append("文件{}个".format(file_count))
        self.model_disk.setHorizontalHeaderLabels(["/".join(name_header), "大小", "时间"])
        folder_ico = QIcon("./icon/folder.gif")
        pwd_ico = QIcon("./icon/keys.ico")
        # infos: ID/None，文件名，大小，日期，下载次数(dl_count)，提取码(pwd)，描述(desc)，|链接(share-url)，直链
        if self._work_id != -1:
            _back = QStandardItem(folder_ico, "..")
            _back.setToolTip("双击返回上层文件夹，选中无效")
            self.model_disk.appendRow([_back, QStandardItem(""), QStandardItem("")])
        for infos in self._folder_list.values():  # 文件夹
            name = QStandardItem(folder_ico, infos[1])
            name.setData(infos)
            tips = ""
            if infos[5] is not False:
                tips = "有提取码"
                if infos[6] is not False:
                    tips = tips + "，描述：" + str(infos[6])
            elif infos[6] is not False:
                tips = "描述：" + str(infos[6])
            name.setToolTip(tips)
            size_ = QStandardItem(pwd_ico, "") if infos[5] else QStandardItem("")  # 提取码+size
            self.model_disk.appendRow([name, size_, QStandardItem("")])
        for infos in self._file_list.values():  # 文件
            name = QStandardItem(self.set_file_icon(infos[1]), infos[1])
            name.setData(infos)
            tips = ""
            if infos[5] is not False:
                tips = "有提取码"
                if infos[6] is not False:
                    tips = tips + "，描述：" + str(infos[6])
            elif infos[6] is not False:
                tips = "描述：" + str(infos[6])
            name.setToolTip(tips)
            size_ = QStandardItem(pwd_ico, infos[2]) if infos[5] else QStandardItem(infos[2])  # 提取码+size
            time_ = QStandardItem(LanZouCloud.time_format(infos[3])) if self.time_fmt else QStandardItem(infos[3])
            self.model_disk.appendRow([name, size_, time_])
        for row in range(self.model_disk.rowCount()):  # 右对齐
            self.model_disk.item(row, 1).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.model_disk.item(row, 2).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def update_lists(self, infos):
        if not infos:
            return
        if infos['r']['files']:
            self._file_list = infos['file_list']
        if infos['r']['folders']:
            self._folder_list = infos['folder_list']
        self._path_list = infos['path_list']

        current_folder = list(self._path_list.keys())[-1]
        self._work_id = self._path_list.get(current_folder, -1)
        if infos['r']['fid'] != -1:
            parent_folder_name = list(self._path_list.keys())[-2]
            self._parent_id = self._path_list.get(parent_folder_name, -1)
        self.show_file_and_folder_lists()
        if infos['r']['path']:
            self.show_full_path()

    def config_tableview(self, tab):
        if tab == "share":
            model = self.model_share
            table = self.table_share
        elif tab == "disk":
            model = self.model_disk
            table = self.table_disk

        model.setHorizontalHeaderLabels(["文件名", "大小", "时间"])
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
        table.horizontalHeader().setStyleSheet("QHeaderView::section{background:lightgray}")
        # 设置 不可选择单个单元格，只可选择一行。
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        # 设置第二三列的宽度
        table.horizontalHeader().resizeSection(1, 90)
        table.horizontalHeader().resizeSection(2, 80)
        # 设置第一列宽度自动调整，充满屏幕
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.setContextMenuPolicy(Qt.CustomContextMenu)  # 允许右键产生子菜单
        table.customContextMenuRequested.connect(self.generateMenu)  # 右键菜单

    def create_left_menus(self):
        self.left_menus = QMenu()
        self.left_menu_share_url = self.left_menus.addAction("外链分享地址等")
        self.left_menu_share_url.setIcon(QIcon("./icon/share.ico"))
        self.left_menu_rename_set_desc = self.left_menus.addAction("修改文件夹名与描述")
        self.left_menu_rename_set_desc.setIcon(QIcon("./icon/desc.ico"))
        self.left_menu_set_pwd = self.left_menus.addAction("设置访问密码")
        self.left_menu_set_pwd.setIcon(QIcon("./icon/password.ico"))
        self.left_menu_move = self.left_menus.addAction("移动（支持批量）")
        self.left_menu_move.setIcon(QIcon("./icon/move.ico"))

    def call_rename_mkdir_worker(self, infos):
        """重命名、修改简介与新建文件夹"""
        self.rename_mkdir_worker.set_values(self._disk, infos, self._work_id, self._folder_list)

    def set_passwd(self, infos):
        """设置文件(夹)提取码"""
        self.set_pwd_worker.set_values(self._disk, infos, self._work_id)

    def call_mkdir(self):
        """弹出新建文件夹对话框"""
        self.rename_dialog.set_values(None)
        self.rename_dialog.exec()

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
            info = self.model_disk.item(index, 0).data()  # 用于提示删除的文件名
            if info:
                infos.append(info[:3])
        delete_dialog = DeleteDialog(infos)
        delete_dialog.new_infos.connect(self.remove_files_worker.set_values)
        delete_dialog.exec()

    def generateMenu(self, pos):
        """右键菜单"""
        row_nums = self.sender().selectionModel().selection().indexes()
        if not row_nums:  # 如果没有选中行，什么也不做
            return
        _model = self.sender().model()
        infos = []  # 多个选中的行，用于移动文件与...
        for one_row in row_nums:
            one_row_data = _model.item(one_row.row(), 0).data()
            if one_row_data and one_row_data not in infos:  # 删掉 .. 行
                infos.append(one_row_data)
        if not infos:
            return
        info = infos[0]  # 取选中的第一行
        # 通过是否有文件 ID 判断是登录界面还是提取界面
        if info[0]:
            self.left_menu_rename_set_desc.setEnabled(True)
            self.left_menu_set_pwd.setEnabled(True)
            # 通过infos第3个字段 size 判断是否为文件夹，文件夹不能移动，设置不同的显示菜单名
            if info[2]:
                self.left_menu_rename_set_desc.setText("修改文件描述")
                self.left_menu_move.setEnabled(True)
            else:
                self.left_menu_rename_set_desc.setText("修改文件夹名与描述")
                self.left_menu_move.setDisabled(True)
        else:
            self.left_menu_rename_set_desc.setDisabled(True)
            self.left_menu_move.setDisabled(True)
            self.left_menu_set_pwd.setDisabled(True)

        action = self.left_menus.exec_(self.sender().mapToGlobal(pos))
        if action == self.left_menu_share_url:  # 显示详细信息
            # 后台跟新信息，并显示信息对话框
            self.more_info_worker.set_values(info, self._disk)
        elif action == self.left_menu_move:  # 移动文件
            self.all_folders_worker.set_values(self._disk, infos)
        elif action == self.left_menu_set_pwd:  # 修改提取码
            self.desc_pwd_fetcher.set_values(self._disk, [info,])  # 兼容下载器，使用列表的列表
            self.set_pwd_dialog.set_values(info)
            self.set_pwd_dialog.exec()
        elif action == self.left_menu_rename_set_desc:  # 重命名与修改描述
            self.desc_pwd_fetcher.set_values(self._disk, [info,])  # 兼容下载器，使用列表的列表
            self.rename_dialog.set_values(info)
            self.rename_dialog.exec()

    def call_update_desc_pwd(self, desc, pwd, infos):
        '''更新 desc、pwd'''
        infos[6] = desc
        infos[5] = pwd
        self.rename_dialog.set_values(infos)
        self.set_pwd_dialog.set_values(infos)

    def show_move_file_dialog(self, infos, all_dirs_dict):
        '''显示移动文件对话框'''
        move_file_dialog = MoveFileDialog(infos, all_dirs_dict)
        move_file_dialog.new_infos.connect(self.all_folders_worker.move_file)  # 调用移动线程
        move_file_dialog.exec()

    def show_info_dialog(self, infos):
        '''显示更多信息对话框'''
        info_dialog = InfoDialog(infos)
        info_dialog.setWindowModality(Qt.ApplicationModal)  # 窗口前置
        info_dialog.exec()

    def call_change_dir(self, folder_id=-1):
        """按钮调用"""
        def callfunc():
            self.list_refresher.set_values(folder_id)

        return callfunc

    def change_dir(self, dir_name):
        """双击切换工作目录"""
        dir_name = self.model_disk.item(dir_name.row(), 0).text()  # 文件夹名
        if dir_name == "..":  # 返回上级路径
            self.list_refresher.set_values(self._parent_id)
        elif dir_name in self._folder_list.keys():
            folder_id = self._folder_list[dir_name][0]
            self.list_refresher.set_values(folder_id)

    def call_upload(self, infos):
        """上传文件(夹)"""
        self._old_work_id = self._work_id  # 记录上传文件夹id
        self.upload_worker.set_values(self._disk, infos, self._old_work_id)
        self.upload_worker.start()

    def show_full_path(self):
        """路径框显示当前路径"""
        index = 1
        for name in self._path_list_old.items():
            self._locs[index].clicked.disconnect()
            self.disk_loc.removeWidget(self._locs[index])
            self._locs[index].deleteLater()
            self._locs[index] = None
            del self._locs[index]
            index += 1
        index = 1
        for name, fid in self._path_list.items():
            self._locs[index] = QPushButton(name, self.disk_tab)
            self._locs[index].setToolTip(f"fid:{fid}")
            self._locs[index].setIcon(QIcon("./icon/folder.gif"))
            self._locs[index].setStyleSheet("QPushButton {border: none; background:transparent;}")
            self.disk_loc.insertWidget(index, self._locs[index])
            self._locs[index].clicked.connect(self.call_change_dir(fid))
            index += 1
        self._path_list_old = self._path_list

    def select_all_btn(self, action="reverse"):
        """默认反转按钮状态"""
        page = self.tabWidget.currentIndex()
        if page == 0:
            btn = self.btn_share_select_all
            table = self.table_share
        elif page == 1:
            btn = self.btn_disk_select_all
            table = self.table_disk
        elif page == 2:
            return
        else:
            return
        if btn.isEnabled():
            if action == "reverse":
                if btn.text() == "全选":
                    table.selectAll()
                    btn.setText("取消")
                    btn.setIcon(QIcon("./icon/select-none.ico"))
                elif btn.text() == "取消":
                    table.clearSelection()
                    btn.setText("全选")
                    btn.setIcon(QIcon("./icon/select-all.ico"))
            elif action == "cancel":  # 点击列表其中一个就表示放弃全选
                btn.setText("全选")
                btn.setIcon(QIcon("./icon/select-all.ico"))
            else:
                table.selectAll()
                btn.setText("取消")
                btn.setIcon(QIcon("./icon/select-none.ico"))

    def finished_upload(self):
        """上传完成调用"""
        if self._old_work_id == self._work_id:
            self.list_refresher.set_values(self._work_id, True, True, False)
        else:
            self._old_work_id = self._work_id
        self.show_status("上传完成！", 7000)

    def init_disk_ui(self):
        self.model_disk = QStandardItemModel(1, 3)
        self.config_tableview("disk")
        self.btn_disk_delete.setIcon(QIcon("./icon/delete.ico"))
        self.btn_disk_dl.setIcon(QIcon("./icon/downloader.ico"))
        self.btn_disk_select_all.setIcon(QIcon("./icon/select-all.ico"))
        self.btn_disk_select_all.setToolTip("按下 Ctrl/Alt + A 全选或则取消全选")
        self.btn_disk_select_all.clicked.connect(lambda: self.select_all_btn("reverse"))
        self.table_disk.clicked.connect(lambda: self.select_all_btn("cancel"))
        self.btn_disk_dl.clicked.connect(self.call_downloader)
        self.btn_disk_mkdir.setIcon(QIcon("./icon/add-folder.ico"))
        self.btn_disk_mkdir.clicked.connect(self.call_mkdir)
        self.btn_disk_delete.clicked.connect(self.call_remove_files)

        self.table_disk.doubleClicked.connect(self.change_dir)
        # 上传器
        self.upload_worker = UploadWorker()
        self.upload_worker.finished.connect(self.finished_upload)
        self.upload_worker.code.connect(self.show_status)

    def show_status(self, msg, duration=0):
        self._msg_label.setText(msg)
        # self.statusbar.showMessage(msg, duration)
        # QCoreApplication.processEvents()  # 重绘界面，在弱网络情况导致程序闪退
        if duration != 0:
            QTimer.singleShot(duration, lambda: self._msg_label.setText(""))

    # shared url
    def call_get_shared_info(self):
        if not self.get_shared_info_thread.isRunning():  # 防止快速多次调用
            self.line_share_url.setEnabled(False)
            self.btn_extract.setEnabled(False)
            text = self.line_share_url.text().strip()
            self.get_shared_info_thread.set_values(text)

    def show_share_url_file_lists(self, infos):
        if infos["code"] == LanZouCloud.SUCCESS:
            file_count = len(infos["info"].keys())
            self.model_share.setHorizontalHeaderLabels(["文件{}个".format(file_count), "大小", "时间"])
            for infos in infos["info"].values():
                name = QStandardItem(self.set_file_icon(infos[1]), infos[1])
                name.setData(infos)
                time = QStandardItem(LanZouCloud.time_format(infos[3])) if self.time_fmt else QStandardItem(infos[3])
                self.model_share.appendRow([name, QStandardItem(infos[2]), time])
            for r in range(self.model_share.rowCount()):  # 右对齐
                self.model_share.item(r, 1).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.model_share.item(r, 2).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table_share.setDisabled(False)
            self.btn_share_select_all.setDisabled(False)
            self.btn_share_select_all.setToolTip("按下 Ctrl/Alt + A 全选或则取消全选")
            self.btn_share_dl.setDisabled(False)
        else:
            self.btn_share_select_all.setDisabled(True)
            self.btn_share_select_all.setToolTip("")
            self.btn_share_dl.setDisabled(True)
            self.table_share.setDisabled(True)

    def set_download_path(self):
        """设置下载路径"""
        dl_path = QFileDialog.getExistingDirectory()
        dl_path = os.path.normpath(dl_path)  # windows backslash
        if dl_path == self.configs["settings"]["dl_path"] or dl_path == ".":
            return
        if dl_path == "":
            dl_path = os.path.dirname(os.path.abspath(__file__)) + os.sep + "downloads"
            up_info = {"dl_path": dl_path}
        else:
            up_info = {"dl_path": dl_path}
        update_settings(self._config_file, up_info, is_settings=True)
        self.load_settings()
        self.line_dl_path.setText(self.configs["settings"]["dl_path"])

    def init_extract_share_ui(self):
        self.btn_share_select_all.setDisabled(True)
        self.btn_share_dl.setDisabled(True)
        self.table_share.setDisabled(True)
        self.model_share = QStandardItemModel(1, 3)
        self.config_tableview("share")
        # 获取分享链接信息线程
        self.get_shared_info_thread = GetSharedInfo()
        self.get_shared_info_thread.update.connect(lambda: self.model_share.removeRows(0, self.model_share.rowCount()))  # 清理旧的信息
        self.get_shared_info_thread.msg.connect(self.show_status)  # 提示信息
        self.get_shared_info_thread.infos.connect(self.show_share_url_file_lists)  # 内容信息
        self.get_shared_info_thread.finished.connect(lambda: self.btn_extract.setEnabled(True))
        self.get_shared_info_thread.finished.connect(lambda: self.line_share_url.setEnabled(True))
        # 控件设置
        self.line_share_url.setPlaceholderText("蓝奏云链接，如有提取码，放后面，空格或汉字等分割，回车键提取")
        self.line_share_url.returnPressed.connect(self.call_get_shared_info)
        self.btn_extract.clicked.connect(self.call_get_shared_info)
        self.btn_share_dl.clicked.connect(self.call_downloader)
        self.btn_share_dl.setIcon(QIcon("./icon/downloader.ico"))
        self.btn_share_select_all.setIcon(QIcon("./icon/select-all.ico"))
        self.btn_share_select_all.clicked.connect(lambda: self.select_all_btn("reverse"))
        self.table_share.clicked.connect(lambda: self.select_all_btn("cancel"))  # 全选按钮

        # 添加文件下载路径选择器
        self.line_dl_path = MyLineEdit(self.share_tab)
        self.line_dl_path.setObjectName("line_dl_path")
        self.horizontalLayout_share_2.insertWidget(2, self.line_dl_path)
        self.line_dl_path.setText(self.configs["settings"]["dl_path"])
        self.line_dl_path.clicked.connect(self.set_download_path)

        # QSS
        self.label_share_url.setStyleSheet("#label_share_url {color: rgb(255,255,60);}")
        self.label_dl_path.setStyleSheet("#label_dl_path {color: rgb(255,255,60);}")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_A:  # Ctrl/Alt + A 全选
            if e.modifiers() and Qt.ControlModifier:
                self.select_all_btn()
        elif e.key() == Qt.Key_F5:  # 刷新
            if self.tabWidget.currentIndex() == 1:  # disk 界面
                self.show_status("正在更新当前目录...", 1000)
                self.list_refresher.set_values(self._work_id)

    def set_window_at_center(self):
        screen = QDesktopWidget().screenGeometry()
        size = self.geometry()
        new_left = int((screen.width() - size.width()) / 2)
        new_top = int((screen.height() - size.height()) / 2)
        self.move(new_left, new_top)

    def open_wiki_url(self):
        # 打开使用说明页面
        url = QUrl('https://github.com/rachpt/lanzou-gui/wiki')
        if not QDesktopServices.openUrl(url):
            self.show_status('Could not open wiki page!', 5000)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("./icon/lanzou-logo2.png"))
    form = MainWindow()
    form.show()
    sys.exit(app.exec())
