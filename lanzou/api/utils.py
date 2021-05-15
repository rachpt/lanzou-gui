"""
API 处理网页数据、数据切片时使用的工具
"""

import os
import pickle
import re
from typing import Tuple
from datetime import timedelta, datetime
from random import uniform, choices, sample, shuffle, choice
import requests

from lanzou.debug import logger


__all__ = ['remove_notes', 'name_format', 'time_format', 'is_name_valid', 'is_file_url',
           'is_folder_url', 'big_file_split', 'un_serialize', 'let_me_upload', 'USER_AGENT',
           'sum_files_size', 'convert_file_size_to_str', 'calc_acw_sc__v2']


USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:78.0) Gecko/20100101 Firefox/78.0'


headers = {
    'User-Agent': USER_AGENT,
    'Referer': 'https://pan.lanzous.com',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}


def remove_notes(html: str) -> str:
    """删除网页的注释"""
    # 去掉 html 里面的 // 和 <!-- --> 注释，防止干扰正则匹配提取数据
    # 蓝奏云的前端程序员喜欢改完代码就把原来的代码注释掉,就直接推到生产环境了 =_=
    html = re.sub(r'<!--.+?-->|\s+//\s*.+', '', html)  # html 注释
    html = re.sub(r'(.+?[,;])\s*//.+', r'\1', html)  # js 注释
    return html


def name_format(name: str) -> str:
    """去除非法字符"""
    name = name.replace(u'\xa0', ' ').replace(u'\u3000', ' ').replace('  ', ' ')  # 去除其它字符集的空白符,去除重复空白字符
    return re.sub(r'[$%^!*<>)(+=`\'\"/:;,?]', '', name)

def convert_file_size_to_int(size_str: str) -> int:
    """文件大小描述转化为字节大小"""
    if 'G' in size_str:
        size_int = float(size_str.replace('G', '')) * (1 << 30)
    elif 'M' in size_str:
        size_int = float(size_str.replace('M', '')) * (1 << 20)
    elif 'K' in size_str:
        size_int = float(size_str.replace('K', '')) * (1 << 10)
    elif 'B' in size_str:
        size_int = float(size_str.replace('B', ''))
    else:
        size_int = 0
        logger.debug(f"Unknown size: {size_str}")
    return int(size_int)


def sum_files_size(files: object) -> int:
    """计算文件夹中所有文件的大小， [files,]: FileInFolder"""
    # 此处的 size 用于全选下载判断、展示文件夹大小
    total = 0
    for file_ in files:
        size_str = file_.size
        total += convert_file_size_to_int(size_str)
    return int(total)


def convert_file_size_to_str(total: int) -> str:
    if total < 1 << 10:
        size = "{:.2f} B".format(total)
    elif total < 1 << 20:
        size = "{:.2f} K".format(total / (1 << 10))
    elif total < 1 << 30:
        size = "{:.2f} M".format(total / (1 << 20))
    else:
        size = "{:.2f} G".format(total / (1 << 30))

    return size


def time_format(time_str: str) -> str:
    """输出格式化时间 %Y-%m-%d"""
    if '秒前' in time_str or '分钟前' in time_str or '小时前' in time_str:
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


def is_name_valid(filename: str) -> bool:
    """检查文件名是否允许上传"""

    valid_suffix_list = ('ppt', 'xapk', 'ke', 'azw', 'cpk', 'gho', 'dwg', 'db', 'docx', 'deb', 'e', 'ttf', 'xls', 'bat',
                         'crx', 'rpm', 'txf', 'pdf', 'apk', 'ipa', 'txt', 'mobi', 'osk', 'dmg', 'rp', 'osz', 'jar',
                         'ttc', 'z', 'w3x', 'xlsx', 'cetrainer', 'ct', 'rar', 'mp3', 'pptx', 'mobileconfig', 'epub',
                         'imazingapp', 'doc', 'iso', 'img', 'appimage', '7z', 'rplib', 'lolgezi', 'exe', 'azw3', 'zip',
                         'conf', 'tar', 'dll', 'flac', 'xpa', 'lua', 'cad', 'hwt', 'accdb', 'ce', 'xmind', 'enc', 'bds', 'bdi', 'ssf', 'it', 'gz')

    return filename.split('.')[-1].lower() in valid_suffix_list


