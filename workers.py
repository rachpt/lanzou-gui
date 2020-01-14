#!/usr/bin/env python3

import os
import sys
from random import random
from PyQt5.QtCore import QThread, pyqtSignal, QMutex
from lanzou.api import LanZouCloud
from time import sleep


def show_progress(file_name, total_size, now_size):
    """显示进度条的回调函数"""
    percent = now_size / total_size
    # 进度条长总度
    file_len = len(file_name)
    if file_len >= 20:
        bar_len = 20
    elif file_len >= 10:
        bar_len = 30
    else:
        bar_len = 40
    if total_size >= 1048576:
        unit = "MB"
        piece = 1048576
    else:
        unit = "KB"
        piece = 1024
    bar_str = ("<font color='#00CC00'>" + ">" * round(bar_len * percent) +
               "</font><font color='#000080'>" + "=" * round(bar_len * (1 - percent)) + "</font>")
    msg = "\r{:>5.1f}%\t[{}] {:.1f}/{:.1f}{} | {} ".format(
        percent * 100,
        bar_str,
        now_size / piece,
        total_size / piece,
        unit,
        file_name,
    )
    if total_size == now_size:
        msg = msg + "| <font color='blue'>Done!</font>"
    return msg


class Downloader(QThread):
    download_proc = pyqtSignal(str)

    def __init__(self, disk, parent=None):
        super(Downloader, self).__init__(parent)
        self._stopped = True
        self._mutex = QMutex()
        self._disk = disk
        self.url = ""
        self.pwd = ""
        self.save_path = ""

    def stop(self):
        self._mutex.lock()
        self._stopped = True
        self._mutex.unlock()

    def _show_progress(self, file_name, total_size, now_size):
        """显示进度条的回调函数"""
        msg = show_progress(file_name, total_size, now_size)
        self.download_proc.emit(msg)

    def __del__(self):
        self.wait()

    def set_values(self, name, url, pwd, save_path):
        self.name = name
        self.url = url
        self.pwd = pwd
        self.save_path = save_path

    def run(self):
        if self._disk.is_file_url(self.url):
            # 下载文件
            self._disk.download_file(self.url, self.pwd, self.save_path, self._show_progress)
        elif self._disk.is_folder_url(self.url):
            # 下载文件夹
            folder_path = self.save_path + os.sep + self.name
            os.makedirs(folder_path, exist_ok=True)
            self.save_path = folder_path
            self._disk.download_dir(self.url, self.pwd, self.save_path, self._show_progress)


class DownloadManager(QThread):
    download_mgr_msg = pyqtSignal(str, int)
    downloaders_msg = pyqtSignal(str, int)

    def __init__(self, disk, threads=3, parent=None):
        super(DownloadManager, self).__init__(parent)
        self._disk = disk
        self.tasks = []
        self._thread = threads
        self._count = 0
        self._mutex = QMutex()
        self._is_work = False
        self._old_msg = ""

    def set_values(self, tasks, threads):
        self.tasks.extend(tasks)
        self._thread = threads

    def __del__(self):
        self.wait()

    def ahead_msg(self, msg):
        if self._old_msg != msg:
            self.downloaders_msg.emit(msg, 10000)
            self._old_msg = msg

    def add_task(self):
        self._count -= 1

    def stop(self):
        self._mutex.lock()
        self._is_work = False
        self._mutex.unlock()

    def run(self):
        if not self._is_work:
            self._mutex.lock()
            self._is_work = True
            downloader = {}
            while True:
                if not self.tasks:
                    break
                while self._count >= self._thread:
                    self.sleep(1)
                self._count += 1
                task = self.tasks.pop()
                dl_id = int(random() * 100000)
                downloader[dl_id] = Downloader(self._disk)
                self.download_mgr_msg.emit("准备下载：<font color='#FFA500'>{}</font>".format(task[0]), 8000)
                downloader[dl_id].finished.connect(self.add_task)
                downloader[dl_id].download_proc.connect(self.ahead_msg)
                downloader[dl_id].set_values(task[0], task[1], task[2], task[3])
                downloader[dl_id].start()
            self._is_work = False
            self._mutex.unlock()


