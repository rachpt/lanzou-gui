from time import sleep
from PyQt6.QtCore import QThread, pyqtSignal, QMutex
from lanzou.api import LanZouCloud
from lanzou.debug import logger


class GetAllFoldersWorker(QThread):
    '''获取所有文件夹name与fid，用于文件移动'''
    infos = pyqtSignal(object, object)
    msg = pyqtSignal(str, int)
    moved = pyqtSignal(bool, bool, bool)

    def __init__(self, parent=None):
        super(GetAllFoldersWorker, self).__init__(parent)
        self._disk = None
        self.org_infos = None
        self._mutex = QMutex()
        self._is_work = False
        self.move_infos = None

    def set_disk(self, disk):
        self._disk = disk

    def set_values(self, org_infos):
        self.org_infos = org_infos  # 对话框标识文件与文件夹
        self.move_infos = [] # 清除上次影响
        self.start()

    def move_file(self, infos):
        '''移动文件至新的文件夹'''
        self.move_infos = infos # file_id, folder_id, f_name, type(size)
        self.start()

    def __del__(self):
        self.wait()

    def stop(self):
        self._mutex.lock()
        self._is_work = False
        self._mutex.unlock()

    def move_file_folder(self, info, no_err:bool, r_files:bool, r_folders:bool):
        """移动文件(夹)"""
        # no_err 判断是否需要更新 UI
        if info.is_file:  # 文件
            if self._disk.move_file(info.id, info.new_id) == LanZouCloud.SUCCESS:
                self.msg.emit(f"{info.name} 移动成功！", 3000)
                no_err = True
                r_files = True
            else:
                self.msg.emit(f"移动文件{info.name}失败！", 4000)
        else:  # 文件夹
            if self._disk.move_folder(info.id, info.new_id) == LanZouCloud.SUCCESS:
                self.msg.emit(f"{info.name} 移动成功！", 3000)
                no_err = True
                r_folders = True
            else:
                self.msg.emit(f"移动文件夹 {info.name} 失败！移动的文件夹中不能包含子文件夹！", 4000)
        return no_err, r_files, r_folders

    def run(self):
        if not self._is_work:
            self._mutex.lock()
            self._is_work = True
            if self.move_infos:  # 移动文件
                no_err = False
                r_files = False
                r_folders = False
                for info in self.move_infos:
                    try:
                        no_err, r_files, r_folders = self.move_file_folder(info, no_err, r_files, r_folders)
                    except TimeoutError:
                        self.msg.emit(f"移动文件(夹) {info.name} 失败，网络超时！请稍后重试", 5000)
                    except Exception as e:
                        logger.error(f"GetAllFoldersWorker error: e={e}")
                        self.msg.emit(f"移动文件(夹) {info.name} 失败，未知错误！", 5000)
                if no_err:  # 没有错误就更新ui
                    sleep(2.1)  # 等一段时间后才更新文件列表
                    self.moved.emit(r_files, r_folders, False)
            else:  # 获取所有文件夹
                try:
                    self.msg.emit("网络请求中，请稍候……", 0)
                    all_dirs_dict = self._disk.get_move_folders().name_id
                    self.infos.emit(self.org_infos, all_dirs_dict)
                    self.msg.emit("", 0)  # 删除提示信息
                except TimeoutError:
                    self.msg.emit("网络超时！稍后重试", 6000)
                except Exception as e:
                    logger.error(f"GetAllFoldersWorker error: e={e}")
            self._is_work = False
            self._mutex.unlock()
        else:
            self.msg.emit("后台正在运行，请稍后重试！", 3100)
