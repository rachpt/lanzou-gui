#!/usr/bin/env python3

import sys
import os
import re
from pickle import dump, load

from PyQt5.QtCore import Qt, QCoreApplication, QTimer, QUrl, QSize, QRectF
from PyQt5.QtGui import (QIcon, QStandardItem, QStandardItemModel, QDesktopServices, QMovie, QTextDocument,
                         QAbstractTextDocumentLayout, QPalette)
from PyQt5.QtWidgets import (QMainWindow, QApplication, QAbstractItemView, QHeaderView, QMenu, QAction, QLabel,
                             QPushButton, QFileDialog, QDesktopWidget, QMessageBox, QSystemTrayIcon, QStyle,
                             QStyledItemDelegate, QStyleOptionViewItem)

from Ui_lanzou import Ui_MainWindow
from lanzou.api import LanZouCloud
from lanzou.api.utils import time_format
from lanzou.api.models import FolderList
from lanzou.api.types import RecFolder

from workers import (DownloadManager, GetSharedInfo, UploadWorker, LoginLuncher, DescPwdFetcher, ListRefresher,
                     GetRecListsWorker, RemoveFilesWorker, GetMoreInfoWorker, GetAllFoldersWorker, RenameMkdirWorker,
                     SetPwdWorker, LogoutWorker, RecManipulator, CheckUpdateWorker)
from dialogs import (update_settings, set_file_icon, btn_style, LoginDialog, UploadDialog, InfoDialog, RenameDialog, 
                     SettingDialog, RecFolderDialog, SetPwdDialog, MoveFileDialog, DeleteDialog, MyLineEdit,
                     AboutDialog)


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
    #table_rec {
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
        border-image:url(./src/default_background_img.jpg);
    }
    #statusbar {
        font: 14px;
        color: white;
    }
    #msg_label, #msg_movie_lb {
        font: 14px;
        color: white;
        background:transparent;
    }
