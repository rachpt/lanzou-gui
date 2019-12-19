import os
import re
from random import sample
from shutil import rmtree

import requests
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor


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

    def __init__(self):
        self._session = requests.Session()
        self._file_id_length = 7  # 目前文件id长度
        self._guise_suffix = ".dll"  # 不支持的文件伪装后缀
        self._fake_file_prefix = "__fake__"  # 假文件前缀
        self._timeout = 2000  # 每个请求的超时 ms(不包含下载响应体的用时)
        self._max_size = 100  # 单个文件大小上限 MB
        self._rar_path = None  # 解压工具路径
        self._host_url = "https://www.lanzous.com"
        self._doupload_url = "https://pc.woozooo.com/doupload.php"
        self._account_url = "https://pc.woozooo.com/account.php"
        self._mydisk_url = "https://pc.woozooo.com/mydisk.php"
        self._headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:71.0) Gecko/20100101 Firefox/71.0",
            "Referer": "https://www.lanzous.com",
            "Accept-Language": "zh-CN,zh;q=0.9",  # 提取直连必需设置这个，否则拿不到数据
        }

    def _get(self, url, **kwargs):
        return self._session.get(
            url=url, headers=self._headers, timeout=self._timeout, **kwargs
        )

    def _post(self, url, data, **kwargs):
        return self._session.post(
            url=url, data=data, headers=self._headers, timeout=self._timeout, **kwargs
        )

    def is_file_url(self, share_url):
        """判断是否为文件的分享链接"""
        pat = "https?://www.lanzous.com/i[a-z0-9]{6,}/?"
        return True if re.fullmatch(pat, share_url) else False

    def is_folder_url(self, share_url):
        """判断是否为文件夹的分享链接"""
        pat = "https?://www.lanzous.com/b[a-z0-9]{7,}/?"
        return True if re.fullmatch(pat, share_url) else False

    def set_rar_tool(self, bin_path):
        """设置解压工具路径"""
        if os.path.isfile(bin_path):
            self._rar_path = bin_path
            return LanZouCloud.SUCCESS
        else:
            return LanZouCloud.ZIP_ERROR

    def login(self, username, passwd):
        """登录蓝奏云控制台"""
        login_data = {
            "action": "login",
            "task": "login",
            "username": username,
            "password": passwd,
        }
        try:
            index = self._session.get(self._account_url).text
            login_data["formhash"] = re.findall(
                r'name="formhash" value="(.+?)"', index
            )[0]
            html = self._session.post(self._account_url, login_data).text
            return LanZouCloud.SUCCESS if "登录成功" in html else LanZouCloud.FAILED
        except (requests.RequestException, IndexError):
            return LanZouCloud.FAILED

    def logout(self):
        """注销"""
        try:
            html = self._get(self._account_url + "?action=logout").text
            return LanZouCloud.SUCCESS if "退出系统成功" in html else LanZouCloud.FAILED
        except requests.RequestException:
            return LanZouCloud.FAILED

    def delete(self, fid):
        """把网盘的文件、无子文件夹的文件夹放到回收站"""
        if len(str(fid)) >= self._file_id_length:
            post_data = {"task": 6, "file_id": fid}
        else:
            post_data = {"task": 3, "folder_id": fid}
        try:
            result = self._post(self._doupload_url, post_data).json()
            return LanZouCloud.SUCCESS if int(result["zt"]) == 1 else LanZouCloud.FAILED
        except requests.RequestException:
            return LanZouCloud.FAILED

    def clean_recycle(self):
        """清空回收站"""
        post_data = {"action": "delete_all", "task": "delete_all"}
        try:
            index = self._get(
                self._mydisk_url, params={"item": "recycle", "action": "files"}
            ).text
            post_data["formhash"] = re.findall(r'name="formhash" value="(.+?)"', index)[
                0
            ]  # 设置表单 hash
            result = self._post(self._mydisk_url + "?item=recycle", post_data).text
            return LanZouCloud.SUCCESS if "清空回收站成功" in result else LanZouCloud.FAILED
        except (requests.RequestException, IndexError):
            return LanZouCloud.FAILED

    def list_recovery(self):
        """获取回收站文件列表"""
        try:
            html = self._get(
                self._mydisk_url, params={"item": "recycle", "action": "files"}
            ).text
            dirs = re.findall(
                r"folder_id=(\d+).*?images/folder.*?>(?:&nbsp;)?(.*?)</a>",
                html,
                re.DOTALL,
            )
            dirs = {k: int(v) for v, k in dirs}
            files = re.findall(
                r'value="(\d+)".*?/images/file.*?>\s(.*?)</a>', html, re.DOTALL
            )
            files = {k: int(v) for v, k in files}
            return {"folder_list": dirs, "file_list": files}
        except (requests.RequestException, re.error):
            return {"folder_list": {}, "file_list": {}}

    def recovery(self, fid):
        """从回收站恢复文件"""
        if len(str(fid)) >= self._file_id_length:
            para = {"item": "recycle", "action": "file_restore", "file_id": fid}
            post_data = {
                "action": "file_restore",
                "task": "file_restore",
                "file_id": fid,
            }
        else:
            para = {"item": "recycle", "action": "folder_restore", "folder_id": fid}
            post_data = {
                "action": "folder_restore",
                "task": "folder_restore",
                "folder_id": fid,
            }
        try:
            index = self._get(self._mydisk_url, params=para).text
            post_data["formhash"] = re.findall(r'name="formhash" value="(.+?)"', index)[
                0
            ]  # 设置表单 hash
            result = self._post(self._mydisk_url + "?item=recycle", post_data).text
            return LanZouCloud.SUCCESS if "恢复成功" in result else LanZouCloud.FAILED
        except (IndexError, requests.RequestException):
            return LanZouCloud.FAILED

    def get_file_list(self, folder_id=-1):
        """获取文件列表"""
        page = 1
        file_list = {}
        while True:
            post_data = {"task": 5, "folder_id": folder_id, "pg": page}
            result = self._post(self._doupload_url, post_data).json()
            if result["info"] != 1:
                break  # 已经拿到全部文件的信息
            for i in result["text"]:
                # 删除文件列表的伪装后缀名
                if i["name_all"].endswith(self._guise_suffix):
                    i["name_all"] = i["name_all"].replace(self._guise_suffix, "")
                file_list[i["name_all"]] = {
                    "id": int(i["id"]),
                    "name": i["name_all"],
                    "time": i["time"],  # 上传时间
                    "size": i["size"],  # 文件大小
                    "downs": int(i["downs"]),  # 下载次数
                    "has_pwd": True if int(i["onof"]) == 1 else False,  # 是否存在提取码
                    "has_des": True if int(i["is_des"]) == 1 else False,  # 是否存在描述
                }
            page += 1
        return file_list

    def get_file_list2(self, folder_id=-1):
        """获取文件名-id列表"""
        info = {
            i["name"]: (
                i["id"],
                i["size"],
                i["time"],
                i["downs"],
                i["has_pwd"],
                i["has_des"],
            )
            for i in self.get_file_list(folder_id).values()
        }
        return {key: info.get(key) for key in sorted(info.keys())}

    def get_dir_list(self, folder_id=-1):
        """获取子文件夹列表"""
        folder_list = {}
        try:
            url = (
                self._mydisk_url
                + "?item=files&action=index&folder_node=1&folder_id="
                + str(folder_id)
            )
            for k, v in re.findall(
                r"&nbsp;(.+?)</a>&nbsp;.+folkey\((.+?)\)", self._session.get(url).text
            ):
                folder_list[k.replace("&amp;", "&")] = int(v)  # 文件夹名 : id
            return folder_list
        except requests.RequestException:
            return {}

    def get_full_path(self, folder_id=-1):
        """获取文件夹完整路径"""
        path_list = {"/": -1}
        try:
            html = self._get(
                self._mydisk_url,
                params={"item": "files", "action": "index", "folder_id": folder_id},
            ).text
            path = re.findall(
                r'&raquo;&nbsp;.+folder_id=([0-9]+)">.+&nbsp;(.+?)</a>', html
            )
            for i in path:
                path_list[i[1]] = int(i[0])
            # 获取当前文件夹名称
            if folder_id != -1:
                current_folder = re.findall(r"&raquo;&nbsp;.+&nbsp;(.+) <font", html)[
                    0
                ].replace("&amp;", "&")
                path_list[current_folder] = folder_id
            return path_list
        except (requests.RequestException, re.error, IndexError):
            return path_list

    def get_share_file_info(self, share_url, pwd=""):
        """获取分享文件信息"""
        if not self.is_file_url(share_url):
            return {"code": LanZouCloud.URL_INVALID, "info": ""}
        html = self._get(share_url).text
        if "文件取消" in html:
            return {"code": LanZouCloud.FILE_CANCELLED, "info": ""}
        if "输入密码" in html:  # 文件设置了提取码时
            if len(pwd) == 0:
                return {"code": LanZouCloud.LACK_PASSWORD, "name": ""}
            post_str = re.findall(r"[^/]*data\s:\s\'(.*)\'", html)[0] + str(pwd)
            f_size = re.findall(
                r'class="n_filesize">[^<]*([\.0-9 MKBmkbGg]+)<div', html
            )[0]
            f_date = re.findall(r'class="n_file_infos">([-0-9]+)<div', html)[0]
            f_desc = re.findall(r'class="n_box_des">(.*)<div', html)[0]
            # action=downprocess&sign=xxxxx&p=
            post_data = {}
            for i in post_str.split("&"):  # 转换成 dict
                k, v = i.split("=")
                post_data[k] = v
            link_info = self._post(self._host_url + "/ajaxm.php", post_data).json()
            if link_info["zt"] == 1:
                info = {link_info["inf"]: (share_url, f_size, f_date, f_desc, pwd)}
                return {"code": LanZouCloud.SUCCESS, "info": info}
            else:
                return {"code": LanZouCloud.PASSWORD_ERROR, "info": ""}
        else:
            f_name = re.findall(r"var filename = '(.*)';", html)[0]
            f_size = re.findall(r'文件大小：</span>([\.0-9 MKBmkbGg]+)<br', html)[0]
            f_date = re.findall(r'上传时间：</span>([-0-9]+)<br', html)[0]
            f_desc = re.findall(r'文件描述：</span><br>([^<]+)</td>', html)[0].strip()
            info = {f_name: (share_url, f_size, f_date, f_desc, pwd)}
            return {"code": LanZouCloud.SUCCESS, "info": info}

    def get_share_folder_info(self, share_url, dir_pwd=""):
        """显示分享文件夹信息"""
        if self.is_file_url(share_url):
            return {"code": LanZouCloud.URL_INVALID, "info": ""}
        html = requests.get(share_url, headers=self._headers).text
        if "文件不存在" in html:
            return {"code": LanZouCloud.FILE_CANCELLED, "info": ""}
        lx = re.findall(r"'lx':'?(\d)'?,", html)[0]
        t = re.findall(r"var [0-9a-z]{6} = '(\d{10})';", html)[0]
        k = re.findall(r"var [0-9a-z]{6} = '([0-9a-z]{15,})';", html)[0]
        fid = re.findall(r"'fid':'?(\d+)'?,", html)[0]
        desc = re.findall(r'id="filename">([^<]+)</span', html)
        if desc:
            desc = str(desc[0])
        if "请输入密码" in html:
            if len(dir_pwd) == 0:
                return {"code": LanZouCloud.LACK_PASSWORD, "info": ""}
            post_data = {"lx": lx, "pg": 1, "k": k, "t": t, "fid": fid, "pwd": dir_pwd}
        else:
            post_data = {"lx": lx, "pg": 1, "k": k, "t": t, "fid": fid}
        try:
            # 这里不用封装好的post函数是为了支持未登录的用户通过 URL 下载
            r = requests.post(
                self._host_url + "/filemoreajax.php",
                data=post_data,
                headers=self._headers,
            ).json()
        except requests.RequestException:
            return {"code": LanZouCloud.FAILED, "info": ""}
        if r["zt"] == 3:
            return {"code": LanZouCloud.PASSWORD_ERROR, "info": ""}
        elif r["zt"] != 1:
            return {"code": LanZouCloud.FAILED, "info": ""}
        # 获取文件信息成功后...
        info = {f["name_all"]: (self._host_url + "/" + f["id"], f["size"], f["time"], desc, "") for f in r["text"]}
        return {"code": LanZouCloud.SUCCESS, "info": info}

    def get_direct_url(self, share_url, pwd=""):
        """获取直链"""
        if not self.is_file_url(share_url):
            return {"code": LanZouCloud.URL_INVALID, "name": "", "direct_url": ""}

        html = self._get(share_url).text
        if "文件取消" in html:
            return {"code": LanZouCloud.FILE_CANCELLED, "name": "", "direct_url": ""}

        # 获取下载直链重定向前的链接
        if "输入密码" in html:  # 文件设置了提取码时
            if len(pwd) == 0:
                return {"code": LanZouCloud.LACK_PASSWORD, "name": "", "direct_url": ""}
            post_str = re.findall(r"[^/]*data\s:\s\'(.*)\'", html)[0] + str(pwd)
            # action=downprocess&sign=xxxxx&p=
            post_data = {}
            for i in post_str.split("&"):  # 转换成 dict
                k, v = i.split("=")
                post_data[k] = v
            link_info = self._post(self._host_url + "/ajaxm.php", post_data).json()
        else:  # 无提取码时
            para = re.findall(r'<iframe.*?src="(.*?)".*?>', html)[1]  # 提取构造下载页面链接所需的参数
            file_name = re.findall(r'<div style="[^"]+">([^><]*?)</div>', html)
            if file_name:
                file_name = file_name[0]
            else:
                file_name = re.findall(r"var filename = '(.*)';", html)[0]
            html = self._get(self._host_url + para).text
            post_data = re.findall(r"[^/]*data\s:\s(.*),", html)[0]
            # {'action': 'downprocess', 'sign': 'xxxxx'}
            post_data = eval(post_data)
            link_info = self._post(self._host_url + "/ajaxm.php", post_data).json()
            link_info["inf"] = file_name  # 无提取码时 inf 字段为 0，有提取码时该字段为文件名
        # 获取文件直链
        if link_info["zt"] == 1:
            fake_url = link_info["dom"] + "/file/" + link_info["url"]  # 假直连，存在流量异常检测
            direct_url = self._get(fake_url, allow_redirects=False).headers[
                "Location"
            ]  # 重定向后的真直链
            return {
                "code": LanZouCloud.SUCCESS,
                "name": link_info["inf"],
                "direct_url": direct_url,
            }
        else:
            return {"code": LanZouCloud.PASSWORD_ERROR, "name": "", "direct_url": ""}

    def get_direct_url2(self, fid):
        """登录用户通过id获取直链"""
        info = self.get_share_info(fid)
        return self.get_direct_url(info["share_url"], info["passwd"])

    def get_share_info(self, fid):
        """获取文件(夹)提取码、分享链接"""
        if len(str(fid)) >= self._file_id_length:
            post_data = {"task": 22, "file_id": fid}
        else:
            post_data = {"task": 18, "folder_id": fid}
        try:
            result = self._post(self._doupload_url, post_data).json()
            f_info = result["info"]
            # id 有效性校验
            if ("f_id" in f_info.keys() and f_info["f_id"] == "i") or (
                "name" in f_info.keys() and not f_info["name"]
            ):
                return {"code": LanZouCloud.ID_ERROR, "share_url": "", "passwd": ""}
            # onof=1 时，存在有效的提取码; onof=0 时不存在提取码，但是 pwd 字段还是有一个无效的随机密码
            pwd = f_info["pwd"] if f_info["onof"] == "1" else ""
            if "f_id" in f_info.keys():
                share_url = f_info["is_newd"] + "/" + f_info["f_id"]  # 文件的分享链接需要拼凑
            else:
                share_url = f_info["new_url"]  # 文件夹的分享链接可以直接拿到
            return {"code": LanZouCloud.SUCCESS, "share_url": share_url, "passwd": pwd}
        except requests.RequestException:
            return {
                "code": LanZouCloud.FAILED,
                "share_url": "",
                "passwd": "",
            }  # 网络问题没拿到数据

    def set_share_passwd(self, fid, passwd=""):
        """设置网盘文件的提取码"""
        passwd_status = 0 if passwd == "" else 1
        if len(str(fid)) >= self._file_id_length:
            post_data = {
                "task": 23,
                "file_id": fid,
                "shows": passwd_status,
                "shownames": passwd,
            }
        else:
            post_data = {
                "task": 16,
                "folder_id": fid,
                "shows": passwd_status,
                "shownames": passwd,
            }
        try:
            result = self._post(self._doupload_url, post_data).json()
            return (
                LanZouCloud.SUCCESS if result["info"] == "设置成功" else LanZouCloud.FAILED
            )
        except requests.RequestException:
            return LanZouCloud.FAILED

    def mkdir(self, parent_id, folder_name, description=""):
        """创建文件夹(同时设置描述)"""
        folder_name = re.sub(r"[#$%^!*<>)(+=`\'\"/:;,?]", "", folder_name)  # 去除非法字符
        folder_list = self.get_dir_list(parent_id)
        if folder_name in folder_list.keys():
            return folder_list.get(folder_name)
        post_data = {
            "task": 2,
            "parent_id": parent_id or -1,
            "folder_name": folder_name,
            "folder_description": description,
        }
        try:
            result = self._post(self._doupload_url, post_data).json()  # 创建文件夹
            if result["zt"] != 1:
                return LanZouCloud.MKDIR_ERROR  # 创建失败
            all_dir = self._post(
                self._doupload_url, data={"task": 19, "file_id": 0}
            ).json()  # 获取ID
            return int(all_dir["info"][-1]["folder_id"])
        except (requests.RequestException, IndexError):
            return LanZouCloud.MKDIR_ERROR

    def rename_dir(self, folder_id, folder_name, description=""):
        """重命名文件夹"""
        if len(str(folder_id)) >= self._file_id_length:
            return LanZouCloud.FAILED  # 文件名是不支持修改的
        post_data = {
            "task": 4,
            "folder_id": folder_id,
            "folder_name": folder_name,
            "folder_description": description,
        }
        try:
            result = self._post(self._doupload_url, post_data).json()
            return (
                LanZouCloud.SUCCESS if result["info"] == "修改成功" else LanZouCloud.FAILED
            )
        except requests.RequestException:
            return LanZouCloud.FAILED

    def move_file(self, file_id, folder_id=-1):
        """移动文件到指定文件夹"""
        post_data = {"task": 20, "file_id": file_id, "folder_id": folder_id}
        try:
            result = self._post(self._doupload_url, post_data).json()
            return (
                LanZouCloud.SUCCESS if result["info"] == "移动成功" else LanZouCloud.FAILED
            )
        except requests.RequestException:
            return LanZouCloud.FAILED

    def _upload_a_file(self, file_path, folder_id=-1, call_back=None):
        """上传文件到蓝奏云上指定的文件夹(默认根目录)"""
        if not os.path.exists(file_path):
            return LanZouCloud.FAILED
        file_name = os.path.basename(file_path)  # 从文件路径截取文件名
        tmp_list = {**self.get_file_list2(folder_id), **self.get_dir_list(folder_id)}
        if file_name in tmp_list.keys():
            self.delete(tmp_list[file_name])  # 文件已经存在就删除

        suffix = file_name.split(".")[-1]
        valid_suffix_list = [
            "doc",
            "docx",
            "zip",
            "rar",
            "apk",
            "txt",
            "exe",
            "7z",
            "e",
            "z",
            "ct",
            "ke",
            "cetrainer",
            "db",
            "tar",
            "pdf",
            "w3x",
            "epub",
            "mobi",
            "azw",
            "azw3",
            "osk",
            "osz",
            "xpa",
            "cpk",
            "lua",
            "jar",
            "dmg",
            "ppt",
            "pptx",
            "xls",
            "xlsx",
            "mp3",
            "ipa",
            "iso",
            "img",
            "gho",
            "ttf",
            "ttc",
            "txf",
            "dwg",
            "bat",
            "dll",
        ]
        if suffix not in valid_suffix_list:
            # 不支持的文件通过修改后缀蒙混过关
            file_name = file_name + self._guise_suffix

        post_data = {
            "task": "1",
            "folder_id": str(folder_id),
            "id": "WU_FILE_0",
            "name": file_name,
            "upload_file": (
                file_name,
                open(file_path, "rb"),
                "application/octet-stream",
            ),
        }

        post_data = MultipartEncoder(post_data)
        tmp_header = self._headers.copy()
        tmp_header["Content-Type"] = post_data.content_type
        # 让回调函数里不显示伪装后缀名
        if file_name.endswith(self._guise_suffix):
            file_name = file_name.replace(self._guise_suffix, "")
        # MultipartEncoderMonitor 每上传 8129 bytes数据调用一次回调函数，问题根源是 httplib 库
        # issue : https://github.com/requests/toolbelt/issues/75
        # 上传完成后，回调函数会被错误的多调用一次。因此，下面重新封装了回调函数，修改了接受的参数，并阻断了多余的一次调用
        self._upload_finished_flag = False  # 上传完成的标志

        def _call_back(read_monitor):
            if call_back is not None:
                if not self._upload_finished_flag:
                    call_back(file_name, read_monitor.len, read_monitor.bytes_read)
                if read_monitor.len == read_monitor.bytes_read:
                    self._upload_finished_flag = True

        try:
            monitor = MultipartEncoderMonitor(post_data, _call_back)
            result = self._session.post(
                "http://pc.woozooo.com/fileup.php", data=monitor, headers=tmp_header
            ).json()
            if result["zt"] == 0:
                return LanZouCloud.FAILED  # 上传失败
            file_id = result["text"][0]["id"]
            # 蓝奏云禁止用户连续上传 100M 的文件，因此需要上传一个 100M 的文件，然后上传一个“假文件”糊弄过去
            # 这里检查上传的文件是否为“假文件”，是的话上传后就立刻删除
            if result["text"][0]["name_all"].startswith(self._fake_file_prefix):
                self.delete(file_id)
            else:
                self.set_share_passwd(file_id)  # 正常的文件上传后默认关闭提取码
            return LanZouCloud.SUCCESS
        except (requests.RequestException, KeyboardInterrupt):
            return LanZouCloud.FAILED

    def upload_file(self, file_path, folder_id=-1, call_back=None):
        """分卷压缩上传"""
        # 单个文件不超过 100MB 时直接上传
        if os.path.getsize(file_path) <= self._max_size * 1048576:
            return self._upload_a_file(file_path, folder_id, call_back)
        # 超过 100MB 的文件，分卷压缩后上传
        if self._rar_path is None:
            return LanZouCloud.ZIP_ERROR
        rar_level = 0  # 压缩等级(0-5)，0 不压缩
        part_sum = os.path.getsize(file_path) // (self._max_size * 1048576) + 1
        file_name = ".".join(
            file_path.split(os.sep)[-1].split(".")[:-1]
        )  # 无后缀的文件名，用作分卷文件名
        file_list = [
            "{}.part{}.rar".format(file_name, i) for i in range(1, part_sum + 1)
        ]
        if not os.path.exists("./tmp"):
            os.mkdir("./tmp")  # 本地保存分卷文件的临时文件夹
        cmd_args = "a -m{} -v{}m -ep -y -rr5% ./tmp/{} {}".format(
            rar_level, self._max_size, file_name, file_path
        )
        if os.name == "nt":
            command = "start /b {} {}".format(
                self._rar_path, cmd_args
            )  # windows 平台调用 rar.exe 实现压缩
        else:
            command = "{} {}".format(self._rar_path, cmd_args)  # linux 平台使用 rar 命令压缩
        try:
            os.popen(command).readlines()
        except os.error:
            return LanZouCloud.ZIP_ERROR
        # 上传并删除分卷文件
        folder_name = ".".join(
            file_list[0].split(".")[:-2]
        )  # 文件名去除".part**.rar"作为网盘新建的文件夹名
        dir_id = self.mkdir(folder_id, folder_name, "分卷压缩文件")
        if dir_id == LanZouCloud.MKDIR_ERROR:
            return LanZouCloud.MKDIR_ERROR  # 创建文件夹失败就退出
        for f in file_list:
            # 蓝奏云禁止用户连续上传 100M 的文件，因此需要上传一个 100M 的文件，然后上传一个“假文件”糊弄过去
            temp_file = (
                "./tmp/"
                + self._fake_file_prefix
                + "".join(sample("abcdefg12345", 6))
                + ".txt"
            )
            with open(temp_file, "w") as t_f:
                t_f.write("FUCK LanZouCloud")
            self._upload_a_file(temp_file, dir_id)
            # 现在上传真正的文件
            if (
                self._upload_a_file("./tmp/" + f, dir_id, call_back)
                == LanZouCloud.FAILED
            ):
                return LanZouCloud.FAILED
        rmtree("./tmp")
        return LanZouCloud.SUCCESS

    def upload_dir(self, dir_path, folder_id=-1, call_back=None):
        """批量上传"""
        if not os.path.isdir(dir_path):
            return LanZouCloud.FAILED
        dir_name = dir_path.split(os.sep)[-1]
        dir_id = self.mkdir(folder_id, dir_name, "批量上传")
        if dir_id == LanZouCloud.MKDIR_ERROR:
            return LanZouCloud.MKDIR_ERROR
        for f in os.listdir(dir_path):
            if os.path.isfile(dir_path + os.sep + f):
                if (
                    self.upload_file(dir_path + os.sep + f, dir_id, call_back)
                    != LanZouCloud.SUCCESS
                ):
                    return LanZouCloud.FAILED
        return LanZouCloud.SUCCESS

    def download_file(self, share_url, pwd="", save_path=".", call_back=None):
        """通过分享链接下载文件(需提取码)"""
        if not self.is_file_url(share_url):
            return LanZouCloud.URL_INVALID
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        info = self.get_direct_url(share_url, pwd)
        if info["code"] != LanZouCloud.SUCCESS:
            return info["code"]
        # 删除伪装后缀名
        if info["name"].endswith(self._guise_suffix):
            info["name"] = info["name"].replace(self._guise_suffix, "")
        try:
            r = requests.get(info["direct_url"], stream=True)
            total_size = int(r.headers["content-length"])
            now_size = 0
            timer = -1
            with open(save_path + os.sep + info["name"], "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        now_size += len(chunk)
                        timer += 1
                        if call_back is not None and (timer % 30 == 0 or total_size == now_size):
                            call_back(info["name"], total_size, now_size)
            return LanZouCloud.SUCCESS
        except (requests.RequestException, KeyboardInterrupt):
            return LanZouCloud.FAILED

    def download_file2(self, fid, save_path=".", call_back=None):
        """登录用户通过id下载文件(无需提取码)"""
        info = self.get_share_info(fid)
        return self.download_file(
            info["share_url"], info["passwd"], save_path, call_back
        )

    def _unrar(self, file_list, save_path):
        # 如果文件都是".part*.rar"结尾，则下载后需要解压
        for f_name in file_list:
            if not re.match(r".*\.part[0-9]+\.rar", f_name):
                return LanZouCloud.SUCCESS
        if self._rar_path is None:
            return LanZouCloud.ZIP_ERROR
        first_rar = save_path + os.sep + file_list[0]
        if os.name == "nt":
            command = "start /b {} -y e {} {}".format(
                self._rar_path, first_rar, save_path
            )  # Windows 平台
        else:
            command = "{} -y e {} {}".format(
                self._rar_path, first_rar, save_path
            )  # Linux 平台
        try:
            os.popen(command).readlines()  # 解压出原文件
            for f_name in file_list:  # 删除分卷文件
                os.remove(save_path + os.sep + f_name)
            return LanZouCloud.SUCCESS
        except os.error:
            return LanZouCloud.ZIP_ERROR

    def download_dir(self, share_url, dir_pwd="", save_path="./down", call_back=None):
        """通过分享链接下载文件夹"""
        if self.is_file_url(share_url):
            return LanZouCloud.URL_INVALID
        html = requests.get(share_url, headers=self._headers).text
        if "文件不存在" in html:
            return LanZouCloud.FILE_CANCELLED
        if "请输入密码" in html:
            if len(dir_pwd) == 0:
                return LanZouCloud.LACK_PASSWORD
            lx = re.findall(r"'lx':'?(\d)'?,", html)[0]
            t = re.findall(r"var [0-9a-z]{6} = '(\d{10})';", html)[0]
            k = re.findall(r"var [0-9a-z]{6} = '([0-9a-z]{15,})';", html)[0]
            fid = re.findall(r"'fid':'?(\d+)'?,", html)[0]
            post_data = {"lx": lx, "pg": 1, "k": k, "t": t, "fid": fid, "pwd": dir_pwd}
            try:
                # 这里不用封装好的post函数是为了支持未登录的用户通过 URL 下载
                r = requests.post(
                    self._host_url + "/filemoreajax.php",
                    data=post_data,
                    headers=self._headers,
                ).json()
            except requests.RequestException:
                return LanZouCloud.FAILED
            if r["zt"] == 3:
                return LanZouCloud.PASSWORD_ERROR
            elif r["zt"] != 1:
                return LanZouCloud.FAILED
            # 获取文件信息成功后...
            info = {f["name_all"]: self._host_url + "/" + f["id"] for f in r["text"]}
            file_list = list(info.keys())
            url_list = [info.get(key) for key in sorted(info.keys())]
            for url in url_list:
                self.download_file(url, "", save_path, call_back)
            return self._unrar(file_list, save_path)

    def download_dir2(self, fid, name, save_path="./down", call_back=None):
        """登录用户通过id下载文件夹"""
        info = self.get_file_list2(fid)
        if len(info) == 0:
            return LanZouCloud.FAILED
        folder_path = save_path + os.sep + name
        os.makedirs(folder_path)
        save_path = folder_path
        for f_id in info.values():
            if self.download_file2(f_id[0], save_path, call_back) == LanZouCloud.FAILED:
                return LanZouCloud.FAILED
        return self._unrar(list(info.keys()), save_path)
