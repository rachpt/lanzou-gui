#!/usr/bin/env python3

import os
import re
from random import random
from PyQt5.QtCore import QThread, pyqtSignal, QMutex
from lanzou.api import LanZouCloud
from time import sleep


def show_progress(file_name, total_size, now_size, symbol="█"):
    """显示进度条的回调函数"""
    percent = now_size / total_size
    # 进度条长总度
    file_len = len(file_name)
    if file_len >= 20:
        bar_len = 20
    elif file_len >= 10:
        bar_len = 30
    else:
        bar_len = 40
    if total_size >= 1048576:
        unit = "MB"
        piece = 1048576
    else:
        unit = "KB"
        piece = 1024
    bar_str = ("<font color='#00CC00'>" + symbol * round(bar_len * percent) +
               "</font><font color='#000080'>" + symbol * round(bar_len * (1 - percent)) + "</font>")
    msg = "\r{:>5.1f}%\t[{}] {:.1f}/{:.1f}{} | {} ".format(
        percent * 100,
        bar_str,
        now_size / piece,
        total_size / piece,
        unit,
        file_name,
    )
    if total_size == now_size:
        msg = msg + "| <font color='blue'>Done!</font>"
    return msg


class Downloader(QThread):
    '''单个文件下载线程'''
    download_proc = pyqtSignal(str)

    def __init__(self, parent=None):
        super(Downloader, self).__init__(parent)
        self._stopped = True
        self._mutex = QMutex()
        self._disk = LanZouCloud()
        self.name = ""
        self.url = ""
        self.pwd = ""
        self.save_path = ""
        if os.name == 'nt':
            self._disk.set_rar_tool("./rar.exe")
        else:
            self._disk.set_rar_tool("/usr/bin/rar")

    def stop(self):
        self._mutex.lock()
        self._stopped = True
        self._mutex.unlock()

    def _show_progress(self, file_name, total_size, now_size):
        """显示进度条的回调函数"""
        msg = show_progress(file_name, total_size, now_size)
        self.download_proc.emit(msg)

    def __del__(self):
        self.wait()

    def set_values(self, name, url, pwd, save_path):
        self.name = name
        self.url = url
        self.pwd = pwd
        self.save_path = save_path

    def run(self):
        if self._disk.is_file_url(self.url):
            # 下载文件
            self._disk.down_file_by_url(self.url, self.pwd, self.save_path, self._show_progress)
        elif self._disk.is_folder_url(self.url):
            # 下载文件夹
            folder_path = self.save_path + os.sep + self.name
            os.makedirs(folder_path, exist_ok=True)
            self.save_path = folder_path
            self._disk.down_dir_by_url(self.url, self.pwd, self.save_path, self._show_progress)


class DownloadManager(QThread):
    '''下载控制器线程，追加下载任务，控制后台下载线程数量'''
    download_mgr_msg = pyqtSignal(str, int)
    downloaders_msg = pyqtSignal(str, int)

    def __init__(self, threads=3, parent=None):
        super(DownloadManager, self).__init__(parent)
        self.tasks = []
        self.save_path = ""
        self._thread = threads
        self._count = 0
        self._mutex = QMutex()
        self._is_work = False
        self._old_msg = ""

    def set_values(self, tasks, save_path, threads):
        self.tasks.extend(tasks)
        self.save_path = save_path
        self._thread = threads

    def __del__(self):
        self.wait()

    def ahead_msg(self, msg):
        if self._old_msg != msg:
            self.downloaders_msg.emit(msg, 0)
            self._old_msg = msg

    def add_task(self):
        self._count -= 1

    def stop(self):
        self._mutex.lock()
        self._is_work = False
        self._mutex.unlock()

    def run(self):
        if not self._is_work:
            self._mutex.lock()
            self._is_work = True
            downloader = {}
            while True:
                if not self.tasks:
                    break
                while self._count >= self._thread:
                    self.sleep(1)
                self._count += 1
                task = self.tasks.pop()
                dl_id = int(random() * 100000)
                downloader[dl_id] = Downloader()
                self.download_mgr_msg.emit("准备下载：<font color='#FFA500'>{}</font>".format(task[0]), 8000)
                try:
                    downloader[dl_id].finished.connect(self.add_task)
                    downloader[dl_id].download_proc.connect(self.ahead_msg)
                    downloader[dl_id].set_values(task[0], task[1], task[2], self.save_path)
                    downloader[dl_id].start()
                except Exception as exp:
                    print(exp)
            self._is_work = False
            self._mutex.unlock()


