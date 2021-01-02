from time import sleep
from PyQt5.QtCore import QThread, pyqtSignal, QMutex
from lanzou.api import LanZouCloud

from lanzou.api.types import RecFolder, RecFile
from lanzou.debug import logger


class GetRecListsWorker(QThread):
    '''获取回收站列表'''
    folders = pyqtSignal(object)
    infos = pyqtSignal(object, object)
    msg = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super(GetRecListsWorker, self).__init__(parent)
        self._disk = None
        self._mutex = QMutex()
        self._is_work = False
        self._folder_id = None

    def set_disk(self, disk):
        self._disk = disk

    def set_values(self, fid):
        # 用于获取回收站指定文件夹内文件信息
        self._folder_id = fid
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
            try:
                if self._folder_id:
                    file_lists = self._disk.get_rec_file_list(folder_id=self._folder_id)
                    self._folder_id = None
                    self.folders.emit(file_lists)
                    raise UserWarning
                dir_lists = self._disk.get_rec_dir_list()
                file_lists = self._disk.get_rec_file_list(folder_id=-1)
                self.infos.emit(dir_lists, file_lists)
                self.msg.emit("刷新列表成功！", 2000)
            except TimeoutError:
                self.msg.emit("网络超时，请稍后重试！", 6000)
            except UserWarning:
                pass
            except Exception as e:
                logger.error(f"GetRecListsWorker error: e={e}")
            self._is_work = False
            self._mutex.unlock()
        else:
            self.msg.emit("后台正在运行，请稍后重试！", 3100)


class RecManipulator(QThread):
    '''操作回收站'''
    msg = pyqtSignal(str, int)
    succeeded = pyqtSignal()

    def __init__(self, parent=None):
        super(RecManipulator, self).__init__(parent)
        self._disk = None
        self._mutex = QMutex()
        self._is_work = False
        self._action = None
        self._folders = []
        self._files= []

    def set_disk(self, disk):
        self._disk = disk

    def set_values(self, infos, action):
        # 操作回收站选定行
        self._action = None
        self._folders = []
        self._files= []
        for item in infos:
            if isinstance(item, RecFile):
                self._files.append(item.id)
            elif isinstance(item, RecFolder):
                self._folders.append(item.id)
        self._action = action
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
            try:
                res = None
                if self._action == "recovery":
                    if self._files or self._folders:
                        res = self._disk.recovery_multi(self._files, self._folders)
                        if res == LanZouCloud.SUCCESS:
                            self.msg.emit("选定文件(夹)恢复成功，即将刷新列表", 2500)
                elif self._action == "delete":
                    if self._files or self._folders:
                        if self._files or self._folders:
                            res = self._disk.delete_rec_multi(self._files, self._folders)
                            if res == LanZouCloud.SUCCESS:
                                self.msg.emit("选定文件(夹)彻底删除成功，即将刷新列表", 2500)
                elif self._action == "clean":
                    res = self._disk.clean_rec()
                    if res == LanZouCloud.SUCCESS:
                        self.msg.emit("清空回收站成功，即将刷新列表", 2500)
                elif self._action == "recovery_all":
                    res = self._disk.recovery_all()
                    if res == LanZouCloud.SUCCESS:
                        self.msg.emit("文件(夹)全部还原成功，即将刷新列表", 2500)
                if isinstance(res, int):
                    if res == LanZouCloud.FAILED:
                        self.msg.emit("失败，请重试！", 4500)
                    elif res == LanZouCloud.NETWORK_ERROR:
                        self.msg.emit("网络错误，请稍后重试！", 4500)
                    else:
                        sleep(2.6)
                        self.succeeded.emit()
            except TimeoutError:
                self.msg.emit("网络超时，请稍后重试！", 6000)
            except Exception as e:
                logger.error(f"RecManipulator error: e={e}")
            self._is_work = False
            self._action = None
            self._folders = []
            self._files= []
            self._mutex.unlock()
        else:
            self.msg.emit("后台正在运行，请稍后重试！", 3100)