def is_file_url(share_url: str) -> bool:
    """判断是否为文件的分享链接"""
    base_pat = r'https?://(\w[-\w]*\.)?lanzou[six].com/.+'
    user_pat = r'https?://(\w[-\w]*\.)?lanzou[six].com/i[a-zA-Z0-9]{5,}/?'  # 普通用户 URL 规则
    if not re.fullmatch(base_pat, share_url):
        return False
    elif re.fullmatch(user_pat, share_url):
        return True
    else:  # VIP 用户的 URL 很随意
        try:
            html = requests.get(share_url, headers=headers).text
            html = remove_notes(html)
            return True if re.search(r'class="fileinfo"|id="file"|文件描述', html) else False
        except (requests.RequestException, Exception) as e:
            logger.error(f"Unexpected error: e={e}")
            return False


def is_folder_url(share_url: str) -> bool:
    """判断是否为文件夹的分享链接"""
    base_pat = r'https?://(\w[-\w]*\.)?lanzou[six].com/.+'
    user_pat = r'https?://(\w[-\w]*\.)?lanzou[six].com/b[a-zA-Z0-9]{7,}/?'
    if not re.fullmatch(base_pat, share_url):
        return False
    elif re.fullmatch(user_pat, share_url):
        return True
    else:  # VIP 用户的 URL 很随意
        try:
            html = requests.get(share_url, headers=headers).text
            html = remove_notes(html)
            return True if re.search(r'id="infos"', html) else False
        except (requests.RequestException, Exception) as e:
            logger.error(f"Unexpected error: e={e}")
            return False


def un_serialize(data: bytes):
    """反序列化文件信息数据"""
    try:
        ret = pickle.loads(data)
        if not isinstance(ret, dict):
            return None
        return ret
    except Exception as e:  # 这里可能会丢奇怪的异常
        logger.debug(f"Pickle e={e}")
        return None


def big_file_split(file_path: str, max_size: int = 100, start_byte: int = 0) -> Tuple[int, str]:
    """将大文件拆分为大小、格式随机的数据块, 可指定文件起始字节位置(用于续传)
    :return 数据块文件的大小和绝对路径
    """
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    tmp_dir = os.path.dirname(file_path) + os.sep + '__' + '.'.join(file_name.split('.')[:-1])

    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)

    def get_random_size() -> int:
        """按权重生成一个不超过 max_size 的文件大小"""
        reduce_size = choices([uniform(0, max_size/10), uniform(max_size/10, 2*max_size/10), uniform(4*max_size/10, 6*max_size/10), uniform(6*max_size/10, 8*max_size/10)], weights=[2, 5, 2, 1])
        return round((max_size - reduce_size[0]) * 1048576)

    def get_random_name() -> str:
        """生成一个随机文件名"""
        # 这些格式的文件一般都比较大且不容易触发下载检测
        suffix_list = ('zip', 'rar', 'apk', 'ipa', 'exe', 'pdf', '7z', 'tar', 'deb', 'dmg', 'rpm', 'flac')
        name = list(file_name.replace('.', '').replace(' ', ''))
        name = name + sample('abcdefghijklmnopqrstuvwxyz', 3) + sample('1234567890', 2)
        shuffle(name)  # 打乱顺序
        name = ''.join(name) + '.' + choice(suffix_list)
        return name_format(name)  # 确保随机名合法

    with open(file_path, 'rb') as big_file:
        big_file.seek(start_byte)
        left_size = file_size - start_byte  # 大文件剩余大小
        random_size = get_random_size()
        tmp_file_size = random_size if left_size > random_size else left_size
        tmp_file_path = tmp_dir + os.sep + get_random_name()

        chunk_size = 524288  # 512KB
        left_read_size = tmp_file_size
        with open(tmp_file_path, 'wb') as small_file:
            while left_read_size > 0:
                if left_read_size < chunk_size:  # 不足读取一次
                    small_file.write(big_file.read(left_read_size))
                    break
                # 一次读取一块,防止一次性读取占用内存
                small_file.write(big_file.read(chunk_size))
                left_read_size -= chunk_size

    return tmp_file_size, tmp_file_path