class GetSharedInfo(QThread):
    '''提取界面获取分享链接信息'''
    infos = pyqtSignal(object)
    msg = pyqtSignal(str, int)
    update = pyqtSignal()

    def __init__(self, parent=None):
        super(GetSharedInfo, self).__init__(parent)
        self._disk = LanZouCloud()
        self.share_url = ""
        self.pwd = ""
        self.is_file = ""
        self.is_folder = ""
        self._mutex = QMutex()
        self._is_work = False
        self._pat = r"(https?://(www\.)?lanzous.com/[bi][a-z0-9]+)[^0-9a-z]*([a-z0-9]+)?"

    def set_values(self, text):
        '''获取分享链接信息'''
        if not text:
            return
        for share_url, _, pwd in re.findall(self._pat, text):
            if LanZouCloud.is_file_url(share_url):  # 文件链接
                is_file = True
                is_folder = False
                self.msg.emit("正在获取文件链接信息……", 0)
            elif LanZouCloud.is_folder_url(share_url):  # 文件夹链接
                is_folder = True
                is_file = False
                self.msg.emit("正在获取文件夹链接信息，可能需要几秒钟，请稍后……", 0)
            else:
                self.msg.emit(f"{share_url} 为非法链接！", 0)
                self.btn_extract.setEnabled(True)
                self.line_share_url.setEnabled(True)
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
        show_time = 7000  # 提示显示时间，单位 ms
        if infos["code"] == LanZouCloud.FILE_CANCELLED:
            self.msg.emit("<font color='red'>文件不存在，或已删除！</font>", show_time)
        elif infos["code"] == LanZouCloud.URL_INVALID:
            self.msg.emit("<font color='red'>链接非法！</font>", show_time)
        elif infos["code"] == LanZouCloud.PASSWORD_ERROR:
            self.msg.emit("<font color='red'>提取码 [<b><font color='magenta'>{}</font></b>] 错误！</font>".format(self.pwd), show_time)
        elif infos["code"] == LanZouCloud.LACK_PASSWORD:
            self.msg.emit("<font color='red'>请在链接后面跟上提取码，空格分割！</font>", show_time)
        elif infos["code"] == LanZouCloud.NETWORK_ERROR:
            self.msg.emit("<font color='red'>网络错误！{}</font>".format(infos["info"]), show_time)
        elif infos["code"] == LanZouCloud.SUCCESS:
            self.msg.emit("<font color='#00CC00'>提取成功！</font>", show_time)

    def run(self):
        if not self._is_work:
            self._mutex.lock()
            self._is_work = True
            try:
                if self.is_file:  # 链接为文件
                    _infos = self._disk.get_share_file_info(self.share_url, self.pwd)
                    self.emit_msg(_infos)
                elif self.is_folder:  # 链接为文件夹
                    _infos = self._disk.get_share_folder_info(self.share_url, self.pwd)
                    self.emit_msg(_infos)
                self.infos.emit(_infos)
            except TimeoutError:
                self.msg.emit("font color='red'>网络超时！请稍后重试</font>", 8000)
            self._is_work = False
            self._mutex.unlock()
        else:
            self.msg.emit("<font color='blue'>后台正在运行，稍后重试！</font>", 3000)


