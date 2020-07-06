from time import time, sleep
from PyQt5.QtCore import QThread, pyqtSignal, QMutex

from lanzou.api.utils import is_folder_url, is_file_url
from lanzou.api import why_error
from lanzou.debug import logger


def change_size_unit(total):
    if total < 1 << 10:
        return "{:.2f} B".format(total)
    elif total < 1 << 20:
        return "{:.2f} KB".format(total / (1 << 10))
    elif total < 1 << 30:
        return "{:.2f} MB".format(total / (1 << 20))
    else:
        return "{:.2f} GB".format(total / (1 << 30))


def show_progress(file_name, total_size, now_size, speed=0, symbol="█"):
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
    bar_str = ("<font color='#00CC00'>" + symbol * round(bar_len * percent)
               + "</font><font color='#000080'>" + symbol * round(bar_len * (1 - percent)) + "</font>")
    msg = "\r{:>5.1f}%\t[{}] {:.1f}/{:.1f}{} | {} | {} ".format(
        percent * 100,
        bar_str,
        now_size / piece,
        total_size / piece,
        unit,
        speed,
        file_name,
    )
    if total_size == now_size:
        msg = msg + "| <font color='blue'>Done!</font>"
    return msg


class Callback(QThread):
    '''回调显示进度'''
    proc = pyqtSignal(str)
    update = pyqtSignal()

    def __init__(self, task, parent=None):
        super(Callback, self).__init__(parent)
        self._task = task
        self._mutex = QMutex()
        self._stopped = True

    def run(self):
        if self._stopped:
            self._mutex.lock()
            self._stopped = False
            old_size = self._task.now_size
            old_rate = int(1000 * old_size / self._task.total_size)
            old_time = time()
            sleep(2)
            now_size = self._task.now_size
            now_rate = int(1000 * now_size / self._task.total_size)
            now_time = time()
            if old_size != now_size and old_rate != now_rate:
                speed = change_size_unit((now_size - old_size) / (now_time - old_time)) + '/s'
                self._task.speed = speed
                self._task.rate = now_rate
                self.update.emit()
                self.proc.emit(show_progress(self._task.name, self._task.total_size, self._task.now_size, speed))
            self._stopped = True
            self._mutex.unlock()


class Downloader(QThread):
    '''单个文件下载线程'''
    download_finished = pyqtSignal(object)
    folder_file_failed = pyqtSignal(object, object)
    download_failed = pyqtSignal()
    download_proc = pyqtSignal(str)
    update = pyqtSignal()

    def __init__(self, disk, task, parent=None):
        super(Downloader, self).__init__(parent)
        self._disk = disk
        self._task = task
        self._callback_thread = Callback(task)
        self._callback_thread.update.connect(self.update_emit)
        self._callback_thread.proc.connect(self.download_proc_emit)

    def stop(self):
        self.terminate()

    def update_emit(self):
        self.update.emit()

    def download_proc_emit(self, msg):
        self.download_proc.emit(msg)

    def _callback(self):
        """显示进度条的回调函数"""
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
                self._task.rate = 1000
                self.update.emit()
            else:
                self._task.info = why_error(res)
                logger.debug(f"Download : {res=}")
                self.download_failed.emit()
        except TimeoutError:
            self._task.info = "网络连接错误！"
            logger.error("Download TimeOut")
            self.download_failed.emit()
        except Exception as err:
            self._task.info = f"未知错误！{err=}"
            logger.error(f"Download error: {err=}")
            self.download_failed.emit()
        except UserWarning: pass
        self._task.run = False
        self.download_finished.emit(self._task)


