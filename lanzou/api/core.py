"""
蓝奏网盘 API，封装了对蓝奏云的各种操作，解除了上传格式、大小限制
"""

import os
import pickle
import re
import shutil
from threading import Thread
from time import sleep
from datetime import datetime
from urllib3 import disable_warnings
from random import shuffle, uniform
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from urllib3.exceptions import InsecureRequestWarning
from lanzou.api.models import FileList, FolderList
from lanzou.api.types import *
from lanzou.api.utils import *
from lanzou.debug import logger


__all__ = ['LanZouCloud']


class LanZouCloud(object):
    FAILED = -1
    SUCCESS = 0
    ID_ERROR = 1
    PASSWORD_ERROR = 2
    LACK_PASSWORD = 3
    ZIP_ERROR = 4
    MKDIR_ERROR = 5
    URL_INVALID = 6
    FILE_CANCELLED = 7
    PATH_ERROR = 8
    NETWORK_ERROR = 9
    CAPTCHA_ERROR = 10
    OFFICIAL_LIMITED = 11

    def __init__(self):
        self._session = requests.Session()
        self._timeout = 15  # 每个请求的超时(不包含下载响应体的用时)
        self._max_size = 100  # 单个文件大小上限 MB
        self._upload_delay = (0, 0)  # 文件上传延时
        self._host_url = 'https://pan.lanzouo.com'
        self._doupload_url = 'https://pc.woozooo.com/doupload.php'
        self._account_url = 'https://pc.woozooo.com/account.php'
        self._mydisk_url = 'https://pc.woozooo.com/mydisk.php'
        self._cookies = None
        self._headers = {
            'User-Agent': USER_AGENT,
            'Referer': 'https://pc.woozooo.com/mydisk.php',
            'Accept-Language': 'zh-CN,zh;q=0.9',  # 提取直连必需设置这个，否则拿不到数据
        }
        disable_warnings(InsecureRequestWarning)  # 全局禁用 SSL 警告

    def _get(self, url, **kwargs):
        for possible_url in self._all_possible_urls(url):
            try:
                kwargs.setdefault('timeout', self._timeout)
                kwargs.setdefault('headers', self._headers)
                return self._session.get(possible_url, verify=False, **kwargs)
            except requests.Timeout:
                logger.warning("Encountered timeout error while requesting network!")
                raise TimeoutError
            except (ConnectionError, requests.RequestException):
                logger.debug(f"Get {possible_url} failed, try another domain")

        return None

    def _post(self, url, data, **kwargs):
        for possible_url in self._all_possible_urls(url):
            try:
                kwargs.setdefault('timeout', self._timeout)
                kwargs.setdefault('headers', self._headers)
                return self._session.post(possible_url, data, verify=False, **kwargs)
            except requests.Timeout:
                logger.warning("Encountered timeout error while requesting network!")
                raise TimeoutError
            except (ConnectionError, requests.RequestException):
                logger.debug(f"Post to {possible_url} ({data}) failed, try another domain")

        return None

    def _get_response_host(self, info):
        """获取蓝奏响应的下载 host 域名"""
        new_host = info.get("is_newd", "")
        if new_host and new_host != self._host_url:
            self._host_url = new_host

    @staticmethod
    def _all_possible_urls(url: str) -> List[str]:
        """蓝奏云的主域名有时会挂掉, 此时尝试切换到备用域名"""
        available_domains = [
            'lanzouw.com',  # 鲁ICP备15001327号-7, 2021-09-02
            'lanzoui.com',  # 鲁ICP备15001327号-6, 2020-06-09
            'lanzoux.com'  # 鲁ICP备15001327号-5, 2020-06-09
        ]
        return [url.replace('lanzouo.com', d) for d in available_domains]


    def set_max_size(self, max_size=100) -> int:
        """设置单文件大小限制(会员用户可超过 100M)"""
        if max_size < 1:
            return LanZouCloud.FAILED
        self._max_size = max_size
        return LanZouCloud.SUCCESS

    def set_upload_delay(self, t_range: tuple) -> int:
        """设置上传大文件数据块时，相邻两次上传之间的延时，减小被封号的可能"""
        if 0 <= t_range[0] <= t_range[1]:
            self._upload_delay = t_range
            return LanZouCloud.SUCCESS
        return LanZouCloud.FAILED

    def login(self, username, passwd) -> int:
        """
        登录蓝奏云控制台[已弃用]
        对某些用户可能有用
        """
        self._session.cookies.clear()
        login_data = {"task": "3", "setSessionId": "", "setToken": "", "setSig": "",
                      "setScene": "", "uid": username, "pwd": passwd}
        phone_header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 5.0; SM-G900P Build/LRX21T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/82.0.4051.0 Mobile Safari/537.36"}
        html = self._get(self._account_url)
        if not html:
            return LanZouCloud.NETWORK_ERROR
        formhash = re.findall(r'name="formhash" value="(.+?)"', html.text)
        if not formhash:
            logger.error("formhash is None!")
            return LanZouCloud.FAILED
        login_data['formhash'] = formhash[0]
        html = self._post(self._mydisk_url, login_data, headers=phone_header)
        if not html:
            return LanZouCloud.NETWORK_ERROR
        try:
            if '成功' in html.json()['info']:
                self._cookies = html.cookies.get_dict()
                self._session.cookies.update(self._cookies)
                return LanZouCloud.SUCCESS
        except ValueError:
            pass
        return LanZouCloud.FAILED

    def get_cookie(self) -> dict:
        """获取用户 Cookie"""
        return self._cookies

    def login_by_cookie(self, cookie: dict) -> int:
        """通过cookie登录"""
        self._session.cookies.update(cookie)
        html = self._get(self._account_url)
        if not html:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.FAILED if '网盘用户登录' in html.text else LanZouCloud.SUCCESS

    def logout(self) -> int:
        """注销"""
        html = self._get(self._account_url, params={'action': 'logout'})
        if not html:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.SUCCESS if '退出系统成功' in html.text else LanZouCloud.FAILED

    def delete(self, fid, is_file=True) -> int:
        """把网盘的文件、无子文件夹的文件夹放到回收站"""
        post_data = {'task': 6, 'file_id': fid} if is_file else {'task': 3, 'folder_id': fid}
        result = self._post(self._doupload_url, post_data)
        if not result:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.SUCCESS if result.json()['zt'] == 1 else LanZouCloud.FAILED

    def clean_rec(self) -> int:
        """清空回收站"""
        post_data = {'action': 'delete_all', 'task': 'delete_all'}
        html = self._get(self._mydisk_url, params={'item': 'recycle', 'action': 'files'})
        if not html:
            return LanZouCloud.NETWORK_ERROR
        post_data['formhash'] = re.findall(r'name="formhash" value="(.+?)"', html.text)[0]  # 设置表单 hash
        html = self._post(self._mydisk_url + '?item=recycle', post_data)
        if not html:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.SUCCESS if '清空回收站成功' in html.text else LanZouCloud.FAILED

    def get_rec_dir_list(self) -> FolderList:
        """获取回收站文件夹列表"""
        # 回收站中文件(夹)名只能显示前 17 个中文字符或者 34 个英文字符，如果这些字符相同，则在文件(夹)名后添加 (序号) ，以便区分
        html = self._get(self._mydisk_url, params={'item': 'recycle', 'action': 'files'})
        if not html:
            return FolderList()
        dirs = re.findall(r'folder_id=(\d+).+?>&nbsp;(.+?)\.{0,3}</a>.*\n+.*<td.+?>(.+?)</td>.*\n.*<td.+?>(.+?)</td>',
                          html.text)
        all_dir_list = FolderList()  # 文件夹信息列表
        dir_name_list = []  # 文件夹名列表d
        counter = 1  # 重复计数器
        for fid, name, size, time in dirs:
            if name in dir_name_list:  # 文件夹名前 17 个中文或 34 个英文重复
                counter += 1
                name = f'{name}({counter})'
            else:
                counter = 1
            dir_name_list.append(name)
            all_dir_list.append(RecFolder(name, int(fid), size, time, None))
        return all_dir_list

    def get_rec_file_list(self, folder_id=-1) -> FileList:
        """获取回收站文件列表"""
        if folder_id == -1:  # 列出回收站根目录文件
            # 回收站文件夹中的文件也会显示在根目录
            html = self._get(self._mydisk_url, params={'item': 'recycle', 'action': 'files'})
            if not html:
                return FileList()
            html = remove_notes(html.text)
            files = re.findall(
                r'fl_sel_ids[^\n]+value="(\d+)".+?filetype/(\w+)\.gif.+?/>\s?(.+?)(?:\.{3})?</a>.+?<td.+?>([\d\-]+?)</td>',
                html, re.DOTALL)
            file_list = FileList()
            file_name_list = []
            counter = 1
            for fid, ftype, name, time in sorted(files, key=lambda x: x[2]):
                if not name.endswith(ftype):  # 防止文件名太长导致丢失了文件后缀
                    name = name + '.' + ftype

                if name in file_name_list:  # 防止长文件名前 17:34 个字符相同重名
                    counter += 1
                    name = f'{name}({counter})'
                else:
                    counter = 1
                    file_name_list.append(name)
                file_list.append(RecFile(name, int(fid), ftype, size='', time=time))
            return file_list
        else:  # 列出回收站中文件夹内的文件,信息只有部分文件名和文件大小
            para = {'item': 'recycle', 'action': 'folder_restore', 'folder_id': folder_id}
            html = self._get(self._mydisk_url, params=para)
            if not html or '此文件夹没有包含文件' in html.text:
                return FileList()
            html = remove_notes(html.text)
            files = re.findall(
                r'com/(\d+?)".+?filetype/(\w+)\.gif.+?/>&nbsp;(.+?)(?:\.{3})?</a> <font color="#CCCCCC">\((.+?)\)</font>',
                html)
            file_list = FileList()
            file_name_list = []
            counter = 1
            for fid, ftype, name, size in sorted(files, key=lambda x: x[2]):
                if not name.endswith(ftype):  # 防止文件名太长丢失后缀
                    name = name + '.' + ftype
                if name in file_name_list:
                    counter += 1
                    name = f'{name}({counter})'  # 防止文件名太长且前17个字符重复
                else:
                    counter = 1
                    file_name_list.append(name)
                file_list.append(RecFile(name, int(fid), ftype, size=size, time=''))
            return file_list

    def get_rec_all(self):
        """获取整理后回收站的所有信息"""
        root_files = self.get_rec_file_list()  # 回收站根目录文件列表
        folder_list = FolderList()  # 保存整理后的文件夹列表
        for folder in self.get_rec_dir_list():  # 遍历所有子文件夹
            this_folder = RecFolder(folder.name, folder.id, folder.size, folder.time, FileList())
            for file in self.get_rec_file_list(folder.id):  # 文件夹内的文件属性: name,id,type,size
                if root_files.find_by_id(file.id):  # 根目录存在同名文件
                    file_time = root_files.pop_by_id(file.id).time  # 从根目录删除, time 信息用来补充文件夹中的文件
                    file = file._replace(time=file_time)  # 不能直接更新 namedtuple, 需要 _replace
                    this_folder.files.append(file)
                else:  # 根目录没有同名文件(用户手动删了),文件还在文件夹中，只是根目录不显示，time 信息无法补全了
                    file = file._replace(time=folder.time)  # 那就设置时间为文件夹的创建时间
                    this_folder.files.append(file)
            folder_list.append(this_folder)
        return root_files, folder_list

    def delete_rec(self, fid, is_file=True) -> int:
        """彻底删除回收站文件(夹)"""
        # 彻底删除后需要 1.5s 才能调用 get_rec_file() ,否则信息没有刷新，被删掉的文件似乎仍然 "存在"
        if is_file:
            para = {'item': 'recycle', 'action': 'file_delete_complete', 'file_id': fid}
            post_data = {'action': 'file_delete_complete', 'task': 'file_delete_complete', 'file_id': fid}
        else:
            para = {'item': 'recycle', 'action': 'folder_delete_complete', 'folder_id': fid}
            post_data = {'action': 'folder_delete_complete', 'task': 'folder_delete_complete', 'folder_id': fid}

        html = self._get(self._mydisk_url, params=para)
        if not html:
            return LanZouCloud.NETWORK_ERROR
        # 此处的 formhash 与 login 时不同，不要尝试精简这一步
        post_data['formhash'] = re.findall(r'name="formhash" value="(\w+?)"', html.text)[0]  # 设置表单 hash
        html = self._post(self._mydisk_url + '?item=recycle', post_data)
        if not html:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.SUCCESS if '删除成功' in html.text else LanZouCloud.FAILED

    def delete_rec_multi(self, files, folders) -> int:
        """彻底删除回收站多个文件(夹)"""
        # 与 recovery_all 几乎一样，task 表单值不一样
        if not files and not folders:
            return LanZouCloud.FAILED
        para = {'item': 'recycle', 'action': 'files'}
        post_data = {'action': 'files', 'task': 'delete_complete_recycle'}
        if folders:
            post_data['fd_sel_ids[]'] = folders
        if files:
            post_data['fl_sel_ids[]'] = files
        html = self._get(self._mydisk_url, params=para)
        if not html:
            return LanZouCloud.NETWORK_ERROR
        post_data['formhash'] = re.findall(r'name="formhash" value="(\w+?)"', html.text)[0]  # 设置表单 hash
        html = self._post(self._mydisk_url + '?item=recycle', post_data)
        if not html:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.SUCCESS if '删除成功' in html.text else LanZouCloud.FAILED

    def recovery(self, fid, is_file=True) -> int:
        """从回收站恢复文件"""
        if is_file:
            para = {'item': 'recycle', 'action': 'file_restore', 'file_id': fid}
            post_data = {'action': 'file_restore', 'task': 'file_restore', 'file_id': fid}
        else:
            para = {'item': 'recycle', 'action': 'folder_restore', 'folder_id': fid}
            post_data = {'action': 'folder_restore', 'task': 'folder_restore', 'folder_id': fid}
        html = self._get(self._mydisk_url, params=para)
        if not html:
            return LanZouCloud.NETWORK_ERROR
        post_data['formhash'] = re.findall(r'name="formhash" value="(\w+?)"', html.text)[0]  # 设置表单 hash
        html = self._post(self._mydisk_url + '?item=recycle', post_data)
        if not html:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.SUCCESS if '恢复成功' in html.text else LanZouCloud.FAILED

    def recovery_multi(self, files, folders) -> int:
        """从回收站恢复多个文件(夹)"""
        if not files and not folders:
            return LanZouCloud.FAILED
        para = {'item': 'recycle', 'action': 'files'}
        post_data = {'action': 'files', 'task': 'restore_recycle'}
        if folders:
            post_data['fd_sel_ids[]'] = folders
        if files:
            post_data['fl_sel_ids[]'] = files
        html = self._get(self._mydisk_url, params=para)
        if not html:
            return LanZouCloud.NETWORK_ERROR
        post_data['formhash'] = re.findall(r'name="formhash" value="(.+?)"', html.text)[0]  # 设置表单 hash
        html = self._post(self._mydisk_url + '?item=recycle', post_data)
        if not html:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.SUCCESS if '恢复成功' in html.text else LanZouCloud.FAILED

    def recovery_all(self) -> int:
        """从回收站恢复所有文件(夹)"""
        para = {'item': 'recycle', 'action': 'restore_all'}
        post_data = {'action': 'restore_all', 'task': 'restore_all'}
        first_page = self._get(self._mydisk_url, params=para)
        if not first_page:
            return LanZouCloud.NETWORK_ERROR
        post_data['formhash'] = re.findall(r'name="formhash" value="(.+?)"', first_page.text)[0]  # 设置表单 hash
        second_page = self._post(self._mydisk_url + '?item=recycle', post_data)
        if not second_page:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.SUCCESS if '还原成功' in second_page.text else LanZouCloud.FAILED

    def get_file_list(self, folder_id=-1) -> FileList:
        """获取文件列表"""
        page = 1
        file_list = FileList()
        while True:
            post_data = {'task': 5, 'folder_id': folder_id, 'pg': page}
            resp = self._post(self._doupload_url, post_data)
            if not resp:  # 网络异常，重试
                continue
            else:
                resp = resp.json()
            if resp["info"] == 0:
                break  # 已经拿到了全部的文件信息
            else:
                page += 1  # 下一页
            # 文件信息处理
            if resp["zt"] == 9:  # login not
                logger.debug(f"Not login resp={resp}")
                break
            for file in resp["text"]:
                file_list.append(File(
                    id=int(file['id']),
                    name=file['name_all'].replace("&amp;", "&"),
                    time=file['time'],  # 上传时间
                    size=file['size'].replace(",", ""),  # 文件大小
                    type=file['name_all'].split('.')[-1],  # 文件类型
                    downs=int(file['downs']),  # 下载次数
                    has_pwd=True if int(file['onof']) == 1 else False,  # 是否存在提取码
                    has_des=True if int(file['is_des']) == 1 else False  # 是否存在描述
                ))
        return file_list

    def get_dir_list(self, folder_id=-1) -> Tuple[FolderList, FolderList]:
        """获取子文件夹列表与全路径"""
        folder_list = FolderList()
        path_list = FolderList()
        post_data = {'task': 47, 'folder_id': folder_id}
        resp = self._post(self._doupload_url, post_data)
        if resp:
            resp = resp.json()
            for folder in resp["text"]:
                if "fol_id" not in folder:  # 切换用户时，有可能得到的是一个字符串 (╥╯^╰╥)
                    continue
                folder_list.append(Folder(
                    id=int(folder['fol_id']),
                    name=folder['name'],
                    has_pwd=True if int(folder['onof']) == 1 else False,
                    desc=folder['folder_des'][1:-1]
                ))
            if folder_id == -1 or resp["info"]:  # 如果 folder_id 有误，就返回空 list
                path_list.append(FolderId('LanZouCloud', -1, '根目录', -1))
            for folder in resp["info"]:
                if "folderid" not in folder:
                    continue
                path_list.append(FolderId(
                    name=folder['name'],
                    id=int(folder['folderid']),
                    desc=folder['folder_des'][1:-1],
                    now=int(folder['now'])
                ))
        return folder_list, path_list

    def clean_ghost_folders(self):
        """清除网盘中的幽灵文件夹"""

        # 可能有一些文件夹，网盘和回收站都看不见它，但是它确实存在，移动文件夹时才会显示
        # 如果不清理掉，不小心将文件移动进去就完蛋了
        def _clean(fid):
            for folder in self.get_dir_list(fid):
                real_folders.append(folder)
                _clean(folder.id)

        folder_with_ghost = self.get_move_folders()
        folder_with_ghost.pop_by_id(-1)  # 忽视根目录
        real_folders = FolderList()
        _clean(-1)
        for folder in folder_with_ghost:
            if not real_folders.find_by_id(folder.id):
                logger.debug(f"Delete ghost folder: {folder.name} #{folder.id}")
                if self.delete(folder.id, False) != LanZouCloud.SUCCESS:
                    return LanZouCloud.FAILED
                if self.delete_rec(folder.id, False) != LanZouCloud.SUCCESS:
                    return LanZouCloud.FAILED
        return LanZouCloud.SUCCESS

    def get_file_info_by_url(self, share_url, pwd='') -> FileDetail:
        """获取文件各种信息(包括下载直链)
        :param share_url: 文件分享链接
        :param pwd: 文件提取码(如果有的话)
        """
        if not is_file_url(share_url):  # 非文件链接返回错误
            return FileDetail(LanZouCloud.URL_INVALID, pwd=pwd, url=share_url)

        first_page = self._get(share_url)  # 文件分享页面(第一页)
        if not first_page:
            return FileDetail(LanZouCloud.NETWORK_ERROR, pwd=pwd, url=share_url)

        if "acw_sc__v2" in first_page.text:
            # 在页面被过多访问或其他情况下，有时候会先返回一个加密的页面，其执行计算出一个acw_sc__v2后放入页面后再重新访问页面才能获得正常页面
            # 若该页面进行了js加密，则进行解密，计算acw_sc__v2，并加入cookie
            acw_sc__v2 = calc_acw_sc__v2(first_page.text)
            self._session.cookies.set("acw_sc__v2", acw_sc__v2)
            logger.debug(f"Set Cookie: acw_sc__v2={acw_sc__v2}")
            first_page = self._get(share_url)  # 文件分享页面(第一页)
            if not first_page:
                return FileDetail(LanZouCloud.NETWORK_ERROR, pwd=pwd, url=share_url)

        first_page = remove_notes(first_page.text)  # 去除网页里的注释
        if '文件取消' in first_page or '文件不存在' in first_page:
            return FileDetail(LanZouCloud.FILE_CANCELLED, pwd=pwd, url=share_url)

        # 这里获取下载直链 304 重定向前的链接
        if 'id="pwdload"' in first_page or 'id="passwddiv"' in first_page or '输入密码' in first_page:  # 文件设置了提取码时
            if len(pwd) == 0:
                return FileDetail(LanZouCloud.LACK_PASSWORD, pwd=pwd, url=share_url)  # 没给提取码直接退出
            # data : 'action=downprocess&sign=AGZRbwEwU2IEDQU6BDRUaFc8DzxfMlRjCjTPlVkWzFSYFY7ATpWYw_c_c&p='+pwd,
            sign = re.search(r"sign=(\w+?)&", first_page)
            sign = sign.group(1) if sign else ""
            post_data = {'action': 'downprocess', 'sign': sign, 'p': pwd}
            link_info = self._post(self._host_url + '/ajaxm.php', post_data)  # 保存了重定向前的链接信息和文件名
            second_page = self._get(share_url)  # 再次请求文件分享页面，可以看见文件名，时间，大小等信息(第二页)
            if not link_info or not second_page.text:
                return FileDetail(LanZouCloud.NETWORK_ERROR, pwd=pwd, url=share_url)
            link_info = link_info.json()
            second_page = remove_notes(second_page.text)
            # 提取文件信息
            f_name = link_info['inf'].replace("*", "_")
            f_size = re.search(r'大小.+?(\d[\d\.,]+\s?[BKM]?)<', second_page)
            f_size = f_size.group(1) if f_size else ''
            f_time = re.search(r'class="n_file_infos">(.+?)</span>', second_page)
            f_time = f_time.group(1) if f_time else ''
            f_desc = re.search(r'class="n_box_des">(.*?)</div>', second_page)
            f_desc = f_desc.group(1) if f_desc else ''
        else:  # 文件没有设置提取码时,文件信息都暴露在分享页面上
            para = re.search(r'<iframe.*?src="(.+?)"', first_page).group(1)  # 提取下载页面 URL 的参数
            # 文件名位置变化很多
            f_name = re.search(r"<title>(.+?) - 蓝奏云</title>", first_page) or \
                     re.search(r'<div class="filethetext".+?>([^<>]+?)</div>', first_page) or \
                     re.search(r'<div style="font-size.+?>([^<>].+?)</div>', first_page) or \
                     re.search(r"var filename = '(.+?)';", first_page) or \
                     re.search(r'id="filenajax">(.+?)</div>', first_page) or \
                     re.search(r'<div class="b"><span>([^<>]+?)</span></div>', first_page)
            f_name = f_name.group(1).replace("*", "_") if f_name else "未匹配到文件名"

            f_time = re.search(r'>(\d+\s?[秒天分小][钟时]?前|[昨前]天\s?[\d:]+?|\d+\s?天前|\d{4}-\d\d-\d\d)<', first_page)
            f_time = f_time.group(1) if f_time else ''
            f_size = re.search(r'大小.+?(\d[\d\.,]+\s?[BKM]?)<', first_page) or \
                     re.search(r'大小：(.+?)</div>', first_page)  # VIP 分享页面
            f_size = f_size.group(1) if f_size else ''
            f_desc = re.search(r'文件描述.+?</span><br>\n?\s*(.*?)\s*</td>', first_page)
            f_desc = f_desc.group(1) if f_desc else ''
            first_page = self._get(self._host_url + para)
            if not first_page:
                return FileDetail(LanZouCloud.NETWORK_ERROR, name=f_name, time=f_time, size=f_size, desc=f_desc, pwd=pwd, url=share_url)
            first_page = remove_notes(first_page.text)
            # 一般情况 sign 的值就在 data 里，有时放在变量后面
            sign = re.search(r"'sign':(.+?),", first_page).group(1)
            if len(sign) < 20:  # 此时 sign 保存在变量里面, 变量名是 sign 匹配的字符
                sign = re.search(rf"var {sign}\s*=\s*'(.+?)';", first_page).group(1)
            post_data = {'action': 'downprocess', 'sign': sign, 'ves': 1}
            # 某些特殊情况 share_url 会出现 webpage 参数, post_data 需要更多参数
            # https://github.com/zaxtyson/LanZouCloud-API/issues/74
            if "?webpage=" in share_url:
                ajax_data = re.search(r"var ajaxdata\s*=\s*'(.+?)';", first_page).group(1)
                web_sign = re.search(r"var websign\s*=\s*'(.+?)';", first_page).group(1)
                web_sign_key = re.search(r"var websignkey\s*=\s*'(.+?)';", first_page).group(1)
                post_data = {'action': 'downprocess', 'signs': ajax_data, 'sign': sign, 'ves': 1,
                             'websign': web_sign, 'websignkey': web_sign_key}
            link_info = self._post(self._host_url + '/ajaxm.php', post_data)
            if not link_info:
                return FileDetail(LanZouCloud.NETWORK_ERROR, name=f_name, time=f_time, size=f_size, desc=f_desc, pwd=pwd, url=share_url)
            link_info = link_info.json()

        # 这里开始获取文件直链
        if link_info['zt'] != 1:  # 返回信息异常，无法获取直链
            return FileDetail(LanZouCloud.FAILED,
                              name=f_name, time=f_time, size=f_size,
                              desc=f_desc, pwd=pwd, url=share_url)

        fake_url = link_info['dom'] + '/file/' + link_info['url']  # 假直连，存在流量异常检测
        download_page = self._get(fake_url, allow_redirects=False)
        if not download_page:
            return FileDetail(LanZouCloud.NETWORK_ERROR,
                              name=f_name, time=f_time, size=f_size,
                              desc=f_desc, pwd=pwd, url=share_url)
        download_page.encoding = 'utf-8'
        download_page_html = remove_notes(download_page.text)
        if '网络异常' not in download_page_html:  # 没有遇到验证码
            direct_url = download_page.headers['Location']  # 重定向后的真直链
        else:  # 遇到验证码，验证后才能获取下载直链
            file_token = re.findall("'file':'(.+?)'", download_page_html)[0]
            file_sign = re.findall("'sign':'(.+?)'", download_page_html)[0]
            check_api = 'https://vip.d0.baidupan.com/file/ajax.php'
            post_data = {'file': file_token, 'el': 2, 'sign': file_sign}
            sleep(2)  # 这里必需等待2s, 否则直链返回 ?SignError
            resp = self._post(check_api, post_data)
            direct_url = resp.json()['url']
            if not direct_url:
                return FileDetail(LanZouCloud.CAPTCHA_ERROR,
                                  name=f_name, time=f_time, size=f_size,
                                  desc=f_desc, pwd=pwd, url=share_url)

        f_type = f_name.split('.')[-1]
        return FileDetail(LanZouCloud.SUCCESS,
                          name=f_name, size=f_size, type=f_type, time=f_time,
                          desc=f_desc, pwd=pwd, url=share_url, durl=direct_url)

    def get_file_info_by_id(self, file_id) -> FileDetail:
        """通过 id 获取文件信息"""
        info = self.get_share_info(file_id)
        if info.code != LanZouCloud.SUCCESS:
            return FileDetail(info.code)
        return self.get_file_info_by_url(info.url, info.pwd)

    def get_durl_by_url(self, share_url, pwd='') -> DirectUrlInfo:
        """通过分享链接获取下载直链"""
        file_info = self.get_file_info_by_url(share_url, pwd)
        if file_info.code != LanZouCloud.SUCCESS:
            return DirectUrlInfo(file_info.code, '', '')
        return DirectUrlInfo(LanZouCloud.SUCCESS, file_info.name, file_info.durl)

    def get_durl_by_id(self, file_id) -> DirectUrlInfo:
        """登录用户通过id获取直链"""
        info = self.get_share_info(file_id, is_file=True)  # 能获取直链，一定是文件
        return self.get_durl_by_url(info.url, info.pwd)

    def get_share_info(self, fid, is_file=True) -> ShareInfo:
        """获取文件(夹)提取码、分享链接"""
        post_data = {'task': 22, 'file_id': fid} if is_file else {'task': 18, 'folder_id': fid}  # 获取分享链接和密码用
        f_info = self._post(self._doupload_url, post_data)
        if not f_info:
            return ShareInfo(LanZouCloud.NETWORK_ERROR)
        else:
            f_info = f_info.json()['info']

        # id 有效性校验
        if ('f_id' in f_info.keys() and f_info['f_id'] == 'i') or ('name' in f_info.keys() and not f_info['name']):
            return ShareInfo(LanZouCloud.ID_ERROR)

        # onof=1 时，存在有效的提取码; onof=0 时不存在提取码，但是 pwd 字段还是有一个无效的随机密码
        self._get_response_host(f_info)
        pwd = f_info['pwd'] if int(f_info['onof']) == 1 else ''
        if 'f_id' in f_info.keys():  # 说明返回的是文件的信息
            url = f_info['is_newd'] + '/' + f_info['f_id']  # 文件的分享链接需要拼凑
            file_info = self._post(self._doupload_url, {'task': 12, 'file_id': fid})  # 文件信息
            if not file_info:
                return ShareInfo(LanZouCloud.NETWORK_ERROR)
            name = file_info.json()['text']  # 无后缀的文件名(获得后缀又要发送请求,没有就没有吧,尽可能减少请求数量)
            desc = file_info.json()['info']
        else:
            url = f_info['new_url']  # 文件夹的分享链接可以直接拿到
            name = f_info['name']  # 文件夹名
            desc = f_info['des']  # 文件夹描述
        return ShareInfo(LanZouCloud.SUCCESS, name=name, url=url, desc=desc, pwd=pwd)

    def set_passwd(self, fid, passwd='', is_file=True) -> int:
        """
        设置网盘文件(夹)的提取码, 现在非会员用户不允许关闭提取码
        id 无效或者 id 类型不对应仍然返回成功 :(
        文件夹提取码长度 0-12 位  文件提取码 2-6 位
        """
        passwd_status = 0 if passwd == '' else 1  # 是否开启密码
        if is_file:
            post_data = {"task": 23, "file_id": fid, "shows": passwd_status, "shownames": passwd}
        else:
            post_data = {"task": 16, "folder_id": fid, "shows": passwd_status, "shownames": passwd}
        result = self._post(self._doupload_url, post_data)
        if not result:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.SUCCESS if result.json()['zt'] == 1 else LanZouCloud.FAILED

    def mkdir(self, parent_id, folder_name, desc='') -> int:
        """创建文件夹(同时设置描述)"""
        folder_name = folder_name.replace(' ', '_')  # 文件夹名称不能包含空格
        folder_name = name_format(folder_name)  # 去除非法字符
        folder_list, _ = self.get_dir_list(parent_id)
        if folder_list.find_by_name(folder_name):  # 如果文件夹已经存在，直接返回 id
            return folder_list.find_by_name(folder_name).id
        raw_folders = self.get_move_folders()
        post_data = {"task": 2, "parent_id": parent_id or -1, "folder_name": folder_name,
                     "folder_description": desc}
        result = self._post(self._doupload_url, post_data)  # 创建文件夹
        if not result or result.json()['zt'] != 1:
            logger.debug(f"Mkdir {folder_name} error, parent_id={parent_id}")
            return LanZouCloud.MKDIR_ERROR  # 正常时返回 id 也是 int，为了方便判断是否成功，网络异常或者创建失败都返回相同错误码
        # 允许再不同路径创建同名文件夹, 移动时可通过 get_move_paths() 区分
        for folder in self.get_move_folders():
            if not raw_folders.find_by_id(folder.id):
                logger.debug(f"Mkdir {folder_name} #{folder.id} in parent_id={parent_id}")
                return folder.id
        logger.debug(f"Mkdir {folder_name} error, parent_id={parent_id}")
        return LanZouCloud.MKDIR_ERROR

    def _set_dir_info(self, folder_id, folder_name, desc='') -> int:
        """重命名文件夹及其描述"""
        # 不能用于重命名文件，id 无效仍然返回成功
        folder_name = name_format(folder_name)
        post_data = {'task': 4, 'folder_id': folder_id, 'folder_name': folder_name, 'folder_description': desc}
        result = self._post(self._doupload_url, post_data)
        if not result:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.SUCCESS if result.json()['zt'] == 1 else LanZouCloud.FAILED

    def rename_dir(self, folder_id, folder_name) -> int:
        """重命名文件夹"""
        # 重命名文件要开会员额
        info = self.get_share_info(folder_id, is_file=False)
        if info.code != LanZouCloud.SUCCESS:
            return info.code
        return self._set_dir_info(folder_id, folder_name, info.desc)

    def set_desc(self, fid, desc, is_file=True) -> int:
        """设置文件(夹)描述"""
        if is_file:
            # 文件描述一旦设置了值，就不能再设置为空
            post_data = {'task': 11, 'file_id': fid, 'desc': desc}
            result = self._post(self._doupload_url, post_data)
            if not result:
                return LanZouCloud.NETWORK_ERROR
            elif result.json()['zt'] != 1:
                return LanZouCloud.FAILED
            return LanZouCloud.SUCCESS
        else:
            # 文件夹描述可以置空
            info = self.get_share_info(fid, is_file=False)
            if info.code != LanZouCloud.SUCCESS:
                return info.code
            return self._set_dir_info(fid, info.name, desc)

    def rename_file(self, file_id, filename):
        """允许会员重命名文件(无法修后缀名)"""
        post_data = {'task': 46, 'file_id': file_id, 'file_name': name_format(filename), 'type': 2}
        result = self._post(self._doupload_url, post_data)
        if not result:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.SUCCESS if result.json()['zt'] == 1 else LanZouCloud.FAILED

    def get_move_folders(self) -> FolderList:
        """获取全部文件夹 id-name 列表，用于移动文件至新的文件夹"""
        # 这里 file_id 可以为任意值,不会对结果产生影响
        result = FolderList()
        result.append(FolderId(name='LanZouCloud', id=-1, desc="", now=0))
        resp = self._post(self._doupload_url, data={"task": 19, "file_id": -1})
        if not resp or resp.json()['zt'] != 1:  # 获取失败或者网络异常
            return result
        info = resp.json()['info'] or []  # 新注册用户无数据, info=None
        for folder in info:
            folder_id, folder_name = int(folder['folder_id']), folder['folder_name']
            result.append(FolderId(folder_name, folder_id, "", ""))
        return result

    def get_move_paths(self) -> List[FolderList]:
        """获取所有文件夹的绝对路径(耗时长)"""
        result = []
        root = FolderList()
        root.append(FolderId('LanZouCloud', -1))
        result.append(root)
        resp = self._post(self._doupload_url, data={"task": 19, "file_id": -1})
        if not resp or resp.json()['zt'] != 1:  # 获取失败或者网络异常
            return result

        ex = ThreadPoolExecutor()  # 线程数 min(32, os.cpu_count() + 4)
        id_list = [int(folder['folder_id']) for folder in resp.json()['info']]
        task_list = [ex.submit(self.get_full_path, fid) for fid in id_list]
        for task in as_completed(task_list):
            result.append(task.result())
        return sorted(result)

    def move_file(self, file_id, folder_id=-1) -> int:
        """移动文件到指定文件夹"""
        # 移动回收站文件也返回成功(实际上行不通) (+_+)?
        post_data = {'task': 20, 'file_id': file_id, 'folder_id': folder_id}
        result = self._post(self._doupload_url, post_data)
        logger.debug(f"Move file file_id={file_id} to folder_id={folder_id}")
        if not result:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.SUCCESS if result.json()['zt'] == 1 else LanZouCloud.FAILED

    def move_folder(self, folder_id: int, parent_folder_id: int=-1) -> int:
        """移动文件夹(官方并没有直接支持此功能)"""
        if folder_id == parent_folder_id or parent_folder_id < -1:
            return LanZouCloud.FAILED  # 禁止移动文件夹到自身，禁止移动到 -2 这样的文件夹(文件还在,但是从此不可见)

        folder = self.get_move_folders().find_by_id(folder_id)
        if not folder:
            logger.debug(f"Not found folder :folder_id={folder_id}")
            return LanZouCloud.FAILED

        _folders, _ = self.get_dir_list(folder_id)
        if _folders:
            logger.debug(f"Found subdirectory in folder={folder}")
            return LanZouCloud.FAILED  # 递归操作可能会产生大量请求,这里只移动单层文件夹

        info = self.get_share_info(folder_id, False)
        new_folder_id = self.mkdir(parent_folder_id, folder.name, info.desc)  # 在目标文件夹下创建同名文件夹

        if new_folder_id == LanZouCloud.MKDIR_ERROR:
            return LanZouCloud.FAILED
        elif new_folder_id == folder_id:  # 移动文件夹到同一目录
            return LanZouCloud.FAILED

        self.set_passwd(new_folder_id, info.pwd, False)  # 保持密码相同
        ex = ThreadPoolExecutor()
        task_list = [ex.submit(self.move_file, file.id, new_folder_id) for file in self.get_file_list(folder_id)]
        for task in as_completed(task_list):
            if task.result() != LanZouCloud.SUCCESS:
                return LanZouCloud.FAILED
        self.delete(folder_id, False)  # 全部移动完成后删除原文件夹
        self.delete_rec(folder_id, False)
        return LanZouCloud.SUCCESS

    def _upload_small_file(self, task, file_path, folder_id=-1, callback=None) -> Tuple[int, int, bool]:
        """绕过格式限制上传不超过 max_size 的文件"""
        if not os.path.isfile(file_path):
            return LanZouCloud.PATH_ERROR, 0, True

        need_delete = False  # 上传完成是否删除
        if not is_name_valid(os.path.basename(file_path)):  # 不允许上传的格式
            file_path = let_me_upload(file_path)  # 添加了报尾的新文件
            need_delete = True

        # 文件已经存在同名文件就删除
        filename = name_format(os.path.basename(file_path))
        file_list = self.get_file_list(folder_id)
        if file_list.find_by_name(filename):
            self.delete(file_list.find_by_name(filename).id)
        logger.debug(f'Upload file file_path={file_path} to folder_id={folder_id}')

        file_ = open(file_path, 'rb')
        post_data = {
            "task": "1",
            "folder_id": str(folder_id),
            "id": "WU_FILE_0",
            "name": filename,
            "upload_file": (filename, file_, 'application/octet-stream')
        }

        post_data = MultipartEncoder(post_data)
        tmp_header = self._headers.copy()
        tmp_header['Content-Type'] = post_data.content_type

        # MultipartEncoderMonitor 每上传 8129 bytes数据调用一次回调函数，问题根源是 httplib 库
        # issue : https://github.com/requests/toolbelt/issues/75
        # 上传完成后，回调函数会被错误的多调用一次(强迫症受不了)。因此，下面重新封装了回调函数，修改了接受的参数，并阻断了多余的一次调用
        self._upload_finished_flag = False  # 上传完成的标志
        start_size = task.now_size
        logger.debug(f"upload small file: start_size={start_size}")

        def _call_back(read_monitor):
            if callback is not None:
                if not self._upload_finished_flag:
                    task.now_size = start_size + read_monitor.bytes_read
                    callback()
                if read_monitor.len == read_monitor.bytes_read:
                    self._upload_finished_flag = True

        monitor = MultipartEncoderMonitor(post_data, _call_back)
        result = self._post('https://pc.woozooo.com/fileup.php', monitor, headers=tmp_header, timeout=None)
        if not result:  # 网络异常
            logger.debug('Upload file no result')
            return LanZouCloud.NETWORK_ERROR, 0, True
        else:
            if result.status_code == 413:
                logger.error(f"Upload file too Large: {result.text}")
                return LanZouCloud.FAILED, 0, True  # 文件超过限制, 上传失败
            result = result.json()
        if result["zt"] != 1:
            logger.debug(f'Upload failed: result={result}')
            return LanZouCloud.FAILED, 0, True  # 上传失败

        file_id = result["text"][0]["id"]
        self.set_passwd(file_id)  # 文件上传后默认关闭提取码
        if need_delete:
            file_.close()
            os.remove(file_path)
        return LanZouCloud.SUCCESS, int(file_id), True

    def _upload_big_file(self, task: object, file_path, dir_id, callback=None):
        """上传大文件, 且使得回调函数只显示一个文件"""
        file_size = os.path.getsize(file_path)  # 原始文件的字节大小
        file_name = os.path.basename(file_path)
        tmp_dir = os.path.dirname(file_path) + os.sep + '__' + '.'.join(file_name.split('.')[:-1])  # 临时文件保存路径
        record_file = tmp_dir + os.sep + file_name + '.record'  # 记录文件，大文件没有完全上传前保留，用于支持续传
        uploaded_size = 0  # 记录已上传字节数，用于回调函数

        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
        if not os.path.exists(record_file):  # 初始化记录文件
            info = {'name': file_name, 'size': file_size, 'uploaded': 0, 'parts': []}
            with open(record_file, 'wb') as f:
                pickle.dump(info, f)
        else:
            with open(record_file, 'rb') as f:
                info = pickle.load(f)
                uploaded_size = info['uploaded']  # 读取已经上传的大小
                logger.debug(f"Find upload record: {uploaded_size}/{file_size}")

        # def _callback(now_size):  # 重新封装回调函数，隐藏数据块上传细节
        #     nonlocal uploaded_size
        #     if callback is not None:
        #         # MultipartEncoder 以后,文件数据流比原文件略大几百字节, now_size 略大于 file_size
        #         now_size = uploaded_size + now_size
        #         task.now_size = now_size if now_size < task.total_size else task.total_size  # 99.99% -> 100.00%
        #         callback()

        while uploaded_size < file_size:
            data_size, data_path = big_file_split(file_path, self._max_size, start_byte=uploaded_size)
            code, _, _ = self._upload_small_file(task, data_path, dir_id, callback)
            if code == LanZouCloud.SUCCESS:
                uploaded_size += data_size  # 更新已上传的总字节大小
                info['uploaded'] = uploaded_size
                info['parts'].append(os.path.basename(data_path))  # 记录已上传的文件名
                with open(record_file, 'wb') as f:
                    logger.debug(f"Update record file: {uploaded_size}/{file_size}")
                    pickle.dump(info, f)
            else:
                logger.debug(f"Upload data file failed: code={code}, data_path={data_path}")
                return LanZouCloud.FAILED, 0, False
            os.remove(data_path)  # 删除临时数据块
            min_s, max_s = self._upload_delay  # 设置两次上传间的延时，减小封号可能性
            sleep_time = uniform(min_s, max_s)
            logger.debug(f"Sleeping, Upload task will resume after {sleep_time:.2f}s...")
            sleep(sleep_time)

        # 全部数据块上传完成
        record_name = list(file_name.replace('.', ''))  # 记录文件名也打乱
        shuffle(record_name)
        record_name = name_format(''.join(record_name)) + '.txt'
        record_file_new = tmp_dir + os.sep + record_name
        os.rename(record_file, record_file_new)
        code, _, _ = self._upload_small_file(task, record_file_new, dir_id, callback)  # 上传记录文件
        if code != LanZouCloud.SUCCESS:
            logger.error(f"Upload record file failed: code={code}, record_file={record_file_new}")
            return LanZouCloud.FAILED, 0, False
        # 记录文件上传成功，删除临时文件
        shutil.rmtree(tmp_dir)
        logger.debug(f"Upload finished, Delete tmp folder:{tmp_dir}")
        return LanZouCloud.SUCCESS, int(dir_id), False  # 大文件返回文件夹id

    def upload_file(self, task: object, file_path, folder_id=-1, callback=None, allow_big_file=False) -> Tuple[int, int, bool]:
        """解除限制上传文件"""
        if not os.path.isfile(file_path):
            return LanZouCloud.PATH_ERROR, 0, True

        file_size = os.path.getsize(file_path)
        if file_size == 0:  # 空文件无法上传
            return LanZouCloud.FAILED, 0, False
        elif file_size <= self._max_size * 1048576:  # 单个文件不超过 max_size 直接上传
            return self._upload_small_file(task, file_path, folder_id, callback)
        elif not allow_big_file:
            logger.debug(f'Forbid upload big file！file_path={file_path}, max_size={self._max_size}')
            task.info = f"文件大于{self._max_size}MB" # LanZouCloud.OFFICIAL_LIMITED
            return LanZouCloud.OFFICIAL_LIMITED, 0, False  # 不允许上传超过 max_size 的文件

        # 上传超过 max_size 的文件
        folder_name = os.path.basename(file_path)  # 保存分段文件的文件夹名
        dir_id = self.mkdir(folder_id, folder_name, 'Big File')
        if dir_id == LanZouCloud.MKDIR_ERROR:
            return LanZouCloud.MKDIR_ERROR, 0, False  # 创建文件夹失败就退出
        return self._upload_big_file(task, file_path, dir_id, callback)

    def upload_dir(self, task: object, callback, allow_big_file=False):
        #  dir_path, folder_id=-1, callback=None, failed_callback=None, allow_big_file=False):
        """批量上传文件夹中的文件(不会递归上传子文件夹)
        :param folder_id: 网盘文件夹 id
        :param dir_path: 文件夹路径
        :param callback (filename, total_size, now_size) 用于显示进度
        :param failed_callback (code, file) 用于处理上传失败的文件
        """
        if not os.path.isdir(task.url):
            task.info = LanZouCloud.PATH_ERROR
            return LanZouCloud.PATH_ERROR, None, False

        dir_name = os.path.basename(task.url)
        dir_id = self.mkdir(task.fid, dir_name, '批量上传')
        if dir_id == LanZouCloud.MKDIR_ERROR:
            task.info = LanZouCloud.MKDIR_ERROR
            return LanZouCloud.MKDIR_ERROR, None, False

        # the default value of task.current is 1
        task.current = 0
        for filename in os.listdir(task.url):
            file_path = task.url + os.sep + filename
            if not os.path.isfile(file_path):
                continue  # 跳过子文件夹
            task.current += 1
            code, _, _ = self.upload_file(task, file_path, dir_id, callback=callback,
                                          allow_big_file=allow_big_file)
            # if code != LanZouCloud.SUCCESS:
            #     if failed_callback is not None:
            #         failed_callback(code, filename)
        return LanZouCloud.SUCCESS, dir_id, False

    def down_file_by_url(self, share_url, task: object, callback) -> int:
        """通过分享链接下载文件(需提取码)"""
        if not is_file_url(share_url):
            task.info = LanZouCloud.URL_INVALID
            return LanZouCloud.URL_INVALID
        if not os.path.exists(task.path):
            os.makedirs(task.path)

        info = self.get_durl_by_url(share_url, task.pwd)
        if info.code != LanZouCloud.SUCCESS:
            task.info = info.code
            logger.error(f'File direct url info: {info}')
            return info.code

        resp = self._get(info.durl, stream=True)
        if not resp:
            task.info = LanZouCloud.NETWORK_ERROR
            return LanZouCloud.NETWORK_ERROR

        # 对于 txt 文件, 可能出现没有 Content-Length 的情况
        # 此时文件需要下载一次才会出现 Content-Length
        # 这时候我们先读取一点数据, 再尝试获取一次, 通常只需读取 1 字节数据
        content_length = resp.headers.get('Content-Length', None)
        if not content_length:
            data_iter = resp.iter_content(chunk_size=1)
            max_retries = 5  # 5 次拿不到就算了
            while not content_length and max_retries > 0:
                max_retries -= 1
                logger.warning("Not found Content-Length in response headers")
                logger.debug("Read 1 byte from stream...")
                try:
                    next(data_iter)  # 读取一个字节
                except StopIteration:
                    logger.debug("Please wait for a moment before downloading")
                    return LanZouCloud.FAILED
                resp_ = self._get(info.durl, stream=True)  # 再请求一次试试
                if not resp_:
                    return LanZouCloud.FAILED
                content_length = resp_.headers.get('Content-Length', None)
                logger.debug(f"Content-Length: {content_length}")

        total_size = int(content_length)

        if share_url == task.url:  # 下载单文件
            task.total_size = total_size
        file_path = task.path + os.sep + info.name.replace("*", "_")  # 替换文件名中的 *
        logger.debug(f'Save file to file_path={file_path}')
        now_size = 0
        if os.path.exists(file_path):
            now_size = os.path.getsize(file_path)  # 本地已经下载的文件大小
            task.now_size += now_size
            callback()
            if now_size >= total_size:
                logger.debug(f'File file_path={file_path} local already exist!')
                return LanZouCloud.SUCCESS

        chunk_size = 1024 * 64  # 4096
        last_512_bytes = b''  # 用于识别文件是否携带真实文件名信息
        headers = {**self._headers, 'Range': 'bytes=%d-' % now_size}
        resp = self._get(info.durl, stream=True, headers=headers, timeout=None)

        if resp is None:  # 网络异常
            task.info = LanZouCloud.NETWORK_ERROR
            return LanZouCloud.FAILED
        if resp.status_code == 416:  # 已经下载完成
            logger.debug('File download finished!')
            return LanZouCloud.SUCCESS

        logger.debug(f'File downloading file_path={file_path} ...')
        with open(file_path, "ab") as f:
            for chunk in resp.iter_content(chunk_size):
                if chunk:
                    f.write(chunk)
                    f.flush()
                    now_size += len(chunk)
                    task.now_size += len(chunk)
                    callback()
                    if total_size - now_size < 512:
                        last_512_bytes += chunk
        # 尝试解析文件报尾
        file_info = un_serialize(last_512_bytes[-512:])
        if file_info is not None and 'padding' in file_info:  # 大文件的记录文件也可以反序列化出 name,但是没有 padding
            real_name = file_info['name']
            new_file_path = task.path + os.sep + real_name
            logger.debug(f"Find meta info: real_name={real_name}")
            if os.path.exists(new_file_path):
                os.remove(new_file_path)  # 存在同名文件则删除
            os.rename(file_path, new_file_path)
            with open(new_file_path, 'rb+') as f:
                f.seek(-512, 2)  # 截断最后 512 字节数据
                f.truncate()
        return LanZouCloud.SUCCESS

    def get_folder_info_by_url(self, share_url, dir_pwd='') -> FolderDetail():
        """获取文件夹里所有文件的信息"""
        if is_file_url(share_url):
            return FolderDetail(LanZouCloud.URL_INVALID)
        try:
            html = requests.get(share_url, headers=self._headers).text
        except requests.RequestException as e:
            logger.error(f"requests error: {e}")
            return FolderDetail(LanZouCloud.NETWORK_ERROR)
        if any(item in html for item in ["文件不存在", "文件取消"]):
            return FolderDetail(LanZouCloud.FILE_CANCELLED)
        if ('id="pwdload"' in html or 'id="passwddiv"' in html or '请输入密码' in html) and len(dir_pwd) == 0:
            return FolderDetail(LanZouCloud.LACK_PASSWORD)

        if "acw_sc__v2" in html:
            # 在页面被过多访问或其他情况下，有时候会先返回一个加密的页面，其执行计算出一个acw_sc__v2后放入页面后再重新访问页面才能获得正常页面
            # 若该页面进行了js加密，则进行解密，计算acw_sc__v2，并加入cookie
            acw_sc__v2 = calc_acw_sc__v2(html)
            self._session.cookies.set("acw_sc__v2", acw_sc__v2)
            logger.debug(f"Set Cookie: acw_sc__v2={acw_sc__v2}")
            html = self._get(share_url).text  # 文件分享页面(第一页)

        try:
            # 获取文件需要的参数
            html = remove_notes(html)
            lx = re.findall(r"'lx':'?(\d)'?,", html)[0]
            t = re.findall(r"var [0-9a-z]{6} = '(\d{10})';", html)[0]
            k = re.findall(r"var [0-9a-z]{6} = '([0-9a-z]{15,})';", html)[0]
            # 文件夹的信息
            folder_id = re.findall(r"'fid':'?(\d+)'?,", html)[0]
            folder_name = re.search(r"var.+?='(.+?)';\n.+document.title", html) or \
                          re.search(r'user-title">(.+?)</div>', html) or \
                          re.search(r'<div class="b">(.+?)<div', html)  # 会员自定义
            folder_name = folder_name.group(1) if folder_name else ''
            folder_time = re.search(r'class="rets">([\d\-]+?)<a', html)  # 日期不全 %m-%d
            folder_time = folder_time.group(1) if folder_time else ''
            folder_desc = re.search(r'id="filename">(.+?)</span>', html, re.DOTALL) or \
                          re.search(r'<div class="user-radio-\d"></div>(.+?)</div>', html) or \
                          re.search(r'class="teta tetb">说</span>(.+?)</div><div class="d2">', html, re.DOTALL)
            folder_desc = folder_desc.group(1) if folder_desc else ''
        except IndexError:
            logger.error("IndexError")
            return FolderDetail(LanZouCloud.FAILED)

        # 提取子文件夹信息(vip用户分享的文件夹可以递归包含子文件夹)
        sub_folders = FolderList()
        # 文件夹描述放在 filesize 一栏, 迷惑行为
        all_sub_folders = re.findall(
            r'mbxfolder"><a href="(.+?)".+class="filename">(.+?)<div class="filesize">(.*?)</div>', html)
        for url, _, _ in all_sub_folders:
            url = self._host_url + url
            sub_forder_detail = self.get_folder_info_by_url(url, dir_pwd)
            sub_folders.append(sub_forder_detail)

        # 提取改文件夹下全部文件
        page = 1
        files = FileList()
        while True:
            try:
                post_data = {'lx': lx, 'pg': page, 'k': k, 't': t, 'fid': folder_id, 'pwd': dir_pwd}
                resp = self._post(self._host_url + '/filemoreajax.php', data=post_data, headers=self._headers).json()
            except requests.RequestException:
                return FolderDetail(LanZouCloud.NETWORK_ERROR)
            if resp['zt'] == 1:  # 成功获取一页文件信息
                for f in resp["text"]:
                    name = f['name_all'].replace("&amp;", "&")
                    if "*" in name:
                        logger.debug(f"Having unexpected file: id={f['id']}, name={name}")
                    if str(f["id"]).startswith('i'):  # 去除不以 i 开头的文件链接
                        files.append(FileInFolder(
                            name=name,  # 文件名
                            time=f["time"],  # 上传时间
                            size=f["size"].replace(",", ""),  # 文件大小
                            type=f["name_all"].split('.')[-1],  # 文件格式
                            url=self._host_url + "/" + f["id"]  # 文件分享链接
                        ))
                page += 1  # 下一页
                continue
            elif resp['zt'] == 2:  # 已经拿到全部的文件信息
                break
            elif resp['zt'] == 3:  # 提取码错误
                return FolderDetail(LanZouCloud.PASSWORD_ERROR)
            elif resp["zt"] == 4:
                continue
            else:
                return FolderDetail(LanZouCloud.FAILED)  # 其它未知错误
        # 通过文件的时间信息补全文件夹的年份(如果有文件的话)
        if files:  # 最后一个文件上传时间最早，文件夹的创建年份与其相同
            if folder_time:
                folder_time = files[-1].time.split('-')[0] + '-' + folder_time
            else:  # 没有时间就取第一个文件日期
                folder_time = files[-1].time
            size_int = sum_files_size(files)
            count = len(files)
        else:  # 可恶，没有文件，日期就设置为今年吧
            folder_time = datetime.today().strftime('%Y-%m-%d')
            size_int = count = 0
        for sub_folder in sub_folders:  # 将子文件夹文件大小数量信息透传到父文件夹
            size_int += sub_folder.folder.size_int
            count += sub_folder.folder.count
        folder_size = convert_file_size_to_str(size_int)
        this_folder = FolderInfo(folder_name, folder_id, dir_pwd, folder_time,
                                 folder_desc, share_url, folder_size, size_int, count)
        return FolderDetail(LanZouCloud.SUCCESS, folder=this_folder, files=files, sub_folders=sub_folders)

    def get_folder_info_by_id(self, folder_id):
        """通过 id 获取文件夹及内部文件信息"""
        info = self.get_share_info(folder_id, is_file=False)
        if info.code != LanZouCloud.SUCCESS:
            return FolderDetail(info.code)
        return self.get_folder_info_by_url(info.url, info.pwd)

    def _check_big_file(self, file_list):
        """检查文件列表,判断是否为大文件分段数据"""
        txt_files = file_list.filter(lambda f: f.name.endswith('.txt') and 'M' not in f.size)
        if txt_files and len(txt_files) == 1:  # 文件夹里有且仅有一个 txt, 很有可能是保存大文件的文件夹
            try:
                info = self.get_durl_by_url(txt_files[0].url)
            except AttributeError:
                info = self.get_durl_by_id(txt_files[0].id)
            if info.code != LanZouCloud.SUCCESS:
                logger.error("Big file checking: Failed")
                return None
            resp = self._get(info.durl)
            # 这里无需知道 txt 文件的 Content-Length, 全部读取即可
            info = un_serialize(resp.content) if resp else None
            if info is not None:  # 确认是大文件
                name, size, *_, parts = info.values()  # 真实文件名, 文件字节大小, (其它数据),分段数据文件名(有序)
                file_list = [file_list.find_by_name(p) for p in parts]
                if all(file_list):  # 分段数据完整
                    logger.debug(f"Big file checking: PASS , name={name}, size={size}")
                    return name, size, file_list
                logger.debug("Big file checking: Failed, Missing some data")
        logger.debug("Big file checking: Failed")
        return None

    def _down_big_file(self, name, total_size, file_list, task: object, callback):
        """下载分段数据到一个文件，回调函数只显示一个文件
        支持大文件下载续传，下载完成后重复下载不会执行覆盖操作，直接返回状态码 SUCCESS
        """
        big_file = task.path + os.sep + name
        record_file = big_file + '.record'

        if not os.path.exists(task.path):
            os.makedirs(task.path)

        if not os.path.exists(record_file):  # 初始化记录文件
            info = {'last_ending': 0, 'finished': []}  # 记录上一个数据块结尾地址和已经下载的数据块
            with open(record_file, 'wb') as rf:
                pickle.dump(info, rf)
        else:  # 读取记录文件，下载续传
            with open(record_file, 'rb') as rf:
                info = pickle.load(rf)
                file_list = [f for f in file_list if f.name not in info['finished']]  # 排除已下载的数据块
                logger.debug(f"Find download record file: {info}")

        task.total_size = total_size
        if os.path.exists(big_file):
            now_size = os.path.getsize(big_file)  # 本地已经下载的文件大小
            task.now_size += now_size
            if callback is not None:
                callback()
            if now_size >= total_size:
                logger.debug(f'File file_path={big_file} local already exist!')
                # 全部数据块下载完成, 记录文件可以删除
                logger.debug(f"Delete download record file: {record_file}")
                os.remove(record_file)
                return LanZouCloud.SUCCESS

        with open(big_file, 'ab') as bf:
            for file in file_list:
                try:
                    durl_info = self.get_durl_by_url(file.url)  # 分段文件无密码
                except AttributeError:
                    durl_info = self.get_durl_by_id(file.id)
                if durl_info.code != LanZouCloud.SUCCESS:
                    logger.debug(f"Can't get direct url: {file}")
                    return durl_info.code
                # 准备向大文件写入数据
                file_size_now = os.path.getsize(big_file)
                down_start_byte = file_size_now - info['last_ending']  # 当前数据块上次下载中断的位置
                headers = {**self._headers, 'Range': 'bytes=%d-' % down_start_byte}
                logger.debug(f"Download {file.name}, Range: {down_start_byte}-")
                resp = self._get(durl_info.durl, stream=True, headers=headers)

                if resp is None:  # 网络错误, 没有响应数据
                    return LanZouCloud.FAILED
                if resp.status_code == 416:  # 下载完成后重复下载导致 Range 越界, 服务器返回 416
                    logger.debug(f"File {name} has already downloaded.")
                    os.remove(record_file)  # 删除记录文件
                    return LanZouCloud.SUCCESS
                try:
                    for chunk in resp.iter_content(4096):
                        if chunk:
                            file_size_now += len(chunk)
                            bf.write(chunk)
                            bf.flush()  # 确保缓冲区立即写入文件，否则下一次写入时获取的文件大小会有偏差
                            task.now_size = file_size_now
                            callback()

                    # 一块数据写入完成，更新记录文件
                    info['finished'].append(file.name)
                finally:
                    info['last_ending'] = file_size_now
                    with open(record_file, 'wb') as rf:
                        pickle.dump(info, rf)
                    logger.debug(f"Update download record info: {info}")
            # 全部数据块下载完成, 记录文件可以删除
            logger.debug(f"Delete download record file: {record_file}")
            os.remove(record_file)
        return LanZouCloud.SUCCESS

    def down_dir_by_url(self, task: object, callback, parent_dir="") -> int:
        """通过分享链接下载文件夹"""
        folder_detail = self.get_folder_info_by_url(task.url, task.pwd)
        if folder_detail.code != LanZouCloud.SUCCESS:  # 获取文件信息失败
            task.info = folder_detail.code
            return folder_detail.code

        # 检查是否大文件分段数据
        info = self._check_big_file(folder_detail.files)
        if info is not None:
            return self._down_big_file(*info, task, callback)

        if parent_dir:  # 递归下载
            task.path = parent_dir + os.sep + folder_detail.folder.name
        else:  # 父文件夹
            task.path = task.path + os.sep + folder_detail.folder.name
            task.total_file = folder_detail.folder.count
            task.total_size = folder_detail.folder.size_int
        # 自动创建子文件夹
        if not os.path.exists(task.path):
            task.path = task.path.replace('*', '_')  # 替换特殊字符以符合路径规则
            os.makedirs(task.path)

        # 不是大文件分段数据,直接下载
        task.size = folder_detail.folder.size
        for index, file in enumerate(folder_detail.files, start=1):
            task.current = index
            code = self.down_file_by_url(file.url, task, callback)
            if code != LanZouCloud.SUCCESS:
                logger.error(f'Download file result: Code:{code}, File: {file}')
                # if failed_callback is not None:
                #     failed_callback(code, file)

        # 如果有子文件夹则递归下载子文件夹
        parent_dir = task.path
        if folder_detail.sub_folders:
            for sub_folder in folder_detail.sub_folders:
                task.url = sub_folder.url
                self.down_dir_by_url(task, callback, parent_dir)
        task.rate = 1000
        return LanZouCloud.SUCCESS

    # ------------------------------------------------------------------------- #
    def set_timeout(self, timeout):
        self._timeout = timeout

    def get_share_info_by_url(self, f_url, pwd="") -> ShareInfo:
        """获取分享文件信息 和 get_file_info_by_url 类似，少一个下载直链"""
        if not is_file_url(f_url):
            return ShareInfo(LanZouCloud.URL_INVALID)
        first_page = self._get(f_url)  # 文件分享页面(第一页)
        if not first_page:
            return ShareInfo(LanZouCloud.NETWORK_ERROR)
        first_page = remove_notes(first_page.text)  # 去除网页里的注释
        if '文件取消' in first_page or '文件不存在' in first_page:
            return ShareInfo(LanZouCloud.FILE_CANCELLED)
        if ('id="pwdload"' in first_page or 'id="passwddiv"' in first_page or "输入密码" in first_page):  # 文件设置了提取码时
            if len(pwd) == 0:
                return ShareInfo(LanZouCloud.LACK_PASSWORD)
            f_size = re.search(r'class="n_filesize">[^<0-9]*([\.0-9 MKBmkbGg]+)<', first_page)
            f_size = f_size.group(1) if f_size else ""
            f_time = re.search(r'class="n_file_infos">([-0-9 :月天小时分钟秒前]+)<', first_page)
            f_time = f_time.group(1) if f_time else ""
            f_desc = re.search(r'class="n_box_des">(.*)<', first_page)
            f_desc = f_desc.group(1) if f_desc else ""
            sign = re.search(r"sign=(\w+?)&", first_page).group(1)
            post_data = {'action': 'downprocess', 'sign': sign, 'p': pwd}
            link_info = self._post(self._host_url + '/ajaxm.php', post_data)  # 保存了重定向前的链接信息和文件名
            second_page = self._get(f_url)  # 再次请求文件分享页面，可以看见文件名，时间，大小等信息(第二页)
            if not link_info or not second_page.text:
                return ShareInfo(LanZouCloud.NETWORK_ERROR)
            second_page = second_page.text
            link_info = link_info.json()
            if link_info["zt"] == 1:
                f_name = link_info['inf'].replace("*", "_")
                if not f_size:
                    f_size = re.search(r'大小：(.+?)</div>', second_page)
                    f_size = f_size.group(1) if f_size else ""
                if not f_time:
                    f_time = re.search(r'class="n_file_infos">(.+?)</span>', second_page)
                    f_time = f_time.group(1) if f_time else ""

                return ShareInfo(LanZouCloud.SUCCESS, name=f_name, url=f_url, pwd=pwd, desc=f_desc, time=f_time, size=f_size)
            else:
                return ShareInfo(LanZouCloud.PASSWORD_ERROR)
        else:
            f_name = re.search(r"<title>(.+?) - 蓝奏云</title>", first_page) or \
                     re.search(r'<div class="filethetext".+?>([^<>]+?)</div>', first_page) or \
                     re.search(r'<div style="font-size.+?>([^<>].+?)</div>', first_page) or \
                     re.search(r"var filename = '(.+?)';", first_page) or \
                     re.search(r'id="filenajax">(.+?)</div>', first_page) or \
                     re.search(r'<div class="b"><span>([^<>]+?)</span></div>', first_page)
            f_name = f_name.group(1) if f_name else "未匹配到文件名"

            f_size = re.search(r'文件大小：</span>([\.0-9 MKBmkbGg]+)<br', first_page)
            f_size = f_size.group(1) if f_size else ""
            f_time = re.search(r'上传时间：</span>([-0-9 :月天小时分钟秒前]+)<br', first_page)
            f_time = f_time.group(1) if f_time else ""
            f_desc = re.search(r'文件描述：</span><br>([^<]+)</td>', first_page)
            f_desc = f_desc.group(1).strip() if f_desc else ""
            return ShareInfo(LanZouCloud.SUCCESS, name=f_name, url=f_url, pwd=pwd, desc=f_desc, time=f_time, size=f_size)

    def get_user_name(self):
        """获取用户名"""
        params = {'item': 'profile', 'action': 'mypower'}
        resp = self._get(self._mydisk_url, params=params)
        if not resp:
            return LanZouCloud.NETWORK_ERROR
        username = re.search(r"com/u/(\w+?)\?t2", remove_notes(resp.text))
        return username.group(1) if username else None