class UploadWorker(QThread):
    '''文件上传线程'''
    code = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super(UploadWorker, self).__init__(parent)
        self._disk = object
        self.infos = []
        self._work_id = ""

    def _show_progress(self, file_name, total_size, now_size):
        """显示进度条的回调函数"""
        msg = show_progress(file_name, total_size, now_size, symbol="█")
        self.code.emit(msg, 0)

    def set_values(self, disk, infos, work_id):
        self._disk = disk
        self.infos = infos
        self._work_id = work_id

    def __del__(self):
        self.wait()

    def run(self):
        for f in self.infos:
            f = os.path.normpath(f)  # windows backslash
            if not os.path.exists(f):
                msg = "<b>ERROR :</b> <font color='red'>文件不存在:{}</font>".format(f)
                self.code.emit(msg, 0)
                continue
            if os.path.isdir(f):
                msg = "<b>INFO :</b> <font color='#00CC00'>批量上传文件夹:{}</font>".format(f)
                self.code.emit(msg, 0)
                self._disk.upload_dir(f, self._work_id, self._show_progress)
            else:
                msg = "<b>INFO :</b> <font color='#00CC00'>上传文件:{}</font>".format(f)
                self.code.emit(msg, 0)
                self._disk.upload_file(f, self._work_id, self._show_progress)


class LoginLuncher(QThread):
    '''登录线程'''
    code = pyqtSignal(bool, str, int)
    update_cookie = pyqtSignal(object)

    def __init__(self, disk, parent=None):
        super(LoginLuncher, self).__init__(parent)
        self._disk = disk
        self.username = ""
        self.password = ""
        self.cookie = None

    def set_values(self, username, password, cookie=None):
        self.username = username
        self.password = password
        self.cookie = cookie

    def __del__(self):
        self.wait()

    def run(self):
        if self.cookie:
            res = self._disk.login_by_cookie(self.cookie)
            if res == LanZouCloud.SUCCESS:
                self.code.emit(True, "<font color='#00CC00'>通过<b>Cookie</b>登录<b>成功</b>！ ≧◉◡◉≦</font>", 5000)
                return
        if (not self.username or not self.password) and not self.cookie:
            self.code.emit(False, "<font color='red'>登录失败: 没有用户或密码</font>", 3000)
        else:
            res = self._disk.login(self.username, self.password)
            if res == LanZouCloud.SUCCESS:
                self.code.emit(True, "<font color='#00CC00'>登录<b>成功</b>！ ≧◉◡◉≦</font>", 5000)
                _cookie = self._disk.get_cookie()
                self.update_cookie.emit(_cookie)
            else:
                self.code.emit(False, "<font color='red'>登录失败，可能是用户名或密码错误！</font>", 8000)
                self.update_cookie.emit(None)


class DescPwdFetcher(QThread):
    '''获取描述与提取码 线程'''
    desc = pyqtSignal(object, object, object)
    tasks = pyqtSignal(object)
    msg = pyqtSignal(object, object)

    def __init__(self, parent=None):
        super(DescPwdFetcher, self).__init__(parent)
        self._disk = object
        self.infos = None
        self.download = False
        self._mutex = QMutex()
        self._is_work = False

    def set_values(self, disk, infos, download=False):
        self._disk = disk
        self.infos = infos  # 列表的列表
        self.download = download  # 标识激发下载器
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
                _tasks = []
                for info in self.infos:
                    if info[0]:  # disk 运行
                        if info[2]:  # 文件
                            res = self._disk.get_share_info(info[0], is_file=True)
                        else:  # 文件夹
                            res = self._disk.get_share_info(info[0], is_file=False)
                        if res['code'] == LanZouCloud.SUCCESS:
                            if not self.download:  # 激发简介更新
                                self.desc.emit(res['desc'], res['pwd'], info)
                            info[5] = res['pwd']
                            info.append(res['url'])
                        elif res['code'] == LanZouCloud.NETWORK_ERROR:
                            self.msg.emit("网络错误，请稍后重试！", 6000)
                            continue
                    _task = (info[1], info[7], info[5])
                    if _task not in _tasks:
                        _tasks.append(_task)
                if self.download:
                    self.tasks.emit(_tasks) #)
            except TimeoutError:
                self.msg.emit("网络超时，请稍后重试！", 6000)
            except UserWarning:
                pass
            self._is_work = False
            self._mutex.unlock()
        else:
            self.msg.emit("后台正在运行指令！请稍后重试", 3000)


