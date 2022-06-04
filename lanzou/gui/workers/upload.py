import os
from PyQt6.QtCore import QThread, pyqtSignal, QMutex
from lanzou.api import LanZouCloud
from lanzou.debug import logger


class Uploader(QThread):
    '''单个文件上传线程'''
    finished_ = pyqtSignal(object)
    folder_file_failed = pyqtSignal(object, object)
    failed = pyqtSignal()
    proc = pyqtSignal(str)
    update = pyqtSignal()

    def __init__(self, disk, task, callback, allow_big_file=False, parent=None):
        super(Uploader, self).__init__(parent)
        self._disk = disk
        self._task = task
        self._allow_big_file = allow_big_file
        self._callback_thread = callback(task)

    def stop(self):
        self.terminate()

    def _callback(self):
        """显示进度条的回调函数"""
        if not self._callback_thread.isRunning():
            self.update.emit()
            self.proc.emit(self._callback_thread.emit_msg)
            self._callback_thread.start()

    def _down_failed(self, code, file):
        """显示下载失败的回调函数"""
        self.folder_file_failed.emit(code, file)

    def __del__(self):
        self.wait()

    def run(self):
        if not self._task:
            logger.error("Upload task is empty!")
            return None
        self._task.run = True
        try:
            if os.path.isdir(self._task.url):
                code, fid, isfile = self._disk.upload_dir(self._task, self._callback, self._allow_big_file)
            else:
                code, fid, isfile = self._disk.upload_file(self._task, self._task.url, self._task.fid,
                                                           self._callback, self._allow_big_file)
        except TimeoutError:
            self._task.info = LanZouCloud.NETWORK_ERROR
            self.update.emit()
        except Exception as err:
            logger.error(f"Upload error: err={err}")
            self._task.info = err
            self.update.emit()
        else:
            if code == LanZouCloud.SUCCESS:
                if self._task.pwd:
                    self._disk.set_passwd(fid, self._task.pwd, is_file=isfile)
                if self._task.desc:
                    self._disk.set_desc(fid, self._task.desc, is_file=isfile)
                self._task.rate = 1000  # 回调线程可能在休眠
            else:
                self.failed.emit()
        self._task.run = False
        self.finished_.emit(self._task)
