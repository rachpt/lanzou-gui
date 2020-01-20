#!/usr/bin/env python3

import time
import sys
import os
import re
from time import sleep
from pickle import dump, load

from PyQt5.QtCore import Qt, QCoreApplication, QTimer, QUrl
from PyQt5.QtGui import QIcon, QStandardItem, QStandardItemModel, QDesktopServices
from PyQt5.QtWidgets import (QMainWindow, QApplication, QAbstractItemView, QHeaderView, QMenu, QAction, QLabel,
                             QPushButton, QFileDialog, QDesktopWidget)

from Ui_lanzou import Ui_MainWindow
from lanzou.api import LanZouCloud

from workers import Downloader, DownloadManager, GetSharedInfo, UploadWorker, LoginLuncher, DescFetcher
from dialogs import (update_settings, LoginDialog, UploadDialog, InfoDialog, RenameDialog,
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
    __version__ = 'v0.0.5'

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)
        self.init_variable()
        self.init_menu()
        self.setWindowTitle("蓝奏云客户端 - {}".format(self.__version__))
        self.setWindowIcon(QIcon("./icon/lanzou-logo2.png"))

        self.set_window_at_center()
        self.init_extract_share_ui()
        self.init_disk_ui()
        self.call_login_luncher()

        self.create_left_menus()

        # print(QApplication.style().objectName())
        self.setObjectName("MainWindow")

        self.setStyleSheet(qssStyle)
        # self.disk_tab.setStyleSheet("* {background-color: rgba(255, 255, 255, 150);}")
        self.tabWidget.setStyleSheet("QTabBar{ background-color: #AEEEEE; }")

    def init_menu(self):
        self.login.triggered.connect(self.show_login_dialog)  # 登录
        self.login.setIcon(QIcon("./icon/login.ico"))
        self.login.setShortcut("Ctrl+L")
        self.toolbar.addAction(self.login)
        self.logout.triggered.connect(self.call_logout)  # 登出
        self.logout.setIcon(QIcon("./icon/logout.ico"))
        self.logout.setShortcut("Ctrl+Q")    # 登出快捷键
        self.download.setShortcut("Ctrl+J")  # 以下还未使用
        self.download.setIcon(QIcon("./icon/download.ico"))
        self.delete.setShortcut("Ctrl+D")
        self.delete.setIcon(QIcon("./icon/delete.ico"))
        # self.how.setShortcut("Ctrl+H")
        self.how.setIcon(QIcon("./icon/help.ico"))
        self.how.triggered.connect(self.open_wiki_url)
        # self.about.setShortcut("Ctrl+O")
        self.about.setIcon(QIcon("./icon/about.ico"))
        self.about.triggered.connect(self.about_dialog.exec)
        self.upload.setIcon(QIcon("./icon/upload.ico"))
        self.upload.setShortcut("Ctrl+U")    # 上传快捷键

    def init_variable(self):
        self._disk = LanZouCloud()
        self._config = "./config.pkl"
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
        if os.name == 'nt':
            self._disk.set_rar_tool("./rar.exe")
        else:
            self._disk.set_rar_tool("/usr/bin/rar")
        # 登录器
        self.login_luncher = LoginLuncher(self._disk)
        self.login_luncher.code.connect(self.login_update_ui)
        # 下载器
        self.download_manager = DownloadManager(self._disk)
        self.download_manager.downloaders_msg.connect(self.show_status)
        self.download_manager.download_mgr_msg.connect(self.show_status)
        self.download_manager.finished.connect(lambda: self.self.show_status("所有下载任务已完成！", 7000))
        # 上传器，信号在登录更新界面设置
        self.upload_dialog = UploadDialog()
        self.upload_dialog.new_infos.connect(self.call_upload)
        # 文件描述更新器
        self.desc_fetcher = DescFetcher(self._disk)
        self.desc_fetcher.desc.connect(self.call_update_desc)
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
        self.rename_dialog.out.connect(self.rename_set_desc_and_mkdir)
        # 菜单栏关于
        self.about_dialog = AboutDialog()
        self.about_dialog.set_values(self.__version__)

    def show_login_dialog(self):
        """显示登录对话框"""
        login_dialog = LoginDialog(self._config)
        login_dialog.clicked_ok.connect(self.call_login_luncher)
        login_dialog.setWindowModality(Qt.ApplicationModal)
        login_dialog.exec()

    def show_upload_dialog(self):
        """显示上传文件对话框"""
        self.upload_dialog.set_values(list(self._path_list.keys())[-1])
        self.upload_dialog.exec()

    def load_settings(self):
        try:
            with open(self._config, "rb") as _file:
                self.settings = load(_file)
        except Exception:
            dl_path = os.path.dirname(os.path.abspath(__file__)) + os.sep + "downloads"
            self.settings = {"user": "", "pwd": "", "path": dl_path}
            with open(self._config, "wb") as _file:
                dump(self.settings, _file)

    def call_downloader(self):
        tab_page = self.tabWidget.currentIndex()
        if tab_page == 0:
            listview = self.table_share
            model = self.model_share
        elif tab_page == 1:
            listview = self.table_disk
            model = self.model_disk
        indexes = []
        tasks = []
        _indexes = listview.selectionModel().selection().indexes()
        for i in _indexes:  # 获取所选行号
            indexes.append(i.row())
        indexes = set(indexes)
        save_path = self.settings["path"]
        for index in indexes:
            infos = model.item(index, 0).data()
            if not infos:
                continue
            # 查询 分享链接 以及 提取码
            if infos[0]:  # 从 disk 运行
                if infos[2]:  # 文件
                    _info = self._disk.get_share_info(infos[0], is_file=True)
                else:  # 文件夹
                    _info = self._disk.get_share_info(infos[0], is_file=False)
                infos[5] = _info['pwd']  # 将bool值改成 字符串
                infos.append(_info['url'])
            tasks.append([infos[1], infos[7], infos[5], save_path])
        self.download_manager.set_values(tasks, 3)
        self.download_manager.start()

    def call_logout(self):
        """菜单栏、工具栏登出"""
        self._disk.logout()
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
        self.statusbar.showMessage("已经退出登录！", 4000)

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
            self.refresh_dir(self._work_id)
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
        self._disk.logout()
        self.toolbar.removeAction(self.logout)
        try:
            username = self.settings["user"]
            password = self.settings["pwd"]
            cookie = self.settings["cookie"]
            self.login_luncher.set_values(username, password, cookie)
            self.login_luncher.start()
        except Exception as exp:
            print(exp)
            pass

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
            self.model_disk.appendRow([name, size_, QStandardItem(infos[3])])
        for r in range(self.model_disk.rowCount()):  # 右对齐
            self.model_disk.item(r, 1).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.model_disk.item(r, 2).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def refresh_dir(self, folder_id=-1, r_files=True, r_folders=True, r_path=True):
        """更新目录列表，包括列表和路径指示器"""
        if r_files:
            info = {i['name']: [i['id'], i['name'], i['size'], i['time'], i['downs'], i['has_pwd'], i['has_des']]
                    for i in self._disk.get_file_list(folder_id)}
            self._file_list = {key: info.get(key) for key in sorted(info.keys())}  # {name-[id,...]}
        if r_folders:
            info = {i['name']: [i['id'], i['name'],  "", "", "", i['has_pwd'], i['desc']]
                    for i in self._disk.get_dir_list(folder_id)}
            self._folder_list = {key: info.get(key) for key in sorted(info.keys())}  # {name-[id,...]}
        self._path_list = self._disk.get_full_path(folder_id)
        current_folder = list(self._path_list.keys())[-1]
        self._work_id = self._path_list.get(current_folder, -1)
        if folder_id != -1:
            parent_folder_name = list(self._path_list.keys())[-2]
            self._parent_id = self._path_list.get(parent_folder_name, -1)
        self.show_file_and_folder_lists()
        if r_path:
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
        self.left_menu_share_url = self.left_menus.addAction("外链分享地址")
        self.left_menu_share_url.setIcon(QIcon("./icon/share.ico"))
        self.left_menu_rename_set_desc = self.left_menus.addAction("修改文件夹名与描述")
        self.left_menu_rename_set_desc.setIcon(QIcon("./icon/desc.ico"))
        self.left_menu_set_pwd = self.left_menus.addAction("设置访问密码")
        self.left_menu_set_pwd.setIcon(QIcon("./icon/password.ico"))
        self.left_menu_move = self.left_menus.addAction("移动")
        self.left_menu_move.setIcon(QIcon("./icon/move.ico"))

    def rename_set_desc_and_mkdir(self, infos):
        """重命名、修改简介与新建文件夹"""
        action = infos[0]
        fid = infos[1]
        new_name = infos[2]
        new_desc = infos[3]
        if not fid:  # 新建文件夹
            fid = self._work_id
            if new_name in self._folder_list.keys():
                self.statusbar.showMessage("文件夹已存在：{}".format(new_name), 7000)
            else:
                res = self._disk.mkdir(self._work_id, new_name, new_desc)
                if res == LanZouCloud.MKDIR_ERROR:
                    self.statusbar.showMessage("创建文件夹失败：{}".format(new_name), 7000)
                else:
                    sleep(1.5)  # 暂停一下，否则无法获取新建的文件夹
                    self.statusbar.showMessage("成功创建文件夹：{}".format(new_name), 7000)
                    # 此处仅更新文件夹，并显示
                    self.refresh_dir(self._work_id, False, True, False)
        else:  # 重命名、修改简介
            if action == "file":  # 修改文件描述
                res = self._disk.set_desc(fid, str(new_desc), is_file=True)
            else:  # 修改文件夹，action == "folder"
                _res = self._disk.get_share_info(fid, is_file=False)
                if _res['code'] == LanZouCloud.SUCCESS:
                    res = self._disk._set_dir_info(fid, str(new_name), str(new_desc))
                else:
                    res = _res['code']
            if res == LanZouCloud.SUCCESS:
                self.statusbar.showMessage("修改成功！", 4000)
            elif res == LanZouCloud.FAILED:
                self.statusbar.showMessage("失败：发生错误！", 4000)
            if action == "file":  # 只更新文件列表
                self.refresh_dir(self._work_id, r_files=True, r_folders=False, r_path=False)
            else:  # 只更新文件夹列表
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
                is_file = True
            else:
                is_file = False
            res = self._disk.set_passwd(fid, new_pass, is_file)
            if res == LanZouCloud.SUCCESS:
                self.statusbar.showMessage("提取码变更成功！♬", 3000)
            elif res == LanZouCloud.NETWORK_ERROR:
                self.statusbar.showMessage("网络错误，稍后重试！☒", 4000)
            else:
                self.statusbar.showMessage("提取码变更失败❀╳❀:{}".format(res), 4000)
            self.refresh_dir(self._work_id, r_files=is_file, r_folders=not is_file, r_path=False)
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
        self.rename_dialog.set_values(None)
        self.rename_dialog.exec()

    def remove_files(self, infos):
        if not infos:
            return
        for i in infos:
            if i[1]:
                is_file = True
            else:
                is_file = False
            self._disk.delete(i[0], is_file)
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
            info = self.model_disk.item(index, 0).data()  # 用于提示删除的文件名
            if info:
                infos.append(info[:3])
        delete_dialog = DeleteDialog(infos)
        delete_dialog.new_infos.connect(self.remove_files)
        delete_dialog.exec()

    def generateMenu(self, pos):
        """右键菜单"""
        row_num = self.sender().selectionModel().selection().indexes()
        if not row_num:  # 如果没有选中行，什么也不做
            return
        # row_num = row_num[0].row()
        _model = self.sender().model()
        infos = _model.item(row_num[0].row(), 0).data()
        if not infos:
            return
        # 通过是否有文件 ID 判断是登录界面还是提取界面
        if infos[0]:
            self.left_menu_rename_set_desc.setEnabled(True)
            self.left_menu_set_pwd.setEnabled(True)
            # 通过infos第3个字段 size 判断是否为文件夹，文件夹不能移动，设置不同的显示菜单名
            if infos[2]:
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
        infos = self.get_more_infomation(infos)  # 点击菜单项后更新信息
        if action == self.left_menu_share_url:
            info_dialog = InfoDialog(infos)
            info_dialog.setWindowModality(Qt.ApplicationModal)
            info_dialog.exec()
        elif action == self.left_menu_move:
            all_dirs_dict = self._disk.get_folder_id_list()
            move_file_dialog = MoveFileDialog(infos, all_dirs_dict)
            move_file_dialog.new_infos.connect(self.move_file)
            move_file_dialog.exec()
        elif action == self.left_menu_set_pwd:
            set_pwd_dialog = SetPwdDialog(infos)
            set_pwd_dialog.new_infos.connect(self.set_passwd)
            set_pwd_dialog.exec()
        elif action == self.left_menu_rename_set_desc:
            self.desc_fetcher.set_values(infos)
            self.desc_fetcher.start()  # 启动后台更新描述
            self.rename_dialog.set_values(infos)
            self.rename_dialog.exec()

    def call_update_desc(self, desc, infos):
        infos[6] = desc  # 更新 desc
        self.rename_dialog.set_values(infos)

    def get_more_infomation(self, infos):
        """获取文件直链、文件(夹)提取码描述"""
        if self._work_name == "Recovery":
            print("ERROR : 回收站模式下无法使用此操作")
            return None
        # infos: ID/None，文件名，大小，日期，下载次数(dl_count)，提取码(pwd)，描述(desc)，|链接(share-url)，直链
        if infos[0]:  # 从 disk 运行
            if infos[2]:  # 文件
                _info = self._disk.get_share_info(infos[0], is_file=True)
            else:  # 文件夹
                _info = self._disk.get_share_info(infos[0], is_file=False)
            infos[5] = _info['pwd']
            infos.append(_info['url'])
        if infos[2]:  # 文件
            res = self._disk.get_file_info_by_url(infos[-1], infos[5])
            if res["code"] == LanZouCloud.SUCCESS:
                infos.append("{}".format(res["durl"] or "无"))  # 下载直链
            elif res["code"] == LanZouCloud.NETWORK_ERROR:
                infos.append("网络错误！获取失败")  # 下载直链
            else:
                infos.append("其它错误！")  # 下载直链
        else:
            infos.append("无")  # 下载直链
        infos[5] = infos[5] or "无"  # 提取码
        return infos

    def chang_dir(self, dir_name):
        """双击切换工作目录"""
        dir_name = self.model_disk.item(dir_name.row(), 0).text()  # 文件夹名
        if self._work_name == "Recovery" and dir_name not in [".", ".."]:
            return None
        if dir_name == "..":  # 返回上级路径
            self.refresh_dir(self._parent_id)
        elif dir_name in self._folder_list.keys():
            folder_id = self._folder_list[dir_name][0]
            self.refresh_dir(folder_id)
        else:
            self.show_status("ERROR : 该文件夹不存在: {}".format(dir_name))

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
        for name, id in self._path_list.items():
            self._locs[index] = QPushButton(name, self.disk_tab)
            self._locs[index].setIcon(QIcon("./icon/folder.gif"))
            self._locs[index].setStyleSheet("QPushButton {border: none; background:transparent;}")
            self.disk_loc.insertWidget(index, self._locs[index])
            self._locs[index].clicked.connect(self.call_change_dir(id))
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
            self.refresh_dir(self._work_id, True, True, False)
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

        self.table_disk.doubleClicked.connect(self.chang_dir)
        # 上传器
        self.upload_worker = UploadWorker()
        self.upload_worker.finished.connect(self.finished_upload)
        self.upload_worker.code.connect(self.show_status)

    def show_status(self, msg, duration=0):
        self._msg_label.setText(msg)
        # self.statusbar.showMessage(msg, duration)
        QCoreApplication.processEvents()  # 重绘界面
        if duration != 0:
            QTimer.singleShot(duration, lambda: self._msg_label.setText(""))

    # shared url
    def call_get_shared_info_worker(self):
        line_share_text = self.line_share_url.text().strip()
        pat = r"(https?://(www\.)?lanzous.com/[bi][a-z0-9]+)[^0-9a-z]*([a-z0-9]+)?"
        for share_url, _, pwd in re.findall(pat, line_share_text):
            pass
        if self._disk.is_file_url(share_url):  # 链接为文件
            is_file = True
            is_folder = False
            self.show_status("正在获取文件链接信息……")
        elif self._disk.is_folder_url(share_url):  # 链接为文件夹
            is_folder = True
            is_file = False
            self.show_status("正在获取文件夹链接信息，可能需要几秒钟，请稍后……")
        else:
            self.show_status("{} 为非法链接！".format(share_url))
            self.btn_extract.setEnabled(True)
            self.line_share_url.setEnabled(True)
            return
        self.model_share.removeRows(0, self.model_share.rowCount())
        QCoreApplication.processEvents()  # 重绘界面

        self.get_shared_info_thread.set_values(self._disk, share_url, pwd, is_file, is_folder)
        self.get_shared_info_thread.start()

    def call_get_shared_info(self):
        if not self.get_shared_info_thread.isRunning():  # 防止阻塞主进程
            self.line_share_url.setEnabled(False)
            self.btn_extract.setEnabled(False)
            self.call_get_shared_info_worker()

    def show_share_url_file_lists(self, infos):
        if infos["code"] == LanZouCloud.SUCCESS:
            file_count = len(infos["info"].keys())
            self.model_share.setHorizontalHeaderLabels(["文件{}个".format(file_count), "大小", "时间"])
            for infos in infos["info"].values():
                name = QStandardItem(self.set_file_icon(infos[1]), infos[1])
                name.setData(infos)
                self.model_share.appendRow([name, QStandardItem(infos[2]), QStandardItem(infos[3])])
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

    def init_extract_share_ui(self):
        self.btn_share_select_all.setDisabled(True)
        self.btn_share_dl.setDisabled(True)
        self.table_share.setDisabled(True)
        self.model_share = QStandardItemModel(1, 3)
        self.config_tableview("share")
        self.get_shared_info_thread = GetSharedInfo()
        self.get_shared_info_thread.code.connect(self.show_status)  # 状态码
        self.get_shared_info_thread.infos.connect(self.show_share_url_file_lists)  # 信息
        self.get_shared_info_thread.finished.connect(lambda: self.btn_extract.setEnabled(True))
        self.get_shared_info_thread.finished.connect(lambda: self.line_share_url.setEnabled(True))
        self.line_share_url.setPlaceholderText("蓝奏云链接，如有提取码，放后面，空格或汉字等分割，回车键提取")
        self.line_share_url.returnPressed.connect(self.call_get_shared_info)
        self.btn_extract.clicked.connect(self.call_get_shared_info)
        self.btn_share_dl.clicked.connect(self.call_downloader)
        self.btn_share_dl.setIcon(QIcon("./icon/downloader.ico"))
        self.btn_share_select_all.setIcon(QIcon("./icon/select-all.ico"))
        self.btn_share_select_all.clicked.connect(lambda: self.select_all_btn("reverse"))
        self.table_share.clicked.connect(lambda: self.select_all_btn("cancel"))

        # 添加文件下载路径选择器
        self.line_dl_path = MyLineEdit(self.share_tab)
        self.line_dl_path.setObjectName("line_dl_path")
        self.horizontalLayout_share_2.insertWidget(2, self.line_dl_path)
        self.line_dl_path.setText(self.settings["path"])
        self.line_dl_path.clicked.connect(self.set_download_path)

        # QSS
        self.label_share_url.setStyleSheet("#label_share_url {color: rgb(255,255,60);}")
        self.label_dl_path.setStyleSheet("#label_dl_path {color: rgb(255,255,60);}")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_A:  # Ctrl/Alt + A 全选
            if e.modifiers() and Qt.ControlModifier:
                self.select_all_btn()

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
    sys.setrecursionlimit(1000000)
    app = QApplication(sys.argv)
    form = MainWindow()
    form.show()
    sys.exit(app.exec())
