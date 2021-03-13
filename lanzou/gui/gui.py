import sys
import os
import re
from logging import getLevelName, DEBUG, ERROR

from PyQt5.QtCore import Qt, QCoreApplication, QTimer, QUrl, QSize
from PyQt5.QtGui import QIcon, QStandardItemModel, QDesktopServices, QKeySequence
from PyQt5.QtWidgets import (QApplication, QAbstractItemView, QHeaderView, QMenu, QAction, QStyle,
                             QPushButton, QFileDialog, QMessageBox, QSystemTrayIcon, QShortcut)

from lanzou.api import LanZouCloud
from lanzou.api.utils import time_format
from lanzou.api.utils import convert_file_size_to_int as format_size_int
from lanzou.api.models import FolderList
from lanzou.api.types import RecFolder, FolderDetail, ShareItem

from lanzou.gui.models import DlJob, Tasks, FileInfos, FolderInfos, ShareFileInfos
from lanzou.gui.ui import Ui_MainWindow
from lanzou.gui.others import set_file_icon, TableDelegate
from lanzou.gui.others import MyStandardItem as QStandardItem
from lanzou.gui.config import config
from lanzou.gui.workers import *
from lanzou.gui.workers.manager import change_size_unit
from lanzou.gui.dialogs import *
from lanzou.gui.qss import *
from lanzou.gui import version
from lanzou.debug import logger, USER_HOME, SRC_DIR


__ALL__ = ['MainWindow']


def get_logo_path():
    """释放图片，并返回 logo 路径"""
    if not os.path.isdir(SRC_DIR) or not os.path.isfile(SRC_DIR + "file.ico"):
        from lanzou.gui.src import release_src

        os.makedirs(SRC_DIR, exist_ok=True)
        release_src(SRC_DIR)

    return SRC_DIR + 'lanzou_logo2.png'


def get_lanzou_logo():
    return QIcon(get_logo_path())


