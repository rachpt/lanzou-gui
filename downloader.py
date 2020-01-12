#!/usr/bin/env python3

import os
import sys
from random import random
from PyQt5.QtCore import QThread, pyqtSignal, QMutex
from lanzou.api import LanZouCloud
from time import sleep


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

    def show_progress(self, file_name, total_size, now_size):
        """显示进度条的回调函数"""
        percent = now_size / total_size
        bar_len = 20  # 进度条长总度
        if total_size >= 1048576:
            unit = "MB"
            piece = 1048576
        else:
            unit = "KB"
            piece = 1024
        bar_str = ">" * round(bar_len * percent) + "=" * round(bar_len * (1 - percent))
        msg = "\r{:.2f}%\t[{}] {:.1f}/{:.1f}{} | {} ".format(
            percent * 100,
            bar_str,
            now_size / piece,
            total_size / piece,
            unit,
            file_name,
        )
        if total_size == now_size:
            msg = msg + "| Done!"
        self.download_proc.emit(msg)

    def __del__(self):
        self.wait()

    def setVal(self, name, url, pwd, save_path):
        self.name = name
        self.url = url
        self.pwd = pwd
        self.save_path = save_path
        self.start()

    def run(self):
        # 下载文件
        if self._disk.is_file_url(self.url):
            self._disk.download_file(
                self.url, self.pwd, self.save_path, self.show_progress
            )
        # 下载文件夹
        elif self._disk.is_folder_url(self.url):
            folder_path = self.save_path + os.sep + self.name
            os.makedirs(folder_path)
            self.save_path = folder_path
            self._disk.download_dir(
                self.url, self.pwd, self.save_path, self.show_progress
            )


class DownloadManager(QThread):
    download_mgr_msg = pyqtSignal(str)
    downloaders_msg = pyqtSignal(str)

    def __init__(self, disk, tasks, parent=None, threads=3):
        super(DownloadManager, self).__init__(parent)
        self._disk = disk
        self.tasks = tasks
        self._thread = threads
        self._count = 0

    def __del__(self):
        self.wait()

    def ahead_msg(self, msg):
        self.downloaders_msg.emit(msg)

    def add_task(self):
        self._count -= 1

    def run(self):
        downloader = {}
        for task in self.tasks:
            while self._count >= self._thread:
                self.sleep(1)
            self._count += 1
            dl_id = int(random() * 100000)
            downloader[dl_id] = Downloader(self._disk)
            self.download_mgr_msg.emit("准备下载：{}".format(task[0]))
            downloader[dl_id].finished.connect(self.add_task)
            downloader[dl_id].download_proc.connect(self.ahead_msg)
            downloader[dl_id].setVal(task[0], task[1], task[2], task[3])


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
        if infos["code"] == LanZouCloud.FILE_CANCELLED:
            self.code.emit("文件不存在！", 0)
        elif infos["code"] == LanZouCloud.URL_INVALID:
            self.code.emit("链接非法！", 0)
        elif infos["code"] == LanZouCloud.PASSWORD_ERROR:
            self.code.emit("提取码 [{}] 错误！".format(self.pwd), 0)
        elif infos["code"] == LanZouCloud.LACK_PASSWORD:
            self.code.emit("请在链接后面跟上提取码，空格分割！", 0)
        elif infos["code"] == LanZouCloud.FAILED:
            self.code.emit("网络错误！{}".format(infos["info"]), 0)
        elif infos["code"] == LanZouCloud.SUCCESS:
            self.code.emit("提取成功！", 5000)

    def run(self):
        if self.is_file:  # 链接为文件
            _infos = self._disk.get_share_file_info(self.share_url, self.pwd)
            self.is_successed(_infos)
        elif self.is_folder:  # 链接为文件夹
            _infos = self._disk.get_share_folder_info(self.share_url, self.pwd)
            self.is_successed(_infos)
        self.infos.emit(_infos)
