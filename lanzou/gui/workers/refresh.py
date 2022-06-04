from PyQt6.QtCore import QThread, pyqtSignal, QMutex
from lanzou.debug import logger


class ListRefresher(QThread):
    '''跟新目录文件与文件夹列表线程'''
    infos = pyqtSignal(object)
    err_msg = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super(ListRefresher, self).__init__(parent)
        self._disk = None
        self._fid = -1
        self.r_files = True
        self.r_folders = True
        self.r_path = True
        self._mutex = QMutex()
        self._is_work = False

    def set_disk(self, disk):
        self._disk = disk

    def set_values(self, fid, r_files=True, r_folders=True, r_path=True):
        if not self._is_work:
            self._fid = fid
            self.r_files = r_files
            self.r_folders = r_folders
            self.r_path = r_path
            self.start()
        else:
            self.err_msg.emit("正在更新目录，请稍后再试！", 3100)

    def __del__(self):
        self.wait()

    def stop(self):
        self._mutex.lock()
        self._is_work = False
        self._mutex.unlock()

    def goto_root_dir(self):
        self._fid = -1
        self.run()

    def run(self):
        if not self._is_work:
            self._mutex.lock()
            self._is_work = True
            emit_infos = {}
            # 传递更新内容
            emit_infos['r'] = {'fid': self._fid, 'files': self.r_files, 'folders': self.r_folders, 'path': self.r_path}
            try:
                if self.r_files:
                    # [i.id, i.name, i.size, i.time, i.downs, i.has_pwd, i.has_des]
                    info = {i.name: i for i in self._disk.get_file_list(self._fid)}
                    emit_infos['file_list'] = {key: info.get(key) for key in sorted(info.keys())}  # {name-File}
                if self.r_folders:
                    folders, full_path = self._disk.get_dir_list(self._fid)
                    if not full_path and not folders and self._fid != -1:
                        self.err_msg.emit(f"文件夹id {self._fid} 不存在，将切换到更目录", 2900)
                        self._is_work = False
                        self._mutex.unlock()
                        return self.goto_root_dir()
                    info = {i.name: i for i in folders}
                    emit_infos['folder_list'] = {key: info.get(key) for key in sorted(info.keys())}  # {name-Folder}
                    emit_infos['path_list'] = full_path
            except TimeoutError:
                self.err_msg.emit("网络超时，无法更新目录，稍后再试！", 7000)
            except Exception as e:
                self.err_msg.emit("未知错误，无法更新目录，稍后再试！", 7000)
                logger.error(f"ListRefresher error: e={e}")
            else:
                self.infos.emit(emit_infos)
            self._is_work = False
            self._mutex.unlock()
