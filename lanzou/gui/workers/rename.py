from time import sleep
from PyQt6.QtCore import QThread, pyqtSignal, QMutex
from lanzou.api import LanZouCloud
from lanzou.debug import logger


class RenameMkdirWorker(QThread):
    """重命名、修改简介与新建文件夹 线程"""
    # infos = pyqtSignal(object, object)
    msg = pyqtSignal(str, int)
    update = pyqtSignal(object, object, object, object)

    def __init__(self, parent=None):
        super(RenameMkdirWorker, self).__init__(parent)
        self._disk = None
        self._work_id = -1
        self._folder_list = None
        self.infos = None
        self._mutex = QMutex()
        self._is_work = False

    def set_disk(self, disk):
        self._disk = disk

    def set_values(self, infos, work_id, folder_list):
        self.infos = infos  # 对话框标识文件与文件夹
        self._work_id = work_id
        self._folder_list = folder_list
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

            action = self.infos[0]
            try:
                if action == 'new':  # 新建文件夹
                    new_name = self.infos[1]
                    new_des = self.infos[2]
                    if new_name in self._folder_list.keys():
                        self.msg.emit(f"文件夹已存在：{new_name}", 7000)
                    else:
                        res = self._disk.mkdir(self._work_id, new_name, new_des)
                        if res == LanZouCloud.MKDIR_ERROR:
                            self.msg.emit(f"创建文件夹失败：{new_name}", 7000)
                        else:
                            sleep(1.5)  # 暂停一下，否则无法获取新建的文件夹
                            self.update.emit(self._work_id, False, True, False)  # 此处仅更新文件夹，并显示
                            self.msg.emit(f"成功创建文件夹：{new_name}", 4000)
                else:  # 重命名、修改简介
                    has_file = False
                    has_folder = False
                    failed = False
                    for info in self.infos[1]:
                        if info.is_file:  # 修改文件描述
                            res = self._disk.set_desc(info.id, info.new_des, is_file=info.is_file)
                            if res == LanZouCloud.SUCCESS:
                                has_file = True
                            else:
                                failed = True
                        else:  # 修改文件夹，action == "folder"
                            name = info.new_name or info.nmae 
                            res = self._disk._set_dir_info(info.id, str(name), str(info.new_des))
                            if res == LanZouCloud.SUCCESS:
                                has_folder = True
                            else:
                                failed = True
                    self.update.emit(self._work_id, has_file, has_folder, False)
                    if failed:
                        self.msg.emit("有发生错误！", 6000)
                    else:
                        self.msg.emit("修改成功！", 4000)
            except TimeoutError:
                self.msg.emit("网络超时，请稍后重试！", 6000)
            except Exception as e:
                logger.error(f"RenameMikdirWorker error: e={e}")

            self._is_work = False
            self._mutex.unlock()
        else:
            self.msg.emit("后台正在运行，请稍后重试！", 3100)
