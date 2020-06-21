from PyQt5.QtCore import QThread, pyqtSignal, QMutex

from lanzou.api.utils import is_folder_url, is_file_url
from lanzou.debug import logger


def show_progress(file_name, total_size, now_size, symbol="█"):
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
    bar_str = ("<font color='#00CC00'>" + symbol * round(bar_len * percent) +
               "</font><font color='#000080'>" + symbol * round(bar_len * (1 - percent)) + "</font>")
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
    '''单个文件下载线程'''
    download_proc = pyqtSignal(str)
    download_failed = pyqtSignal(object, object)
    folder_file_failed = pyqtSignal(object, object)
    download_rate = pyqtSignal(object, object)

    def __init__(self, parent=None):
        super(Downloader, self).__init__(parent)
        self._disk = None
        self._stopped = True
        self._mutex = QMutex()
        self.name = ""
        self.url = ""
        self.pwd = ""
        self.save_path = ""

    def set_disk(self, disk):
        self._disk = disk

    def stop(self):
        self._mutex.lock()
        self._stopped = True
        self._mutex.unlock()
        self.terminate()

    def _show_progress(self, file_name, total_size, now_size):
        """显示进度条的回调函数"""
        msg = show_progress(file_name, total_size, now_size)
        self.download_rate.emit(self.url, int(1000 * now_size/total_size))
        self.download_proc.emit(msg)

    def _down_failed(self, code, file):
        """显示下载失败的回调函数"""
        self.folder_file_failed.emit(code, file)

    def __del__(self):
        self.wait()

    def set_values(self, name, url, pwd, save_path):
        self.name = name
        self.url = url
        self.pwd = pwd
        self.save_path = save_path
        self.start()

    def run(self):
        try:
            if is_file_url(self.url):  # 下载文件
                res = self._disk.down_file_by_url(self.url, self.pwd, self.save_path, self._show_progress)
            elif is_folder_url(self.url):  # 下载文件夹
                res = self._disk.down_dir_by_url(self.url, self.pwd, self.save_path, self._show_progress,
                                                 mkdir=True, failed_callback=self._down_failed)
            else:
                return
            if res == 0:
                self.download_rate.emit(self.url, 1000)
            else:
                self.download_failed.emit(self.url, res)
            logger.debug(f"Download res: {res}")
        except TimeoutError:
            logger.error("Download TimeOut")
            self.download_failed.emit(self.url, "网络连接错误！")
        except Exception as e:
            logger.error(f"Download error: {e=}")
            self.download_failed.emit(self.url, f"未知错误！{e}")


class DownloadManager(QThread):
    '''下载控制器线程，追加下载任务，控制后台下载线程数量'''
    downloaders_msg = pyqtSignal(str, int)
    update = pyqtSignal(dict)

    def __init__(self, threads=3, parent=None):
        super(DownloadManager, self).__init__(parent)
        self._disk = None
        self._tasks = {}
        self._thread = threads
        self._count = 0
        self._mutex = QMutex()
        self._is_work = False
        self._old_msg = ""
        self._dl_ing = {}
        self.downloaders = {}

    def set_disk(self, disk):
        self._disk = disk

    def set_thread(self, thread):
        self._thread = thread

    def stop_task(self, task):
        if self.downloaders[task.url].isRunning():
            self.downloaders[task.url].stop()
            self._dl_ing[task.url] = self._dl_ing[task.url]._replace(run=False)
            logger.debug(f"Stop job: {task}")
            self.update.emit(self._dl_ing)

    def start_task(self, task):
        if task.url not in self.downloaders:
            self.add_task(task)
        elif not self.downloaders[task.url].isRunning():
            logger.debug(f"Start job: {task}")
            self.downloaders[task.url].start()
            self._dl_ing[task.url] = self._dl_ing[task.url]._replace(run=True)
            self.update.emit(self._dl_ing)

    def add_task(self, task):
        if task.url not in self._tasks.keys():
            logger.debug(f"DownloadMgr add one: {task=}")
            self._tasks[task.url] = task
        self.start()

    def add_tasks(self, tasks: dict):
        logger.debug(f"DownloadMgr add: {tasks=}")
        self._tasks.update(tasks)
        self.start()

    def __del__(self):
        self.wait()

    def del_task(self, url):
        logger.debug(f"DownloadMgr del: {url=}")
        if url in self._dl_ing:
            del self._dl_ing[url]
        if url in self.downloaders:
            del self.downloaders[url]

    def _ahead_msg(self, msg):
        if self._old_msg != msg:
            if self._count == 1:
                self.downloaders_msg.emit(msg, 0)
            else:
                self.downloaders_msg.emit(f"有{self._count}个下载任务正在运行", 0)
            self._old_msg = msg

    def _ahead_error(self, url, error):
        self._dl_ing[url] = self._dl_ing[url]._replace(info=error)
        self.update.emit(self._dl_ing)

    def _ahead_folder_error(self, code, file):
        # 需要单独考虑，不在 task中
        pass
        # self._dl_ing[file.url] = code
        # self._dl_ing.emit(self._dl_ing)

    def _ahead_rate(self, url, rate):
        self._dl_ing[url] = self._dl_ing[url]._replace(rate=rate)
        self.update.emit(self._dl_ing)

    def _add_thread(self, url):
        logger.debug(f"DownloadMgr count: {self._count}")
        self._count -= 1
        del self.downloaders[url]

    def stop(self):
        self._mutex.lock()
        self._is_work = False
        self._mutex.unlock()

    def run(self):
        if not self._is_work:
            self._mutex.lock()
            self._is_work = True
            while True:
                if not self._tasks:
                    break
                while self._count >= self._thread:
                    self.sleep(1)
                self._count += 1
                url = list(self._tasks.keys())[0]
                task = self._tasks[url]
                logger.debug(f"DownloadMgr run: {task=}")
                self.downloaders[url] = Downloader()
                self.downloaders[url].set_disk(self._disk)
                self.downloaders_msg.emit("准备下载：<font color='#FFA500'>{}</font>".format(task.name), 8000)
                try:
                    self.downloaders[url].finished.connect(lambda: self._add_thread(url))
                    self.downloaders[url].download_proc.connect(self._ahead_msg)
                    self.downloaders[url].download_rate.connect(self._ahead_rate)
                    self.downloaders[url].folder_file_failed.connect(self._ahead_folder_error)
                    self.downloaders[url].download_failed.connect(self._ahead_error)
                    self._dl_ing[url] = task._replace(run=True)
                    self.downloaders[url].set_values(task.name, task.url, task.pwd, task.path)
                except Exception as exp:
                    logger.error(f"DownloadMgr Error: {exp=}")
                del self._tasks[url]
            self._is_work = False
            self._mutex.unlock()
