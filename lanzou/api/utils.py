"""
API 处理网页数据、数据切片时使用的工具
"""

import logging
import re
import os
from datetime import timedelta, datetime
from random import uniform, choices, sample, shuffle, choice
from shutil import rmtree
import pickle

__all__ = ['logger', 'remove_notes', 'name_format', 'time_format', 'is_name_valid', 'is_file_url',
           'is_folder_url', 'big_file_split', 'un_serialize', 'let_me_upload']

# 调试日志设置
logger = logging.getLogger('lanzou')
logger.setLevel(logging.ERROR)
formatter = logging.Formatter(
    fmt="%(asctime)s [line:%(lineno)d] %(funcName)s %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S")
console = logging.StreamHandler()
console.setFormatter(formatter)
logger.addHandler(console)


def remove_notes(html: str) -> str:
    """删除网页的注释"""
    # 去掉 html 里面的 // 和 <!-- --> 注释，防止干扰正则匹配提取数据
    # 蓝奏云的前端程序员喜欢改完代码就把原来的代码注释掉,就直接推到生产环境了 =_=
    return re.sub(r'<!--.+?-->|\s+//\s*.+', '', html)


def name_format(name: str) -> str:
    """去除非法字符"""
    name = name.replace(u'\xa0', ' ').replace(u'\u3000', ' ')  # 去除其它字符集的空白符
    return re.sub(r'[$%^!*<>)(+=`\'\"/:;,?]', '', name)


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

    valid_suffix_list = ('doc', 'docx', 'zip', 'rar', 'apk', 'ipa', 'txt', 'exe', '7z', 'e', 'z', 'ct',
                         'ke', 'cetrainer', 'db', 'tar', 'pdf', 'w3x', 'epub', 'mobi', 'azw', 'azw3',
                         'osk', 'osz', 'xpa', 'cpk', 'lua', 'jar', 'dmg', 'ppt', 'pptx', 'xls', 'xlsx',
                         'mp3', 'iso', 'img', 'gho', 'ttf', 'ttc', 'txf', 'dwg', 'bat', 'dll')

    return filename.split('.')[-1] in valid_suffix_list


def is_file_url(share_url: str) -> bool:
    """判断是否为文件的分享链接"""
    pat = 'https?://www.lanzous.com/i[a-z0-9]{6,}/?'
    return True if re.fullmatch(pat, share_url) else False


def is_folder_url(share_url: str) -> bool:
    """判断是否为文件夹的分享链接"""
    pat = 'https?://www.lanzous.com/b[a-z0-9]{7,}/?'
    return True if re.fullmatch(pat, share_url) else False


def un_serialize(data: bytes):
    """反序列化文件信息数据"""
    try:
        ret = pickle.loads(data)
        if not isinstance(ret, dict):
            return None
        return ret
    except (TypeError, pickle.UnpicklingError):
        return None


def big_file_split(file_path: str, max_size: int = 100):
    """将大文件拆分为大小、格式随机的文件
    :return 新文件绝对路径的生成器
    """
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    tmp_dir = os.path.dirname(file_path) + os.sep + 'tmp'

    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)

    def get_random_size() -> int:
        """按权重生成一个不超过 max_size 的文件大小"""
        reduce_size = choices([uniform(0, 10), uniform(10, 20), uniform(40, 60), uniform(60, 80)], weights=[6, 2, 1, 1])
        return round((max_size - reduce_size[0]) * 1048576)

    def get_random_name() -> str:
        """生成一个随机文件名"""
        # 这些格式的文件一般都比较大
        suffix_list = ('zip', 'rar', 'apk', 'exe', 'pdf', '7z', 'tar', 'iso', 'img', 'gho', 'dmg', 'dwg')
        name = list(file_name.replace('.', '')) + sample('abcdefghijklmnopqrstuvwxyz', 3) + sample('1234567890', 2)
        shuffle(name)  # 打乱顺序
        name = ''.join(name) + '.' + choice(suffix_list)
        return name_format(name)  # 确保随机名合法

    all_file_list = []  # 全部的临时文件
    with open(file_path, 'rb') as big_file:
        big_file_left_size = file_size
        chunk_size = 524288  # 512KB
        while big_file_left_size > 0:
            tmp_file_size = get_random_size() if file_size > 52428800 else file_size  # 文件剩下 50 MB 时不再分割
            tmp_file_name = get_random_name()
            tmp_file_path = tmp_dir + os.sep + tmp_file_name

            left_size = tmp_file_size
            with open(tmp_file_path, 'wb') as f:
                while left_size > 0:
                    if left_size < chunk_size:  # 不足读取一次
                        f.write(big_file.read(left_size))
                        break
                    # 一次读取一块,防止一次性读取占用内存
                    f.write(big_file.read(chunk_size))
                    left_size -= chunk_size

            big_file_left_size -= tmp_file_size
            all_file_list.append(tmp_file_name)  # 按顺序保存文件名
            yield tmp_file_path

    # 序列化文件信息到 txt 文件,下载时尝试反序列化,成功则说明这是大文件的数据
    info = {'name': file_name, 'size': file_size, 'parts': all_file_list}
    info_file = tmp_dir + os.sep + '.'.join(get_random_name().split('.')[:-1]) + '.txt'
    with open(info_file, 'wb') as f:
        pickle.dump(info, f)
    yield info_file

    # 正常遍历结束时删除临时目录,失败时保留,方便复现 Bug
    # rmtree(tmp_dir)
    # logger.debug(f"Delete tmp dir: {tmp_dir}")


def let_me_upload(file_path):
    """允许文件上传"""
    file_size = os.path.getsize(file_path) / 1024 / 1024  # MB
    file_name = os.path.basename(file_path)

    big_file_suffix = choice(['zip', 'rar', 'apk', 'exe', 'pdf', '7z', 'tar', 'iso', 'img', 'gho', 'dmg', 'dwg'])
    small_file_suffix = choice(['doc', 'ipa', 'epub', 'mobi', 'azw', 'ppt', 'pptx'])
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