def let_me_upload(file_path):
    """允许文件上传"""
    file_size = os.path.getsize(file_path) / 1024 / 1024  # MB
    file_name = os.path.basename(file_path)

    big_file_suffix = ['zip', 'rar', 'apk', 'ipa', 'exe', 'pdf', '7z', 'tar', 'deb', 'dmg', 'rpm', 'flac']
    small_file_suffix = big_file_suffix + ['doc', 'epub', 'mobi', 'mp3', 'ppt', 'pptx']
    big_file_suffix = choice(big_file_suffix)
    small_file_suffix = choice(small_file_suffix)
    suffix = small_file_suffix if file_size < 30 else big_file_suffix
    new_file_path = '.'.join(file_path.split('.')[:-1]) + '.' + suffix

    with open(new_file_path, 'wb') as out_f:
        # 写入原始文件数据
        with open(file_path, 'rb') as in_f:
            chunk = in_f.read(4096)
            while chunk:
                out_f.write(chunk)
                chunk = in_f.read(4096)
        # 构建文件 "报尾" 保存真实文件名,大小 512 字节
        # 追加数据到文件尾部，并不会影响文件的使用，无需修改即可分享给其他人使用，自己下载时则会去除，确保数据无误
        padding = 512 - len(file_name.encode('utf-8')) - 42  # 序列化后空字典占 42 字节
        data = {'name': file_name, 'padding': b'\x00' * padding}
        data = pickle.dumps(data)
        out_f.write(data)
    return new_file_path



def auto_rename(file_path) -> str:
    """如果文件存在，则给文件名添加序号"""
    if not os.path.exists(file_path):
        return file_path
    fpath, fname = os.path.split(file_path)
    fname_no_ext, ext = os.path.splitext(fname)
    flist = [f for f in os.listdir(fpath) if re.fullmatch(rf"{fname_no_ext}\(?\d*\)?{ext}", f)]
    count = 1
    while f"{fname_no_ext}({count}){ext}" in flist:
        count += 1
    return fpath + os.sep + fname_no_ext + '(' + str(count) + ')' + ext


def calc_acw_sc__v2(html_text: str) -> str:
    arg1 = re.search(r"arg1='([0-9A-Z]+)'", html_text)
    arg1 = arg1.group(1) if arg1 else ""
    acw_sc__v2 = hex_xor(unsbox(arg1), "3000176000856006061501533003690027800375")
    return acw_sc__v2


# 参考自 https://zhuanlan.zhihu.com/p/228507547
def unsbox(str_arg):
    v1 = [15, 35, 29, 24, 33, 16, 1, 38, 10, 9, 19, 31, 40, 27, 22, 23, 25, 13, 6, 11, 39, 18, 20, 8, 14, 21, 32, 26, 2,
          30, 7, 4, 17, 5, 3, 28, 34, 37, 12, 36]
    v2 = ["" for _ in v1]
    for idx in range(0, len(str_arg)):
        v3 = str_arg[idx]
        for idx2 in range(len(v1)):
            if v1[idx2] == idx + 1:
                v2[idx2] = v3

    res = ''.join(v2)
    return res


def hex_xor(str_arg, args):
    res = ''
    for idx in range(0, min(len(str_arg), len(args)), 2):
        v1 = int(str_arg[idx:idx + 2], 16)
        v2 = int(args[idx:idx + 2], 16)
        v3 = format(v1 ^ v2, 'x')
        if len(v3) == 1:
            v3 = '0' + v3
        res += v3

    return res