class ListRefresher(QThread):
    '''跟新目录文件与文件夹列表线程'''
    infos = pyqtSignal(object)
    err_msg = pyqtSignal(str, int)

    def __init__(self, disk, parent=None):
        super(ListRefresher, self).__init__(parent)
        self._disk = disk
        self._fid = -1
        self.r_files = True
        self.r_folders = True
        self.r_path = True
        self._mutex = QMutex()
        self._is_work = False

    def set_values(self, fid, r_files=True, r_folders=True, r_path=True):
        if not self._is_work:
            self._fid = fid
            self.r_files = r_files
            self.r_folders = r_folders
            self.r_path = r_path
            self.start()
        else:
            self.err_msg.emit("正在更新目录，请稍后再试！", 4000)

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
            emit_infos = {}
            # 传递更新内容
            emit_infos['r'] = {'fid': self._fid, 'files': self.r_files, 'folders': self.r_folders, 'path': self.r_path}
            try:
                if self.r_files:
                    info = {i['name']: [i['id'], i['name'], i['size'], i['time'], i['downs'], i['has_pwd'], i['has_des']] for i in self._disk.get_file_list(self._fid)}
                    emit_infos['file_list'] = {key: info.get(key) for key in sorted(info.keys())}  # {name-[id,...]}
                if self.r_folders:
                    info = {i['name']: [i['id'], i['name'],  "", "", "", i['has_pwd'], i['desc']] for i in self._disk.get_dir_list(self._fid)}
                    emit_infos['folder_list'] = {key: info.get(key) for key in sorted(info.keys())}  # {name-[id,...]}
                emit_infos['path_list'] = self._disk.get_full_path(self._fid)
            except TimeoutError:
                self.err_msg.emit("网络超时，无法更新目录，稍后再试！", 7000)
            else:
                self.infos.emit(emit_infos)
            self._is_work = False
            self._mutex.unlock()


class RemoveFilesWorker(QThread):
    '''删除文件(夹)线程'''
    msg = pyqtSignal(object, object)
    finished = pyqtSignal()

    def __init__(self, disk, parent=None):
        super(RemoveFilesWorker, self).__init__(parent)
        self._disk = disk
        self.infos = None
        self._mutex = QMutex()
        self._is_work = False

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
            self.finished.emit()
            self._is_work = False
            self._mutex.unlock()
        else:
            self.msg.emit("后台正在运行删除指令！", 2000)


class GetMoreInfoWorker(QThread):
    '''获取文件直链、文件(夹)提取码描述，用于登录后显示更多信息'''
    infos = pyqtSignal(object)
    msg = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super(GetMoreInfoWorker, self).__init__(parent)
        self._disk = LanZouCloud()
        self.old_infos = None
        self._mutex = QMutex()
        self._is_work = False

    def set_values(self, infos, disk=None):
        if disk:  # 登录情况
            self._disk = disk
        self.old_infos = infos
        self.start()

    def __del__(self):
        self.wait()

    def stop(self):
        self._mutex.lock()
        self._is_work = False
        self._mutex.unlock()

    def run(self):
        # infos: ID/None，文件名，大小，日期，下载次数(dl_count)，提取码(pwd)，描述(desc)，|链接(share-url)，直链
        if not self._is_work and self.old_infos:
            self._mutex.lock()
            self._is_work = True
            try:
                self.msg.emit("网络请求中，请稍后……", 0)
                if self.old_infos[0]:  # 从 disk 运行
                    if self.old_infos[2]:  # 文件
                        _info = self._disk.get_share_info(self.old_infos[0], is_file=True)
                    else:  # 文件夹
                        _info = self._disk.get_share_info(self.old_infos[0], is_file=False)
                    self.old_infos[5] = _info['pwd']
                    self.old_infos.append(_info['url'])
                if self.old_infos[2]:  # 是文件，解析下载直链
                    res = self._disk.get_file_info_by_url(self.old_infos[-1], self.old_infos[5])
                    if res["code"] == LanZouCloud.SUCCESS:
                        self.old_infos.append("{}".format(res["durl"] or "无"))  # 下载直链
                    elif res["code"] == LanZouCloud.NETWORK_ERROR:
                        self.old_infos.append("网络错误！获取失败")  # 下载直链
                    else:
                        self.old_infos.append("其它错误！")  # 下载直链
                else:
                    self.old_infos.append("无")  # 下载直链
                self.old_infos[5] = self.old_infos[5] or "无"  # 提取码
                self.infos.emit(self.old_infos)
                self.msg.emit("", 0)  # 删除提示信息
            except TimeoutError:
                self.msg.emit("网络超时！稍后重试", 6000)
            self._is_work = False
            self._mutex.unlock()
        else:
            self.msg.emit("后台正在运行，请稍后重试！", 2000)


