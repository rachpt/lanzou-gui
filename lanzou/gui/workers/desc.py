from PyQt6.QtCore import QThread, pyqtSignal, QMutex
from lanzou.api import LanZouCloud

from lanzou.gui.models import DlJob
from lanzou.debug import logger


class DescPwdFetcher(QThread):
    '''获取描述与提取码 线程'''
    desc = pyqtSignal(object)
    tasks = pyqtSignal(object)
    msg = pyqtSignal(object, object)

    def __init__(self, parent=None):
        super(DescPwdFetcher, self).__init__(parent)
        self._disk = None
        self.infos = None
        self.download = False
        self.dl_path = ""
        self._mutex = QMutex()
        self._is_work = False

    def set_disk(self, disk):
        self._disk = disk

    def set_values(self, infos, download=False, dl_path=""):
        self.infos = infos  # 列表的列表
        self.download = download  # 标识激发下载器
        self.dl_path = dl_path
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
                if not self.infos:
                    raise UserWarning
                _tasks = {}
                _infos = []
                for info in self.infos:
                    if info.id:  # disk 运行
                        if info.is_file:  # 文件
                            res = self._disk.get_share_info(info.id, is_file=True)
                        else:  # 文件夹
                            res = self._disk.get_share_info(info.id, is_file=False)
                        if res.code == LanZouCloud.SUCCESS:
                            info.pwd = res.pwd
                            info.url = res.url
                            info.desc = res.desc
                        elif res.code == LanZouCloud.NETWORK_ERROR:
                            self.msg.emit("网络错误，请稍后重试！", 6000)
                            continue
                    _infos.append(info)  # info -> lanzou.gui.models.FileInfos
                    _tasks[info.url] = DlJob(infos=info, path=self.dl_path, total_file=1)
                if self.download:
                    self.tasks.emit(_tasks)
                else:  # 激发简介更新
                    self.desc.emit(_infos)
            except TimeoutError:
                self.msg.emit("网络超时，请稍后重试！", 6000)
            except UserWarning:
                pass
            except Exception as e:
                logger.error(f"GetPwdFetcher error: e={e}")
            self._is_work = False
            self._mutex.unlock()
        else:
            self.msg.emit("后台正在运行指令！请稍后重试", 3100)
