import os
from PyQt5.QtCore import QThread, pyqtSignal, QMutex
from lanzou.gui.workers.down import show_progress
from lanzou.api import LanZouCloud
from lanzou.debug import logger


class UploadWorker(QThread):
    '''文件上传线程'''
    code = pyqtSignal(str, int)
    update = pyqtSignal(dict)

    def __init__(self, parent=None):
        super(UploadWorker, self).__init__(parent)
        self._disk = None
        self._tasks = {}
        self._mutex = QMutex()
        self._is_work = False
        self._furl = ""
        self._task = None
        self._allow_big_file = False

    def _show_progress(self, file_name, total_size, now_size):
        """显示进度条的回调函数"""
        msg = show_progress(file_name, total_size, now_size, symbol="█")
        rate = int(1000 * now_size/total_size)
        self._task = self._task._replace(rate=rate)
        self.update.emit({self._furl: self._task})
        self.code.emit(msg, 0)

    def set_allow_big_file(self, allow_big_file):
        self._allow_big_file = allow_big_file

    def set_disk(self, disk):
        self._disk = disk

    def add_task(self, task):
        if task.furl not in self._tasks.keys():
            logger.debug(f"upload add one task: {task}")
            self._tasks[task.furl] = task
        self.start()

    def add_tasks(self, tasks: dict):
        logger.debug(f"upload add tasks: {tasks.values()}")
        self._tasks.update(tasks)
        self.start()

    def __del__(self):
        self.wait()

    def stop(self):  # 用于手动停止
        self._mutex.lock()
        self._is_work = False
        self._mutex.unlock()

    def run(self):
        if not self._is_work:
            self._mutex.lock()
            self._is_work = True
            while True:
                if not self._tasks:
                    logger.debug(f"upload finished!")
                    break
                self._furl = list(self._tasks.keys())[0]
                self._task = self._tasks[self._furl]
                logger.debug(f"run task: {self._task=}")
                if not os.path.exists(self._furl):
                    logger.error(f"upload file not exist : {self._furl}")
                    msg = f"<b>ERROR :</b> <font color='red'>文件不存在:{self._furl}</font>"
                    self.code.emit(msg, 3100)
                    continue
                if os.path.isdir(self._furl):
                    logger.error(f"upload dir : {self._furl}")
                    msg = f"<b>INFO :</b> <font color='#00CC00'>批量上传文件夹:{self._furl}</font>"
                    self.code.emit(msg, 30000)
                    self._disk.upload_dir(self._furl,
                                          self._task.id,
                                          self._show_progress,
                                          None,
                                          self._allow_big_file)
                else:
                    msg = f"<b>INFO :</b> <font color='#00CC00'>上传文件:{self._furl}</font>"
                    self.code.emit(msg, 20000)
                    try:
                        code, fid, isfile = self._disk.upload_file(self._task.furl,
                                                                   self._task.id,
                                                                   self._show_progress,
                                                                   self._allow_big_file)
                    except TimeoutError:
                        msg = "<b>ERROR :</b> <font color='red'>网络连接超时，请重试！</font>"
                        self.code.emit(msg, 3100)
                        self._task = self._task._replace(info="网络连接超时")
                        self.update.emit({self._furl: self._task})
                    except Exception as e:
                        logger.error(f"UploadWorker error: {e=}")
                        self._task = self._task._replace(info="未知错误")
                        self.update.emit({self._furl: self._task})
                    else:
                        self._task = self._task._replace(info="上传成功")
                        if code == LanZouCloud.SUCCESS:
                            if self._task.set_pwd:
                                self._disk.set_passwd(fid, self._task.pwd, is_file=isfile)
                            if self._task.set_desc:
                                self._disk.set_desc(fid, self._task.desc, is_file=isfile)
                del self._tasks[self._furl]
            self._is_work = False
            self._mutex.unlock()
