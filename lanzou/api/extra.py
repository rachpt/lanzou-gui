import re
import requests
from random import choice

from lanzou.api.utils import USER_AGENT

timeout = 2

def get_short_url(url: str):
    """短链接生成器"""
    headers = {'User-Agent': USER_AGENT}
    short_url = ""
    api_infos = ['http://xuewaurl.cn/user/info', 'http://yldwz.cn/user/info', 'http://knurl.cn/user/info']
    apis = ['http://pay.jump-api.cn/tcn/web/test', 'http://pay.jump-api.cn/urlcn/web/test']  # 新浪、腾讯
    try:
        http = requests.get(choice(api_infos), verify=False, headers=headers, timeout=timeout)
        infos = http.json()

        uid = infos["uid"]
        username = infos["username"]
        token = infos["token"]
        site_id = infos["site_id"]
        role = infos["role"]
        fid = infos["fid"]

        post_data = {
            "uid": uid,
            "username": username,
            "token": token,
            "site_id": site_id,
            "role": role,
            "fid": fid,
            "url_long": url
        }
        for api in apis:
            resp = requests.post(api, data=post_data, verify=False, headers=headers, timeout=timeout)
            if resp.text.startswith('http'):
                short_url = resp.text
                break
    except: pass

    if not short_url:
        chinaz_api = 'http://tool.chinaz.com/tools/dwz.aspx'
        post_data = {"longurl":url, "aliasurl":""}
        try:
            html = requests.post(chinaz_api, data=post_data, verify=False, headers=headers, timeout=timeout).text
            short_url = re.findall('id="shorturl">(http[^<]*?)</span>', html)
            if short_url:
                short_url = short_url[0] 
        except: pass
    return short_url
