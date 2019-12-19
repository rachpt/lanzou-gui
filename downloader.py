#!/usr/bin/env python3

import sys
from random import random
from PyQt5.QtCore import QThread, pyqtSignal, QMutex


class Downloader(QThread):
    download_proc = pyqtSignal(str)

    def __init__(self, disk, parent=None):
        super(Downloader, self).__init__(parent)
        self._stopped = True
        self._mutex = QMutex()
        self._disk = disk
        self.isfile = ""
        self.isfolder = ""
        self.isurl = ""
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

    def setVal(self, isfile, isfolder, isurl, name, save_path):
        self.isfile = isfile
        self.isfolder = isfolder
        self.isurl = isurl
        self.name = name
        self.save_path = save_path
        self.start()

    def run(self):
        if self.isfolder:
            self._disk.download_dir2(
                self.isfolder, self.name, self.save_path, self.show_progress
            )
        elif self.isfile:
            self._disk.download_file2(
                self.isfile[0], self.save_path, self.show_progress
            )
        elif self.isurl:
            self._disk.download_file(
                self.isurl[0], self.isurl[1], self.save_path, self.show_progress
            )


class DownloadManger(QThread):
    download_mgr_msg = pyqtSignal(str)
    downloaders_msg = pyqtSignal(str)

    def __init__(self, disk, tasks, parent=None, threads=3):
        super(DownloadManger, self).__init__(parent)
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
            self.download_mgr_msg.emit("准备下载：{}".format(task[3]))
            downloader[dl_id].finished.connect(self.add_task)
            downloader[dl_id].download_proc.connect(self.ahead_msg)
            downloader[dl_id].setVal(task[0], task[1], task[2], task[3], task[4])
