import logging
import os
import re
from random import sample
from shutil import rmtree
from datetime import timedelta, datetime
from subprocess import Popen, PIPE
import requests
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from time import sleep

__all__ = ['LanZouCloud']

# 调试日志设置
logger = logging.getLogger('lanzou')
logger.setLevel(logging.ERROR)
formatter = logging.Formatter(
    fmt="%(asctime)s [line:%(lineno)d] %(funcName)s %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S")
console = logging.StreamHandler()
console.setFormatter(formatter)
logger.addHandler(console)


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
        self._guise_suffix = '.dll'  # 不支持的文件伪装后缀
        self._fake_file_prefix = '__fake__'  # 假文件前缀
        self._rar_part_name = 'wtf'  # rar 分卷文件后缀 *.wtf01.rar
        self._timeout = 2000  # 每个请求的超时 ms(不包含下载响应体的用时)
        self._max_size = 8  # 单个文件大小上限 MB
        self._rar_path = None  # 解压工具路径
        self._host_url = 'https://www.lanzous.com'
        self._doupload_url = 'https://pc.woozooo.com/doupload.php'
        self._account_url = 'https://pc.woozooo.com/account.php'
        self._mydisk_url = 'https://pc.woozooo.com/mydisk.php'
        self._headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36',
            'Referer': 'https://www.lanzous.com',
            'Accept-Language': 'zh-CN,zh;q=0.9',  # 提取直连必需设置这个，否则拿不到数据
        }
        disable_warnings(InsecureRequestWarning)  # 全局禁用 SSL 警告

    def _get(self, url, **kwargs):
        try:
            return self._session.get(url, headers=self._headers, verify=False, timeout=self._timeout, **kwargs)
        except (ConnectionError, requests.RequestException):
            return None

    def _post(self, url, data, **kwargs):
        try:
            if 'headers' in kwargs.keys():  # 上传文件需要重新设置 headers，防止重复冲突
                return self._session.post(url, data, verify=False, timeout=self._timeout, **kwargs)
            return self._session.post(url, data, headers=self._headers, verify=False, timeout=self._timeout, **kwargs)
        except (ConnectionError, requests.RequestException):
            return None

    @staticmethod
    def _remove_notes(html) -> str:
        """删除网页的注释"""
        # 去掉 html 里面的 // 和 <!-- --> 注释，防止干扰正则匹配提取数据
        # 蓝奏云的前端程序员喜欢改完代码就把原来的代码注释掉,就直接推到生产环境了 =_=
        return re.sub(r'<!--.+?-->|\s+//\s*.+', '', html)

    @staticmethod
    def _name_format(name):
        """去除文件(夹)非法字符"""
        name = re.sub(r'\s', '_', name)  # 文件夹不能包含空白字符 (Linux 系统限制)
        name = re.sub(r'[#$%^!*<>)(+=`\'\"/:;,?]', '', name)  # 去除非法字符
        return name

    @staticmethod
    def _time_format(time_str) -> str:
        """输出格式化时间 %Y-%m-%d"""
        if '秒前' or '分钟前' in time_str:
            return datetime.today().strftime('%Y-%m-%d')
        elif '昨天' in time_str:
            return (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        elif '前天' in time_str:
            return (datetime.today() - timedelta(days=2)).strftime('%Y-%m-%d')
        elif '天前' in time_str:
            days = time_str.replace(' 天前', '')
            return (datetime.today() - timedelta(days=int(days))).strftime('%Y-%m-%d')
        else:
            return time_str

    def _get_right_name(self, filename):
        """去除伪装后缀，返回正确文件名和格式"""
        if filename.endswith(self._guise_suffix):
            filename = '.'.join(filename.split('.')[:-1])
        ftype = filename.split('.')[-1]  # 正确的文件后缀
        return filename, ftype.lower()

    @staticmethod
    def is_file_url(share_url) -> bool:
        """判断是否为文件的分享链接"""
        pat = 'https?://www.lanzous.com/i[a-z0-9]{6,}/?'
        return True if re.fullmatch(pat, share_url) else False

    @staticmethod
    def is_folder_url(share_url) -> bool:
        """判断是否为文件夹的分享链接"""
        pat = 'https?://www.lanzous.com/b[a-z0-9]{7,}/?'
        return True if re.fullmatch(pat, share_url) else False

    def set_rar_tool(self, bin_path) -> int:
        """设置解压工具路径"""
        if os.path.isfile(bin_path):
            self._rar_path = bin_path
            return LanZouCloud.SUCCESS
        else:
            return LanZouCloud.ZIP_ERROR

    def login(self, username, passwd) -> int:
        """登录蓝奏云控制台"""
        login_data = {"action": "login", "task": "login", "username": username, "password": passwd}
        html = self._get(self._account_url)
        if not html:
            return LanZouCloud.NETWORK_ERROR
        login_data['formhash'] = re.findall(r'name="formhash" value="(.+?)"', html.text)[0]
        html = self._post(self._account_url, login_data)
        if not html:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.SUCCESS if '登录成功' in html.text else LanZouCloud.FAILED

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

    def get_rec_dir_list(self) -> list:
        """获取回收站文件夹列表"""
        # 回收站中文件(夹)名只能显示前 17 个中文字符或者 34 个英文字符，如果这些字符相同，则在文件(夹)名后添加 (序号) ，以便区分
        html = self._get(self._mydisk_url, params={'item': 'recycle', 'action': 'files'})
        if not html:
            return []
        dirs = re.findall(r'folder_id=(\d+).+?>&nbsp;(.+?)\.{0,3}</a>.*\n+.*<td.+?>(.+?)</td>.*\n.*<td.+?>(.+?)</td>',
                          html.text)
        all_dir_list = []   # 文件夹信息列表
        dir_name_list = []  # 文件夹名列表d
        counter = 1     # 重复计数器
        for fid, name, size, time in dirs:
            if name in dir_name_list:   # 文件夹名前 17 个中文或 34 个英文重复
                counter += 1
                name = f'{name}({counter})'
            else:
                counter = 1
            dir_name_list.append(name)
            all_dir_list.append({'name': name, 'id': int(fid), 'size': size, 'time': time})
        return all_dir_list

    def get_rec_file_list(self, folder_id=-1) -> list:
        """获取回收站文件列表"""
        if folder_id == -1:  # 列出回收站根目录文件
            # 回收站文件夹中的文件也会显示在根目录
            html = self._get(self._mydisk_url, params={'item': 'recycle', 'action': 'files'})
            if not html:
                return []
            html = LanZouCloud._remove_notes(html.text)
            files = re.findall(
                r'fl_sel_ids[^\n]+value="(\d+)".+?filetype/(\w+)\.gif.+?/>\s(.*?)\.{0,3}</a>.+?<td.+?>([\d\-]+?)</td>',
                html, re.DOTALL)
            all_file_list = []
            file_name_list = []
            counter = 1
            for fid, ftype, name, time in files:
                if name in file_name_list:  # 防止长文件名前 17:34 个字符相同重名
                    counter += 1
                    name = f'{name}({counter})'
                else:
                    counter = 1
                file_name_list.append(name)

                if not name.endswith(ftype):    # 防止文件名太长导致丢失了文件后缀
                    name = name + '.' + ftype

                name, ftype = self._get_right_name(name)
                all_file_list.append({'name': name, 'id': int(fid), 'time': time, 'type': ftype})
            return all_file_list
        else:  # 列出回收站中文件夹内的文件,信息只有部分文件名和文件大小
            para = {'item': 'recycle', 'action': 'folder_restore', 'folder_id': folder_id}
            html = self._get(self._mydisk_url, params=para)
            if not html or '此文件夹没有包含文件' in html.text:
                return []
            html = LanZouCloud._remove_notes(html.text)
            files = re.findall(
                r'com/(\d+?)".+?filetype/(\w+)\.gif.+?/>&nbsp;(.+?)\.{0,3}</a> <font color="#CCCCCC">\((.+?)\)</font>',
                html)
            all_file_list = []
            file_name_list = []
            counter = 1
            for fid, ftype, name, size in files:
                name, ftype = self._get_right_name(name)
                if name in file_name_list:
                    counter += 1
                    name = f'{name}({counter})'
                else:
                    counter = 1
                file_name_list.append(name)
                if not name.endswith(ftype):
                    name = name + '.' + ftype
                all_file_list.append({'name': name, 'id': int(fid), 'size': size, 'type': ftype})
            return all_file_list

    def get_rec_all(self) -> (dict, list):
        """获取整理后回收站的所有信息"""
        root_files = self.get_rec_file_list()  # 根目录下的所有文件，包括零碎的和文件夹里面的,文件属性: name,id,type,time
        root_file_name_list = {root_files[n]['name']: n for n in range(len(root_files))}  # 根目录文件 name-index 列表
        all_sub_folders = []  # 保存整理后的文件夹列表
        for folder in self.get_rec_dir_list():  # 遍历所有子文件夹
            this_folder = {'name': folder['name'], 'id': folder['id'], 'time': folder['time'], 'size': folder['size'], 'files': []}
            for file in self.get_rec_file_list(folder['id']):   # 文件夹内的文件属性: name,id,type,size
                if file['name'] in root_file_name_list.keys():  # 根目录存在同名文件
                    same_file_in_root = root_files.pop(root_file_name_list.get(file['name']))   # 从根目录文件列表弹出
                    file['time'] = same_file_in_root['time']    # time 信息可以用来补充文件夹中的文件
                    this_folder['files'].append(file)
                else:   # 根目录没有同名文件(用户手动删了),文件任在文件夹中，只是根目录不显示，time 信息无法补全了
                    file['time'] = folder['time']   # 那就设置时间为文件夹的创建时间
                    this_folder['files'].append(file)
            all_sub_folders.append(this_folder)
        return root_files, all_sub_folders

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

    def recovery(self, fid, is_file=True):
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

    def get_file_list(self, folder_id=-1) -> list:
        """获取文件列表"""
        page = 1
        file_list = []
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
            for file in resp["text"]:
                filename, ftype = self._get_right_name(file['name_all'])    # 获取真实文件名和格式
                file_list.append({
                    'id': int(file['id']),
                    'name': filename,
                    'time': LanZouCloud._time_format(file['time']),  # 上传时间
                    'size': file['size'],  # 文件大小
                    'type': ftype,  # 文件类型
                    'downs': int(file['downs']),  # 下载次数
                    'has_pwd': True if int(file['onof']) == 1 else False,  # 是否存在提取码
                    'has_des': True if int(file['is_des']) == 1 else False  # 是否存在描述
                })
        return file_list

    def get_file_id_list(self, folder_id=-1) -> dict:
        """获取文件name-id列表"""
        info = {i['name']: i['id'] for i in self.get_file_list(folder_id)}
        return {key: info.get(key) for key in sorted(info.keys())}

    def get_dir_list(self, folder_id=-1) -> list:
        """获取子文件夹列表"""
        folder_list = []
        para = {'item': 'files', 'action': 'index', 'folder_node': 1, 'folder_id': folder_id}
        html = self._get(self._mydisk_url, params=para)
        if not html:
            return []
        info = re.findall(r'&nbsp;(.+?)</a>&nbsp;.+"folk(\d+)"(.*?)>.+#BBBBBB">\[?(.*?)\.*\]?</font>', html.text)
        for folder_name, fid, pwd_flag, desc in info:
            folder_list.append({
                "id": int(fid),
                "name": folder_name.replace('&amp;', '&'),  # 修复网页中的 &amp; 为 &
                "has_pwd": True if pwd_flag else False,  # 有密码时 pwd_flag 值为 style="display:initial"
                "desc": desc  # 文件夹描述信息
            })
        return folder_list

    def get_dir_id_list(self, folder_id=-1) -> dict:
        """获取文件夹 name-id 列表"""
        info = {i['name']: i['id'] for i in self.get_dir_list(folder_id)}
        return {key: info.get(key) for key in sorted(info.keys())}

    def get_full_path(self, folder_id=-1) -> dict:
        """获取文件夹完整路径"""
        path_list = {'LanZouCloud': -1}
        html = self._get(self._mydisk_url, params={'item': 'files', 'action': 'index', 'folder_id': folder_id})
        if not html:
            return path_list
        html = LanZouCloud._remove_notes(html.text)
        path = re.findall(r'&raquo;&nbsp;.+?folder_id=(\d+)">.+?&nbsp;(.+?)</a>', html)
        for fid, name in path:
            path_list[name] = int(fid)
        # 获取当前文件夹名称
        if folder_id != -1:
            current_folder = re.search(r'align="(top|absmiddle)" />&nbsp;(.+?)\s<(span|font)', html).group(2).replace('&amp;', '&')
            path_list[current_folder] = folder_id
        return path_list

    def get_file_info_by_url(self, share_url, pwd=''):
        """获取直链"""
        no_result = {'name': '', 'size': '', 'type': '', 'time': '', 'desc': '', 'pwd': '', 'url': '', 'durl': ''}
        if not self.is_file_url(share_url):  # 非文件链接返回错误
            return {'code': LanZouCloud.URL_INVALID, **no_result}

        first_page = self._get(share_url)  # 文件分享页面(第一页)
        if not first_page:
            return {'code': LanZouCloud.NETWORK_ERROR, **no_result}

        first_page = LanZouCloud._remove_notes(first_page.text)  # 去除网页里的注释
        if '文件取消' in first_page:
            return {'code': LanZouCloud.FILE_CANCELLED, **no_result}

        # 这里获取下载直链 304 重定向前的链接
        if '输入密码' in first_page:  # 文件设置了提取码时
            if len(pwd) == 0:
                return {'code': LanZouCloud.LACK_PASSWORD, **no_result}  # 没给提取码直接退出
            # data : 'action=downprocess&sign=AGZRbwEwU2IEDQU6BDRUaFc8DzxfMlRjCjTPlVkWzFSYFY7ATpWYw_c_c&p='+pwd,
            sign = re.findall(r"sign=(\w+?)&", first_page)[0]
            post_data = {'action': 'downprocess', 'sign': sign, 'p': pwd}
            link_info = self._post(self._host_url + '/ajaxm.php', post_data)  # 保存了重定向前的链接信息和文件名
            second_page = self._get(share_url)  # 再次请求文件分享页面，可以看见文件名，时间，大小等信息(第二页)
            if not link_info or not second_page.text:
                return {'code': LanZouCloud.NETWORK_ERROR, **no_result}
            link_info = link_info.json()
            second_page = LanZouCloud._remove_notes(second_page.text)
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
            f_size = re.findall(r'文件大小：</span>(.+?)<br>', first_page)[0]
            f_time = re.findall(r'上传时间：</span>(.+?)<br>', first_page)[0]
            f_desc = re.findall(r'文件描述：</span><br>\n?\s*(.+?)\s*</td>', first_page)[0]
            first_page = self._get(self._host_url + para)
            if not first_page:
                return {'code': LanZouCloud.NETWORK_ERROR, **no_result}
            first_page = LanZouCloud._remove_notes(first_page.text)  # 去除网页注释
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
                return {'code': LanZouCloud.NETWORK_ERROR, **no_result}
            else:
                link_info = link_info.json()

        # 这里开始获取文件直链
        if link_info['zt'] == 1:
            fake_url = link_info['dom'] + '/file/' + link_info['url']  # 假直连，存在流量异常检测
            direct_url = self._get(fake_url, allow_redirects=False).headers['Location']  # 重定向后的真直链
            f_name, ftype = self._get_right_name(f_name)
            return {'code': LanZouCloud.SUCCESS, 'name': f_name, 'size': f_size, 'type': ftype,
                    'time': LanZouCloud._time_format(f_time), 'desc': f_desc, 'pwd': pwd,
                    'url': share_url, 'durl': direct_url}
        else:
            return {'code': LanZouCloud.PASSWORD_ERROR, **no_result}

    def get_file_info_by_id(self, file_id):
        """通过 id 获取文件信息"""
        info = self.get_share_info(file_id)
        if info['code'] != LanZouCloud.SUCCESS:
            return {'code': info['code'], 'name': '', 'size': '', 'type': '', 'time': '', 'desc': '', 'durl': ''}
        return self.get_file_info_by_url(info['url'], info['pwd'])

    def get_durl_by_url(self, share_url, pwd=''):
        """通过分享链接获取下载直链"""
        file_info = self.get_file_info_by_url(share_url, pwd)
        if file_info['code'] != LanZouCloud.SUCCESS:
            return {'code': file_info['code'], 'name': '', 'durl': ''}
        return {'code': LanZouCloud.SUCCESS, 'name': file_info['name'], 'durl': file_info['durl']}

    def get_durl_by_id(self, file_id):
        """登录用户通过id获取直链"""
        info = self.get_share_info(file_id, is_file=True)  # 能获取直链，一定是文件
        return self.get_durl_by_url(info['url'], info['pwd'])

    def get_share_info(self, fid, is_file=True) -> dict:
        """获取文件(夹)提取码、分享链接"""
        no_result = {'name': '', 'url': '', 'pwd': '', 'desc': ''}
        post_data = {'task': 22, 'file_id': fid} if is_file else {'task': 18, 'folder_id': fid}  # 获取分享链接和密码用
        f_info = self._post(self._doupload_url, post_data)
        if not f_info:
            return {'code': LanZouCloud.NETWORK_ERROR, **no_result}
        else:
            f_info = f_info.json()['info']

        # id 有效性校验
        if ('f_id' in f_info.keys() and f_info['f_id'] == 'i') or ('name' in f_info.keys() and not f_info['name']):
            return {'code': LanZouCloud.ID_ERROR, **no_result}

        # onof=1 时，存在有效的提取码; onof=0 时不存在提取码，但是 pwd 字段还是有一个无效的随机密码
        pwd = f_info['pwd'] if f_info['onof'] == '1' else ''
        if 'f_id' in f_info.keys():  # 说明返回的是文件的信息
            url = f_info['is_newd'] + '/' + f_info['f_id']  # 文件的分享链接需要拼凑
            file_info = self._post(self._doupload_url, {'task': 12, 'file_id': fid})  # 文件信息
            if not file_info:
                return {'code': LanZouCloud.NETWORK_ERROR, **no_result}
            name, _ = self._get_right_name(file_info.json()['text'])
            desc = file_info.json()['info']
        else:
            url = f_info['new_url']  # 文件夹的分享链接可以直接拿到
            name = f_info['name']  # 文件夹名
            desc = f_info['des']  # 文件夹描述
        return {'code': LanZouCloud.SUCCESS, 'name': name, 'url': url, 'pwd': pwd, 'desc': desc}

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
        folder_name = LanZouCloud._name_format(folder_name)
        folder_list = self.get_dir_id_list(parent_id)
        if folder_name in folder_list.keys():  # 如果文件夹已经存在，直接返回 id
            return folder_list.get(folder_name)
        if folder_name in self.get_folder_id_list().keys():     # 防止文件夹名重复导致其它功能混乱
            return self.mkdir(parent_id, folder_name + '_', desc)
        post_data = {"task": 2, "parent_id": parent_id or -1, "folder_name": folder_name,
                     "folder_description": desc}
        result = self._post(self._doupload_url, post_data)  # 创建文件夹
        if not result or result.json()['zt'] != 1:
            return LanZouCloud.MKDIR_ERROR  # 正常时返回 id 也是 int，为了方便判断是否成功，网络异常或者创建失败都返回相同错误码
        return self.get_folder_id_list().get(folder_name)  # 返回文件夹 id

    def _set_dir_info(self, folder_id, folder_name, desc='') -> int:
        """重命名文件夹及其描述"""
        # 不能用于重命名文件，id 无效仍然返回成功
        folder_name = LanZouCloud._name_format(folder_name)
        post_data = {'task': 4, 'folder_id': folder_id, 'folder_name': folder_name, 'folder_description': desc}
        result = self._post(self._doupload_url, post_data)
        if not result:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.SUCCESS if result.json()['zt'] == 1 else LanZouCloud.FAILED

    def rename_dir(self, folder_id, folder_name) -> int:
        """重命名文件夹"""
        # 重命名文件要开会员额
        info = self.get_share_info(folder_id, is_file=False)
        if info['code'] != LanZouCloud.SUCCESS:
            return info['code']
        return self._set_dir_info(folder_id, folder_name, info['desc'])

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
            if info['code'] != LanZouCloud.SUCCESS:
                return info['code']
            return self._set_dir_info(fid, info['name'], desc)

    def get_folder_id_list(self) -> dict:
        """获取全部文件夹 name-id 列表，用于移动文件至新的文件夹"""
        # 这里 file_id 可以为任意值,不会对结果产生影响
        result = {'LanZouCloud': -1}
        resp = self._post(self._doupload_url, data={"task": 19, "file_id": -1})
        if not resp or resp.json()['zt'] != 1:  # 获取失败或者网络异常
            return result
        folder_id_list = {i['folder_name']: int(i['folder_id']) for i in resp.json()['info']}
        return {**result, **folder_id_list}

    def move_file(self, file_id, folder_id=-1) -> int:
        """移动文件到指定文件夹"""
        # 移动回收站文件也返回成功(实际上行不通) (+_+)?
        post_data = {'task': 20, 'file_id': file_id, 'folder_id': folder_id}
        result = self._post(self._doupload_url, post_data)
        if not result:
            return LanZouCloud.NETWORK_ERROR
        return LanZouCloud.SUCCESS if result.json()['zt'] == 1 else LanZouCloud.FAILED

    def _upload_a_file(self, file_path, folder_id=-1, call_back=None) -> int:
        """上传文件到蓝奏云上指定的文件夹(默认根目录)"""
        if not os.path.isfile(file_path):
            return LanZouCloud.PATH_ERROR
        file_name = re.sub(r'\s', '_', os.path.basename(file_path))  # 从文件路径截取文件名，去除空白字符(Linux文件名限制)
        tmp_list = {**self.get_file_id_list(folder_id), **self.get_dir_id_list(folder_id)}
        if file_name in tmp_list.keys():
            self.delete(tmp_list[file_name])  # 文件已经存在就删除

        suffix = file_name.split(".")[-1]
        valid_suffix_list = ['doc', 'docx', 'zip', 'rar', 'apk', 'ipa', 'txt', 'exe', '7z', 'e', 'z', 'ct',
                             'ke', 'cetrainer', 'db', 'tar', 'pdf', 'w3x', 'epub', 'mobi', 'azw', 'azw3',
                             'osk', 'osz', 'xpa', 'cpk', 'lua', 'jar', 'dmg', 'ppt', 'pptx', 'xls', 'xlsx',
                             'mp3', 'iso', 'img', 'gho', 'ttf', 'ttc', 'txf', 'dwg', 'bat', 'dll']
        # 不支持上传的格式，通过修改后缀蒙混过关
        if suffix not in valid_suffix_list:
            file_name = file_name + self._guise_suffix

        # 分卷后缀 .part[0-9]+.rar 被蓝奏云限制上传，改一下命名规则
        # .part[0-9]+.rar 改成 .xxx[0-9]+.rar 仍可以解压,以此绕过蓝奏云的检测
        if suffix == 'rar' and 'part' in file_name.split(".")[-2]:
            file_name = file_name.replace('.part', f'.{self._rar_part_name}')
        logger.debug(f'Upload file {file_path} to folder ID#{folder_id} as "{file_name}"')
        with open(file_path, 'rb') as _file_handle:
            post_data = {
                "task": "1",
                "folder_id": str(folder_id),
                "id": "WU_FILE_0",
                "name": file_name,
                "upload_file": (file_name, _file_handle, 'application/octet-stream')
            }

            post_data = MultipartEncoder(post_data)
            tmp_header = self._headers.copy()
            tmp_header['Content-Type'] = post_data.content_type
            # 让回调函数里不显示伪装后缀名
            file_name, _ = self._get_right_name(file_name)

            # MultipartEncoderMonitor 每上传 8129 bytes数据调用一次回调函数，问题根源是 httplib 库
            # issue : https://github.com/requests/toolbelt/issues/75
            # 上传完成后，回调函数会被错误的多调用一次(强迫症受不了)。因此，下面重新封装了回调函数，修改了接受的参数，并阻断了多余的一次调用
            self._upload_finished_flag = False  # 上传完成的标志

            def _call_back(read_monitor):
                if call_back is not None:
                    if not self._upload_finished_flag:
                        call_back(file_name, read_monitor.len, read_monitor.bytes_read)
                    if read_monitor.len == read_monitor.bytes_read:
                        self._upload_finished_flag = True

            monitor = MultipartEncoderMonitor(post_data, _call_back)
            result = self._post('http://pc.woozooo.com/fileup.php', data=monitor, headers=tmp_header)
            if not result:  # 网络异常
                return LanZouCloud.NETWORK_ERROR
            else:
                result = result.json()
            if result["zt"] != 1:
                logger.warning(f'Upload failed: {result}')
                return LanZouCloud.FAILED  # 上传失败

            # 蓝奏云禁止用户连续上传 100M 的文件，因此需要上传一个 100M 的文件，然后上传一个“假文件”糊弄过去
            # 这里检查上传的文件是否为“假文件”，是的话上传后就立刻删除
            file_id = result["text"][0]["id"]
            if result['text'][0]['name_all'].startswith(self._fake_file_prefix):
                self.delete(file_id)
                self.delete_rec(file_id)
            else:
                self.set_passwd(file_id)  # 文件上传后默认关闭提取码
            return LanZouCloud.SUCCESS

    def upload_file(self, file_path, folder_id=-1, call_back=None) -> dict:
        """解除限制上传文件"""
        if not os.path.isfile(file_path):
            return {'code': LanZouCloud.PATH_ERROR, 'failed': None}

        # 单个文件不超过 100MB 时直接上传
        if os.path.getsize(file_path) <= self._max_size * 1048576:
            code = self._upload_a_file(file_path, folder_id, call_back)
            if code == LanZouCloud.SUCCESS:
                return {'code': code, 'failed': []}
            else:
                return {'code': code, 'failed': [file_path.split(os.sep)[-1]]}

        # 超过 100MB 的文件，分卷压缩后上传
        if not self._rar_path:
            return {'code': LanZouCloud.ZIP_ERROR, 'failed': None}
        rar_level = 0  # 压缩等级(0-5)，0 不压缩, 5 最好压缩(耗时长)
        part_sum = os.path.getsize(file_path) // (self._max_size * 1048576) + 1
        file_name = file_path.split(os.sep)[-1].split('.')  # 文件名去掉无后缀，用作分卷文件的名字
        file_name = file_name[0] if len(file_name) == 1 else '.'.join(file_name[:-1])  # 处理没有后缀的文件
        file_list = [f"{file_name}.part{i}.rar" for i in range(1, part_sum + 1)]
        if not os.path.exists('./tmp'):
            os.mkdir('./tmp')  # 本地保存分卷文件的临时文件夹
        # 使用压缩工具分卷压缩大文件  # -rr5% 导致 rar.exe 一直在后台占用文件
        cmd_args = f'a -m{rar_level} -v{self._max_size}m -ep -y "./tmp/{file_name}" "{file_path}"'
        if os.name == 'nt':
            command = f"start /b {self._rar_path} {cmd_args}"  # windows 平台调用 rar.exe 实现压缩
        else:
            command = f"{self._rar_path} {cmd_args}"  # linux 平台使用 rar 命令压缩
        try:
            logger.debug(f'rar command: {command}')
            p = Popen(command, shell=True, close_fds=True, stdout=PIPE, stderr=PIPE, stdin=PIPE)
            p.wait()
            if p.returncode != 0:  # 打包压缩失败
                rmtree('./tmp')
                return {'code': LanZouCloud.ZIP_ERROR, 'failed': None}
        except Exception:  # 其它未知错误
            rmtree('./tmp')
            return {'code': LanZouCloud.ZIP_ERROR, 'failed': None}


        # 上传并删除分卷文件
        folder_name = '.'.join(file_list[0].split('.')[:-2])  # 文件名去除".xxx.rar"作为网盘新建的文件夹名
        dir_id = self.mkdir(folder_id, folder_name, '分卷压缩文件')
        if dir_id == LanZouCloud.MKDIR_ERROR:
            rmtree('./tmp')
            return {'code': LanZouCloud.MKDIR_ERROR, 'failed': None}  # 创建文件夹失败就退出

        result = {'code': LanZouCloud.SUCCESS, 'failed': []}  # 文件上传结果
        for f in file_list:
            # 蓝奏云禁止用户连续上传 100M 的文件，因此需要上传一个 100M 的文件，然后上传一个“假文件”糊弄过去
            temp_file = './tmp/' + self._fake_file_prefix + ''.join(sample('abcdefg12345', 6)) + '.txt'
            with open(temp_file, 'w') as t_f:
                t_f.write('FUCK LanZouCloud')
            self._upload_a_file(temp_file, dir_id)
            os.remove(temp_file)
            # 现在上传真正的文件并保存上传结果
            code = self._upload_a_file('./tmp/' + f, dir_id, call_back)
            if code != LanZouCloud.SUCCESS:  # 记录上传失败的文件
                result['code'] = LanZouCloud.FAILED
                result['failed'].append(f)
            else:
                try:
                    os.remove('./tmp/' + f)
                except PermissionError:
                    print(f"无法删除文件{f}，rar占用文件中！")
        try:
            rmtree('./tmp')  # 此处可能会遇到bug !!!
        except PermissionError:
            print("无法删除文件，rar占用文件中！")
        return result

    def upload_dir(self, dir_path, folder_id=-1, call_back=None) -> dict:
        """批量上传"""
        if not os.path.isdir(dir_path):
            return {'code': LanZouCloud.PATH_ERROR, 'failed': None}
        dir_name = dir_path.split(os.sep)[-1]
        dir_id = self.mkdir(folder_id, dir_name, '批量上传')
        if dir_id == LanZouCloud.MKDIR_ERROR:
            return {'code': LanZouCloud.MKDIR_ERROR, 'failed': None}
        result = {'code': LanZouCloud.SUCCESS, 'failed': []}  # 全部上传成功
        for file in os.listdir(dir_path):
            if not os.path.isfile(dir_path + os.sep + file):
                continue  # 跳过子文件夹
            up_failed = self.upload_file(dir_path + os.sep + file, dir_id, call_back)['failed']
            if up_failed:  # 上传失败的文件列表
                result['code'] = LanZouCloud.FAILED
                result['failed'] += up_failed
        return result

    def down_file_by_url(self, share_url, pwd='', save_path='.', call_back=None) -> int:
        """通过分享链接下载文件(需提取码)"""
        if not self.is_file_url(share_url):
            return LanZouCloud.URL_INVALID
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        info = self.get_durl_by_url(share_url, pwd)
        logger.debug(f'File direct url info: {info}')
        if info['code'] != LanZouCloud.SUCCESS:
            return info['code']
        try:
            sleep(1.2)
            r = requests.get(info['durl'], stream=True)
            total_size = int(r.headers['content-length'])
            now_size = 0
            save_path = save_path + os.sep + info['name']
            logger.debug(f'Save file to {save_path}')
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        now_size += len(chunk)
                        if call_back is not None:
                            call_back(info['name'], total_size, now_size)
            return LanZouCloud.SUCCESS
        # except ValueError as err:
        except Exception as err:
            print("err:[", err, "]END-err")
            return LanZouCloud.FAILED

    def down_file_by_id(self, fid, save_path='.', call_back=None) -> int:
        """登录用户通过id下载文件(无需提取码)"""
        info = self.get_share_info(fid, is_file=True)
        if info['code'] != LanZouCloud.SUCCESS:
            return info['code']
        return self.down_file_by_url(info['url'], info['pwd'], save_path, call_back)

    def _unzip(self, file_list, save_path) -> int:
        """解压分卷文件"""
        if not self._rar_path:  # 没有设置解压工具
            logger.debug('NOT SET UNRAR TOOL!')
            return LanZouCloud.ZIP_ERROR

        first_rar = save_path + os.sep + file_list[0]
        if os.name == 'nt':
            command = f'start /b {self._rar_path} -y e "{first_rar}" "{save_path}"'  # Windows 平台
        else:
            command = f'{self._rar_path} -y e {first_rar} {save_path}'  # Linux 平台
        try:
            logger.debug(f'unzip command: {command}')
            # 解压出原文件
            p = Popen(command, shell=True, stdout=PIPE, stderr=PIPE, stdin=PIPE)
            p.wait()
            if p.returncode != 0:  # 解压失败状态码非0
                return LanZouCloud.ZIP_ERROR
            sleep(1)
            for f_name in file_list:  # 删除分卷文件
                logger.debug(f'delete rar file: {save_path + os.sep + f_name}')
                os.remove(save_path + os.sep + f_name)
            return LanZouCloud.SUCCESS
        except Exception:  # 其它未知错误
            return LanZouCloud.ZIP_ERROR

    def get_folder_info_by_url(self, share_url, dir_pwd='') -> dict:
        """获取文件夹里所有文件的信息"""
        no_result = {'folder': {}, 'files': []}
        if LanZouCloud.is_file_url(share_url):
            return {'code': LanZouCloud.URL_INVALID, **no_result}
        try:
            html = requests.get(share_url, headers=self._headers).text
            html = LanZouCloud._remove_notes(html)
        except requests.RequestException:
            return {'code': LanZouCloud.NETWORK_ERROR, **no_result}
        if '文件不存在' in html:
            return {'code': LanZouCloud.FILE_CANCELLED, **no_result}
        if '请输入密码' in html and len(dir_pwd) == 0:
            return {'code': LanZouCloud.LACK_PASSWORD, **no_result}
        try:
            # 获取文件需要的参数
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
            return {'code': LanZouCloud.FAILED, **no_result}

        page = 1
        files = []
        while True:
            try:
                # 这里不用封装好的 post 函数是为了支持未登录的用户通过 URL 下载, 无密码时设置 pwd 字段也不影响
                post_data = {'lx': lx, 'pg': page, 'k': k, 't': t, 'fid': folder_id, 'pwd': dir_pwd}
                resp = requests.post(self._host_url + '/filemoreajax.php', data=post_data, headers=self._headers).json()
            except requests.RequestException:
                return {'code': LanZouCloud.NETWORK_ERROR, **no_result}
            if resp['zt'] == 1:  # 成功获取一页文件信息
                for f in resp["text"]:
                    filename, ftype = self._get_right_name(f["name_all"])
                    files.append({
                        'name': filename,  # 文件名
                        'time': LanZouCloud._time_format(f["time"]),  # 上传时间
                        'size': f["size"],  # 文件大小
                        'type': ftype,  # 文件格式
                        'url': self._host_url + "/" + f["id"]  # 文件分享链接
                    })
                page += 1  # 下一页
                continue
            elif resp['zt'] == 2:  # 已经拿到全部的文件信息
                break
            elif resp['zt'] == 3:  # 提取码错误
                return {'code': LanZouCloud.PASSWORD_ERROR, **no_result}
            elif resp["zt"] == 4:
                sleep(1)  # 服务器要求刷新，间隔大于一秒才能获得下一个页面
                continue
            else:
                return {'code': LanZouCloud.FAILED, **no_result}  # 其它未知错误
        # 通过文件的时间信息补全文件夹的年份(如果有文件的话)
        if files:   # 最后一个文件上传时间最早，文件夹的创建年份与其相同
            folder_time = files[-1]['time'].split('-')[0] + '-' + folder_time
        else:   # 可恶，没有文件，日期就设置为今年吧
            folder_time = datetime.today().strftime('%Y-%m-%d')
        return {'code': LanZouCloud.SUCCESS,
                'folder': {'name': folder_name, 'id': folder_id, 'pwd': dir_pwd, 'time': folder_time,
                           'desc': folder_desc, 'url': share_url},
                'files': files}

    def get_folder_info_by_id(self, folder_id):
        """通过 id 获取文件夹及内部文件信息"""
        info = self.get_share_info(folder_id, is_file=False)
        if info['code'] != LanZouCloud.SUCCESS:
            return {'code': info['code'], 'folder': {}, 'files': []}
        return self.get_folder_info_by_url(info['url'], info['pwd'])

    def down_dir_by_url(self, share_url, dir_pwd='', save_path='./down', call_back=None) -> dict:
        """通过分享链接下载文件夹"""
        files = self.get_folder_info_by_url(share_url, dir_pwd)
        if files['code'] != LanZouCloud.SUCCESS:  # 获取文件信息失败
            return {'code': files['code'], 'failed': None}
        files = {f['name']: f['url'] for f in files['files']}  # { "name": "share_url", ...}
        info = sorted(files.items(), key=lambda x: x[0])  # info = [(name, url),(name, url),...] 已排序
        # 开始批量下载操作
        result = {'code': LanZouCloud.SUCCESS, 'failed': []}  # 假设全部下载成功，无失败的文件
        for name, url in info:
            code = self.down_file_by_url(url, '', save_path, call_back)
            if code != LanZouCloud.SUCCESS:  # 有文件下载失败了
                result['code'] = LanZouCloud.FAILED
                result['failed'].append({'name': name, 'url': url, 'code': code})

        # 部分文件下载失败，没必要尝试解压了
        if result['code'] != LanZouCloud.SUCCESS:
            return result

        # 全部下载成功且文件都是分卷压缩文件 *.xxx[0-9]+.rar，则下载后需要解压
        f_name_list = [f[0] for f in info]  # 文件名列表
        for name in f_name_list:
            if not re.match(r'.*\.\w+[0-9]+\.rar', name):
                return result  # 有一个不匹配，就无需解压

        if self._unzip(f_name_list, save_path) == LanZouCloud.ZIP_ERROR:
            return {'code': LanZouCloud.ZIP_ERROR, 'failed': []}  # 解压时发生错误
        return result

    def down_dir_by_id(self, fid, save_path='./down', call_back=None) -> dict:
        """登录用户通过id下载文件夹"""
        file_list = self.get_file_id_list(fid)
        if len(file_list) == 0:
            return {'code': LanZouCloud.FAILED, 'failed': []}
        result = {'code': LanZouCloud.SUCCESS, 'failed': []}
        for name, fid in file_list.items():
            code = self.down_file_by_id(fid, save_path, call_back)
            logger.debug(f'Download file result code: {code}')
            if code != LanZouCloud.SUCCESS:
                result['code'] = LanZouCloud.FAILED
                result['failed'].append({'name': name, 'id': fid, 'code': code})
        if result['code'] != LanZouCloud.SUCCESS:
            return result
        f_name_list = list(file_list.keys())  # 文件名列表
        for name in f_name_list:
            if not re.match(r'.*\.\w+[0-9]+\.rar', name):
                return result
        if self._unzip(f_name_list, save_path) == LanZouCloud.ZIP_ERROR:
            return {'code': LanZouCloud.ZIP_ERROR, 'failed': []}  # 解压时发生错误
        return result

    def get_share_file_info(self, share_url, pwd=""):
        """获取分享文件信息"""
        if not self.is_file_url(share_url):
            return {"code": LanZouCloud.URL_INVALID, "info": ""}
        first_page = self._get(share_url)  # 文件分享页面(第一页)
        if not first_page:
            return {'code': LanZouCloud.NETWORK_ERROR, "info": ""}
        first_page = LanZouCloud._remove_notes(first_page.text)  # 去除网页里的注释
        if "文件取消" in first_page:
            return {"code": LanZouCloud.FILE_CANCELLED, "info": ""}
        if "输入密码" in first_page:  # 文件设置了提取码时
            if len(pwd) == 0:
                return {"code": LanZouCloud.LACK_PASSWORD, "info": ""}
            f_size = re.findall(r'class="n_filesize">[^<0-9]*([\.0-9 MKBmkbGg]+)<', first_page)
            f_size = f_size[0] if f_size else ""
            f_date = re.findall(r'class="n_file_infos">([-0-9 月天小时分钟秒前]+)<', first_page)
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
            f_date = re.findall(r'上传时间：</span>([-0-9 月天小时分钟秒前]+)<br', first_page)
            f_date = f_date[0] if f_date else ""
            f_desc = re.findall(r'文件描述：</span><br>([^<]+)</td>', first_page)
            f_desc = f_desc[0].strip() if f_desc else ""
            infos = {f_name: [None, f_name, f_size, f_date, "", pwd, f_desc, share_url]}
            return {"code": LanZouCloud.SUCCESS, "info": infos}

    def get_share_folder_info(self, share_url, dir_pwd=""):
        """显示分享文件夹信息"""
        if self.is_file_url(share_url):
            return {"code": LanZouCloud.URL_INVALID, "info": ""}
        r = requests.get(share_url, headers=self._headers)
        if r.status_code != requests.codes.OK:  # 可能有403状态码
            return {"code": LanZouCloud.NETWORK_ERROR, "info": r.status_code}
        html = LanZouCloud._remove_notes(r.text)
        if "文件不存在" in html:
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