class DownloadManager(QThread):
    '''下载控制器线程，追加下载任务，控制后台下载线程数量'''
    downloaders_msg = pyqtSignal(str, int)
    update = pyqtSignal()
    mgr_finished = pyqtSignal(int)

    def __init__(self, thread=3, parent=None):
        super(DownloadManager, self).__init__(parent)
        self._disk = None
        self._tasks = {}
        self._queues = []
        self._thread = thread
        self._count = 0
        self._mutex = QMutex()
        self._is_work = False
        self._old_msg = ""
        self.downloaders = {}

    def set_disk(self, disk):
        self._disk = disk

    def set_thread(self, thread):
        self._thread = thread

    def stop_task(self, task):
        """暂停任务"""
        if task.url in self.downloaders and self.downloaders[task.url].isRunning():
            logger.debug(f"Stop job: {task.url}")
            try:
                self._tasks[task.url].pause = True
                self.downloaders[task.url].stop()
                self._tasks[task.url].run = False
            except Exception as err:
                logger.error(f"Stop task: {err=}")
        else:
            logger.debug(f"Stop job: {task.url} is not running!")
        self.update.emit()

    def start_task(self, task):
        """开始已暂停任务"""
        if task.url not in self.downloaders:
            self.add_task(task)
        elif not self.downloaders[task.url].isRunning():
            logger.debug(f"Start job: {task}")
            self.downloaders[task.url].start()
            self._tasks[task.url].run = True
            self._tasks[task.url].pause = False
            self.update.emit()

    def add_task(self, task):
        logger.debug(f"DownloadMgr add one: {task.added=}, {task.pause=}")
        if task.url not in self._tasks.keys():
            self._tasks[task.url] = task
        task.added = False
        task.pause = False
        task.info = None
        self.start()

    def add_tasks(self, tasks: dict):
        logger.debug(f"DownloadMgr add: {tasks=}")
        self._tasks.update(tasks)
        self.start()

    def del_task(self, task):
        logger.debug(f"DownloadMgr del: {task.url=}")
        # self.stop_task(task)
        if task.url in self._tasks:
            del self._tasks[task.url]
        if task.url in self.downloaders:
            del self.downloaders[task.url]

    def _task_to_queue(self):
        for task in self._tasks.values():
            if not task.added and not task.pause and task not in self._queues:
                logger.debug(f"DownloadMgr task2queue: {task.url=}")
                self._queues.append(task)

    def __del__(self):
        self.wait()

    def _ahead_msg(self, msg):
        if self._old_msg != msg:
            if self._count == 1:
                self.downloaders_msg.emit(msg, 0)
            else:
                self.downloaders_msg.emit(f"有{self._count}个下载任务正在运行", 0)
            self._old_msg = msg

    def _ahead_error(self):
        self.update.emit()

    def _ahead_folder_error(self, code, file):
        # 需要单独考虑，不在 task中
        pass

    def _ahead_rate(self):
        self.update.emit()

    def _add_thread(self, task):
        self.update.emit()
        logger.debug(f"DownloadMgr count: {self._count=}")
        self._count -= 1
        del self.downloaders[task.url]
        # 发送所有任务完成信号
        failed_task_num = 0
        for task in self._tasks.values():
            if not task.info:
                if task.rate < 1000:
                    return None
            else:
                failed_task_num += 1
        logger.debug(f"DownloadMgr all finished!: {failed_task_num=}")
        self.mgr_finished.emit(failed_task_num)

    def stop(self):
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
                    break
                while self._count >= self._thread:
                    self.sleep(1)
                self._count += 1
                task = self._queues.pop()
                logger.debug(f"DownloadMgr run: {task.url=}")
                self.downloaders[task.url] = Downloader(self._disk, task)
                self.downloaders_msg.emit(f"准备下载：<font color='#FFA500'>{task.name}</font>", 0)
                try:
                    self.downloaders[task.url].download_finished.connect(self._add_thread)
                    self.downloaders[task.url].download_proc.connect(self._ahead_msg)
                    self.downloaders[task.url].update.connect(self._ahead_rate)
                    self.downloaders[task.url].folder_file_failed.connect(self._ahead_folder_error)
                    self.downloaders[task.url].download_failed.connect(self._ahead_error)
                    task.added = True
                    self.downloaders[task.url].start()
                except Exception as err:
                    logger.error(f"DownloadMgr Error: {err=}")
            self._is_work = False
            self._mutex.unlock()
