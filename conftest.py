import logging
import os

import pytest
import requests

from config import settings

# ---------- 日志配置 ----------
# 【两个输出目的地，各管一摊】
#   终端：由 pytest 的 log_cli 负责（见 pytest.ini），所以这里不重复加 StreamHandler
#   文件：由下面的 FileHandler 负责，落盘 logs/autotest.log
#
# 【为什么挂在 root logger 上】
#   logging 的层级按名字的点号划分："api.user_api" 的父级是 "api"，不是 "autotest"。
#   而所有 logger 的记录最终都会向上传播到 root —— 所以挂 root 能让全部模块的日志都落盘。
#   这比挂在某个具体名字上更省心：新增模块不用改配置。
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

_log_file = logging.FileHandler(os.path.join(LOG_DIR, "autotest.log"), encoding="utf-8")
_log_file.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
))

_root = logging.getLogger()
_root.setLevel(logging.INFO)
_root.addHandler(_log_file)


@pytest.fixture
def base_url():
    return settings.BASE_URL


@pytest.fixture
def only_name():
    import time
    return f"autotest_{int(time.time() * 1000)}"


@pytest.fixture
def cleanup_user(base_url,only_name):
    yield only_name
    token=take_token(base_url)
    r=requests.post(url=base_url+"/user/getUserList",json={"page":1,"pageSize":10,"username":only_name},headers={"x-token":token})
    users = r.json()['data']['list']
    print(f"\n[清理] 查找用户 {only_name} → 查到 {len(users)} 条")    
    if users:
        user_id = users[0]['ID']
        delete_user(base_url,token,user_id)
        print(f"[清理] 删除 id={user_id} → {r.json()}") 





def post_login(base_url, request_body=None):        
    if request_body is None:
        request_body = {"username": "admin", "password": "123456"}
    return requests.post(url=base_url + "/base/login", json=request_body)


def take_token(base_url):
    r=post_login(base_url)
    r_json=r.json()
    token=r_json["data"]["token"]
    return token


def delete_user(base_url, token, user_id):
    return requests.delete(url=base_url+"/user/deleteUser",headers={"x-token":token},json={"id":user_id})
    