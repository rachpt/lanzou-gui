"""
蓝奏网盘 API，封装了对蓝奏云的各种操作，解除了上传格式、大小限制
"""

import os
import re
from time import sleep
from datetime import datetime
from urllib3 import disable_warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from urllib3.exceptions import InsecureRequestWarning
from lanzou.api.utils import *
from lanzou.api.types import *
from typing import List
from lanzou.api.models import FileList, FolderList

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

    def __init__(self):
        self._session = requests.Session()
        self._timeout = 5  # 每个请求的超时(不包含下载响应体的用时)
        self._max_size = 100  # 单个文件大小上限 MB
        self._host_url = 'https://www.lanzous.com'
        self._doupload_url = 'https://pc.woozooo.com/doupload.php'
        self._account_url = 'https://pc.woozooo.com/account.php'
        self._mydisk_url = 'https://pc.woozooo.com/mydisk.php'
        self._cookies = None
        self._headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36',
            'Referer': 'https://www.lanzous.com',
            'Accept-Language': 'zh-CN,zh;q=0.9',  # 提取直连必需设置这个，否则拿不到数据
        }
        disable_warnings(InsecureRequestWarning)  # 全局禁用 SSL 警告

    def _get(self, url, **kwargs):
        try:
            kwargs.setdefault('timeout', self._timeout)
            kwargs.setdefault('headers', self._headers)
            return self._session.get(url, verify=False, **kwargs)
        except (ConnectionError, requests.RequestException):
            raise TimeoutError

    def _post(self, url, data, **kwargs):
        try:
            kwargs.setdefault('timeout', self._timeout)
            kwargs.setdefault('headers', self._headers)
            return self._session.post(url, data, verify=False, **kwargs)
        except (ConnectionError, requests.RequestException):
            raise TimeoutError

    def set_max_size(self, max_size=100) -> int:
        """设置单文件大小限制(会员用户可超过 100M)"""
        if max_size < 1:
            return LanZouCloud.FAILED
        self._max_size = max_size
        return LanZouCloud.SUCCESS

    def login(self, username, passwd) -> int:
        self._session.cookies.clear()
        """登录蓝奏云控制台"""
        login_data = {"action": "login", "task": "login", "setSessionId": "", "setToken": "", "setSig": "",
                      "setScene": "", "username": username, "password": passwd}
        phone_header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 5.0; SM-G900P Build/LRX21T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/82.0.4051.0 Mobile Safari/537.36"}
        html = self._get(self._account_url)
        if not html:
            return LanZouCloud.NETWORK_ERROR
        formhash = re.findall(r'name="formhash" value="(.+?)"', html.text)
        if not formhash:
            return LanZouCloud.FAILED
        login_data['formhash'] = formhash[0]
        html = self._post(self._account_url, login_data, headers=phone_header)
        if not html:
            return LanZouCloud.NETWORK_ERROR
        if '登录成功' in html.text:
            self._cookies = html.cookies.get_dict()
            return LanZouCloud.SUCCESS
        else:
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
            return
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
        """从回收站恢复多个文件"""
        if not files and not folders:
            return
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
        """从回收站恢复所有文件"""
        para = {'item': 'recycle', 'action': 'restore_all'}
        post_data = {'action': 'restore_all', 'task': 'restore_all'}
        html1 = self._get(self._mydisk_url, params=para)
        if not html1:
            return LanZouCloud.NETWORK_ERROR
        post_data['formhash'] = re.findall(r'name="formhash" value="(.+?)"', html1.text)[0]  # 设置表单 hash
        html = self._post(self._mydisk_url + '?item=recycle', post_data)
        if not html:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.SUCCESS if '还原成功' in html.text else LanZouCloud.FAILED

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
            if resp["zt"]  == 9:  # login not
                print(resp)
                break
            for file in resp["text"]:
                file_list.append(File(
                    id=int(file['id']),
                    name=file['name_all'],
                    time=file['time'],  # 上传时间
                    size=file['size'],  # 文件大小
                    type=file['name_all'].split('.')[-1],  # 文件类型
                    downs=int(file['downs']),  # 下载次数
                    has_pwd=True if int(file['onof']) == 1 else False,  # 是否存在提取码
                    has_des=True if int(file['is_des']) == 1 else False  # 是否存在描述
                ))
        return file_list

    def get_dir_list(self, folder_id=-1) -> (FolderList, FolderList):
        """获取子文件夹列表与全路径"""
        folder_list = FolderList()
        path_list = FolderList()
        path_list.append(FolderId('LanZouCloud', -1, '根目录', -1))
        post_data = {'task': 47, 'folder_id': folder_id}
        resp = self._post(self._doupload_url, post_data)
        if resp:  # 网络异常，重试
            resp = resp.json()
            # if resp["zt"] == 1:  # 成功
            for folder in resp["text"]:
                folder_list.append(Folder(
                    id=folder['fol_id'],
                    name=folder['name'],
                    has_pwd=True if int(folder['onof']) == 1 else False,  # 是否存在提取码
                    desc=folder['folder_des'][1:-1]
                ))
            for folder in resp["info"]:
                path_list.append(FolderId(
                    name=folder['name'],
                    id=folder['folderid'],
                    desc=folder['folder_des'][1:-1],
                    now=int(folder['now'])
                ))
        return folder_list, path_list

    def get_file_info_by_url(self, share_url, pwd='') -> FileDetail:
        """获取直链"""
        if not is_file_url(share_url):  # 非文件链接返回错误
            return FileDetail(LanZouCloud.URL_INVALID)

        first_page = self._get(share_url)  # 文件分享页面(第一页)
        if not first_page:
            return FileDetail(LanZouCloud.NETWORK_ERROR)

        first_page = remove_notes(first_page.text)  # 去除网页里的注释
        if '文件取消' in first_page:
            return FileDetail(LanZouCloud.FILE_CANCELLED)

        # 这里获取下载直链 304 重定向前的链接
        if '输入密码' in first_page:  # 文件设置了提取码时
            if len(pwd) == 0:
                return FileDetail(LanZouCloud.LACK_PASSWORD)  # 没给提取码直接退出
            # data : 'action=downprocess&sign=AGZRbwEwU2IEDQU6BDRUaFc8DzxfMlRjCjTPlVkWzFSYFY7ATpWYw_c_c&p='+pwd,
            sign = re.findall(r"sign=(\w+?)&", first_page)[0]
            post_data = {'action': 'downprocess', 'sign': sign, 'p': pwd}
            link_info = self._post(self._host_url + '/ajaxm.php', post_data)  # 保存了重定向前的链接信息和文件名
            second_page = self._get(share_url)  # 再次请求文件分享页面，可以看见文件名，时间，大小等信息(第二页)
            if not link_info or not second_page.text:
                return FileDetail(LanZouCloud.NETWORK_ERROR)
            link_info = link_info.json()
            second_page = remove_notes(second_page.text)
            # 提取文件信息
            f_name = link_info['inf']
            f_size = re.findall(r'大小：(.+?)</div>', second_page)[0]
            f_time = re.findall(r'class="n_file_infos">(.+?)</span>', second_page)[0]
            f_desc = re.findall(r'class="n_box_des">(.*?)</div>', second_page)[0]
        else:  # 文件没有设置提取码时,文件信息都暴露在分享页面上
            para = re.findall(r'<iframe.*?src="(.+?)"', first_page)[0]  # 提取下载页面 URL 的参数
            # 文件名可能在 <div> 中，可能在变量 filename 后面
            f_name = re.findall(r"<div style.+>([^<]+)</div>\n<div class=\"d2\">|filename = '(.*?)';", first_page)[0]
            f_name = f_name[0] or f_name[1]  # 确保正确获取文件名
            # f_size = re.findall(r'文件大小：</span>(.+?)<br>', first_page)[0]
            # f_time = re.findall(r'上传时间：</span>(.+?)<br>', first_page)[0]
            # f_desc = re.findall(r'文件描述：</span><br>\n?\s*(.+?)\s*</td>', first_page)[0]
            f_size = re.findall(r'文件大小：</span>(.+?)<br>', first_page)
            f_size = f_size[0] if f_size else ''
            f_time = re.findall(r'上传时间：</span>(.+?)<br>', first_page)
            f_time = f_time[0] if f_time else ''
            f_desc = re.findall(r'文件描述：</span><br>\n?\s*(.+?)\s*</td>', first_page)
            f_desc = f_desc[0] if f_desc else ''
            first_page = self._get(self._host_url + para)
            if not first_page:
                return FileDetail(LanZouCloud.NETWORK_ERROR)
            first_page = remove_notes(first_page.text)  # 去除网页注释
            # data: {'action': 'downprocess', 'sign': 'xxx', 'ver': 1}
            # 一般情况 sign 的值就在 data 里，有时放在变量 sg 后面
            post_data = re.findall(r'data : (.*),', first_page)[0]
            try:
                post_data = eval(post_data)  # 尝试转化为 dict,失败说明 sign 的值放在变量 sg 里
            except NameError:
                var_sg = re.search(r"var sg\s*=\s*'(.+?)'", first_page).group(1)  # 提取 sign 的值 'AmRVaw4_a.....'
                post_data = eval(post_data.replace('sg', f"'{var_sg}'"))  # 替换 sg 为 'AmRVaw4_a.....', 并转换为 dict
            link_info = self._post(self._host_url + '/ajaxm.php', post_data)
            if not link_info:
                return FileDetail(LanZouCloud.NETWORK_ERROR)
            else:
                link_info = link_info.json()
        # 这里开始获取文件直链
        if link_info['zt'] == 1:
            fake_url = link_info['dom'] + '/file/' + link_info['url']  # 假直连，存在流量异常检测
            direct_url = self._get(fake_url, allow_redirects=False).headers['Location']  # 重定向后的真直链
            f_type = f_name.split('.')[-1]
            return FileDetail(LanZouCloud.SUCCESS,
                              name=f_name, size=f_size, type=f_type, time=f_time,
                              desc=f_desc, pwd=pwd, url=share_url, durl=direct_url)
        else:
            return FileDetail(LanZouCloud.PASSWORD_ERROR)

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
        pwd = f_info['pwd'] if f_info['onof'] == '1' else ''
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
        """设置网盘文件(夹)的提取码"""
        # id 无效或者 id 类型不对应仍然返回成功 :(
        # 文件夹提取码长度 0-12 位  文件提取码 2-6 位
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
        folder_list = self.get_dir_list(parent_id)
        if folder_list.find_by_name(folder_name):  # 如果文件夹已经存在，直接返回 id
            return folder_list.find_by_name(folder_name).id
        raw_folders = self.get_move_folders()
        post_data = {"task": 2, "parent_id": parent_id or -1, "folder_name": folder_name,
                     "folder_description": desc}
        result = self._post(self._doupload_url, post_data)  # 创建文件夹
        if not result or result.json()['zt'] != 1:
            logger.debug(f"Mkdir {folder_name} error, {parent_id=}")
            return LanZouCloud.MKDIR_ERROR  # 正常时返回 id 也是 int，为了方便判断是否成功，网络异常或者创建失败都返回相同错误码
        # 允许再不同路径创建同名文件夹, 移动时可通过 get_move_paths() 区分
        for folder in self.get_move_folders():
            if not raw_folders.find_by_id(folder.id):
                return folder.id
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
        result.append(FolderId(name='LanZouCloud', id=-1))
        resp = self._post(self._doupload_url, data={"task": 19, "file_id": -1})
        if not resp or resp.json()['zt'] != 1:  # 获取失败或者网络异常
            return result
        for folder in resp.json()['info']:
            folder_id, folder_name = int(folder['folder_id']), folder['folder_name']
            result.append(FolderId(folder_name, folder_id))
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
        logger.debug(f"Move file {file_id=} to {folder_id=}")
        if not result:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.SUCCESS if result.json()['zt'] == 1 else LanZouCloud.FAILED

    def move_folder(self, folder_id, parent_folder_id=-1) -> int:
        """移动文件夹(官方并没有直接支持此功能)"""
        if folder_id == parent_folder_id or parent_folder_id < -1:
            return LanZouCloud.FAILED  # 禁止移动文件夹到自身，禁止移动到 -2 这样的文件夹(文件还在,但是从此不可见)

        folder = self.get_move_folders().find_by_id(folder_id)
        if not folder:
            logger.debug(f"Not found folder :{folder_id=}")
            return LanZouCloud.FAILED

        if self.get_dir_list(folder_id):
            logger.debug(f"Found subdirectory in {folder=}")
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

    def _upload_small_file(self, file_path, folder_id=-1, callback=None) -> int:
        """绕过格式限制上传不超过 max_size 的文件"""
        if not os.path.isfile(file_path):
            return LanZouCloud.PATH_ERROR

        need_delete = False  # 上传完成是否删除
        if not is_name_valid(os.path.basename(file_path)):  # 不允许上传的格式
            file_path = let_me_upload(file_path)  # 添加了报尾的新文件
            need_delete = True

        # 文件已经存在同名文件就删除
        filename = name_format(os.path.basename(file_path))
        file_list = self.get_file_list(folder_id)
        if file_list.find_by_name(filename):
            self.delete(file_list.find_by_name(filename).id)
        logger.debug(f'Upload file {file_path=} to {folder_id=}')

        file = open(file_path, 'rb')
        post_data = {
            "task": "1",
            "folder_id": str(folder_id),
            "id": "WU_FILE_0",
            "name": filename,
            "upload_file": (filename, file, 'application/octet-stream')
        }

        post_data = MultipartEncoder(post_data)
        tmp_header = self._headers.copy()
        tmp_header['Content-Type'] = post_data.content_type

        # MultipartEncoderMonitor 每上传 8129 bytes数据调用一次回调函数，问题根源是 httplib 库
        # issue : https://github.com/requests/toolbelt/issues/75
        # 上传完成后，回调函数会被错误的多调用一次(强迫症受不了)。因此，下面重新封装了回调函数，修改了接受的参数，并阻断了多余的一次调用
        self._upload_finished_flag = False  # 上传完成的标志

        def _call_back(read_monitor):
            if callback is not None:
                if not self._upload_finished_flag:
                    callback(filename, read_monitor.len, read_monitor.bytes_read)
                if read_monitor.len == read_monitor.bytes_read:
                    self._upload_finished_flag = True

        monitor = MultipartEncoderMonitor(post_data, _call_back)
        result = self._post('https://pc.woozooo.com/fileup.php', data=monitor, headers=tmp_header, timeout=None)
        if not result:  # 网络异常
            return LanZouCloud.NETWORK_ERROR
        else:
            result = result.json()
        if result["zt"] != 1:
            logger.debug(f'Upload failed: {result=}')
            return LanZouCloud.FAILED  # 上传失败

        file_id = result["text"][0]["id"]
        self.set_passwd(file_id)  # 文件上传后默认关闭提取码
        if need_delete:
            file.close()
            os.remove(file_path)
        return LanZouCloud.SUCCESS

    def _upload_big_file(self, file_path, dir_id, callback=None):
        """上传大文件, 且使得回调函数只显示一个文件"""
        file_size = os.path.getsize(file_path)  # 原始文件的字节大小
        file_name = os.path.basename(file_path)
        uploaded_size = 0

        def _callback(name, t_size, now_size):
            nonlocal uploaded_size
            if callback is not None:
                # MultipartEncoder 以后,文件数据流比原文件略大几百字节, now_size 略大于 file_size
                now_size = uploaded_size + now_size
                now_size = now_size if now_size < file_size else file_size  # 99.99% -> 100.00%
                callback(file_name, file_size, now_size)

        for path in big_file_split(file_path, max_size=self._max_size):
            if not path.endswith('.txt'):  # 记录文件大小不计入文件总大小
                code = self._upload_small_file(path, dir_id, _callback)
                uploaded_size += os.path.getsize(path)  # 记录上传总大小
            else:
                code = self._upload_small_file(path, dir_id)
            if code != LanZouCloud.SUCCESS:
                logger.debug(f"Upload big file failed:{path=}, {code=}")
                return LanZouCloud.FAILED  # 只要有一个失败就不用再继续了
        return LanZouCloud.SUCCESS

    def upload_file(self, file_path, folder_id=-1, callback=None) -> int:
        """解除限制上传文件"""
        if not os.path.isfile(file_path):
            return LanZouCloud.PATH_ERROR

        # 单个文件不超过 max_size 直接上传
        if os.path.getsize(file_path) <= self._max_size * 1048576:
            return self._upload_small_file(file_path, folder_id, callback)

        # 上传超过 max_size 的文件
        folder_name = os.path.basename(file_path).replace('.', '')  # 保存分段文件的文件夹名
        dir_id = self.mkdir(folder_id, folder_name, 'Big File')
        if dir_id == LanZouCloud.MKDIR_ERROR:
            return LanZouCloud.MKDIR_ERROR  # 创建文件夹失败就退出
        return self._upload_big_file(file_path, dir_id, callback)

    def upload_dir(self, dir_path, folder_id=-1, callback=None, failed_callback=None):
        """批量上传文件
        callback(filename, total_size, now_size) 用于显示进度
        failed_callback(code, file) 用于处理上传失败的文件
        """
        if not os.path.isdir(dir_path):
            return LanZouCloud.PATH_ERROR

        dir_name = dir_path.split(os.sep)[-1]
        dir_id = self.mkdir(folder_id, dir_name, '批量上传')
        if dir_id == LanZouCloud.MKDIR_ERROR:
            return LanZouCloud.MKDIR_ERROR

        for filename in os.listdir(dir_path):
            file_path = dir_path + os.sep + filename
            if not os.path.isfile(file_path):
                continue  # 跳过子文件夹
            code = self.upload_file(file_path, dir_id, callback)
            if code != LanZouCloud.SUCCESS:
                if failed_callback is not None:
                    failed_callback(code, filename)
        return LanZouCloud.SUCCESS

    def down_file_by_url(self, share_url, pwd='', save_path='./Download', callback=None) -> int:
        """通过分享链接下载文件(需提取码)"""
        if not is_file_url(share_url):
            return LanZouCloud.URL_INVALID
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        info = self.get_durl_by_url(share_url, pwd)
        logger.debug(f'File direct url info: {info}')
        if info.code != LanZouCloud.SUCCESS:
            return info.code

        resp = self._get(info.durl, stream=True)
        if not resp:
            return LanZouCloud.FAILED
        total_size = int(resp.headers['Content-Length'])
        file_path = save_path + os.sep + info.name
        logger.debug(f'Save file to {file_path=}')
        if os.path.exists(file_path):
            now_size = os.path.getsize(file_path)  # 本地已经下载的文件大小
        else:
            now_size = 0
        chunk_size = 4096
        last_512_bytes = b''  # 用于识别文件是否携带真实文件名信息
        headers = {'Range': 'bytes=%d-' % now_size}
        resp = self._get(info.durl, stream=True, headers=headers)
        with open(file_path, "ab") as f:
            for chunk in resp.iter_content(chunk_size):
                if chunk:
                    f.write(chunk)
                    # f.flush()  # 刷新，保证一点点的写入
                    now_size += len(chunk)
                    if total_size - now_size < 512:
                        last_512_bytes += chunk
                    if callback is not None:
                        callback(info.name, total_size, now_size)
        # 尝试解析文件报尾
        file_info = un_serialize(last_512_bytes[-512:])
        if file_info is not None and 'padding' in file_info:  # 大文件的记录文件也可以反序列化出 name,但是没有 padding
            real_name = file_info['name']
            new_file_path = save_path + os.sep + real_name
            logger.debug(f"Find meta info: {real_name=}")
            if os.path.exists(new_file_path):
                os.remove(new_file_path)  # 存在同名文件则删除
            os.rename(file_path, new_file_path)
            with open(new_file_path, 'rb+') as f:
                f.seek(-512, 2)  # 截断最后 512 字节数据
                f.truncate()
        return LanZouCloud.SUCCESS

    def down_file_by_id(self, fid, save_path='./Download', callback=None) -> int:
        """登录用户通过id下载文件(无需提取码)"""
        info = self.get_share_info(fid, is_file=True)
        if info.code != LanZouCloud.SUCCESS:
            return info.code
        return self.down_file_by_url(info.url, info.pwd, save_path, callback)

    def get_folder_info_by_url(self, share_url, dir_pwd=''):
        """获取文件夹里所有文件的信息"""
        if is_file_url(share_url):
            return FolderDetail(LanZouCloud.URL_INVALID)
        try:
            html = requests.get(share_url, headers=self._headers).text
        except requests.RequestException:
            return FolderDetail(LanZouCloud.NETWORK_ERROR)
        if "文件不存在" in html or "文件取消分享了" in html:
            return FolderDetail(LanZouCloud.FILE_CANCELLED)
        if '请输入密码' in html and len(dir_pwd) == 0:
            return FolderDetail(LanZouCloud.LACK_PASSWORD)
        try:
            # 获取文件需要的参数
            html = remove_notes(html)
            lx = re.findall(r"'lx':'?(\d)'?,", html)[0]
            t = re.findall(r"var [0-9a-z]{6} = '(\d{10})';", html)[0]
            k = re.findall(r"var [0-9a-z]{6} = '([0-9a-z]{15,})';", html)[0]
            # 文件夹的信息
            folder_id = re.findall(r"'fid':'?(\d+)'?,", html)[0]
            folder_name = re.findall(r"var.+?='(.+?)';\n.+document.title", html)[0]
            folder_time = re.findall(r'class="rets">([\d\-]+?)<a', html)[0]  # 日期不全 %m-%d
            folder_desc = re.findall(r'id="filename">(.+?)</span>', html)  # 无描述时无法完成匹配
            folder_desc = folder_desc[0] if len(folder_desc) == 1 else ''
        except IndexError:
            return FolderDetail(LanZouCloud.FAILED)

        page = 1
        files = FileList()
        while True:
            try:
                # 这里不用封装好的 post 函数是为了支持未登录的用户通过 URL 下载, 无密码时设置 pwd 字段也不影响
                post_data = {'lx': lx, 'pg': page, 'k': k, 't': t, 'fid': folder_id, 'pwd': dir_pwd}
                resp = self._post(self._host_url + '/filemoreajax.php', data=post_data, headers=self._headers).json()
            except requests.RequestException:
                return FolderDetail(LanZouCloud.NETWORK_ERROR)
            if resp['zt'] == 1:  # 成功获取一页文件信息
                for f in resp["text"]:
                    files.append(FileInFolder(
                        name=f["name_all"],  # 文件名
                        time=f["time"],  # 上传时间
                        size=f["size"],  # 文件大小
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
            folder_time = files[-1].time.split('-')[0] + '-' + folder_time
        else:  # 可恶，没有文件，日期就设置为今年吧
            folder_time = datetime.today().strftime('%Y-%m-%d')
        return FolderDetail(LanZouCloud.SUCCESS,
                            FolderInfo(folder_name, folder_id, dir_pwd, folder_time, folder_desc, share_url),
                            files)

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
                logger.debug(f"Big file checking: Failed")
                return None
            resp = self._get(info.durl)
            info = un_serialize(resp.content) if resp else None
            if info is not None:  # 确认是大文件
                name, size, parts = info.values()  # 真实文件名, 文件字节大小, 分段数据文件名(有序)
                file_list = [file_list.find_by_name(p) for p in parts]
                if all(file_list):  # 分段数据完整
                    logger.debug(f"Big file checking: PASS , {name=}, {size=}")
                    return name, size, file_list
                logger.debug(f"Big file checking: Failed, Missing some data")
        logger.debug(f"Big file checking: Failed")
        return None

    def _down_big_file(self, name, total_size, file_list, save_path, *, callback=None):
        """下载分段数据到一个文件，回调函数只显示一个文件"""
        now_size = 0
        chunk_size = 4096

        if not os.path.exists(save_path):
            os.makedirs(save_path)

        with open(save_path + os.sep + name, 'wb') as big_file:
            for file in file_list:
                try:
                    durl_info = self.get_durl_by_url(file.url)  # 分段文件无密码
                except AttributeError:
                    durl_info = self.get_durl_by_id(file.id)
                if durl_info.code != LanZouCloud.SUCCESS:
                    logger.debug(f"Can't get direct url: {file}")
                    return durl_info.code
                resp = self._get(durl_info.durl, stream=True)
                if not resp:
                    return LanZouCloud.FAILED
                data_iter = resp.iter_content(chunk_size)

                for chunk in data_iter:
                    if chunk:
                        now_size += len(chunk)
                        big_file.write(chunk)
                        if callback:
                            callback(name, total_size, now_size)

        return LanZouCloud.SUCCESS

    def down_dir_by_url(self, share_url, dir_pwd='', save_path='./Download', callback=None, mkdir=True,
                        failed_callback=None) -> int:
        """通过分享链接下载文件夹"""
        folder_detail = self.get_folder_info_by_url(share_url, dir_pwd)
        if folder_detail.code != LanZouCloud.SUCCESS:  # 获取文件信息失败
            return folder_detail.code

        # 检查是否大文件分段数据
        info = self._check_big_file(folder_detail.files)
        if info is not None:
            return self._down_big_file(*info, save_path, callback=callback)

        if mkdir:  # 自动创建子文件夹
            save_path = save_path + os.sep + folder_detail.folder.name
            if not os.path.exists(save_path):
                os.makedirs(save_path)

        # 不是大文件分段数据,直接下载
        for file in folder_detail.files:
            code = self.down_file_by_url(file.url, dir_pwd, save_path, callback)
            logger.debug(f'Download file result: Code:{code}, File: {file}')
            if code != LanZouCloud.SUCCESS:
                if failed_callback is not None:
                    failed_callback(code, file)

        return LanZouCloud.SUCCESS

    def down_dir_by_id(self, folder_id, save_path='./Download', *, callback=None, mkdir=True,
                       failed_callback=None) -> int:
        """登录用户通过id下载文件夹"""
        file_list = self.get_file_list(folder_id)
        if len(file_list) == 0:
            return LanZouCloud.FAILED

        # 检查是否大文件分段数据
        info = self._check_big_file(file_list)
        if info is not None:
            return self._down_big_file(*info, save_path, callback=callback)

        if mkdir:  # 自动创建子目录
            share_info = self.get_share_info(folder_id, False)
            if share_info.code != LanZouCloud.SUCCESS:
                return share_info.code
            save_path = save_path + os.sep + share_info.name
            if not os.path.exists(save_path):
                logger.debug(f"Mkdir {save_path}")
                os.makedirs(save_path)

        for file in file_list:
            code = self.down_file_by_id(file.id, save_path, callback)
            logger.debug(f'Download file result: Code:{code}, File: {file}')
            if code != LanZouCloud.SUCCESS:
                if failed_callback is not None:
                    failed_callback(code, file)

        return LanZouCloud.SUCCESS

    #-------------------------------------------------------------------------#
    def set_timeout(self, timeout):
        self._timeout = timeout

    def get_share_file_info(self, share_url, pwd=""):
        """获取分享文件信息"""
        if not is_file_url(share_url):
            return {"code": LanZouCloud.URL_INVALID, "info": ""}
        first_page = self._get(share_url)  # 文件分享页面(第一页)
        if not first_page:
            return {'code': LanZouCloud.NETWORK_ERROR, "info": ""}
        first_page = remove_notes(first_page.text)  # 去除网页里的注释
        if "文件取消" in first_page:
            return {"code": LanZouCloud.FILE_CANCELLED, "info": ""}
        if "输入密码" in first_page:  # 文件设置了提取码时
            if len(pwd) == 0:
                return {"code": LanZouCloud.LACK_PASSWORD, "info": ""}
            f_size = re.findall(r'class="n_filesize">[^<0-9]*([\.0-9 MKBmkbGg]+)<', first_page)
            f_size = f_size[0] if f_size else ""
            f_date = re.findall(r'class="n_file_infos">([-0-9 :月天小时分钟秒前]+)<', first_page)
            f_date = f_date[0] if f_date else ""
            f_desc = re.findall(r'class="n_box_des">(.*)<', first_page)
            f_desc = f_desc[0] if f_desc else ""
            sign = re.findall(r"sign=(\w+?)&", first_page)[0]
            post_data = {'action': 'downprocess', 'sign': sign, 'p': pwd}
            link_info = self._post(self._host_url + '/ajaxm.php', post_data)  # 保存了重定向前的链接信息和文件名
            second_page = self._get(share_url)  # 再次请求文件分享页面，可以看见文件名，时间，大小等信息(第二页)
            # link_info = self._post(self._host_url + "/ajaxm.php", post_data).json()
            if not link_info or not second_page.text:
                return {'code': LanZouCloud.NETWORK_ERROR, "info": ""}
            link_info = link_info.json()
            if link_info["zt"] == 1:
                if not f_size:
                    f_size = re.findall(r'大小：(.+?)</div>', second_page)[0]
                if not f_date:
                    f_date = re.findall(r'class="n_file_infos">(.+?)</span>', second_page)[0]
                infos = {link_info["inf"]: [None, link_info["inf"], f_size, f_date, "", pwd, f_desc, share_url]}
                return {"code": LanZouCloud.SUCCESS, "info": infos}
            else:
                return {"code": LanZouCloud.PASSWORD_ERROR, "info": ""}
        else:
            f_name = re.findall(r'<div style="[^"]+">([^><]*?)</div>', first_page)
            if f_name:
                f_name = f_name[0]
            else:
                f_name = re.findall(r"var filename = '(.*)';", first_page)[0]
            f_size = re.findall(r'文件大小：</span>([\.0-9 MKBmkbGg]+)<br', first_page)
            f_size = f_size[0] if f_size else ""
            f_date = re.findall(r'上传时间：</span>([-0-9 :月天小时分钟秒前]+)<br', first_page)
            f_date = f_date[0] if f_date else ""
            f_desc = re.findall(r'文件描述：</span><br>([^<]+)</td>', first_page)
            f_desc = f_desc[0].strip() if f_desc else ""
            infos = {f_name: [None, f_name, f_size, f_date, "", pwd, f_desc, share_url]}
            return {"code": LanZouCloud.SUCCESS, "info": infos}

    def get_share_folder_info(self, share_url, dir_pwd=""):
        """显示分享文件夹信息"""
        if is_file_url(share_url):
            return {"code": LanZouCloud.URL_INVALID, "info": ""}
        r = requests.get(share_url, headers=self._headers)
        if r.status_code != requests.codes.OK:  # 可能有403状态码
            return {"code": LanZouCloud.NETWORK_ERROR, "info": r.status_code}
        html = remove_notes(r.text)
        if "文件不存在" in html or "文件取消分享了" in html:
            return {"code": LanZouCloud.FILE_CANCELLED, "info": ""}
        lx = re.findall(r"'lx':'?(\d)'?,", html)[0]
        t = re.findall(r"var [0-9a-z]{6} = '(\d{10})';", html)[0]
        k = re.findall(r"var [0-9a-z]{6} = '([0-9a-z]{15,})';", html)[0]
        fid = re.findall(r"'fid':'?(\d+)'?,", html)[0]
        desc = re.findall(r'id="filename">([^<]+)</span', html)
        if desc:
            desc = str(desc[0])
        else:
            desc = ""
        page = 1
        if "请输入密码" in html:
            if len(dir_pwd) == 0:
                return {"code": LanZouCloud.LACK_PASSWORD, "info": ""}
            post_data = {"lx": lx, "pg": page, "k": k, "t": t, "fid": fid, "pwd": dir_pwd}
        else:
            post_data = {"lx": lx, "pg": page, "k": k, "t": t, "fid": fid}
        infos = {}
        while True:
            try:
                # 这里不用封装好的post函数是为了支持未登录的用户通过 URL 下载
                resp = requests.post(self._host_url + "/filemoreajax.php", data=post_data, headers=self._headers)
                if resp.status_code != requests.codes.OK:
                    return {"code": LanZouCloud.NETWORK_ERROR, "info": r.status_code}
                resp = resp.json()
            except requests.RequestException:
                return {"code": LanZouCloud.FAILED, "info": ""}

            if resp["zt"] == 3:  # 提取码错误
                return {"code": LanZouCloud.PASSWORD_ERROR, "info": ""}
            elif resp['zt'] == 2:  # 已经拿到全部文件的信息 r["info"] == "没有了"
                break
            elif resp["zt"] == 4:
                sleep(1.2)  # 服务器要求刷新，间隔大于一秒才能获得下一个页面，r["info"] == "请刷新，重试"
                continue
            elif resp["zt"] != 1:  # 其他错误
                return {"code": LanZouCloud.FAILED, "info": ""}
            # 获取文件信息成功后...
            infos.update({f["name_all"]: [None, f["name_all"], f["size"], f["time"], "", dir_pwd, desc,
                                    self._host_url + "/" + f["id"]] for f in resp["text"]})
            page += 1
            post_data["pg"] = page
        return {"code": LanZouCloud.SUCCESS, "info": infos}
