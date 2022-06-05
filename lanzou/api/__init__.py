from lanzou.api.core import LanZouCloud

version = '2.6.7'


def why_error(code):
    """错误原因"""
    if code == LanZouCloud.URL_INVALID:
        return '分享链接无效'
    elif code == LanZouCloud.LACK_PASSWORD:
        return '缺少提取码'
    elif code == LanZouCloud.PASSWORD_ERROR:
        return '提取码错误'
    elif code == LanZouCloud.FILE_CANCELLED:
        return '分享链接已失效'
    elif code == LanZouCloud.ZIP_ERROR:
        return '解压过程异常'
    elif code == LanZouCloud.NETWORK_ERROR:
        return '网络连接异常'
    elif code == LanZouCloud.CAPTCHA_ERROR:
        return '验证码错误'
    else:
        return f'未知错误 {code}'


__all__ = ['utils', 'types', 'models', 'LanZouCloud', 'version']