class GetSharedInfo(QThread):
    infos = pyqtSignal(object)
    code = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super(GetSharedInfo, self).__init__(parent)
        self._disk = object
        self.share_url = ""
        self.pwd = ""
        self.is_file = ""
        self.is_folder = ""

    def set_values(self, disk, share_url, pwd, is_file, is_folder):
        self._disk = disk
        self.share_url = share_url
        self.pwd = pwd
        self.is_file = is_file
        self.is_folder = is_folder

    def __del__(self):
        self.wait()

    def is_successed(self, infos):
        show_time = 7000
        if infos["code"] == LanZouCloud.FILE_CANCELLED:
            self.code.emit("<font color='red'>文件不存在，或已删除！</font>", show_time)
        elif infos["code"] == LanZouCloud.URL_INVALID:
            self.code.emit("<font color='red'>链接非法！</font>", show_time)
        elif infos["code"] == LanZouCloud.PASSWORD_ERROR:
            self.code.emit("<font color='red'>提取码 [{}] 错误！</font>".format(self.pwd), show_time)
        elif infos["code"] == LanZouCloud.LACK_PASSWORD:
            self.code.emit("<font color='red'>请在链接后面跟上提取码，空格分割！</font>", show_time)
        elif infos["code"] == LanZouCloud.FAILED:
            self.code.emit("<font color='red'>网络错误！{}</font>".format(infos["info"]), show_time)
        elif infos["code"] == LanZouCloud.SUCCESS:
            self.code.emit("<font color='#00CC00'>提取成功！</font>", show_time)

    def run(self):
        if self.is_file:  # 链接为文件
            _infos = self._disk.get_share_file_info(self.share_url, self.pwd)
            self.is_successed(_infos)
        elif self.is_folder:  # 链接为文件夹
            _infos = self._disk.get_share_folder_info(self.share_url, self.pwd)
            self.is_successed(_infos)
        self.infos.emit(_infos)


class UploadWorker(QThread):
    code = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super(UploadWorker, self).__init__(parent)
        self._disk = object
        self.infos = []
        self._work_id = ""

    def _show_progress(self, file_name, total_size, now_size):
        """显示进度条的回调函数"""
        msg = show_progress(file_name, total_size, now_size)
        self.code.emit(msg, 0)

    def set_values(self, disk, infos, work_id):
        self._disk = disk
        self.infos = infos
        self._work_id = work_id

    def __del__(self):
        self.wait()

    def run(self):
        for f in self.infos:
            if not os.path.exists(f):
                msg = "<b>ERROR :</b> <font color='red'>文件不存在:{}</font>".format(f)
                self.code.emit(msg, 0)
                continue
            if os.path.isdir(f):
                msg = "<b>INFO :</b> <font color='#00CC00'>批量上传文件夹:{}</font>".format(f)
                self.code.emit(msg, 0)
                self._disk.upload_dir(f, self._work_id, self._show_progress)
            else:
                msg = "<b>INFO :</b> <font color='#00CC00'>上传文件:{}</font>".format(f)
                self.code.emit(msg, 0)
                self._disk.upload_file(f, self._work_id, self._show_progress)


class LoginLuncher(QThread):
    code = pyqtSignal(bool, str, int)

    def __init__(self, disk, parent=None):
        super(LoginLuncher, self).__init__(parent)
        self._disk = disk
        self.username = ""
        self.password = ""
        self.cookie = ""

    def set_values(self, username, password, cookie=None):
        self.username = username
        self.password = password
        self.cookie = cookie

    def __del__(self):
        self.wait()

    def run(self):
        if (not self.username or not self.password) and not self.cookie:
            self.code.emit(False, "<font color='red'>登录失败: 没有用户或密码</font>", 3000)
        else:
            res = self._disk.login(self.username, self.password)
            if res == LanZouCloud.SUCCESS:
                self.code.emit(True, "<font color='#00CC00'>登录<b>成功</b>！ ≧◉◡◉≦</font>", 5000)
            else:
                self.code.emit(False, "<font color='red'>登录失败，可能是用户名或密码错误！</font>", 8000)