'''


class TableDelegate(QStyledItemDelegate):
    """Table 富文本"""
    def __init__(self, parent=None):
        super(TableDelegate, self).__init__(parent)
        self.doc = QTextDocument(self)

    def paint(self, painter, option, index):
        painter.save()
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        self.doc.setHtml(options.text)
        options.text = ""  # 原字符
        style = QApplication.style() if options.widget is None else options.widget.style()
        style.drawControl(QStyle.CE_ItemViewItem, options, painter)

        ctx = QAbstractTextDocumentLayout.PaintContext()

        if option.state & QStyle.State_Selected:
            ctx.palette.setColor(QPalette.Text, option.palette.color(
                QPalette.Active, QPalette.HighlightedText))
        else:
            ctx.palette.setColor(QPalette.Text, option.palette.color(
                QPalette.Active, QPalette.Text))

        text_rect = style.subElementRect(QStyle.SE_ItemViewItemText, options)

        the_fuck_your_shit_up_constant = 3  # ￣へ￣ #
        margin = (option.rect.height() - options.fontMetrics.height()) // 2
        margin = margin - the_fuck_your_shit_up_constant
        text_rect.setTop(text_rect.top() + margin)

        painter.translate(text_rect.topLeft())
        painter.setClipRect(text_rect.translated(-text_rect.topLeft()))
        self.doc.documentLayout().draw(painter, ctx)

        painter.restore()

    def sizeHint(self, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        self.doc.setHtml(options.text)
        self.doc.setTextWidth(options.rect.width())
        return QSize(self.doc.idealWidth(), self.doc.size().height())


class MainWindow(QMainWindow, Ui_MainWindow):
    __version__ = 'v0.2.2'
    if not os.path.isdir("./src") or not os.path.isfile("./src/file.ico"):
        from src import release_src

        os.makedirs("./src", exist_ok=True)
        release_src()

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
        self.init_rec_ui()
        self.call_login_luncher()
        self.create_left_menus()

        self.setStyleSheet(qssStyle)
        self.tabWidget.setStyleSheet("QTabBar{ background-color: #AEEEEE; }")
        self.check_update_worker.set_values(self.__version__, False)  # 检测新版
        self.clipboard_listener()  # 系统粘贴板

    def create_tray(self):
        """创建 系统托盘"""
        if not self._created_tray:
            self.tray = QSystemTrayIcon(QIcon('src/lanzou_logo2.png'), parent=self)
            show_action = QAction("显示窗口", self)
            hide_action = QAction("最小化到托盘", self)
            quit_action = QAction("退出程序", self)
            show_action.triggered.connect(self.show)
            hide_action.triggered.connect(self.hide)
            quit_action.triggered.connect(self.Exit)
            show_action.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
            hide_action.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMinButton))
            quit_action.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
            self.tray.activated[QSystemTrayIcon.ActivationReason].connect(self.icon_activated)  #托盘点击事件
            tray_menu = QMenu(QApplication.desktop())
            tray_menu.addAction(show_action)
            tray_menu.addAction(hide_action)
            tray_menu.addAction(quit_action)
            self.tray.setContextMenu(tray_menu)
            tip_title = f"蓝奏云客户端 <{self._user}>" if self._user else "蓝奏云客户端"
            self.tray.setToolTip(f"{tip_title}\n双击到托盘")
            self.tray.show()
            self._created_tray = True

    def icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            tip_title = f"蓝奏云客户端 <{self._user}>" if self._user else "蓝奏云客户端"
            if self.isHidden():
                self.show()
                self.tray.setToolTip(f"{tip_title}\n双击到托盘")
            else:
                self.hide()
                self.tray.setToolTip(f"{tip_title}\n双击显示")

    def init_menu(self):
        self.login.triggered.connect(self.show_login_dialog)  # 登录
        self.login.setIcon(QIcon("./src/login.ico"))
        self.login.setShortcut("Ctrl+L")
        self.toolbar.addAction(self.login)
        self.logout.triggered.connect(lambda: self.logout_worker.set_values(self._disk))  # 登出
        self.logout.setIcon(QIcon("./src/logout.ico"))
        self.logout.setShortcut("Ctrl+Q")    # 登出快捷键
        self.download.setShortcut("Ctrl+J")
        self.download.setIcon(QIcon("./src/download.ico"))
        self.download.setEnabled(False)  # 暂时不用
        self.delete.setShortcut("Ctrl+D")
        self.delete.setIcon(QIcon("./src/delete.ico"))
        self.delete.setEnabled(False)  # 暂时不用
        self.how.setShortcut("F1")
        self.how.setIcon(QIcon("./src/help.ico"))
        self.how.triggered.connect(self.open_wiki_url)
        self.about.setShortcut("Ctrl+B")
        self.about.setIcon(QIcon("./src/about.ico"))
        self.about.triggered.connect(self.about_dialog.exec)
        self.upload.setIcon(QIcon("./src/upload.ico"))
        self.upload.setShortcut("Ctrl+U")  # 上传快捷键
        # 添加设置菜单，暂时放这里
        self.setting_menu = QAction(self)  # 设置菜单
        self.setting_menu.setObjectName("setting_menu")
        self.setting_menu.setText("设置")
        self.files.addAction(self.setting_menu)
        self.setting_menu.setIcon(QIcon("./src/settings.ico"))
        self.setting_menu.triggered.connect(lambda: self.setting_dialog.open_dialog(self._user))
        self.setting_menu.setShortcut("Ctrl+P")  # 设置快捷键
        # tab 切换时更新
        self.tabWidget.currentChanged.connect(self.call_change_tab)

    def init_default_settings(self):
        """初始化默认设置"""
        download_threads = 3           # 同时三个下载任务
        max_size = 100                 # 单个文件大小上限 MB
        timeout = 5                    # 每个请求的超时 s(不包含下载响应体的用时)
        time_fmt = False               # 是否使用年月日时间格式
        to_tray = False                # 关闭到系统托盘
        watch_clipboard = False        # 监听系统剪切板
        dl_path = os.path.dirname(os.path.abspath(__file__)) + os.sep + "downloads"
        self._default_settings = {"download_threads": download_threads, "max_size": max_size, "to_tray": to_tray,
                                  "dl_path": dl_path, "timeout": timeout, "time_fmt": time_fmt, "watch_clipboard": watch_clipboard}

    def init_variables(self):
        self._disk = LanZouCloud()
        self._config_file = "./config.pkl"
        self._user = None    # 当前登录用户名
        self._folder_list = {}
        self._file_list = {}
        self._path_list = FolderList()
        self._path_list_old = FolderList()
        self._locs = {}
        self._parent_id = -1  # --> ..
        self._work_name = ""  # share disk rec, not use now
        self._work_id = -1    # disk folder id
        self._old_work_id = self._work_id  # 用于上传完成后判断是否需要更新disk界面
        self._show_to_tray_msg = True
        self._created_tray = False
        self.load_settings()

    def update_lanzoucloud_settings(self):
        """更新LanzouCloud实例设置"""
        self._disk.set_timeout(self.configs["settings"]["timeout"])
        self._disk.set_max_size(self.configs["settings"]["max_size"])
        self.download_threads = self.configs["settings"]["download_threads"]
        self.time_fmt = self.configs["settings"]["time_fmt"]  # 时间显示格式
        self.to_tray = self.configs["settings"]["to_tray"] if "to_tray" in self.configs["settings"] else False
        self.watch_clipboard = self.configs["settings"]["watch_clipboard"] if "watch_clipboard" in self.configs["settings"] else False
        if self.to_tray:
            self.create_tray()
        elif self._created_tray:
            self.tray.hide()
            del self.tray
            self._created_tray = False

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
        self.download_manager.finished.connect(lambda: self.show_status("所有下载任务已完成！", 2999))
        # 获取更多信息，直链、下载次数等
        self.info_dialog = InfoDialog()  # 对话框
        self.info_dialog.setWindowModality(Qt.ApplicationModal)  # 窗口前置
        self.more_info_worker = GetMoreInfoWorker()  # 后台更新线程
        self.more_info_worker.msg.connect(self.show_status)
        self.more_info_worker.infos.connect(self.info_dialog.set_values)
        self.more_info_worker.dl_link.connect(self.info_dialog.tx_dl_link.setText)
        self.info_dialog.get_dl_link.connect(self.more_info_worker.get_dl_link)
        # 登录文件列表更新器
        self.list_refresher = ListRefresher(self._disk)
        self.list_refresher.err_msg.connect(self.show_status)
        self.list_refresher.infos.connect(self.update_disk_lists)
        self.list_refresher.infos.connect(lambda: self.show_status(""))
        # 获取所有文件夹fid，并移动
        self.all_folders_worker = GetAllFoldersWorker()
        self.all_folders_worker.msg.connect(self.show_status)
        self.all_folders_worker.infos.connect(self.show_move_file_dialog)
        self.all_folders_worker.moved.connect(self.on_moved) # 更新文件列表
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
        self._msg_movie_lb = QLabel()
        self._msg_movie = QMovie("src/loading_more.gif")
        self._msg_movie.setScaledSize(QSize(24,24))
        self._msg_movie_lb.setMovie(self._msg_movie)
        self._msg_label.setObjectName("msg_label")
        self._msg_movie_lb.setObjectName("msg_movie_lb")
        self.statusbar.addWidget(self._msg_movie_lb)
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
        # 登录回收站信息更新器
        self.get_rec_lists_worker = GetRecListsWorker(self._disk)
        self.get_rec_lists_worker.msg.connect(self.show_status)
        self.get_rec_lists_worker.infos.connect(self.update_rec_lists)
        self.get_rec_lists_worker.folders.connect(lambda: self.show_status('', 0))
        self.get_rec_lists_worker.folders.connect(self.pop_up_rec_folder_dialog)
        # 回收站操作器
        self.rec_manipulator = RecManipulator(self._disk)
        self.rec_manipulator.msg.connect(self.show_status)
        self.rec_manipulator.successed.connect(self.get_rec_lists_worker.start)
        # 检查软件版本
        self.check_update_worker = CheckUpdateWorker()
        self.about_dialog.check_update.connect(self.check_update_worker.set_values)
        self.check_update_worker.infos.connect(self.about_dialog.show_update)
        self.check_update_worker.bg_update_infos.connect(self.show_new_version_msg)

    def show_login_dialog(self):
        """显示登录对话框"""
        login_dialog = LoginDialog(self._config_file)
        login_dialog.clicked_ok.connect(self.call_login_luncher)
        login_dialog.setWindowModality(Qt.ApplicationModal)
        login_dialog.exec()

    def show_upload_dialog(self, files):
        """显示上传文件对话框"""
        if len(self._path_list) > 0:
            self.upload_dialog.set_values(self._path_list[-1].name, files)
        else:
            self.show_status("等待文件列表更新...", 2000)

    def show_upload_dialog_menus(self):
        '''菜单栏显示上传对话框槽函数'''
        self.show_upload_dialog(None)

    def load_settings(self, ref_ui=False):
        """加载用户设置"""
        try:
            with open(self._config_file, "rb") as _file:
                _configs = load(_file)
                self._user = _configs["choose"]
                self.configs = _configs[self._user]
        except:
            self.configs = {"settings": self._default_settings}
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

    def call_multi_manipulator(self, action):
        """批量操作器"""
        tab_page = self.tabWidget.currentIndex()
        if tab_page == 0:
            listview = self.table_share
            model = self.model_share
        elif tab_page == 1:
            listview = self.table_disk
            model = self.model_disk
        elif tab_page == 2:
            listview = self.table_rec
            model = self.model_rec
        else:
            return
        infos = []
        _indexes = listview.selectionModel().selection().indexes()
        for i in _indexes:  # 获取所选行号
            info = model.item(i.row(), 0).data()
            if info and info not in infos:
                infos.append(info)

        if tab_page == 0 or tab_page == 1:
            if not infos:
                return
            self.desc_pwd_fetcher.set_values(self._disk, infos, download=True)
        elif tab_page == 2:
            if action == "recovery":
                title = "确定恢复选定文件(夹)？"
            elif action == "delete":
                title = "确定彻底删除选定文件(夹)？"
            elif action == "recovery_all":
                title = "确定还原全部文件(夹)？"
                msg = "提示: 恢复回收站中的文件将不可撤销，请确认。"
            elif action == "clean":
                title = "确定清除全部文件(夹)？"
                msg = "提示: 删除回收站中的文件将不可恢复，请确认。"
            if action == "recovery" or action == "delete":
                if not infos:
                    self.show_status("请先选中需要操作的文件！", 2999)
                    return
                msg = "\t\t列表：\n"
                for i in infos:
                    msg += f"{i.time}\t{i.name}\t{i.size}\n"
            message_box = QMessageBox(self)
            message_box.setStyleSheet(btn_style)
            message_box.setWindowTitle(title)
            message_box.setText(msg)
            message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            buttonY = message_box.button(QMessageBox.Yes)
            buttonY.setText('确定')
            buttonN = message_box.button(QMessageBox.No)
            buttonN.setText('取消')
            message_box.exec_()
            if message_box.clickedButton() == buttonY:
                self.rec_manipulator.set_values(infos, action)

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
        self.upload.triggered.disconnect(self.show_upload_dialog_menus)
        self._user = None

    def login_update_ui(self, success, msg, duration):
        """根据登录是否成功更新UI"""
        if success:
            self.show_status(msg, duration)
            self.tabWidget.insertTab(1, self.disk_tab, "我的蓝奏云")
            self.tabWidget.insertTab(2, self.rec_tab, "回收站")
            if self._user:
                self.tabWidget.setToolTip(f"当前登录用户：{self._user}")
            else:
                self.tabWidget.setToolTip("")
            self.disk_tab.setEnabled(True)
            self.rec_tab.setEnabled(True)
            # 更新快捷键与工具栏
            self.toolbar.addAction(self.logout)  # 添加登出工具栏
            self.toolbar.addAction(self.upload)  # 添加上传文件工具栏
            # 菜单栏槽
            self.logout.setEnabled(True)
            self.upload.setEnabled(True)
            self.upload.triggered.connect(self.show_upload_dialog_menus)
            # 设置当前显示 tab
            self.tabWidget.setCurrentIndex(1)
            QCoreApplication.processEvents()  # 重绘界面
            # 刷新文件列表
            # self.list_refresher.set_values(self._work_id)
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
        except Exception:
            pass

    def call_update_cookie(self, cookie, user):
        """更新cookie至config文件"""
        up_info = {"cookie": cookie}
        update_settings(self._config_file, up_info, user=user)

    def show_file_and_folder_lists(self):
        """显示用户文件和文件夹列表"""
        self.model_disk.removeRows(0, self.model_disk.rowCount())  # 清理旧的内容
        file_count = len(self._file_list.keys())
        folder_count = len(self._folder_list.keys())
        name_header = [f"文件夹{folder_count}个"] if folder_count else []
        if file_count:
            name_header.append(f"文件{file_count}个")
        self.model_disk.setHorizontalHeaderLabels(["/".join(name_header), "大小", "时间"])
        folder_ico = QIcon("./src/folder.gif")
        desc_style = ' <span style="font-size:14px;color:blue;text-align:right">'
        pwd_ico = ' <img src="./src/keys.ico" width="14" height="14" />'
        dl_count_style = ' <span style="font-size:14px;color:red;text-align:right">'
        # infos: ID/None，文件名，大小，日期，下载次数(dl_count)，提取码(pwd)，描述(desc)，|链接(share-url)
        if self._work_id != -1:
            _back = QStandardItem(folder_ico, "..")
            _back.setData(["..", ".."])
            _back.setToolTip("双击返回上层文件夹，选中无效")
            self.model_disk.appendRow([_back, QStandardItem(""), QStandardItem("")])
        for infos in self._folder_list.values():  # 文件夹
            name = QStandardItem()
            name.setIcon(folder_ico)
            txt = infos[1] + desc_style + infos[6] + "</span>" if infos[6] else infos[1]
            if infos[5]:
                txt = txt + pwd_ico
            name.setText(txt)
            name.setData(infos)
            tips = ""
            if infos[5] is not False:
                tips = "有提取码"
                if infos[6] is not False:
                    tips = tips + "，描述：" + str(infos[6])
            elif infos[6] is not False:
                tips = "描述：" + str(infos[6])
            name.setToolTip(tips)
            size_ = QStandardItem("")  # size
            self.model_disk.appendRow([name, size_, QStandardItem("")])
        for infos in self._file_list.values():  # 文件
            name = QStandardItem(set_file_icon(infos[1]), infos[1])
            txt = infos[1] + desc_style + "有描述" + "</span>" if infos[6] else infos[1]
            if infos[5]:
                txt = txt + pwd_ico
            if infos[4]:
                txt = txt + dl_count_style + str(infos[4]) + "</span>"
            name.setText(txt)
            name.setData(infos)
            tips = ""
            if infos[5] is not False:
                tips = "有提取码"
                if infos[6] is not False:
                    tips = tips + "，描述：" + str(infos[6])
            elif infos[6] is not False:
                tips = "描述：" + str(infos[6])
            name.setToolTip(tips)
            size_ = QStandardItem(infos[2])  # size
            time_ = QStandardItem(time_format(infos[3])) if self.time_fmt else QStandardItem(infos[3])
            self.model_disk.appendRow([name, size_, time_])
        for row in range(self.model_disk.rowCount()):  # 右对齐
            self.model_disk.item(row, 1).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.model_disk.item(row, 2).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def update_disk_lists(self, infos):
        """更新用户文件列表"""
        if not infos:
            return
        if infos['r']['files']:
            self._file_list = infos['file_list']
        if infos['r']['folders']:
            self._folder_list = infos['folder_list']
            self._path_list = infos['path_list']

        self._work_id = self._path_list[-1].id
        if infos['r']['fid'] != -1:
            self._parent_id = self._path_list[-2].id
        self.show_file_and_folder_lists()
        if infos['r']['path']:
            self.show_full_path()

    def config_tableview(self, tab):
        """Tab 初始化"""
        if tab == "share":
            model = self.model_share
            table = self.table_share
        elif tab == "disk":
            model = self.model_disk
            table = self.table_disk
        elif tab == "rec":
            model = self.model_rec
            table = self.table_rec

        model.setHorizontalHeaderLabels(["文件名", "大小", "时间"])
        table.setItemDelegateForColumn(0, TableDelegate())  # table 支持富文本
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
        table.horizontalHeader().resizeSection(1, 64)
        table.horizontalHeader().resizeSection(2, 84)
        # 设置第一列宽度自动调整，充满屏幕
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        if tab != "rec":
            table.setContextMenuPolicy(Qt.CustomContextMenu)  # 允许右键产生子菜单
            table.customContextMenuRequested.connect(self.generateMenu)  # 右键菜单

    def create_left_menus(self):
        self.left_menus = QMenu()
        self.left_menu_share_url = self.left_menus.addAction("外链分享地址等")
        self.left_menu_share_url.setIcon(QIcon("./src/share.ico"))
        self.left_menu_rename_set_desc = self.left_menus.addAction("修改文件夹名与描述")
        self.left_menu_rename_set_desc.setIcon(QIcon("./src/desc.ico"))
        self.left_menu_set_pwd = self.left_menus.addAction("设置访问密码")
        self.left_menu_set_pwd.setIcon(QIcon("./src/password.ico"))
        self.left_menu_move = self.left_menus.addAction("移动（支持批量）")
        self.left_menu_move.setIcon(QIcon("./src/move.ico"))

    def call_rename_mkdir_worker(self, infos):
        """重命名、修改简介与新建文件夹"""
        self.rename_mkdir_worker.set_values(self._disk, infos, self._work_id, self._folder_list)

    def set_passwd(self, infos):
        """设置文件(夹)提取码"""
        self.set_pwd_worker.set_values(self._disk, infos, self._work_id)
    
    def on_moved(self, r_files=True, r_folders=True, r_path=True):
        """移动文件(夹)后更新界面槽函数"""
        self.list_refresher.set_values(self._work_id, r_files, r_folders, r_path)

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
            self.left_menu_move.setEnabled(True)
            # 通过infos第3个字段 size 判断是否为文件夹，文件夹不能移动，设置不同的显示菜单名
            if info[2]:
                self.left_menu_rename_set_desc.setText("修改文件描述")
                self.left_menu_move.setEnabled(True)
            else:
                self.left_menu_rename_set_desc.setText("修改文件夹名与描述")
                # self.left_menu_move.setDisabled(True)
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

    def call_change_dir(self, folder_id=-1):
        """顶部路径按钮调用"""
        def callfunc():
            self.list_refresher.set_values(folder_id)

        return callfunc

    def change_dir(self, dir_name):
        """双击切换工作目录"""
        dir_name = self.model_disk.item(dir_name.row(), 0).data()[1]  # 文件夹名
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
        for _ in iter(self._path_list_old):
            self._locs[index].clicked.disconnect()
            self.disk_loc.removeWidget(self._locs[index])
            self._locs[index].deleteLater()
            self._locs[index] = None
            del self._locs[index]
            index += 1
        index = 1
        for item in iter(self._path_list):
            self._locs[index] = QPushButton(item.name, self.disk_tab)
            tip = f"fid:{item.id} | 描述:{item.desc}" if item.desc else f"fid:{item.id}"
            self._locs[index].setToolTip(tip)
            self._locs[index].setIcon(QIcon("./src/folder.gif"))
            self._locs[index].setStyleSheet("QPushButton {border:none; background:transparent;}")
            self.disk_loc.insertWidget(index, self._locs[index])
            self._locs[index].clicked.connect(self.call_change_dir(item.id))
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
            btn = self.btn_rec_select_all
            table = self.table_rec
        else:
            return
        if btn.isEnabled():
            if action == "reverse":
                if btn.text() == "全选":
                    table.selectAll()
                    btn.setText("取消")
                    btn.setIcon(QIcon("./src/select_none.ico"))
                elif btn.text() == "取消":
                    table.clearSelection()
                    btn.setText("全选")
                    btn.setIcon(QIcon("./src/select_all.ico"))
            elif action == "cancel":  # 点击列表其中一个就表示放弃全选
                btn.setText("全选")
                btn.setIcon(QIcon("./src/select_all.ico"))
            else:
                table.selectAll()
                btn.setText("取消")
                btn.setIcon(QIcon("./src/select_none.ico"))

    def finished_upload(self):
        """上传完成调用"""
        if self._old_work_id == self._work_id:
            self.list_refresher.set_values(self._work_id, True, True, False)
        else:
            self._old_work_id = self._work_id
        self.show_status("上传完成！", 7000)

    # disk tab
    def init_disk_ui(self):
        self.model_disk = QStandardItemModel(1, 3)
        self.config_tableview("disk")
        self.btn_disk_delete.setIcon(QIcon("./src/delete.ico"))
        self.btn_disk_dl.setIcon(QIcon("./src/downloader.ico"))
        self.btn_disk_select_all.setIcon(QIcon("./src/select_all.ico"))
        self.btn_disk_select_all.setToolTip("按下 Ctrl/Alt + A 全选或则取消全选")
        self.btn_disk_select_all.clicked.connect(lambda: self.select_all_btn("reverse"))
        self.table_disk.clicked.connect(lambda: self.select_all_btn("cancel"))
        self.btn_disk_dl.clicked.connect(lambda: self.call_multi_manipulator("download"))
        self.btn_disk_mkdir.setIcon(QIcon("./src/add_folder.ico"))
        self.btn_disk_mkdir.clicked.connect(self.call_mkdir)
        self.btn_disk_delete.clicked.connect(self.call_remove_files)
        # 文件拖拽上传
        self.table_disk.drop_files.connect(self.show_upload_dialog)

        self.table_disk.doubleClicked.connect(self.change_dir)
        # 上传器
        self.upload_worker = UploadWorker()
        self.upload_worker.finished.connect(self.finished_upload)
        self.upload_worker.code.connect(self.show_status)

    # rec tab
    def pop_up_rec_folder_dialog(self, files):
        # 弹出回收站文件夹内容对话框
        if files:
            rec_file_dialog = RecFolderDialog(files)
            rec_file_dialog.exec()
        else:
            self.show_status("文件夹为空！", 2999)

    def call_rec_folder_dialog(self, dir_name):
        # 显示弹出对话框
        dir_data = self.model_rec.item(dir_name.row(), 0).data()  # 文件夹信息
        if isinstance(dir_data, RecFolder):
            self.show_status(f"正在获取文件夹 {dir_data.name} 信息，稍后", 10000)
            self.get_rec_lists_worker.set_values(dir_data.id)

    def update_rec_lists(self, dir_lists, file_lists):
        """显示回收站文件和文件夹列表"""
        self.model_rec.removeRows(0, self.model_rec.rowCount())  # 清理旧的内容
        file_count = len(file_lists)
        folder_count = len(dir_lists)
        if ((not dir_lists) and (not file_lists)) or (file_count==0 and folder_count==0):
            self.show_status("回收站为空！", 4000)
            return
        name_header = ["文件夹{}个".format(folder_count), ] if folder_count else []
        if file_count:
            name_header.append("文件{}个".format(file_count))
        self.model_rec.setHorizontalHeaderLabels(["/".join(name_header), "大小", "时间"])
        folder_ico = QIcon("./src/folder.gif")

        for item in iter(dir_lists):  # 文件夹
            name = QStandardItem(folder_ico, item.name)
            name.setData(item)
            name.setToolTip("双击查看详情")
            size_ = QStandardItem(item.size)
            time_ = QStandardItem(item.time)
            self.model_rec.appendRow([name, size_, time_])
        for item in iter(file_lists):  # 文件
            name = QStandardItem(set_file_icon(item.name), item.name)
            name.setData(item)
            size_ = QStandardItem(item.size)
            time_ = QStandardItem(item.time)
            self.model_rec.appendRow([name, size_, time_])
        for row in range(self.model_rec.rowCount()):  # 右对齐
            self.model_rec.item(row, 1).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.model_rec.item(row, 2).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def init_rec_ui(self):
        """回收站ui初始化"""
        self.model_rec = QStandardItemModel(1, 3)
        self.config_tableview("rec")
        self.table_rec.doubleClicked.connect(self.call_rec_folder_dialog)
        self.btn_rec_select_all.setIcon(QIcon("./src/select_all.ico"))
        self.btn_rec_select_all.clicked.connect(lambda: self.select_all_btn("reverse"))
        self.btn_rec_delete.clicked.connect(lambda: self.call_multi_manipulator("delete"))
        self.btn_rec_delete.setIcon(QIcon("./src/delete.ico"))
        self.btn_recovery.clicked.connect(lambda: self.call_multi_manipulator("recovery"))
        self.btn_recovery.setIcon(QIcon("./src/rec_folder.ico"))
        self.btn_rec_delete.setToolTip("彻底删除选中文件(夹)")
        self.btn_recovery.setToolTip("恢复选中文件(夹)")
        self.btn_recovery_all.clicked.connect(lambda: self.call_multi_manipulator("recovery_all"))
        self.btn_recovery_all.setIcon(QIcon("./src/rec_folder.ico"))
        self.btn_recovery_all.setToolTip("恢复全部")
        self.btn_rec_clean.clicked.connect(lambda: self.call_multi_manipulator("clean"))
        self.btn_rec_clean.setIcon(QIcon("./src/rec_bin.ico"))
        self.btn_rec_clean.setToolTip("清理回收站全部")
        self.expire_files_btn.setToolTip("暂时无效！")

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
                name = QStandardItem(set_file_icon(infos[1]), infos[1])
                name.setData(infos)
                time = QStandardItem(time_format(infos[3])) if self.time_fmt else QStandardItem(infos[3])
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
        self.btn_share_dl.clicked.connect(lambda: self.call_multi_manipulator("download"))
        self.btn_share_dl.setIcon(QIcon("./src/downloader.ico"))
        self.btn_share_select_all.setIcon(QIcon("./src/select_all.ico"))
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

    # others
    def clean_status(self):
        self._msg_label.setText("")
        self._msg_movie_lb.clear()
        self._msg_movie.stop()

    def show_status(self, msg, duration=0):
        self._msg_label.setText(msg)
        if msg and duration >= 3000:
            self._msg_movie_lb.setMovie(self._msg_movie)
            self._msg_movie.start()
        else:
            self._msg_movie_lb.clear()
            self._msg_movie.stop()
        if duration != 0:
            QTimer.singleShot(duration, self.clean_status)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_A:  # Ctrl/Alt + A 全选
            if e.modifiers() and Qt.ControlModifier:
                self.select_all_btn()
        elif e.key() == Qt.Key_F5:  # 刷新
            if self.tabWidget.currentIndex() == 1:  # disk 界面
                self.show_status("正在更新当前目录...", 10000)
                self.list_refresher.set_values(self._work_id)
            elif self.tabWidget.currentIndex() == 2:  # rec 界面
                self.show_status("正在更新回收站...", 10000)
                self.get_rec_lists_worker.start()

    def call_change_tab(self):
        """切换标签页 动作"""
        tab_index = self.tabWidget.currentIndex()
        if tab_index == 2:
            self.show_status("正在更新回收站...", 10000)
            self.get_rec_lists_worker.start()
        elif tab_index == 1:
            self.show_status("正在更新当前目录...", 10000)
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

    def show_new_version_msg(self, ver, msg):
        message_box = QMessageBox(self)
        message_box.setStyleSheet(btn_style)
        message_box.setWindowTitle(f"检测到新版 {ver}")
        message_box.setText(msg)
        message_box.setStandardButtons(QMessageBox.Close)
        buttonC = message_box.button(QMessageBox.Close)
        buttonC.setText('关闭')
        message_box.exec()

    def closeEvent(self, event):
        if self.to_tray:
            event.ignore()
            self.hide()
            if self._show_to_tray_msg:
                self.tray.showMessage(
                    "已经最小化到托盘",
                    "双击显示/隐藏窗口，退出请右击",
                    QSystemTrayIcon.Information,
                    3000
                )
                self._show_to_tray_msg = False  # 提示一次

    def Exit(self):
        # 点击关闭按钮或者点击退出事件会出现图标无法消失的bug，那就先隐藏吧(｡･ω･｡)
        self.tray.hide()
        del self.tray
        sys.exit(app.exec_())

    def auto_extract_clipboard(self):
        if not self.watch_clipboard:
            return
        text = self.clipboard.text()
        pat = r"(https?://(www\.)?lanzous.com/[bi][a-z0-9]+)[^0-9a-z]*([a-z0-9]+)?"
        for share_url, _, pwd in re.findall(pat, text):
            if share_url and not self.get_shared_info_thread.isRunning():
                self.line_share_url.setEnabled(False)
                self.btn_extract.setEnabled(False)
                txt = share_url + "提取码：" + pwd if pwd else share_url
                self.line_share_url.setText(txt)
                self.get_shared_info_thread.set_values(txt)
                self.tabWidget.setCurrentIndex(0)
                self.show()
                break

    def clipboard_listener(self):
        """监听系统剪切板"""
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.auto_extract_clipboard)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("./src/lanzou_logo2.png"))
    form = MainWindow()
    form.show()
    sys.exit(app.exec())
