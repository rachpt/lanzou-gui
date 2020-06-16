import re
from PyQt5.QtCore import QThread, pyqtSignal, QMutex

from lanzou.api.utils import is_folder_url, is_file_url, logger
from lanzou.api import LanZouCloud


class GetSharedInfo(QThread):
    '''提取界面获取分享链接信息'''
    infos = pyqtSignal(object)
    msg = pyqtSignal(str, int)
    update = pyqtSignal()

    def __init__(self, parent=None):
        super(GetSharedInfo, self).__init__(parent)
        self._disk = None
        self.share_url = ""
        self.pwd = ""
        self.is_file = ""
        self.is_folder = ""
        self._mutex = QMutex()
        self._is_work = False
        self._pat = r"(https?://(\w[-\w]*\.)?lanzous.com/[bi]?[A-Za-z0-9]+)[^0-9a-z]*([a-z0-9]+)?"

    def set_disk(self, disk):
        self._disk = disk

    def set_values(self, text):
        '''获取分享链接信息'''
        if not text:
            return
        for share_url, _, pwd in re.findall(self._pat, text):
            if is_file_url(share_url):  # 文件链接
                is_file = True
                is_folder = False
                self.msg.emit("正在获取文件链接信息……", 20000)
            elif is_folder_url(share_url):  # 文件夹链接
                is_folder = True
                is_file = False
                self.msg.emit("正在获取文件夹链接信息，可能需要几秒钟，请稍后……", 30000)
            else:
                self.msg.emit(f"{share_url} 为非法链接！", 0)
                return
            self.update.emit()  # 清理旧的显示信息
            self.share_url = share_url
            self.pwd = pwd
            self.is_file = is_file
            self.is_folder = is_folder
            self.start()
            break

    def __del__(self):
        self.wait()

    def stop(self):  # 用于手动停止
        self._mutex.lock()
        self._is_work = False
        self._mutex.unlock()

    def emit_msg(self, infos):
        '''根据查询信息发送状态信号'''
        show_time = 2999  # 提示显示时间，单位 ms
        if infos.code == LanZouCloud.FILE_CANCELLED:
            self.msg.emit("<font color='red'>文件不存在，或已删除！</font>", show_time)
        elif infos.code == LanZouCloud.URL_INVALID:
            self.msg.emit("<font color='red'>链接非法！</font>", show_time)
        elif infos.code == LanZouCloud.PASSWORD_ERROR:
            self.msg.emit("<font color='red'>提取码 [<b><font color='magenta'>{}</font></b>] 错误！</font>".format(self.pwd), show_time)
        elif infos.code == LanZouCloud.LACK_PASSWORD:
            self.msg.emit("<font color='red'>请在链接后面跟上提取码，空格分割！</font>", show_time)
        elif infos.code == LanZouCloud.NETWORK_ERROR:
            self.msg.emit("<font color='red'>网络错误！{}</font>".format(infos["info"]), show_time)
        elif infos.code == LanZouCloud.SUCCESS:
            self.msg.emit("<font color='#00CC00'>提取成功！</font>", show_time)

    def run(self):
        if not self._is_work:
            self._mutex.lock()
            self._is_work = True
            try:
                if self.is_file:  # 链接为文件
                    _infos = self._disk.get_share_info_by_url(self.share_url, self.pwd)
                    self.emit_msg(_infos)
                elif self.is_folder:  # 链接为文件夹
                    _infos = self._disk.get_folder_info_by_url(self.share_url, self.pwd)
                    self.emit_msg(_infos)
                self.infos.emit(_infos)
            except TimeoutError:
                self.msg.emit("font color='red'>网络超时！请稍后重试</font>", 5000)
            except Exception as e:
                logger.error(f"GetShareInfo error: {e=}")
            self._is_work = False
            self._mutex.unlock()
        else:
            self.msg.emit("<font color='blue'>后台正在运行，稍后重试！</font>", 4000)
