'''
调试日志设置
'''

import os
import logging


__all__ = ['logger']


# 全局常量
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(ROOT_DIR)
SRC_DIR = ROOT_DIR + os.sep + "src" + os.sep
BG_IMG = (SRC_DIR + "default_background_img.jpg").replace('\\', '/')


log_file = ROOT_DIR + os.sep + 'debug-lanzou-gui.log'
logger = logging.getLogger('lanzou')
fmt_str = "%(asctime)s [%(filename)s:%(lineno)d] %(funcName)s %(levelname)s - %(message)s"
logging.basicConfig(level=logging.ERROR,
                    filename=log_file,
                    filemode="a",
                    format=fmt_str,
                    datefmt="%Y-%m-%d %H:%M:%S")

logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
