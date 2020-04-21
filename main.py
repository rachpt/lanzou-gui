#!/usr/bin/env python3

import sys
import os
import re
from pickle import dump, load
from logging import getLevelName, DEBUG, ERROR

from PyQt5.QtCore import Qt, QCoreApplication, QTimer, QUrl, QSize
from PyQt5.QtGui import (QIcon, QStandardItem, QStandardItemModel, QDesktopServices, QTextDocument,
                         QAbstractTextDocumentLayout, QPalette)
from PyQt5.QtWidgets import (QApplication, QAbstractItemView, QHeaderView, QMenu, QAction, QStyle,
                             QPushButton, QFileDialog, QDesktopWidget, QMessageBox, QSystemTrayIcon,
                             QStyledItemDelegate, QStyleOptionViewItem)

from ui_lanzou import Ui_MainWindow
from lanzou.api import LanZouCloud
from lanzou.api.utils import time_format, logger
from lanzou.api.models import FolderList
from lanzou.api.types import RecFolder, FolderDetail

from workers import (DownloadManager, GetSharedInfo, UploadWorker, LoginLuncher, DescPwdFetcher, ListRefresher,
                     GetRecListsWorker, RemoveFilesWorker, GetMoreInfoWorker, GetAllFoldersWorker, RenameMkdirWorker,
                     SetPwdWorker, LogoutWorker, RecManipulator, CheckUpdateWorker)
from dialogs import (update_settings, set_file_icon, btn_style, LoginDialog, UploadDialog, InfoDialog, RenameDialog, 
                     SettingDialog, RecFolderDialog, SetPwdDialog, MoveFileDialog, DeleteDialog, KEY,
                     AboutDialog, CaptchaDialog)
from tools import UserInfo, decrypt, DlJob, FileInfos, FolderInfos
from qss import *


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


