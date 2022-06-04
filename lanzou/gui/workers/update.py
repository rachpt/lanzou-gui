from time import sleep
import re
import requests
from PyQt6.QtCore import QThread, pyqtSignal, QMutex
from lanzou.debug import logger


class CheckUpdateWorker(QThread):
    '''检测软件更新'''
    infos = pyqtSignal(object, object)
    bg_update_infos = pyqtSignal(object, object)

    def __init__(self, parent=None):
        super(CheckUpdateWorker, self).__init__(parent)
        self._ver = ''
        self._manual = False
        self._mutex = QMutex()
        self._is_work = False
        self._folder_id = None
        self._api = 'https://api.github.com/repos/rachpt/lanzou-gui/releases/latest'
        self._api_mirror = 'https://gitee.com/api/v5/repos/rachpt/lanzou-gui/releases/latest'

    def set_values(self, ver: str, manual: bool=False):
        # 检查更新
        self._ver = ver
        self._manual = manual
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
            resp = None
            try:
                resp = requests.get(self._api).json()
            except (requests.RequestException, TimeoutError, requests.exceptions.ConnectionError):
                logger.debug("chcek update from github error")
                try: resp = requests.get(self._api_mirror).json()
                except:
                    logger.debug("chcek update from gitee error")
            except Exception as e:
                logger.error(f"CheckUpdateWorker error: e={e}")
            if resp:
                try:
                    tag_name, msg = resp['tag_name'], resp['body']
                    ver = self._ver.replace('v', '').split('-')[0].split('.')
                    ver2 = tag_name.replace('v', '').split('-')[0].split('.')
                    local_version = int(ver[0]) * 100 + int(ver[1]) * 10 + int(ver[2])
                    remote_version = int(ver2[0]) * 100 + int(ver2[1]) * 10 + int(ver2[2])
                    if remote_version > local_version:
                        urls = re.findall(r'https?://[-\.a-zA-Z0-9/_#?&%@]+', msg)
                        for url in urls:
                            new_url = f'<a href="{url}">{url}</a>'
                            msg = msg.replace(url, new_url)
                        msg = msg.replace('\n', '<br />')
                        self.infos.emit(tag_name, msg)
                        if not self._manual:  # 打开软件时检测更新
                            self.bg_update_infos.emit(tag_name, msg)
                    elif self._manual:
                        self.infos.emit("0", "目前还没有发布新版本！")
                except AttributeError:
                    if self._manual:
                        self.infos.emit("v0.0.0", "检查更新时发生异常，请重试！")
                except Exception as e:
                    logger.error(f"Check Update Version error: e={e}")
            else:
                if self._manual:
                    self.infos.emit("v0.0.0", f"检查更新时 <a href='{self._api}'>api.github.com</a>、<a href='{self._api_mirror}'>gitee.com</a> 拒绝连接，请稍后重试！")
            self._manual = False
            self._is_work = False
            self._mutex.unlock()
        else:
            if self._manual:
                self.infos.emit("v0.0.0", "后台正在运行，请稍等！")
