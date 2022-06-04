__all__ = ['api', 'gui']

"""
  是否开启使用 PyQtWebEngine 辅助获取cookie
  pyinstaller 打包 PyQtWebEngine 会使体积变大很多
  False 时移除 lanzou 目录下 login_assister.py
"""
USE_WEB_ENG = False 
