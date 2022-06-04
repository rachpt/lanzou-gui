from PyQt6.QtCore import QThread, pyqtSignal, QMutex
from lanzou.api import LanZouCloud

from lanzou.gui.models import Infos
from lanzou.debug import logger


class GetMoreInfoWorker(QThread):
    '''获取文件直链、文件(夹)提取码描述，用于登录后显示更多信息'''
    infos = pyqtSignal(object)
    share_url = pyqtSignal(object)
    dl_link = pyqtSignal(object)
    msg = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super(GetMoreInfoWorker, self).__init__(parent)
        self._disk = None
        self._infos = None
        self._url = ''
        self._pwd = ''
        self._emit_link = False
        self._mutex = QMutex()
        self._is_work = False

    def set_disk(self, disk):
        self._disk = disk

    def set_values(self, infos, emit_link=False):
        self._infos = infos
        self._emit_link = emit_link
        self.start()

    def get_dl_link(self, url, pwd):
        self._url = url
        self._pwd = pwd
        self.start()

    def __del__(self):
        self.wait()

    def stop(self):
        self._mutex.lock()
        self._is_work = False
        self._mutex.unlock()

    def run(self):
        # infos: ID/None，文件名，大小，日期，下载次数(dl_count)，提取码(pwd)，描述(desc)，|链接(share-url)
        if not self._is_work and self._infos:
            self._mutex.lock()
            self._is_work = True
            try:
                if not self._url:  # 获取普通信息
                    if isinstance(self._infos, Infos):
                        if self._infos.id:  # 从 disk 运行
                            self.msg.emit("网络请求中，请稍候……", 0)
                            _info = self._disk.get_share_info(self._infos.id, is_file=self._infos.is_file)
                            self._infos.desc = _info.desc
                            self._infos.pwd = _info.pwd
                            self._infos.url = _info.url
                        if self._emit_link:
                            self.share_url.emit(self._infos)
                        else:
                            self.infos.emit(self._infos)
                        self.msg.emit("", 0)  # 删除提示信息
                else:  # 获取下载直链
                    res = self._disk.get_file_info_by_url(self._url, self._pwd)
                    if res.code == LanZouCloud.SUCCESS:
                        self.dl_link.emit("{}".format(res.durl or "无"))  # 下载直链
                    elif res.code == LanZouCloud.NETWORK_ERROR:
                        self.dl_link.emit("网络错误！获取失败")  # 下载直链
                    else:
                        self.dl_link.emit("其它错误！")  # 下载直链
            except TimeoutError:
                self.msg.emit("网络超时！稍后重试", 6000)
            except Exception as e:
                logger.error(f"GetMoreInfoWorker error: e={e}")
            self._is_work = False
            self._url = ''
            self._pwd = ''
            self._mutex.unlock()
        else:
            self.msg.emit("后台正在运行，请稍后重试！", 3100)