class MainWindow(Ui_MainWindow):
    __version__ = 'v0.2.7'
    if not os.path.isdir("./src") or not os.path.isfile("./src/file.ico"):
        from src import release_src

        os.makedirs("./src", exist_ok=True)
        release_src()

    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)
        self.init_variables()
        # 设置 tab
        self.tabWidget.setCurrentIndex(0)
        self.tabWidget.removeTab(3)
        self.tabWidget.removeTab(2)
        self.tabWidget.removeTab(1)
        self.disk_tab.setEnabled(False)
        self.rec_tab.setEnabled(False)
        self.jobs_tab.setEnabled(False)

        self.init_workers()
        self.load_settings()

        self.set_window_at_center()
        self.init_menu()
        self.init_extract_share_ui()
        self.init_disk_ui()
        self.init_rec_ui()
        self.init_jobs_ui()
        self.call_login_luncher()
        self.create_left_menus()

        self.setWindowTitle("蓝奏云客户端 - {}".format(self.__version__))
        self.setStyleSheet(qssStyle)
        self.check_update_worker.set_values(self.__version__, False)  # 检测新版
        self.clipboard_monitor()  # 系统粘贴板

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
        self.logout.triggered.connect(lambda: self.logout_worker.set_values(True))  # 登出
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
        debug = False                  # 调试
        upload_delay = 20              # 上传大文件延时 0 - 20s
        dl_path = os.path.dirname(os.path.abspath(__file__)) + os.sep + "downloads"
        self._default_settings = {"download_threads": download_threads,
                                  "timeout": timeout,
                                  "max_size": max_size,
                                  "dl_path": dl_path,
                                  "time_fmt": time_fmt,
                                  "to_tray": to_tray,
                                  "watch_clipboard": watch_clipboard,
                                  "debug": debug,
                                  "set_pwd": False,
                                  "pwd": "",
                                  "set_desc": False,
                                  "desc": "",
                                  "upload_delay": upload_delay,
                                  "allow_big_file": False}

    def init_variables(self):
        self._disk = LanZouCloud()
        self._config_file = "./config.pickle"
        self._configs = UserInfo()
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
        self._dl_path = "./downloads"
        self._dl_jobs_lists = {}
        self._up_jobs_lists = {}
        self._captcha_code = None
        self.init_default_settings()

    def set_disk(self):
        self.download_manager.set_disk(self._disk)
        self.get_shared_info_thread.set_disk(self._disk)
        self.login_luncher.set_disk(self._disk)
        self.list_refresher.set_disk(self._disk)
        self.remove_files_worker.set_disk(self._disk)
        self.get_rec_lists_worker.set_disk(self._disk)
        self.rec_manipulator.set_disk(self._disk)
        self.desc_pwd_fetcher.set_disk(self._disk)
        self.logout_worker.set_disk(self._disk)
        self.rename_mkdir_worker.set_disk(self._disk)
        self.set_pwd_worker.set_disk(self._disk)
        self.more_info_worker.set_disk(self._disk)
        self.all_folders_worker.set_disk(self._disk)
        self.upload_worker.set_disk(self._disk)

    def update_lanzoucloud_settings(self):
        """更新LanzouCloud实例设置"""
        settings = self._configs.settings
        self._disk.set_captcha_handler(self.captcha_handler)
        self._disk.set_timeout(settings["timeout"])
        self._disk.set_max_size(settings["max_size"])
        self.download_manager.set_thread(settings["download_threads"])  # 同时下载任务数量
        self._dl_path = settings["dl_path"]  # 下载路径
        self.time_fmt = settings["time_fmt"]  # 时间显示格式
        self.to_tray = settings["to_tray"] if "to_tray" in settings else False
        self.watch_clipboard = settings["watch_clipboard"] if "watch_clipboard" in settings else False
        set_pwd = settings["set_pwd"] if "set_pwd" in settings else False  # 兼容旧版
        set_desc = settings["set_desc"] if "set_desc" in settings else False  # 兼容旧版
        pwd = settings["pwd"] if "pwd" in settings else ""  # 兼容旧版
        desc = settings["desc"] if "desc" in settings else ""  # 兼容旧版
        allow_big_file = settings["allow_big_file"] if "allow_big_file" in settings else False
        self.upload_dialog.set_pwd_desc_bigfile(set_pwd, pwd, set_desc, desc, allow_big_file, settings["max_size"])
        self.upload_worker.set_allow_big_file(allow_big_file)
        if 'upload_delay' in settings:
            delay = int(settings["upload_delay"])
            if delay > 0:
                self._disk.set_upload_delay((delay/2, delay))
            else:
                self._disk.set_upload_delay((0, 0))
        # debug
        debug = settings["debug"] if "debug" in settings else False  # 兼容旧版
        if debug:
            if getLevelName(logger.level) != "DEBUG":
                logger.setLevel(DEBUG)
                logger.debug("\n" + "=" * 69)
                logger.debug(f"Start New Debug: version {self.__version__}")
        else:
            logger.setLevel(ERROR)
        # 托盘图标
        if self.to_tray:
            self.create_tray()
        elif self._created_tray:
            self.tray.hide()
            del self.tray
            self._created_tray = False

    def init_workers(self):
        # 登录器
        self.login_luncher = LoginLuncher()
        self.login_luncher.code.connect(self.login_update_ui)
        self.login_luncher.update_cookie.connect(self.call_update_cookie)
        # 登出器
        self.logout_worker = LogoutWorker()
        self.logout_worker.successed.connect(self.call_logout_update_ui)
        # 下载器
        self.download_manager = DownloadManager()
        self.download_manager.downloaders_msg.connect(self.show_status)
        self.download_manager.update.connect(self.update_dl_jobs_info)
        self.download_manager.finished.connect(lambda: self.show_status("所有下载任务已完成！", 2999))
        # 获取更多信息，直链、下载次数等
        self.info_dialog = InfoDialog()  # 对话框
        self.info_dialog.setWindowModality(Qt.ApplicationModal)  # 窗口前置
        self.more_info_worker = GetMoreInfoWorker()  # 后台更新线程
        self.more_info_worker.msg.connect(self.show_status)
        self.more_info_worker.infos.connect(lambda: self.pause_extract_clipboard(True))  # 禁用剪切板监听
        self.more_info_worker.infos.connect(self.info_dialog.set_values)
        self.more_info_worker.share_url.connect(self.call_copy_share_url)
        self.more_info_worker.dl_link.connect(self.info_dialog.tx_dl_link.setText)
        self.info_dialog.get_dl_link.connect(self.more_info_worker.get_dl_link)
        self.info_dialog.closed.connect(lambda: self.pause_extract_clipboard(False))  # 恢复剪切板监听
        # 登录文件列表更新器
        self.list_refresher = ListRefresher()
        self.list_refresher.err_msg.connect(self.show_status)
        self.list_refresher.infos.connect(self.update_disk_lists)
        self.list_refresher.infos.connect(lambda: self.show_status(""))

        # 显示移动文件对话框
        self.move_file_dialog = MoveFileDialog()
        # 获取所有文件夹fid，并移动
        self.all_folders_worker = GetAllFoldersWorker()
        self.all_folders_worker.msg.connect(self.show_status)
        self.move_file_dialog.new_infos.connect(self.all_folders_worker.move_file)  # 调用移动线程
        self.all_folders_worker.infos.connect(self.move_file_dialog.set_values)
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
        self.remove_files_worker = RemoveFilesWorker()
        self.remove_files_worker.msg.connect(self.show_status)  # 显示错误提示
        self.remove_files_worker.finished.connect(lambda: self.list_refresher.set_values(self._work_id))  # 更新界面
        # 上传器，信号在登录更新界面设置
        self.upload_dialog = UploadDialog()
        self.upload_dialog.new_infos.connect(self.call_upload)
        # 文件描述与提取码更新器
        self.desc_pwd_fetcher = DescPwdFetcher()
        self.desc_pwd_fetcher.desc.connect(self.call_update_desc_pwd)
        self.desc_pwd_fetcher.tasks.connect(self.call_download_manager_thread)  # 连接下载管理器线程

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
        self.get_rec_lists_worker = GetRecListsWorker()
        self.get_rec_lists_worker.msg.connect(self.show_status)
        self.get_rec_lists_worker.infos.connect(self.update_rec_lists)
        self.get_rec_lists_worker.folders.connect(lambda: self.show_status('', 0))
        self.get_rec_lists_worker.folders.connect(self.pop_up_rec_folder_dialog)
        # 回收站操作器
        self.rec_manipulator = RecManipulator()
        self.rec_manipulator.msg.connect(self.show_status)
        self.rec_manipulator.successed.connect(self.get_rec_lists_worker.start)
        # 检查软件版本
        self.check_update_worker = CheckUpdateWorker()
        self.about_dialog.check_update.connect(self.check_update_worker.set_values)
        self.check_update_worker.infos.connect(self.about_dialog.show_update)
        self.check_update_worker.bg_update_infos.connect(self.show_new_version_msg)
        # 获取分享链接信息线程
        self.get_shared_info_thread = GetSharedInfo()
        # 上传器
        self.upload_worker = UploadWorker()
        self.upload_worker.finished.connect(self.finished_upload)
        self.upload_worker.update.connect(self.update_up_jobs_info)
        self.upload_worker.code.connect(self.show_status)
        # 验证码对话框
        self.captcha_dialog = CaptchaDialog()
        self.captcha_dialog.captcha.connect(self._captcha_handler)
        self.captcha_dialog.setWindowModality(Qt.ApplicationModal)

        self.set_disk()

    def _captcha_handler(self, code):
        self._captcha_code = code

    def captcha_handler(self, img_data):
        """处理下载时出现的验证码"""
        self.captcha_dialog.handle(img_data)
        self._captcha_code = None
        self.captcha_dialog.exec()
        from time import sleep
        while True:
            sleep(1)
            if self._captcha_code:
                break
        return self._captcha_code

    def show_login_dialog(self):
        """显示登录对话框"""
        login_dialog = LoginDialog(self._config_file)
        login_dialog.clicked_ok.connect(self.call_login_luncher)
        login_dialog.setWindowModality(Qt.ApplicationModal)
        login_dialog.exec()

    def show_upload_dialog(self, files):
        """显示上传文件对话框"""
        if len(self._path_list) > 0:
            self.upload_dialog.set_values(self._path_list[-1].name, self._path_list[-1].id, files)
        else:
            self.show_status("等待文件列表更新...", 2000)

    def show_upload_dialog_menus(self):
        '''菜单栏显示上传对话框槽函数'''
        self.show_upload_dialog(None)

    def load_settings(self, ref_ui=False):
        """加载用户设置"""
        try:
            with open(self._config_file, "rb") as _file:
                all_configs = load(_file)
            self._user = decrypt(KEY, all_configs["choose"])
            self._configs = all_configs["users"][self._user]
        except:
            try: self._configs = all_configs["none_user"]
            except:
                self._configs.settings = self._default_settings
                with open(self._config_file, "wb") as _file:
                    dump({"none_user": self._configs}, _file)
        if not self._configs.settings:
            self._configs.settings = self._default_settings
            update_settings(self._config_file, self._default_settings, user=self._user, is_settings=True)
        self.update_lanzoucloud_settings()
        if ref_ui and self.tabWidget.currentIndex() == self.tabWidget.indexOf(self.disk_tab):  # 更新文件界面的时间
            self.show_file_and_folder_lists()

    def call_download_manager_thread(self, tasks: dict):
        self.download_manager.add_tasks(tasks)
        self.tabWidget.insertTab(3, self.jobs_tab, "任务管理")
        self.jobs_tab.setEnabled(True)
        self._dl_jobs_lists.update(tasks)
        self.show_jobs_lists()

    def call_multi_manipulator(self, action):
        """批量操作器"""
        tab_page = self.tabWidget.currentIndex()
        if tab_page == self.tabWidget.indexOf(self.share_tab):
            listview = self.table_share
            model = self.model_share
        elif tab_page == self.tabWidget.indexOf(self.disk_tab):
            listview = self.table_disk
            model = self.model_disk
        elif tab_page == self.tabWidget.indexOf(self.rec_tab):
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

        if tab_page == self.tabWidget.indexOf(self.share_tab):  # 提取界面下载
            if not infos:
                return
            tasks = {}
            for info in infos:
                info = info[0]  # 单文件信息
                tasks[info.url] = DlJob(name=info.name, url=info.url, pwd=info.pwd, path=self._dl_path)

            if len(tasks) != 1 and len(tasks) == infos[0][2]:
                info = infos[0][1]  # 文件夹信息
                tasks[info.url] = DlJob(name=info.name, url=info.url, pwd=info.pwd, path=self._dl_path)
            logger.debug(f"manipulator, share tab {tasks=}")
            self.call_download_manager_thread(tasks)
        elif tab_page == self.tabWidget.indexOf(self.disk_tab):  # 登录文件界面下载
            if not infos:
                return
            logger.debug(f"manipulator, disk tab {infos=}")
            self.desc_pwd_fetcher.set_values(infos, download=True, dl_path=self._dl_path)
        elif tab_page == self.tabWidget.indexOf(self.rec_tab):  # 回收站
            logger.debug(f"manipulator, rec tab {action=}")
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
        self.show_status(msg, duration)
        if success:
            if self._user:
                if len(self._user) <= 6:
                    disk_tab = f"我的蓝奏<{self._user}>"
                else:
                    disk_tab = f"我的蓝奏<{self._user[:4]}..>"
            else:
                disk_tab = "我的蓝奏云"
            self.tabWidget.insertTab(1, self.disk_tab, disk_tab)
            self.tabWidget.insertTab(2, self.rec_tab, "回收站")
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
            self.tabWidget.setCurrentIndex(self.tabWidget.indexOf(self.disk_tab))
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
        self.logout_worker.set_values(update_ui=False)
        self.toolbar.removeAction(self.logout)
        try:
            username = self._configs.name
            password = self._configs.pwd
            cookie = self._configs.cookie
            if not username:
                return
            self.show_status("正在登陆，稍等……", 25000)
            self.login_luncher.set_values(username, password, cookie)
        except: pass

    def call_update_cookie(self, cookie, user):
        """更新cookie至config文件"""
        up_info = {"cookie": cookie}
        update_settings(self._config_file, up_info, user=user)

    def show_file_and_folder_lists(self):
        """显示用户文件和文件夹列表"""
        self.model_disk.removeRows(0, self.model_disk.rowCount())  # 清理旧的内容
        file_count = len(self._file_list)
        folder_count = len(self._folder_list)
        name_header = [f"文件夹{folder_count}个"] if folder_count else []
        if file_count:
            name_header.append(f"文件{file_count}个")
        self.model_disk.setHorizontalHeaderLabels(["/".join(name_header), "大小", "时间"])
        folder_ico = QIcon("./src/folder.gif")
        desc_style = ' <span style="font-size:14px;color:blue;text-align:right">'
        pwd_ico = ' <img src="./src/keys.ico" width="14" height="14" />'
        dl_count_style = ' <span style="font-size:14px;color:red;text-align:right">'
        if self._work_id != -1:
            _back = QStandardItem(folder_ico, "..")
            _back.setToolTip("双击返回上层文件夹，选中无效")
            self.model_disk.appendRow([_back, QStandardItem(""), QStandardItem("")])
        for infos in self._folder_list.values():  # 文件夹
            tips = ""
            name = QStandardItem()
            name.setData(FolderInfos(infos))
            name.setIcon(folder_ico)
            txt = infos.name + desc_style + infos.desc + "</span>" if infos.desc else infos.name
            if infos.has_pwd:
                tips = "有提取码"
                txt = txt + pwd_ico
                if infos.desc:
                    tips = tips + "，描述：" + str(infos.desc)
            elif infos.desc:
                tips = "描述：" + str(infos.desc)
            name.setText(txt)
            name.setToolTip(tips)
            self.model_disk.appendRow([name, QStandardItem(""), QStandardItem("")])
        for infos in self._file_list.values():  # 文件
            tips = ""
            name = QStandardItem(set_file_icon(infos.name), infos.name)
            name.setData(FileInfos(infos))
            txt = infos.name + desc_style + "有描述" + "</span>" if infos.has_des else infos.name
            if infos.has_pwd:
                tips = "有提取码"
                txt = txt + pwd_ico
                if infos.has_des:
                    tips = tips + "，有描述"
            elif infos.has_des:
                tips = "有描述"
            if infos.downs:
                txt = txt + dl_count_style + str(infos.downs) + "</span>"
            name.setText(txt)
            name.setToolTip(tips)
            time = time_format(infos.time) if self.time_fmt else infos.time
            self.model_disk.appendRow([name, QStandardItem(infos.size), QStandardItem(time)])
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
        elif tab == "jobs":
            model = self.model_jobs
            table = self.table_jobs

        if tab == "jobs":
            model.setHorizontalHeaderLabels(["任务名", "完成度", "状态", "操作"])
            table.horizontalHeader().resizeSection(3, 40)
        else:
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
        if tab != "rec" and tab != "jobs":
            table.setContextMenuPolicy(Qt.CustomContextMenu)  # 允许右键产生子菜单
            table.customContextMenuRequested.connect(self.generateMenu)  # 右键菜单

    def create_left_menus(self):
        self.left_menus = QMenu()
        self.left_menu_share_url = self.left_menus.addAction("外链分享地址等")
        self.left_menu_share_url.setIcon(QIcon("./src/share.ico"))
        self.left_menu_rename_set_desc = self.left_menus.addAction("修改文件描述（支持批量）")
        self.left_menu_rename_set_desc.setIcon(QIcon("./src/desc.ico"))
        self.left_menu_set_pwd = self.left_menus.addAction("设置提取码（支持批量）")
        self.left_menu_set_pwd.setIcon(QIcon("./src/password.ico"))
        self.left_menu_move = self.left_menus.addAction("移动（支持批量）")
        self.left_menu_move.setIcon(QIcon("./src/move.ico"))
        self.left_menu_copy = self.left_menus.addAction("复制分享链接")
        self.left_menu_copy.setIcon(QIcon("./src/count.ico"))

    def call_rename_mkdir_worker(self, infos):
        """重命名、修改简介与新建文件夹"""
        self.rename_mkdir_worker.set_values(infos, self._work_id, self._folder_list)

    def set_passwd(self, infos):
        """设置文件(夹)提取码"""
        self.set_pwd_worker.set_values(infos, self._work_id)
    
    def on_moved(self, r_files=True, r_folders=True, r_path=True):
        """移动文件(夹)后更新界面槽函数"""
        self.list_refresher.set_values(self._work_id, r_files, r_folders, r_path)

    def call_mkdir(self):
        """弹出新建文件夹对话框"""
        self.rename_dialog.set_values()
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
                infos.append(info)
        delete_dialog = DeleteDialog(infos)
        delete_dialog.new_infos.connect(self.remove_files_worker.set_values)
        delete_dialog.exec()

    def call_copy_share_url(self, infos):
        self.pause_extract_clipboard(True)
        text = infos.url + ' 提取码：' + infos.pwd if infos.has_pwd else infos.url
        self.clipboard.setText(text)
        QTimer.singleShot(500, self.pause_extract_clipboard)
        self.show_status("已复制到剪切板", 2999)

    def generateMenu(self, pos):
        """右键菜单"""
        row_nums = self.sender().selectionModel().selection().indexes()
        if not row_nums:  # 如果没有选中行，什么也不做
            return
        _model = self.sender().model()
        infos = []  # 多个选中的行，用于移动文件与...
        for one_row in row_nums:
            row_data = _model.item(one_row.row(), 0).data()
            if row_data and row_data not in infos:  # 删掉 .. 行
                if isinstance(row_data, FileInfos):
                    infos.append(row_data)
                else:
                    infos.append(row_data)
        if not infos:
            return
        info = infos[0]  # 取选中的第一行
        # 通过是否有文件 ID 判断是登录界面还是提取界面
        if isinstance(info, (FileInfos, FolderInfos)):
            self.left_menu_rename_set_desc.setEnabled(True)
            self.left_menu_set_pwd.setEnabled(True)
            self.left_menu_move.setEnabled(True)
            # 文件夹不能移动，设置不同的显示菜单名
            if isinstance(info, FileInfos):
                self.left_menu_rename_set_desc.setText("修改文件描述（支持批量）")
            else:
                self.left_menu_rename_set_desc.setText("修改文件夹名与描述")
            if info.has_pwd:
                self.left_menu_copy.setText("复制分享链接与提取码")
            else:
                self.left_menu_copy.setText("复制分享链接")
        else:
            self.left_menu_rename_set_desc.setDisabled(True)
            self.left_menu_move.setDisabled(True)
            self.left_menu_set_pwd.setDisabled(True)

        action = self.left_menus.exec_(self.sender().mapToGlobal(pos))
        if action == self.left_menu_share_url:  # 显示详细信息
            # 后台跟新信息，并显示信息对话框
            self.more_info_worker.set_values(info)
            self.info_dialog.exec()
        elif action == self.left_menu_move:  # 移动文件
            self.all_folders_worker.set_values(infos)
        elif action == self.left_menu_set_pwd:  # 修改提取码
            if len(infos) == 1:
                self.desc_pwd_fetcher.set_values([info,])  # 兼容下载器，使用列表的列表
            self.set_pwd_dialog.set_values(infos)
            self.set_pwd_dialog.exec()
        elif action == self.left_menu_rename_set_desc:  # 重命名与修改描述
            if len(infos) == 1:
                self.desc_pwd_fetcher.set_values([info,])  # 兼容下载器，使用列表的列表
            self.rename_dialog.set_values(infos)
            self.rename_dialog.exec()
        elif action == self.left_menu_copy:  # 复制分享链接
            self.more_info_worker.set_values(info, emit_link=True)

    def call_update_desc_pwd(self, infos):
        '''更新 desc、pwd'''
        self.rename_dialog.set_values(infos)
        self.set_pwd_dialog.set_values(infos)

    def call_change_dir(self, folder_id=-1):
        """顶部路径按钮调用"""
        def callfunc():
            self.list_refresher.set_values(folder_id)

        return callfunc

    def change_dir(self, dir_name):
        """双击切换工作目录"""
        if self.model_disk.item(dir_name.row(), 0).text() == "..":  # 返回上级路径
            self.list_refresher.set_values(self._parent_id)
            return
        dir_name = self.model_disk.item(dir_name.row(), 0).data().name  # 文件夹名
        if dir_name in self._folder_list.keys():
            folder_id = self._folder_list[dir_name].id
            self.list_refresher.set_values(folder_id)

    def call_upload(self, tasks: dict):
        """上传文件(夹)"""
        self._old_work_id = self._work_id  # 记录上传文件夹id
        self.upload_worker.add_tasks(tasks)
        self.tabWidget.insertTab(3, self.jobs_tab, "任务管理")
        self.jobs_tab.setEnabled(True)
        self._up_jobs_lists.update(tasks)

    def show_full_path(self):
        """路径框显示当前路径"""
        index = 1
        for _ in iter(self._path_list_old):
            self._locs[index].clicked.disconnect()
            self.disk_loc_hbox.removeWidget(self._locs[index])
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
            self.disk_loc_hbox.insertWidget(index, self._locs[index])
            self._locs[index].clicked.connect(self.call_change_dir(item.id))
            index += 1
        self._path_list_old = self._path_list

    def select_all_btn(self, action="reverse"):
        """默认反转按钮状态"""
        page = self.tabWidget.currentIndex()
        if page == self.tabWidget.indexOf(self.share_tab):
            btn = self.btn_share_select_all
            table = self.table_share
        elif page == self.tabWidget.indexOf(self.disk_tab):
            btn = self.btn_disk_select_all
            table = self.table_disk
        elif page == self.tabWidget.indexOf(self.rec_tab):
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
        self.btn_rec_expire_files.setToolTip("暂时无效！")

    # shared url
    def call_get_shared_info(self):
        if not self.get_shared_info_thread.isRunning():  # 防止快速多次调用
            self.line_share_url.setEnabled(False)
            self.btn_extract.setEnabled(False)
            text = self.line_share_url.text().strip()
            self.get_shared_info_thread.set_values(text)

    def show_share_url_file_lists(self, infos):
        if infos.code == LanZouCloud.SUCCESS:
            if isinstance(infos, FolderDetail):  # 文件夹
                file_count = len(infos.files)
                desc = " | " + infos.folder.desc[:50] if infos.folder.desc else ""
                title = f"{infos.folder.name} | 文件{file_count}个{desc}"
                for one in iter(infos.files):
                    name = QStandardItem(set_file_icon(one.name), one.name)
                    name.setData((one, infos.folder, file_count))
                    time = QStandardItem(time_format(one.time)) if self.time_fmt else QStandardItem(one.time)
                    self.model_share.appendRow([name, QStandardItem(one.size), time])
            else:  # 单文件
                title = "文件名"
                name = QStandardItem(set_file_icon(infos.name), infos.name)
                name.setData((infos, None, 1))
                time = time_format(infos.time) if self.time_fmt else infos.time
                self.model_share.appendRow([name, QStandardItem(infos.size), QStandardItem(time)])
            self.model_share.setHorizontalHeaderLabels([title, "大小", "时间"])
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
        if dl_path == self._configs.settings["dl_path"] or dl_path == ".":
            return
        if dl_path == "":
            dl_path = os.path.dirname(os.path.abspath(__file__)) + os.sep + "downloads"
            up_info = {"dl_path": dl_path}
        else:
            up_info = {"dl_path": dl_path}
        update_settings(self._config_file, up_info, user=self._user, is_settings=True)
        self.load_settings()
        self.share_set_dl_path.setText(self._configs.settings["dl_path"])

    def init_extract_share_ui(self):
        self.btn_share_select_all.setDisabled(True)
        self.btn_share_dl.setDisabled(True)
        self.table_share.setDisabled(True)
        self.model_share = QStandardItemModel(1, 3)
        self.config_tableview("share")

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
        self.share_set_dl_path.setText(self._configs.settings["dl_path"])
        self.share_set_dl_path.clicked.connect(self.set_download_path)

        # QSS
        self.label_share_url.setStyleSheet("#label_share_url {color: rgb(255,255,60);}")
        self.label_dl_path.setStyleSheet("#label_dl_path {color: rgb(255,255,60);}")

    # jobs tab
    def call_jobs_clean_all(self):
        try:
            for k, v in self._dl_jobs_lists.items():
                if v.rate >= 1000:
                    self.download_manager.del_task(k)
                    del self._dl_jobs_lists[k]
            for k, v in self._up_jobs_lists.items():
                if v.rate >= 1000:
                    del self._up_jobs_lists[k]
        except: pass
        self.show_jobs_lists()

    def update_dl_jobs_info(self, tasks):
        self._dl_jobs_lists.update(tasks)
        self.show_jobs_lists()

    def update_up_jobs_info(self, tasks):
        self._up_jobs_lists.update(tasks)
        self.show_jobs_lists()

    def redo_upload(self, task):
        logger.debug(f"re upload {task=}")
        self.upload_worker.add_task(task)

    def redo_download(self, task):
        logger.debug(f"re download {task=}")
        self.download_manager.add_task(task)

    def start_download_job(self, task):
        self.download_manager.start_task(task)

    def stop_download_job(self, task):
        self.download_manager.stop_task(task)

    def start_upload_job(self, task):
        pass

    def stop_upload_job(self, task):
        pass

    def show_jobs_lists(self):
        """任务列表"""
        self.model_jobs.removeRows(0, self.model_jobs.rowCount())  # 清理旧的内容
        download_ico = QIcon("./src/download.ico")
        upload_ico = QIcon("./src/upload.ico")
        path_style = ' <span style="font-size:14px;color:blue;text-align:right">'
        error_style = ' <span style="font-size:14px;color:red;text-align:right">'
        _index = 0
        for dl_job in self._dl_jobs_lists.values():  # 下载
            name = QStandardItem()
            name.setIcon(download_ico)
            txt = dl_job.name + path_style + '➩ ' + dl_job.path + "</span>"
            if dl_job.info:
                txt = txt + error_style + str(dl_job.info) + "</span>"
            name.setText(txt)
            name.setData(dl_job)
            rate = "{:5.1f}".format(dl_job.rate / 10)
            precent = QStandardItem(rate)  # precent
            self.model_jobs.appendRow([name, precent, QStandardItem(""), QStandardItem("")])

            _action = QPushButton()
            _action.resize(_action.sizeHint())
            if dl_job.run:
                _action.setText("暂停")
                _action.setStyleSheet(jobs_btn_completed_style)
                _action.clicked.connect(lambda: self.stop_download_job(dl_job))
            else:
                _action.setText("开始")
                _action.setStyleSheet(jobs_btn_completed_style)
                _action.clicked.connect(lambda: self.start_download_job(dl_job))
            self.table_jobs.setIndexWidget(self.model_jobs.index(_index, 3), _action)

            _status = QPushButton()
            _status.resize(_status.sizeHint())
            if dl_job.rate >= 1000:
                _status.setDisabled(True)
                _status.setText("已完成")
                _status.setStyleSheet(jobs_btn_completed_style)
            elif dl_job.info:
                _status.setText("重试")
                _status.clicked.connect(lambda: self.redo_download(dl_job))
                _status.setStyleSheet(jobs_btn_redo_style)
            else:
                if dl_job.run:
                    _status.setText("下载中")
                else:
                    _status.setText("暂停中")
                _status.setStyleSheet(jobs_btn_processing_style)

            self.table_jobs.setIndexWidget(self.model_jobs.index(_index,2), _status)
            _index += 1

        for up_job in self._up_jobs_lists.values():  # 上传
            name = QStandardItem()
            name.setIcon(upload_ico)
            txt = str(up_job.furl[-100:]) + path_style + '➩ ' + str(up_job.folder) + "</span>"
            if up_job.info:
                txt = txt + error_style + str(up_job.info) + "</span>"
            name.setText(txt)
            name.setData(up_job)
            rate = "{:5.1f}".format(up_job.rate / 10)
            precent = QStandardItem(rate)  # precent
            self.model_jobs.appendRow([name, precent, QStandardItem(""), QStandardItem("")])

            _action = QPushButton()
            _action.resize(_action.sizeHint())
            if up_job.run:
                _action.setText("开始")
                _action.setStyleSheet(jobs_btn_completed_style)
                _action.clicked.connect(lambda: self.start_upload_job(up_job))
            else:
                _action.setText("暂停")
                _action.setStyleSheet(jobs_btn_completed_style)
                _action.clicked.connect(lambda: self.stop_upload_job(up_job))
            self.table_jobs.setIndexWidget(self.model_jobs.index(_index, 3), _action)

            _status = QPushButton()
            _status.resize(_status.sizeHint())
            if up_job.rate >= 1000:
                _status.setDisabled(True)
                _status.setText("已完成")
                _status.setStyleSheet(jobs_btn_completed_style)
            elif up_job.info:
                _status.setText("重试")
                _status.clicked.connect(lambda: self.redo_upload(up_job))
                _status.setStyleSheet(jobs_btn_redo_style)
            else:
                _status.setText("上传中")
                _status.setStyleSheet(jobs_btn_processing_style)
            self.table_jobs.setIndexWidget(self.model_jobs.index(_index, 2), _status)
            _index += 1

        for row in range(self.model_jobs.rowCount()):  # 右对齐
            self.model_jobs.item(row, 1).setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.model_jobs.item(row, 2).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def init_jobs_ui(self):
        """初始化上传下载任务管理界面"""
        self.model_jobs = QStandardItemModel(1, 4)
        self.config_tableview("jobs")
        self.jobs_tab.setEnabled(True)

        # 信号
        self.btn_jobs_clean_all.clicked.connect(self.call_jobs_clean_all)

    # others
    def clean_status(self):
        self.statusbar_msg_label.setText("")
        self.statusbar_load_lb.clear()
        self.statusbar_load_movie.stop()

    def show_status(self, msg, duration=0):
        self.statusbar_msg_label.setText(msg)
        if msg and duration >= 3000:
            self.statusbar_load_lb.setMovie(self.statusbar_load_movie)
            self.statusbar_load_movie.start()
        else:
            self.statusbar_load_lb.clear()
            self.statusbar_load_movie.stop()
        if duration != 0:
            QTimer.singleShot(duration, self.clean_status)

    def call_change_tab(self):
        """切换标签页 动作"""
        tab_index = self.tabWidget.currentIndex()
        if tab_index == self.tabWidget.indexOf(self.rec_tab):  # rec 界面
            if not self.statusbar_msg_label.text():
                self.show_status("正在更新回收站...", 10000)
            self.get_rec_lists_worker.start()
        elif tab_index == self.tabWidget.indexOf(self.disk_tab):  # disk 界面
            if not self.statusbar_msg_label.text():
                self.show_status("正在更新当前目录...", 10000)
            self.list_refresher.set_values(self._work_id)
        elif tab_index == self.tabWidget.indexOf(self.jobs_tab):  # jobs 界面
            self.show_jobs_lists()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_A:  # Ctrl/Alt + A 全选
            if e.modifiers() and Qt.ControlModifier:
                self.select_all_btn()
        elif e.key() == Qt.Key_F5:  # 刷新
            self.call_change_tab()

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

    def pause_extract_clipboard(self, show=False):
        """登录文件界面屏蔽剪切板监听功能"""
        if show:
            self._watch_clipboard_old = self.watch_clipboard
            self.watch_clipboard = False
        else:
            self.watch_clipboard = self._watch_clipboard_old

    def auto_extract_clipboard(self):
        if not self.watch_clipboard:
            return
        text = self.clipboard.text()
        pat = r"(https?://(\w[-\w]*\.)?lanzous.com/[bi]?[a-z0-9]+)[^0-9a-z]*([a-z0-9]+)?"
        for share_url, _, pwd in re.findall(pat, text):
            if share_url and not self.get_shared_info_thread.isRunning():
                self.line_share_url.setEnabled(False)
                self.btn_extract.setEnabled(False)
                txt = share_url + "提取码：" + pwd if pwd else share_url
                self.line_share_url.setText(txt)
                self.get_shared_info_thread.set_values(txt)
                self.tabWidget.setCurrentIndex(0)
                self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)  # 窗口最前
                self.show()
                self.setWindowFlags(Qt.WindowCloseButtonHint | Qt.WindowMinMaxButtonsHint)  # 窗口恢复
                self.show()
                break

    def clipboard_monitor(self):
        """监听系统剪切板"""
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.auto_extract_clipboard)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("./src/lanzou_logo2.png"))
    form = MainWindow()
    form.show()
    sys.exit(app.exec())