class MainWindow(Ui_MainWindow):

    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)
        self.init_variables()
        self.init_workers()
        self.update_lanzoucloud_settings()

        self.main_menu_add_slot()
        self.init_extract_share_ui()
        self.init_disk_ui()
        self.init_rec_ui()
        self.init_jobs_ui()
        self.create_left_menus()

        self.setWindowTitle("蓝奏云客户端 - {}".format(version))
        self.setStyleSheet(qssStyle)
        if self.upgrade:  # 检测新版
            self.check_update_worker.set_values(version, False)
        self.clipboard_monitor()  # 系统粘贴板
        # self.call_login_launcher()

    def create_tray(self):
        """创建 系统托盘"""
        if not self._created_tray:
            self.tray = QSystemTrayIcon(get_lanzou_logo(), parent=self)
            show_action = QAction("显示窗口", self)
            hide_action = QAction("最小化到托盘", self)
            quit_action = QAction("退出程序", self)
            show_action.triggered.connect(self.show)
            hide_action.triggered.connect(self.hide)
            quit_action.triggered.connect(self.Exit)
            show_action.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
            hide_action.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMinButton))
            quit_action.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
            self.tray.activated[QSystemTrayIcon.ActivationReason].connect(self.icon_activated)  # 托盘点击事件
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

    def main_menu_add_slot(self):
        """主菜单添加槽函数"""
        self.login.triggered.connect(self.show_login_dialog)  # 登录
        self.logout.triggered.connect(self.call_logout)  # 登出
        self.download.triggered.connect(self.call_download_shortcut)  # 快捷键下载
        self.delete.triggered.connect(self.call_delete_shortcut)  # 快捷键删除
        self.upload.triggered.connect(self.show_upload_dialog_menus)
        self.setting_menu.triggered.connect(lambda: self.setting_dialog.open_dialog(self._config))
        self.show_toolbar.triggered.connect(self.show_toolbar_slot)
        self.how.triggered.connect(self.open_wiki_url)
        self.about.triggered.connect(self.about_dialog.exec)
        self.tabWidget.currentChanged.connect(self.call_change_tab)  # tab 切换时更新
        self.merge_file.triggered.connect(self.merge_file_dialog.exec)  # 合并文件

    def init_variables(self):
        self._disk = LanZouCloud()
        self._config = config
        self._user = None    # 当前登录用户名
        self._folder_list = {}  # disk 工作目录文件夹
        self._file_list = {}  # disk 工作目录文件
        self._extract_folder_list = {}  # share 提取子文件夹
        self._extract_show_dir = []  # share 提取文件显示子文件夹
        self._extract_setted_head = False  # share 提取界面设置表头标示
        self._extract_count = 0  # share 提取界面文件数
        self._path_list = FolderList()
        self._path_list_old = FolderList()
        self._locs = {}
        self._parent_id = -1  # --> ..
        self._work_name = ""  # share disk rec, not use now
        self._work_id = -1    # disk folder id
        self._old_work_id = self._work_id  # 用于上传完成后判断是否需要更新disk界面
        self._show_to_tray_msg = True
        self._created_tray = False
        self._tasks = Tasks()
        self._dl_jobs_lists = {}
        self._up_jobs_lists = {}
        self._to_tray = False
        self._show_subfolder = False  # 提取界面递归展示子文件

    def set_disk(self):
        """方便切换用户更新信息"""
        self.task_manager.set_disk(self._disk)
        self.get_shared_info_thread.set_disk(self._disk)
        self.login_launcher.set_disk(self._disk)
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

    def update_lanzoucloud_settings(self):
        """更新LanzouCloud实例设置"""
        self._user = self._config.name
        settings = self._config.settings
        self._disk.set_timeout(settings["timeout"])
        self._disk.set_max_size(settings["max_size"])
        self.task_manager.set_thread(settings["download_threads"])  # 同时下载任务数量
        self.share_set_dl_path.setText(self._config.path)  # 提取界面下载路径
        self.time_fmt = settings["time_fmt"]  # 时间显示格式
        self._to_tray = settings["to_tray"]
        self.watch_clipboard = settings["watch_clipboard"]
        self.upgrade = settings["upgrade"] if 'upgrade' in settings else True  # 自动检测更新
        self.upload_dialog.set_pwd_desc_bigfile(settings)
        self.task_manager.set_allow_big_file(settings["allow_big_file"])
        if 'upload_delay' in settings:
            delay = int(settings["upload_delay"])
            if delay > 0:
                self._disk.set_upload_delay((delay / 2, delay))
            else:
                self._disk.set_upload_delay((0, 0))
        # debug
        debug = settings["debug"]
        if debug:
            if getLevelName(logger.level) != "DEBUG":
                logger.setLevel(DEBUG)
                logger.debug("\n" + "=" * 69)
                logger.debug(f"Start New Debug: version {version}")
        else:
            logger.setLevel(ERROR)
        # 托盘图标
        if self._to_tray:
            self.create_tray()
        elif self._created_tray:
            self.tray.hide()
            del self.tray
            self._created_tray = False

    def init_workers(self):
        # 登录器
        self.login_launcher = LoginLuncher()
        self.login_launcher.update_username.connect(self._config.set_username)
        self.login_launcher.update_cookie.connect(self._config.set_cookie)  # 目前失效
        self.login_launcher.code.connect(self.login_update_ui)
        # 登出器
        self.logout_worker = LogoutWorker()
        self.logout_worker.succeeded.connect(self.call_logout_update_ui)
        # 任务管理器
        self.task_manager = TaskManager()
        self.task_manager.mgr_msg.connect(self.show_status)
        self.task_manager.update.connect(self.update_jobs_info)
        self.task_manager.mgr_finished.connect(self.call_show_mgr_finished)
        # 获取更多信息，直链、下载次数等
        self.info_dialog = InfoDialog()  # 对话框
        self.info_dialog.setWindowModality(Qt.ApplicationModal)  # 窗口前置
        self.more_info_worker = GetMoreInfoWorker()  # 后台更新线程
        self.more_info_worker.msg.connect(self.show_status)
        self.more_info_worker.infos.connect(lambda: self.pause_extract_clipboard(True))  # 禁用剪切板监听
        self.more_info_worker.infos.connect(self.info_dialog.set_values)
        self.more_info_worker.share_url.connect(self.call_copy_share_url)
        self.more_info_worker.dl_link.connect(self.info_dialog.set_dl_link_tx)
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
        self.all_folders_worker.moved.connect(self.on_moved)  # 更新文件列表

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
        self.upload_dialog = UploadDialog(USER_HOME)
        self.upload_dialog.new_infos.connect(self.call_upload)
        # 文件描述与提取码更新器
        self.desc_pwd_fetcher = DescPwdFetcher()
        self.desc_pwd_fetcher.desc.connect(self.call_update_desc_pwd)
        self.desc_pwd_fetcher.tasks.connect(self.call_task_manager_thread)  # 连接下载管理器线程

        # 重命名、修改简介与新建文件夹对话框
        self.rename_dialog = RenameDialog()
        self.rename_dialog.out.connect(self.call_rename_mkdir_worker)
        # 修改设置 提取码对话框
        self.set_pwd_dialog = SetPwdDialog()
        self.set_pwd_dialog.new_infos.connect(self.set_passwd)
        # 菜单栏关于
        self.about_dialog = AboutDialog()
        self.about_dialog.set_values(version)

        # 菜单栏设置
        self.setting_dialog = SettingDialog()
        self.setting_dialog.saved.connect(self.update_time_fmt)
        self.setting_dialog.saved.connect(self.update_lanzoucloud_settings)
        # 登录回收站信息更新器
        self.get_rec_lists_worker = GetRecListsWorker()
        self.get_rec_lists_worker.msg.connect(self.show_status)
        self.get_rec_lists_worker.infos.connect(self.update_rec_lists)
        self.get_rec_lists_worker.folders.connect(lambda: self.show_status('', 0))
        self.get_rec_lists_worker.folders.connect(self.pop_up_rec_folder_dialog)
        # 回收站操作器
        self.rec_manipulator = RecManipulator()
        self.rec_manipulator.msg.connect(self.show_status)
        self.rec_manipulator.succeeded.connect(self.get_rec_lists_worker.start)
        # 检查软件版本
        self.check_update_worker = CheckUpdateWorker()
        self.about_dialog.check_update.connect(self.check_update_worker.set_values)
        self.check_update_worker.infos.connect(self.about_dialog.show_update)
        self.check_update_worker.bg_update_infos.connect(self.show_new_version_msg)
        # 获取分享链接信息线程
        self.get_shared_info_thread = GetSharedInfo()
        # 验证码对话框
        # self.captcha_dialog = CaptchaDialog()
        # self.captcha_dialog.captcha.connect(self.set_captcha)
        # self.captcha_dialog.setWindowModality(Qt.ApplicationModal)

        self.merge_file_dialog = MergeFileDialog(USER_HOME)
        self.set_disk()

    # def set_captcha(self, code):
    #     self._captcha_code = code

    # def captcha_handler(self, img_data):
    #     """处理下载时出现的验证码(暂时不需要了)"""
    #     self.captcha_dialog.handle(img_data)
    #     self._captcha_code = None
    #     self.captcha_dialog.exec()
    #     from time import sleep
    #     while True:
    #         sleep(1)
    #         if self._captcha_code:
    #             break
    #     return self._captcha_code

    def show_toolbar_slot(self):
        if self.toolbar.isVisible():
            self.toolbar.close()
            self.show_toolbar.setText("显示工具栏")
        else:
            self.toolbar.show()
            self.toolbar.setIconSize(QSize(20,20))
            self.show_toolbar.setText("关闭工具栏")

    def show_login_dialog(self):
        """显示登录对话框"""
        login_dialog = LoginDialog(self._config)
        login_dialog.clicked_ok.connect(self.call_login_launcher)
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

    def update_time_fmt(self):
        """更新文件界面的时间"""
        if self.tabWidget.currentIndex() == self.tabWidget.indexOf(self.disk_tab):
            self.show_file_and_folder_lists()

    def call_task_manager_thread(self, tasks: dict):
        self.task_manager.add_tasks(tasks)
        self._tasks.add(tasks)
        self.tabWidget.insertTab(3, self.jobs_tab, "任务管理")
        self.jobs_tab.setEnabled(True)
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
            return None
        infos = []
        _indexes = listview.selectionModel().selection().indexes()
        for i in _indexes:  # 获取所选行号
            info = model.item(i.row(), 0).data()
            if info and info not in infos:
                infos.append(info)

        if tab_page == self.tabWidget.indexOf(self.share_tab):  # 提取界面下载
            if not infos:
                return None
            tasks = {}
            first_item = infos[0]
            if first_item.all is None:  # 单文件信息链接 (info, None, 1, [])
                info = first_item.item  # ShareInfo(code=0, name, url, pwd, desc, time, size)
                tasks[info.url] = DlJob(infos=info, path=self._config.path, total_file=1)
            elif len(infos) != 1 and len(infos) >= first_item.count:  # 下载整个文件夹文件 (info, all, count, parrent)
                info = first_item.all.folder  # 当前文件夹信息
                tasks[info.url] = DlJob(infos=info, path=self._config.path, total_file=first_item.count)
            else:  # 下载文件夹中部分文件
                parent_dir_lst = first_item.parrent  # 父文件夹信息
                parent_dir = os.sep.join(parent_dir_lst)
                path = self._config.path + os.sep + parent_dir if parent_dir_lst else self._config.path
                for info in infos:
                    info = info.item  # 文件夹中单文件信息
                    tasks[info.url] = DlJob(infos=info, path=path, total_file=1)
            logger.debug(f"manipulator, share tab tasks={tasks}")
            self.call_task_manager_thread(tasks)
        elif tab_page == self.tabWidget.indexOf(self.disk_tab):  # 登录文件界面下载
            if not infos:
                return None
            logger.debug(f"manipulator, disk tab infos={infos}")
            self.desc_pwd_fetcher.set_values(infos, download=True, dl_path=self._config.path)
        elif tab_page == self.tabWidget.indexOf(self.rec_tab):  # 回收站
            logger.debug(f"manipulator, rec tab action={action}")
            title = msg = ""
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
                    return None
                msg = "\t\t列表：\n"
                for i in infos:
                    msg += f"{i.time}\t{i.name}\t{i.size}\n"
            message_box = QMessageBox(self)
            message_box.setIcon(QMessageBox.Warning)
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
        self._user = None

    def login_update_ui(self, success, msg, duration):
        """根据登录是否成功更新UI，并保持用户信息"""
        self.show_status(msg, duration)
        if success:
            self.update_lanzoucloud_settings()
            self._work_id = self._config.work_id  # 切换用户后刷新 根目录
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
            self.download.setEnabled(True)
            self.delete.setEnabled(True)
            # 设置当前显示 tab
            self.tabWidget.setCurrentIndex(self.tabWidget.indexOf(self.disk_tab))
            QCoreApplication.processEvents()  # 重绘界面
            self._config.update_user()  # 存储用户信息
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
            self.download.setEnabled(False)
            self.delete.setEnabled(False)

    def call_login_launcher(self):
        """登录网盘"""
        self.logout_worker.set_values(update_ui=False)
        self.toolbar.removeAction(self.logout)
        try:
            username = self._config.name
            password = self._config.pwd
            cookie = self._config.cookie
            if not username and not cookie:
                return None
            self.show_status("正在登陆，稍候……", 25000)
            self.login_launcher.set_values(username, password, cookie)
        except Exception as err:
            logger.error(f"Login: err={err}")

    def call_logout(self):
        """登出确认对话框"""
        message_box = QMessageBox(self)
        message_box.setStyleSheet(btn_style)
        message_box.setIcon(QMessageBox.Question)
        message_box.setWindowTitle("确认登出")
        message_box.setText("提示：登出不会删除已经保存的用户信息！\n\n是否确认登出？")
        message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        buttonY = message_box.button(QMessageBox.Yes)
        buttonY.setText('确定')
        buttonN = message_box.button(QMessageBox.No)
        buttonN.setText('取消')
        message_box.accepted.connect(lambda: self.logout_worker.set_values(True))
        message_box.exec()

    def show_file_and_folder_lists(self):
        """显示用户文件和文件夹列表"""
        self.model_disk.removeRows(0, self.model_disk.rowCount())  # 清理旧的内容
        file_count = len(self._file_list)
        folder_count = len(self._folder_list)
        name_header = [f"文件夹{folder_count}个"] if folder_count else []
        if file_count:
            name_header.append(f"文件{file_count}个")
        self.model_disk.setHorizontalHeaderLabels(["/".join(name_header), "大小", "时间"])
        folder_ico = QIcon(SRC_DIR + "folder.gif")
        desc_style = ' <span style="font-size:14px;color:green;text-align:right">'
        pwd_ico = f' <img src="{SRC_DIR}keys.ico" width="14" height="14" />'
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
            size = QStandardItem(infos.size)
            size.setData(format_size_int(infos.size), Qt.UserRole)  # 配合MyStandardItem实现正确排序
            self.model_disk.appendRow([name, size, QStandardItem(time)])
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
        self._config.work_id = self._work_id
        if len(self._path_list) > 1:
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
        else:
            logger.error(f"Gui config_tableview: tab={tab}")
            return None

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
        if tab == 'jobs':
            table.setSortingEnabled(False)
        else:
            table.setSortingEnabled(True)
        table.setMouseTracking(False)
        # 设置表头的背景色为绿色
        table.horizontalHeader().setStyleSheet("QHeaderView::section{background:lightgray}")
        # 设置 不可选择单个单元格，只可选择一行。
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        # 设置第二三列的宽度
        table.horizontalHeader().resizeSection(1, 76)
        table.horizontalHeader().resizeSection(2, 90)
        # 设置第一列宽度自动调整，充满屏幕
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        if tab != "rec" and tab != "jobs":
            table.setContextMenuPolicy(Qt.CustomContextMenu)  # 允许右键产生子菜单
            table.customContextMenuRequested.connect(self.generateMenu)  # 右键菜单

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
        indexes = []
        infos = []
        _indexes = self.table_disk.selectionModel().selection().indexes()
        if not _indexes:
            return
        for i in _indexes:  # 获取所选行号
            indexes.append(i.row())
        indexes = set(indexes)
        for index in indexes:
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
            if isinstance(info, ShareItem):
                info = ShareFileInfos(info.item)  # 提取界面 info 在第一个位置
            self.more_info_worker.set_values(info)
            self.info_dialog.exec()
        elif action == self.left_menu_move:  # 移动文件
            self.all_folders_worker.set_values(infos)
        elif action == self.left_menu_set_pwd:  # 修改提取码
            if len(infos) == 1:
                self.desc_pwd_fetcher.set_values([info, ])  # 兼容下载器，使用列表的列表
            self.set_pwd_dialog.set_values(infos)
            self.set_pwd_dialog.exec()
        elif action == self.left_menu_rename_set_desc:  # 重命名与修改描述
            if len(infos) == 1:
                self.desc_pwd_fetcher.set_values([info, ])  # 兼容下载器，使用列表的列表
            self.rename_dialog.set_values(infos)
            self.rename_dialog.exec()
        elif action == self.left_menu_copy:  # 复制分享链接
            if isinstance(info, tuple) and len(info) == 3:
                info = ShareFileInfos(info[0])  # 提取界面 info 在第一个位置
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

    def change_disk_dir(self, dir_name):
        """双击切换工作目录"""
        if self.model_disk.item(dir_name.row(), 0).text() == "..":  # 返回上级路径
            self.list_refresher.set_values(self._parent_id)
            return None
        dir_name = self.model_disk.item(dir_name.row(), 0).data().name  # 文件夹名
        if dir_name in self._folder_list.keys():
            folder_id = self._folder_list[dir_name].id
            self.list_refresher.set_values(folder_id)

    def call_upload(self, tasks: dict):
        """上传文件(夹)"""
        self._old_work_id = self._work_id  # 记录上传文件夹id
        self.task_manager.add_tasks(tasks)
        self.tabWidget.insertTab(3, self.jobs_tab, "任务管理")
        self.jobs_tab.setEnabled(True)
        self._tasks.add(tasks)

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
            self._locs[index].setIcon(QIcon(SRC_DIR + "folder.gif"))
            self._locs[index].setStyleSheet("QPushButton {border:none; background:transparent;\
                                            color: rgb(139,0,139); font-weight:bold;}")
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
                    btn.setIcon(QIcon(SRC_DIR + "select_none.ico"))
                elif btn.text() == "取消":
                    table.clearSelection()
                    btn.setText("全选")
                    btn.setIcon(QIcon(SRC_DIR + "select_all.ico"))
            elif action == "cancel":  # 点击列表其中一个就表示放弃全选
                btn.setText("全选")
                btn.setIcon(QIcon(SRC_DIR + "select_all.ico"))
            else:
                table.selectAll()
                btn.setText("取消")
                btn.setIcon(QIcon(SRC_DIR + "select_none.ico"))

    def call_delete_shortcut(self):
        if self.tabWidget.currentIndex() == self.tabWidget.indexOf(self.disk_tab):
            self.call_remove_files()

    def call_download_shortcut(self):
        if self.tabWidget.currentIndex() == self.tabWidget.indexOf(self.disk_tab):
            self.call_multi_manipulator("download")

    # disk tab
    def init_disk_ui(self):
        self.model_disk = QStandardItemModel(1, 3)
        self.config_tableview("disk")
        self.btn_disk_delete.setIcon(QIcon(SRC_DIR + "delete.ico"))
        self.btn_disk_delete.setToolTip("按下 Ctrl + D 删除选中文件")
        self.btn_disk_dl.setIcon(QIcon(SRC_DIR + "downloader.ico"))
        self.btn_disk_dl.setToolTip("按下 Ctrl + J 下载选中文件")
        self.btn_disk_select_all.setIcon(QIcon(SRC_DIR + "select_all.ico"))
        self.btn_disk_select_all.setToolTip("按下 Ctrl/Alt + A 全选或则取消全选")
        self.btn_disk_select_all.clicked.connect(lambda: self.select_all_btn("reverse"))
        self.table_disk.clicked.connect(lambda: self.select_all_btn("cancel"))
        self.btn_disk_dl.clicked.connect(lambda: self.call_multi_manipulator("download"))
        self.btn_disk_mkdir.setIcon(QIcon(SRC_DIR + "add_folder.ico"))
        self.btn_disk_mkdir.clicked.connect(self.call_mkdir)
        self.btn_disk_delete.clicked.connect(self.call_remove_files)
        # 文件拖拽上传
        self.table_disk.drop_files.connect(self.show_upload_dialog)
        self.table_disk.doubleClicked.connect(self.change_disk_dir)

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
            self.show_status(f"正在获取文件夹 {dir_data.name} 信息，稍候", 10000)
            self.get_rec_lists_worker.set_values(dir_data.id)

    def update_rec_lists(self, dir_lists, file_lists):
        """显示回收站文件和文件夹列表"""
        self.model_rec.removeRows(0, self.model_rec.rowCount())  # 清理旧的内容
        file_count = len(file_lists)
        folder_count = len(dir_lists)
        if ((not dir_lists) and (not file_lists)) or (file_count == 0 and folder_count == 0):
            self.show_status("回收站为空！", 4000)
            return
        name_header = ["文件夹{}个".format(folder_count), ] if folder_count else []
        if file_count:
            name_header.append("文件{}个".format(file_count))
        self.model_rec.setHorizontalHeaderLabels(["/".join(name_header), "大小", "时间"])
        folder_ico = QIcon(SRC_DIR + "folder.gif")

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
        self.btn_rec_select_all.setIcon(QIcon(SRC_DIR + "select_all.ico"))
        self.btn_rec_select_all.clicked.connect(lambda: self.select_all_btn("reverse"))
        self.btn_rec_delete.clicked.connect(lambda: self.call_multi_manipulator("delete"))
        self.btn_rec_delete.setIcon(QIcon(SRC_DIR + "delete.ico"))
        self.btn_recovery.clicked.connect(lambda: self.call_multi_manipulator("recovery"))
        self.btn_recovery.setIcon(QIcon(SRC_DIR + "rec_folder.ico"))
        self.btn_rec_delete.setToolTip("彻底删除选中文件(夹)")
        self.btn_recovery.setToolTip("恢复选中文件(夹)")
        self.btn_recovery_all.clicked.connect(lambda: self.call_multi_manipulator("recovery_all"))
        self.btn_recovery_all.setIcon(QIcon(SRC_DIR + "rec_folder.ico"))
        self.btn_recovery_all.setToolTip("恢复全部")
        self.btn_rec_clean.clicked.connect(lambda: self.call_multi_manipulator("clean"))
        self.btn_rec_clean.setIcon(QIcon(SRC_DIR + "rec_bin.ico"))
        self.btn_rec_clean.setToolTip("清理回收站全部")
        self.btn_rec_expire_files.setToolTip("暂时无效！")

    # shared url
    def call_get_shared_info(self):
        """提取分享链接槽函数"""
        if not self.get_shared_info_thread.isRunning():  # 防止快速多次调用
            self._extract_show_dir = []
            self._extract_folder_list = {}
            self._extract_setted_head = False
            self._extract_count = 0
            self.line_share_url.setEnabled(False)
            self.line_share_pwd.setEnabled(False)
            self.btn_extract.setEnabled(False)
            text = self.line_share_url.text().strip()
            input_pwd = self.line_share_pwd.text().strip()
            self.model_share.setHorizontalHeaderLabels(['文件(夹)', "大小", "时间"])
            self.get_shared_info_thread.set_values(text, input_pwd)

    def show_share_folder_url_lists(self, infos, root_dir=[], show_dir=[]):
        # infos: 文件夹 FolderDetail -> code, folder, files, sub_folders
        folder_ico = QIcon(SRC_DIR + "folder.gif")
        if not (show_dir or self._extract_setted_head):
            self._extract_setted_head = True
            all_file = infos.folder.count  # 包括子文件夹的所有文件
            file_count = len(infos.files)  # 父文件夹中的文件数量
            folder_count = len(infos.sub_folders) or 0
            if self._show_subfolder:
                self._extract_count = all_file + folder_count  # 标记是否为全选下载
            else:
                self._extract_count = file_count + folder_count  # 标记是否为全选下载
            dots = '...' if len(infos.folder.desc) > 60 else ''
            desc = "| " + infos.folder.desc.replace('\n', ' ')[:60] + dots if infos.folder.desc else ""
            title = f"{infos.folder.name} | 文件{file_count}个 "
            if folder_count:
                title += f"| 子文件夹{folder_count}个 "
            if self._show_subfolder and all_file != file_count:
                title += f"| 递归文件{all_file}个 "
            title += f"｜ 总共 {infos.folder.size} {desc}"
            self.model_share.setHorizontalHeaderLabels([title, "大小", "时间"])

        if len(show_dir) == 1:
            _back = QStandardItem(folder_ico, "..")
            _back.setToolTip("双击返回上层文件夹，选中无效")
            _back.setData(ShareItem(all=infos))
            self.model_share.appendRow([_back, QStandardItem(""), QStandardItem("")])
        for sub_folder in iter(infos.sub_folders):  # 展示子文件夹
            if sub_folder.folder.name:  # 没有密码的子文件夹不展示在提取界面
                name = QStandardItem(folder_ico, sub_folder.folder.name)
                if root_dir:
                    root_path = [*show_dir, infos.folder.url]
                    post_root_dir = [*root_dir, sub_folder.folder.name]
                    pre_root_dir = f'<span style="font-size:14px;color:pink;text-align:right">{"/".join(root_dir)}/</span>'
                else:
                    root_path = [infos.folder.url, ]
                    pre_root_dir = ''
                    post_root_dir = [sub_folder.folder.name,]
                if sub_folder.folder.desc:
                    text = ' <span style="font-size:14px;color:green;text-align:right">{}</span>'.format(
                        sub_folder.folder.desc.replace("\n", " "))
                else:
                    text = ''
                set_data = ShareItem(item=sub_folder.folder, all=infos, count=self._extract_count, parrent=root_dir)
                if not show_dir:
                    name.setData(set_data)
                    name.setText(pre_root_dir + sub_folder.folder.name + text)
                    if self.time_fmt:
                        time = QStandardItem(time_format(sub_folder.folder.time)) 
                    else:
                        time = QStandardItem(sub_folder.folder.time)
                    size = QStandardItem(sub_folder.folder.size)
                    size.setData(format_size_int(sub_folder.folder.size), Qt.UserRole)
                    self.model_share.appendRow([name, size, time])
                if self._show_subfolder or show_dir:  # 在当前窗口递归展示子文件夹中的文件
                    self.show_share_folder_url_lists(sub_folder, root_dir=post_root_dir, show_dir=show_dir[1:])
                else:  # 不递归展示才会记录子文件夹信息
                    self._extract_folder_list[sub_folder.folder.url] = root_path
        if show_dir:
            return None
        for item in iter(infos.files):  # 展示文件
            if item:
                if root_dir:
                    pre_root_dir = f'<span style="font-size:14px;color:pink;text-align:right">{"/".join(root_dir)}/</span>'
                else:
                    pre_root_dir = ''
                name = QStandardItem(set_file_icon(item.name), item.name)
                name.setData(ShareItem(item=item, all=infos, count=self._extract_count, parrent=root_dir))
                name.setText(pre_root_dir + item.name)
                size = QStandardItem(item.size)
                size.setData(format_size_int(item.size), Qt.UserRole)
                time = QStandardItem(time_format(item.time)) if self.time_fmt else QStandardItem(item.time)
                self.model_share.appendRow([name, size, time])

    def show_share_url_file_lists(self, infos):
        if infos.code == LanZouCloud.SUCCESS:
            if isinstance(infos, FolderDetail):  # 文件夹 FolderDetail -> code, folder, files, sub_folders
                self.show_share_folder_url_lists(infos)
            else:  # 单文件
                name = QStandardItem(set_file_icon(infos.name), infos.name)
                name.setData(ShareItem(item=infos))
                time = time_format(infos.time) if self.time_fmt else infos.time
                self.model_share.appendRow([name, QStandardItem(infos.size), QStandardItem(time)])
                self.model_share.setHorizontalHeaderLabels(["文件名", "大小", "时间"])
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
        dl_path = QFileDialog.getExistingDirectory(self, "选择文件下载保存文件夹", self._config.path)
        dl_path = os.path.normpath(dl_path)  # windows backslash
        if dl_path == self._config.path or dl_path == ".":
            return None
        elif dl_path == "":
            self._config.default_path()
        else:
            self._config.path = dl_path
        self.share_set_dl_path.setText(self._config.path)

    def change_share_dir(self, dir_name):
        """双击子文件夹改变路径"""
        all_infos = self.model_share.item(dir_name.row(), 0).data() # 
        if self.model_share.item(dir_name.row(), 0).text() == "..":  # 返回父文件夹
            if self._extract_show_dir:
                self.model_share.removeRows(0, self.model_share.rowCount())
                self.show_share_folder_url_lists(all_infos.all, show_dir=self._extract_show_dir[:-1])
        elif all_infos.item.url in self._extract_folder_list.keys():
            show_url = self._extract_folder_list[all_infos.item.url]
            self._extract_show_dir = show_url
            self.model_share.removeRows(0, self.model_share.rowCount())
            self.show_share_folder_url_lists(all_infos.all, show_dir=show_url)

    def call_show_share_url_sub_folder(self, infos):
        """切换展示子文件夹按钮"""
        if self._show_subfolder:
            self._show_subfolder = False
            self._share_url_show_subfolder.setText("递归展示")
            self._share_url_show_subfolder.setToolTip("将子文件递归展示")
        else:
            self._show_subfolder = True
            self._extract_folder_list = {}  # 递归展示时不记录子文件夹信息
            self._share_url_show_subfolder.setText("收起文件")
            self._share_url_show_subfolder.setToolTip("将子文件收起，不展示")
        self.model_share.removeRows(0, self.model_share.rowCount())
        self.show_share_folder_url_lists(infos)

    def show_share_url_judge_folder(self, infos):
        """判断是否包含子文件夹"""
        try:
            if infos.sub_folders:
                logger.debug('Have subfolders!')
                self._share_url_show_subfolder = QPushButton("递归展示", self.share_tab)
                self._share_url_show_subfolder.setToolTip("将子文件递归展示")
                self._share_url_show_subfolder.setIcon(QIcon(SRC_DIR + "folder.gif"))
                self.share_hlayout_top.addWidget(self._share_url_show_subfolder)
                self._share_url_show_subfolder.clicked.connect(lambda: self.call_show_share_url_sub_folder(infos))
            else:
                logger.debug('Have No subfolders!')
                self.share_hlayout_top.removeWidget(self._share_url_show_subfolder)
                self._share_url_show_subfolder.deleteLater()
                self._share_url_show_subfolder = None
                del self._share_url_show_subfolder
        except: pass

    def init_extract_share_ui(self):
        self.btn_share_select_all.setDisabled(True)
        self.btn_share_dl.setDisabled(True)
        self.table_share.setDisabled(True)
        self.model_share = QStandardItemModel(1, 3)
        self.config_tableview("share")

        # 清理旧的信息
        self.get_shared_info_thread.clean.connect(lambda: self.model_share.removeRows(0, self.model_share.rowCount()))
        self.get_shared_info_thread.msg.connect(self.show_status)  # 提示信息
        self.get_shared_info_thread.infos.connect(self.show_share_url_judge_folder)  # 判断是否包含子文件夹
        self.get_shared_info_thread.infos.connect(self.show_share_url_file_lists)  # 内容信息
        self.get_shared_info_thread.update.connect(lambda: self.btn_extract.setEnabled(True))
        self.get_shared_info_thread.update.connect(lambda: self.line_share_url.setEnabled(True))
        self.get_shared_info_thread.update.connect(lambda: self.line_share_pwd.setEnabled(True))
        self.table_share.doubleClicked.connect(self.change_share_dir)  # 双击
        # 控件设置
        self.line_share_url.setPlaceholderText("蓝奏云链接，如有提取码，放后面，空格或汉字等分割(汉字、特殊符号提取码手动右侧输入！)，回车键提取")
        self.line_share_url.returnPressed.connect(self.call_get_shared_info)
        self.line_share_url.setFocus()  # 光标焦点
        self.line_share_pwd.setPlaceholderText("特殊提取码")
        self.line_share_pwd.setFixedWidth(100)  # 提取码输入框 宽度
        self.btn_extract.clicked.connect(self.call_get_shared_info)
        self.btn_share_dl.clicked.connect(lambda: self.call_multi_manipulator("download"))
        self.btn_share_dl.setIcon(QIcon(SRC_DIR + "downloader.ico"))
        self.btn_share_select_all.setIcon(QIcon(SRC_DIR + "select_all.ico"))
        self.btn_share_select_all.clicked.connect(lambda: self.select_all_btn("reverse"))
        self.table_share.clicked.connect(lambda: self.select_all_btn("cancel"))  # 全选按钮

        self.extract_input_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.extract_input_shortcut.activated.connect(self.call_extract_input_shortcut)

        # 添加文件下载路径选择器
        self.share_set_dl_path.setText(self._config.path)
        self.share_set_dl_path.clicked.connect(self.set_download_path)

    def call_extract_input_shortcut(self):
        """Ctrl+F槽函数"""
        self.tabWidget.setCurrentIndex(self.tabWidget.indexOf(self.share_tab))
        self.line_share_url.selectAll()  # 全选中
        self.line_share_url.setFocus()  # 焦点

    # jobs tab
    def call_jobs_clean_all(self):
        self._tasks.clear()
        self.show_jobs_lists()

    def call_jobs_start_all(self):
        for task in self._tasks.values():
            if task.pause:
                task.pause = False
        self.task_manager.start()
        self.show_jobs_lists()

    def call_show_mgr_finished(self, num: int):
        if num:
            self.show_status(f"所有任务已完成！ <font color='red'>{num} 个任务失败</font>", 2999)
        else:
            self.show_status("所有任务已完成！", 2999)
        # 上传完成调用
        if self._old_work_id == self._work_id:
            self.list_refresher.set_values(self._work_id, True, True, False)
        else:
            self._old_work_id = self._work_id
        self.show_jobs_lists()

    def update_jobs_info(self):
        self._tasks.update()
        self.show_jobs_lists()

    def redo_job(self, task):
        logger.debug(f"re do job task={task}")
        self.task_manager.add_task(task)

    def start_work_job(self, task):
        self.task_manager.start_task(task)

    def stop_work_job(self, task):
        self.task_manager.stop_task(task)

    def del_work_job(self, task):
        self.task_manager.del_task(task)
        self._tasks.clear(task)
        self.show_jobs_lists()

    def show_jobs_lists(self):
        """显示任务列表"""
        self.model_jobs.removeRows(0, self.model_jobs.rowCount())  # 清理旧的内容
        download_ico = QIcon(SRC_DIR + "download.ico")
        upload_ico = QIcon(SRC_DIR + "upload.ico")
        path_style = ' <span style="font-size:14px;color:green;text-align:right">'
        error_style = ' <span style="font-size:14px;color:red;text-align:right">'
        _index = 0
        for task in self._tasks.values():
            name = QStandardItem()
            if task.type == 'dl':
                name.setIcon(download_ico)
                txt = task.name + '  ' + path_style + task.size + '|' + task.speed + '|' + task.prog \
                    + ' ➩ ' + task.path + "</span>"
            else:
                name.setIcon(upload_ico)
                txt = str(task.url[-100:]) + '  ' + path_style + change_size_unit(task.total_size) + '|' \
                    + task.speed + '|' + task.prog + ' ➩ ' + str(task.folder) + "</span>"
            if task.info:
                txt = txt + error_style + str(task.info) + "</span>"
            name.setText(txt)
            name.setToolTip(txt)
            name.setData(task)
            rate = "{:5.1f}%".format(task.rate / 10)
            precent = QStandardItem(rate)  # precent
            self.model_jobs.appendRow([name, precent, QStandardItem(""), QStandardItem("")])

            _status = QPushButton()
            _status.resize(_status.sizeHint())
            _action = QPushButton()
            _action.resize(_action.sizeHint())

            _status.setDisabled(True)
            if task.rate >= 1000 and task.current >= task.total_file:
                _status.setText("已完成")
                _status.setStyleSheet(jobs_btn_completed_style)
                _action.setText("删除")
                _action.clicked.connect(lambda: self.del_work_job(task))
                _action.setStyleSheet(jobs_btn_delete_style)
            elif task.info:
                _status.setText("出错了")
                _status.setStyleSheet(jobs_btn_redo_style)
                if task.run:
                    _action.setText("暂停")
                    _action.clicked.connect(lambda: self.stop_work_job(task))
                else:
                    _action.setText("重试")
                    _action.clicked.connect(lambda: self.redo_job(task))
                _action.setStyleSheet(jobs_btn_completed_style)
            else:
                if task.run:
                    if task.type == 'dl':
                        _status.setText("下载中")
                    else:
                        _status.setText("上传中")
                    _status.setStyleSheet(jobs_btn_processing_style)
                    _action.setText("暂停")
                    _action.clicked.connect(lambda: self.stop_work_job(task))
                    _action.setStyleSheet(jobs_btn_completed_style)
                else:
                    if task.added:
                        _status.setText("排队中")
                        _status.setStyleSheet(jobs_btn_queue_style)

                        _action.setText("删除")
                        _action.clicked.connect(lambda: self.del_work_job(task))
                    else:
                        _status.setText("暂停中")
                        _status.setStyleSheet(jobs_btn_redo_style)

                        _action.setText("开始")
                        _action.clicked.connect(lambda: self.start_work_job(task))
                _action.setStyleSheet(jobs_btn_completed_style)

            self.table_jobs.setIndexWidget(self.model_jobs.index(_index, 2), _status)
            self.table_jobs.setIndexWidget(self.model_jobs.index(_index, 3), _action)
            _index += 1

        for row in range(self.model_jobs.rowCount()):  # 右对齐
            self.model_jobs.item(row, 1).setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.model_jobs.item(row, 2).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def init_jobs_ui(self):
        """初始化上传下载任务管理界面"""
        self.model_jobs = QStandardItemModel(1, 4)
        self.config_tableview("jobs")
        self.jobs_tab.setEnabled(True)
        self.btn_jobs_clean_all.clicked.connect(self.call_jobs_clean_all)  # 信号
        self.btn_jobs_start_all.clicked.connect(self.call_jobs_start_all)  # 信号

    # others
    def clean_status(self):
        self.statusbar_msg_label.setText("")
        self.statusbar_load_lb.clear()
        self.statusbar_load_movie.stop()

    def show_status(self, msg, duration=0):
        self.statusbar_msg_label.setText(msg)
        if msg and duration >= 3000:
            self.statusbar_load_lb.clear()
            self.statusbar_load_movie.stop()
            ht = self.statusbar_msg_label.size().height()
            self.statusbar_load_movie.setScaledSize(QSize(ht, ht))
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
        if tab_index == self.tabWidget.indexOf(self.share_tab):  # share 界面
            if self.get_shared_info_thread.isRunning():
                self.show_status("正在获取文件夹链接信息，可能需要几秒钟，请稍候……", 500000)
        elif tab_index == self.tabWidget.indexOf(self.rec_tab):  # rec 界面
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

    def open_wiki_url(self):
        # 打开使用说明页面
        url = QUrl('https://github.com/rachpt/lanzou-gui/wiki')
        if not QDesktopServices.openUrl(url):
            self.show_status('Could not open wiki page!', 5000)

    def show_new_version_msg(self, ver, msg):
        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Information)
        message_box.setStyleSheet(btn_style)
        message_box.setWindowTitle(f"检测到新版 {ver}")
        message_box.setText(msg)
        message_box.setStandardButtons(QMessageBox.Close)
        buttonC = message_box.button(QMessageBox.Close)
        buttonC.setText('关闭')
        message_box.exec()

    def closeEvent(self, event):
        if self._to_tray:
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
        sys.exit(0)

    def pause_extract_clipboard(self, show=False):
        """登录文件界面屏蔽剪切板监听功能"""
        if show:
            self._watch_clipboard_old = self.watch_clipboard
            self.watch_clipboard = False
        else:
            try:
                self.watch_clipboard = self._watch_clipboard_old
            except:
                pass

    def auto_extract_clipboard(self):
        if not self.watch_clipboard:
            return
        text = self.clipboard.text()
        pat = r"(https?://(\w[-\w]*\.)?lanzou[six].com/[a-z]?[-/a-zA-Z0-9]+)[^a-zA-Z0-9]*([a-zA-Z0-9]+)?"
        for share_url, _, pwd in re.findall(pat, text):
            if share_url and not self.get_shared_info_thread.isRunning():
                self.line_share_url.setEnabled(False)
                self.line_share_pwd.setEnabled(False)
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
