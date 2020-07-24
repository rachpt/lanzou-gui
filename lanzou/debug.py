'''
调试日志设置，全局常量
'''

import os
import logging


__all__ = ['logger']


# 全局常量: USER_HOME, DL_DIR, SRC_DIR, BG_IMG, CONFIG_FILE
USER_HOME = os.path.expanduser('~')
if os.name == 'nt':  # Windows
    root_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(root_dir)
    import winreg

    sub_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders'
    downloads_guid = '{374DE290-123F-4565-9164-39C4925E467B}'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
        DL_DIR = winreg.QueryValueEx(key, downloads_guid)[0]
else:  # Linux and MacOS ...
    root_dir = USER_HOME + os.sep + '.config' + os.sep + 'lanzou-gui'
    if not os.path.exists(root_dir):
        os.makedirs(root_dir)
    DL_DIR = USER_HOME + os.sep + 'Downloads'

SRC_DIR = root_dir + os.sep + "src" + os.sep
BG_IMG = (SRC_DIR + "default_background_img.jpg").replace('\\', '/')
CONFIG_FILE = root_dir + os.sep + 'config.pkl'


# 日志设置
log_file = root_dir + os.sep + 'debug-lanzou-gui.log'
logger = logging.getLogger('lanzou')
fmt_str = "%(asctime)s [%(filename)s:%(lineno)d] %(funcName)s %(levelname)s - %(message)s"
logging.basicConfig(level=logging.ERROR,
                    filename=log_file,
                    filemode="a",
                    format=fmt_str,
                    datefmt="%Y-%m-%d %H:%M:%S")

logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
