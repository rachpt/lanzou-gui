#!/usr/bin/env python3

import sys
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
        self.save_path = ""

    def stop(self):
        self._mutex.lock()
        self._stopped = True
        self._mutex.unlock()

    def _show_progress(self, file_name, total_size, now_size):
        """显示进度条的回调函数"""
        percent = now_size / total_size
        bar_len = 20  # 进度条长总度
        bar_str = ">" * round(bar_len * percent) + "=" * round(bar_len * (1 - percent))
        msg = "\r{:.2f}%\t[{}] {:.1f}/{:.1f}MB | {} ".format(
            percent * 100, bar_str, now_size / 1048576, total_size / 1048576, file_name,
        )
        if total_size == now_size:
            msg = msg + " <b>Done!</b>"
        self.download_proc.emit(msg)

    def setVal(self, isfile, isfolder, save_path):
        self.isfile = isfile
        self.isfolder = isfolder
        self.save_path = save_path
        self.start()

    def run(self):
        if self.isfolder:
            self._disk.download_dir2(self.isfolder, self.save_path, self._show_progress)
        elif self.isfile:
            self._disk.download_file2(
                self.isfile[0], self.save_path, self._show_progress
            )
