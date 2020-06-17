'''
调试日志设置
'''

import os
import sys
import logging


__all__ = ['logger']

logger = logging.getLogger('lanzou')
log_file = os.path.dirname(sys.argv[0]) + os.sep + 'debug-lanzou-gui.log'
fmt_str = "%(asctime)s [%(filename)s:%(lineno)d] %(funcName)s %(levelname)s - %(message)s"
logging.basicConfig(level=logging.ERROR,
                    filename=log_file,
                    filemode="a",
                    format=fmt_str,
                    datefmt="%Y-%m-%d %H:%M:%S")

logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
