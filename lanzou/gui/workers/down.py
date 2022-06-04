from PyQt6.QtCore import QThread, pyqtSignal, QMutex

from lanzou.api.utils import is_folder_url, is_file_url
from lanzou.api import why_error
from lanzou.debug import logger


class Downloader(QThread):
    '''单个文件下载线程'''
    finished_ = pyqtSignal(object)
    folder_file_failed = pyqtSignal(object, object)
    failed = pyqtSignal()
    proc = pyqtSignal(str)
    update = pyqtSignal()

    def __init__(self, disk, task, callback, parent=None):
        super(Downloader, self).__init__(parent)
        self._disk = disk
        self._task = task
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
            logger.error("Download task is empty!")
            return None
        self._task.run = True
        try:
            if is_file_url(self._task.url):  # 下载文件
                res = self._disk.down_file_by_url(self._task.url, self._task, self._callback)
            elif is_folder_url(self._task.url):  # 下载文件夹
                res = self._disk.down_dir_by_url(self._task, self._callback)
            else:
                raise UserWarning
            if res == 0:
                self._task.rate = 1000  # 回调线程可能在休眠
                self.update.emit()
            else:
                self._task.info = why_error(res)
                logger.debug(f"Download : res={res}")
                self.failed.emit()
        except TimeoutError:
            self._task.info = "网络连接错误！"
            logger.error("Download TimeOut")
            self.failed.emit()
        except Exception as err:
            self._task.info = f"未知错误！err={err}"
            logger.error(f"Download error: err={err}")
            self.failed.emit()
        except UserWarning: pass
        self._task.run = False
        self.finished_.emit(self._task)