class GetAllFoldersWorker(QThread):
    '''获取所有文件夹name与fid，用于文件移动'''
    infos = pyqtSignal(object, object)
    msg = pyqtSignal(str, int)
    moved = pyqtSignal()

    def __init__(self, parent=None):
        super(GetAllFoldersWorker, self).__init__(parent)
        self._disk = object
        self.org_infos = None
        self._mutex = QMutex()
        self._is_work = False
        self.move_infos = None

    def set_values(self, disk, org_infos):
        # 登录信息可能会有变化，重新给 disk
        self._disk = disk
        self.org_infos = org_infos  # 对话框标识文件与文件夹
        self.move_infos = None # 清除上次影响
        self.start()

    def move_file(self, info):
        '''移动文件至新的文件夹'''
        self.move_infos = info # file_id, folder_id, f_name
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
            if self.move_infos:  # 移动文件
                for info in self.move_infos:
                    try:
                        if self._disk.move_file(info[0], info[1]) == LanZouCloud.SUCCESS:
                            self.msg.emit(f"{info[2]} 移动成功！", 3000)
                            sleep(2.5)  # 等一段时间后才更新文件列表
                            self.moved.emit()
                        else:
                            self.msg.emit(f"移动文件{info[2]}失败！", 4000)
                    except TimeoutError:
                        self.msg.emit(f"移动文件{info[2]}失败，网络超时！请稍后重试", 5000)
            else:  # 获取所有文件夹
                try:
                    self.msg.emit("网络请求中，请稍后……", 0)
                    all_dirs_dict = self._disk.get_folder_id_list()
                    self.infos.emit(self.org_infos, all_dirs_dict)
                    self.msg.emit("", 0)  # 删除提示信息
                except TimeoutError:
                    self.msg.emit("网络超时！稍后重试", 6000)
            self._is_work = False
            self._mutex.unlock()
        else:
            self.msg.emit("后台正在运行，请稍后重试！", 2000)


class RenameMkdirWorker(QThread):
    """重命名、修改简介与新建文件夹 线程"""
    # infos = pyqtSignal(object, object)
    msg = pyqtSignal(str, int)
    update = pyqtSignal(object, object, object, object)

    def __init__(self, parent=None):
        super(RenameMkdirWorker, self).__init__(parent)
        self._disk = object
        self._work_id = -1
        self._folder_list = None
        self.infos = None
        self._mutex = QMutex()
        self._is_work = False

    def set_values(self, disk, infos, work_id, folder_list):
        # 登录信息可能会有变化，重新给 disk
        self._disk = disk
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
            fid = self.infos[1]
            new_name = self.infos[2]
            new_desc = self.infos[3]
            try:
                if not fid:  # 新建文件夹
                    if hasattr(self,'_folder_list') and new_name in self._folder_list.keys():
                        self.msg.emit(f"文件夹已存在：{new_name}", 7000)
                    else:
                        res = self._disk.mkdir(self._work_id, new_name, new_desc)
                        if res == LanZouCloud.MKDIR_ERROR:
                            self.msg.emit(f"创建文件夹失败：{new_name}", 7000)
                        else:
                            sleep(1.5)  # 暂停一下，否则无法获取新建的文件夹
                            self.update.emit(self._work_id, False, True, False)  # 此处仅更新文件夹，并显示
                            self.msg.emit(f"成功创建文件夹：{new_name}", 4000)
                else:  # 重命名、修改简介
                    if action == "file":  # 修改文件描述
                        res = self._disk.set_desc(fid, str(new_desc), is_file=True)
                    else:  # 修改文件夹，action == "folder"
                        _res = self._disk.get_share_info(fid, is_file=False)
                        if _res['code'] == LanZouCloud.SUCCESS:
                            res = self._disk._set_dir_info(fid, str(new_name), str(new_desc))
                        else:
                            res = _res['code']
                    if res == LanZouCloud.SUCCESS:
                        if action == "file":  # 只更新文件列表
                            self.update.emit(self._work_id, True, False, False)
                        else:  # 只更新文件夹列表
                            self.update.emit(self._work_id, False, True, False)
                        self.msg.emit("修改成功！", 4000)
                    elif res == LanZouCloud.FAILED:
                        self.msg.emit("失败：发生错误！", 6000)
            except TimeoutError:
                self.msg.emit("网络超时，请稍后重试！", 6000)

            self._is_work = False
            self._mutex.unlock()
        else:
            self.msg.emit("后台正在运行，请稍后重试！", 2000)


