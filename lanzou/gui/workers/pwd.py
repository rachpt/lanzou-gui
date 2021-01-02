from PyQt5.QtCore import QThread, pyqtSignal, QMutex
from lanzou.api import LanZouCloud
from lanzou.debug import logger


class SetPwdWorker(QThread):
    '''设置文件(夹)提取码 线程'''
    msg = pyqtSignal(str, int)
    update = pyqtSignal(object, object, object, object)

    def __init__(self, parent=None):
        super(SetPwdWorker, self).__init__(parent)
        self._disk = None
        self.infos = []
        self._work_id = -1
        self._mutex = QMutex()
        self._is_work = False

    def set_disk(self, disk):
        self._disk = disk

    def set_values(self, infos, work_id):
        self.infos = infos
        self._work_id = work_id
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
                has_file = False
                has_folder = False
                failed = False
                failed_code = ""
                for infos in self.infos:
                    if infos.is_file:  # 文件
                        has_file = True
                        new_pwd = infos.new_pwd
                        if 2 > len(new_pwd) >= 1 or len(new_pwd) > 6:
                            self.msg.emit("文件提取码为2-6位字符,关闭请留空！", 4000)
                            raise UserWarning
                    else:  # 文件夹
                        has_folder = True
                        new_pwd = infos.new_pwd
                        if 2 > len(new_pwd) >= 1 or len(new_pwd) > 12:
                            self.msg.emit("文件夹提取码为0-12位字符,关闭请留空！", 4000)
                            raise UserWarning
                    res = self._disk.set_passwd(infos.id, infos.new_pwd, infos.is_file)
                    if res != LanZouCloud.SUCCESS:
                        failed_code = failed_code + str(res)
                        failed = True
                if failed:
                    self.msg.emit(f"❌部分提取码变更失败:{failed_code}，请勿使用特殊符号!", 4000)
                else:
                    self.msg.emit("✅提取码变更成功！♬", 3000)

                self.update.emit(self._work_id, has_file, has_folder, False)
            except TimeoutError:
                self.msg.emit("网络超时，请稍后重试！", 6000)
            except UserWarning:
                pass
            except Exception as e:
                logger.error(f"SetPwdWorker error: e={e}")
            self._is_work = False
            self._mutex.unlock()
        else:
            self.msg.emit("后台正在运行，请稍后重试！", 3100)
