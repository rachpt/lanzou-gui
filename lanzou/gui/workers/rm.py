from PyQt6.QtCore import QThread, pyqtSignal, QMutex
from lanzou.debug import logger


class RemoveFilesWorker(QThread):
    '''删除文件(夹)线程'''
    msg = pyqtSignal(object, object)
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super(RemoveFilesWorker, self).__init__(parent)
        self._disk = None
        self.infos = None
        self._mutex = QMutex()
        self._is_work = False

    def set_disk(self, disk):
        self._disk = disk

    def set_values(self, infos):
        self.infos = infos
        self.start()

    def __del__(self):
        self.wait()

    def stop(self):
        self._mutex.lock()
        self._is_work = False
        self._mutex.unlock()

    def run(self):
        if not self._is_work:
            self._mutex.lock()
            self._is_work = True
            if not self.infos:
                self._is_work = False
                self._mutex.unlock()
                return
            for i in self.infos:
                try:
                    self._disk.delete(i['fid'], i['is_file'])
                except TimeoutError:
                    self.msg.emit(f"删除 {i['name']} 因网络超时失败！", 3000)
                except Exception as e:
                    logger.error(f"RemoveFileWorker error: e={e}")
            self.finished.emit()
            self._is_work = False
            self._mutex.unlock()
        else:
            self.msg.emit("后台正在运行删除指令！", 3100)