class SetPwdWorker(QThread):
    '''设置文件(夹)提取码 线程'''
    msg = pyqtSignal(str, int)
    update = pyqtSignal(object, object, object, object)

    def __init__(self, parent=None):
        super(SetPwdWorker, self).__init__(parent)
        self._disk = object
        self.infos = None
        self._work_id = -1
        self._mutex = QMutex()
        self._is_work = False

    def set_values(self, disk, infos, work_id):
        # 登录信息可能会有变化，重新给 disk
        self._disk = disk
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
            fid = self.infos[0]
            print(self.infos)
            new_pass = self.infos[1]
            try:
                if self.infos[2]:  # 文件
                    is_file = True
                    if 2 > len(new_pass) >= 1 or len(new_pass) > 6:
                        self.msg.emit("文件提取码为2-6位字符,关闭请留空！", 4000)
                        raise UserWarning
                else:  # 文件夹
                    is_file = False
                    if 2 > len(new_pass) >= 1 or len(new_pass) > 12:
                        self.msg.emit("文件夹提取码为0-12位字符,关闭请留空！", 4000)
                        raise UserWarning
                res = self._disk.set_passwd(fid, new_pass, is_file)
                if res == LanZouCloud.SUCCESS:
                    self.msg.emit("提取码变更成功！♬", 3000)
                elif res == LanZouCloud.NETWORK_ERROR:
                    self.msg.emit("网络错误，稍后重试！☒", 4000)
                else:
                    self.msg.emit("提取码变更失败❀╳❀:{}，请勿使用特殊符号!".format(res), 4000)
                self.update.emit(self._work_id, is_file, not is_file, False)
            except TimeoutError:
                self.msg.emit("网络超时，请稍后重试！", 6000)
            except UserWarning:
                pass
            self._is_work = False
            self._mutex.unlock()
        else:
            self.msg.emit("后台正在运行，请稍后重试！", 2000)


class LogoutWorker(QThread):
    '''获取所有文件夹name与fid，用于文件移动'''
    successed = pyqtSignal()
    msg = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super(LogoutWorker, self).__init__(parent)
        self._disk = object
        self.update_ui = True
        self._mutex = QMutex()
        self._is_work = False

    def set_values(self, disk, update_ui=True):
        # 登录信息可能会有变化，重新给 disk
        self._disk = disk
        self.update_ui = update_ui
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
                res = self._disk.logout()
                if res == LanZouCloud.SUCCESS:
                    if self.update_ui:
                        self.successed.emit()
                    self.msg.emit("已经退出登录！", 4000)
                else:
                    self.msg.emit("失败，请重试！", 5000)
            except TimeoutError:
                self.msg.emit("网络超时，请稍后重试！", 6000)
            self._is_work = False
            self._mutex.unlock()
        else:
            self.msg.emit("后台正在运行，请稍后重试！", 2000)
