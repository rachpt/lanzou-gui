from time import sleep, time
from random import uniform
from PyQt5.QtCore import QThread, pyqtSignal, QMutex

from lanzou.gui.workers.down import Downloader
from lanzou.gui.workers.upload import Uploader
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
    def __init__(self, task, parent=None):
        super(Callback, self).__init__(parent)
        self._task = task
        self._mutex = QMutex()
        self._stopped = True
        self._emit_msg = ''

    @property
    def emit_msg(self):
        return self._emit_msg

    def run(self):
        if self._stopped:
            self._mutex.lock()
            self._stopped = False
            old_size = self._task.now_size
            old_rate = int(1000 * old_size / self._task.total_size)
            old_time = time()
            sleep(uniform(0.5, 2))
            now_size = self._task.now_size
            now_rate = int(1000 * now_size / self._task.total_size)
            now_time = time()
            if old_size != now_size and old_rate != now_rate:
                speed = change_size_unit((now_size - old_size) / (now_time - old_time)) + '/s'
                self._task.speed = speed
                self._task.rate = now_rate
                self._emit_msg = show_progress(self._task.name, self._task.total_size, self._task.now_size, speed)
            self._stopped = True
            self._mutex.unlock()


class TaskManager(QThread):
    """任务控制器线程，控制后台上传下载"""
    mgr_msg = pyqtSignal(str, int)
    mgr_finished = pyqtSignal(int)
    update = pyqtSignal()

    def __init__(self, thread=3, parent=None):
        super(TaskManager, self).__init__(parent)
        self._disk = None
        self._tasks = {}
        self._queues = []
        self._thread = thread
        self._count = 0
        self._mutex = QMutex()
        self._is_work = False
        self._old_msg = ""
        self._workers = {}
        self._allow_big_file = False

    def set_allow_big_file(self, allow_big_file):
        self._allow_big_file = allow_big_file

    def set_disk(self, disk):
        self._disk = disk

    def set_thread(self, thread):
        self._thread = thread

    def stop_task(self, task):
        """暂停任务"""
        if task.url in self._workers and self._workers[task.url].isRunning():
            logger.debug(f"Stop job: {task.url}")
            try:
                self._tasks[task.url].pause = True
                self._workers[task.url].stop()
                self._tasks[task.url].run = False
            except Exception as err:
                logger.error(f"Stop task: err={err}")
        else:
            logger.debug(f"Stop job: {task.url} is not running!")
        self.update.emit()

    def start_task(self, task):
        """开始已暂停任务"""
        if task.url not in self._workers:
            self.add_task(task)
        elif not self._workers[task.url].isRunning():
            logger.debug(f"Start job: {task}")
            self._workers[task.url].start()
            self._tasks[task.url].run = True
            self._tasks[task.url].pause = False
            self.update.emit()
        self.start()

    def add_task(self, task):
        logger.debug(f"TaskMgr add one: added={task.added}, pause={task.pause}")
        if task.url not in self._tasks.keys():
            self._tasks[task.url] = task
        task.added = False
        task.pause = False
        task.info = None
        self.start()

    def add_tasks(self, tasks: dict):
        logger.debug(f"TaskMgr add: tasks={tasks}")
        self._tasks.update(tasks)
        self.start()

    def del_task(self, task):
        logger.debug(f"TaskMgr del: url={task.url}")
        if task in self._queues:
            self._queues.remove(task)
        if task.url in self._tasks:
            del self._tasks[task.url]
        if task.url in self._workers:
            del self._workers[task.url]

    def _task_to_queue(self):
        for task in self._tasks.values():
            if not task.added and not task.pause and task not in self._queues:
                logger.debug(f"TaskMgr task2queue: url={task.url}")
                self._queues.append(task)
                task.added = True

    def __del__(self):
        self.wait()

    def _ahead_msg(self, msg):
        if self._old_msg != msg:
            if self._count == 1:
                self.mgr_msg.emit(msg, 0)
            else:
                self.mgr_msg.emit(f"有{self._count}个后台任务正在运行", 0)
            self._old_msg = msg

    def _ahead_error(self):
        self.update.emit()

    def _ahead_folder_error(self, code, file):
        # 需要单独考虑，不在 task中
        pass

    def _update_emit(self):
        self.update.emit()

    def _add_thread(self, task):
        self.update.emit()
        logger.debug(f"TaskMgr count: count={self._count}")
        self._count -= 1
        del self._workers[task.url]
        # 发送所有任务完成信号
        failed_task_num = 0
        for task in self._tasks.values():
            if not task.info:
                if task.rate < 1000:
                    return None
            else:
                failed_task_num += 1
        logger.debug(f"TaskMgr all finished!: failed_task_num={failed_task_num}")
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
                logger.debug(f"TaskMgr run: url={task.url}")
                if task.type == 'dl':
                    self._workers[task.url] = Downloader(self._disk, task, Callback)
                    self.mgr_msg.emit(f"准备下载：<font color='#FFA500'>{task.name}</font>", 0)
                else:
                    self._workers[task.url] = Uploader(self._disk, task, Callback, self._allow_big_file)
                    self.mgr_msg.emit(f"准备上传：<font color='#FFA500'>{task.name}</font>", 0)
                try:
                    self._workers[task.url].finished_.connect(self._add_thread)
                    self._workers[task.url].proc.connect(self._ahead_msg)
                    self._workers[task.url].update.connect(self._update_emit)
                    self._workers[task.url].folder_file_failed.connect(self._ahead_folder_error)
                    self._workers[task.url].failed.connect(self._ahead_error)
                    self._workers[task.url].start()
                except Exception as err:
                    logger.error(f"TaskMgr Error: err={err}")
            self._is_work = False
            self._mutex.unlock()
