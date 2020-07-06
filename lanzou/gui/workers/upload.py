import os
from PyQt5.QtCore import QThread, pyqtSignal, QMutex
from lanzou.api import LanZouCloud
from lanzou.debug import logger
from lanzou.gui.workers.down import Callback


class UploadWorker(QThread):
    '''文件上传线程'''
    upload_msg = pyqtSignal(str, int)
    upload_finished = pyqtSignal()
    update = pyqtSignal()

    def __init__(self, parent=None):
        super(UploadWorker, self).__init__(parent)
        self._disk = None
        self._tasks = {}
        self._queues = []
        self._mutex = QMutex()
        self._is_work = False
        self._allow_big_file = False

    def set_allow_big_file(self, allow_big_file):
        self._allow_big_file = allow_big_file

    def set_disk(self, disk):
        self._disk = disk

    def add_task(self, task):
        if task.url not in self._tasks.keys():
            logger.debug(f"upload add one task: {task}")
            self._tasks[task.url] = task
        task.added = False
        task.pause = False
        task.info = None
        self.start()

    def add_tasks(self, tasks: dict):
        logger.debug(f"upload add tasks: {tasks.values()}")
        self._tasks.update(tasks)
        self.start()

    def del_task(self, task):
        logger.debug(f"Uploader del: {task.url=}")
        # self.stop_task(task)
        if task.url in self._tasks:
            del self._tasks[task.url]

    def update_emit(self):
        self.update.emit()

    def download_proc_emit(self, msg):
        self.upload_msg.emit(msg, 0)

    def _task_to_queue(self):
        for task in self._tasks.values():
            if not task.added and not task.pause and task not in self._queues:
                logger.debug(f"Uploader task2queue: {task.url=}")
                self._queues.append(task)

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
                self._task_to_queue()
                if not self._queues:
                    logger.debug("upload finished!")
                    break
                task = self._queues.pop()
                task.added = True
                task.run = True
                logger.debug(f"Uploader run: {task.url=}")

                callback_thread = Callback(task)
                callback_thread.update.connect(self.update_emit)
                callback_thread.proc.connect(self.download_proc_emit)

                def callback():
                    """显示进度条的回调函数"""
                    callback_thread.start()

                if not os.path.exists(task.url):
                    logger.error(f"upload file not exist : {task.url}")
                    msg = f"<b>ERROR :</b> <font color='red'>文件不存在:{task.url}</font>"
                    self.upload_msg.emit(msg, 3100)
                    continue
                try:
                    if os.path.isdir(task.url):
                        logger.error(f"upload dir : {task.url}")
                        msg = f"<b>INFO :</b> <font color='#00CC00'>批量上传文件夹:{task.url}</font>"
                        self.upload_msg.emit(msg, 30000)
                        code, fid, isfile = self._disk.upload_dir(task,
                                                                callback,
                                                                self._allow_big_file)
                    else:
                        msg = f"<b>INFO :</b> <font color='#00CC00'>上传文件:{task.url}</font>"
                        self.upload_msg.emit(msg, 20000)
                        code, fid, isfile = self._disk.upload_file(task,
                                                                task.url,
                                                                task.fid,
                                                                callback,
                                                                self._allow_big_file)
                except TimeoutError:
                    msg = "<b>ERROR :</b> <font color='red'>网络连接超时，请重试！</font>"
                    self.upload_msg.emit(msg, 3100)
                    task.info = "网络连接超时"
                    self.update.emit()
                except Exception as e:
                    logger.error(f"UploadWorker error: {e=}")
                    task.info = "未知错误"
                    self.update.emit()
                else:
                    task.info = "上传成功"
                    if code == LanZouCloud.SUCCESS:
                        if task.pwd:
                            self._disk.set_passwd(fid, task.pwd, is_file=isfile)
                        if task.desc:
                            self._disk.set_desc(fid, task.desc, is_file=isfile)
                task.run = False
            self._is_work = False
            self.upload_finished.emit()
            self._mutex.unlock()
