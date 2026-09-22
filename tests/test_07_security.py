import requests
import pytest
from conftest import post_login
from api.user_api import UserApi
import allure

@allure.feature("登录模块")           # 模块分组（报告里第一级）
@allure.story("安全")                 # 场景分组（第二级）
@allure.severity(allure.severity_level.CRITICAL)   # 严重级别
@pytest.mark.smoke
def test_login_failure_indistinguishable(base_url):
    user_api = UserApi(requests.Session(), base_url)
    login_one=user_api.login(username="admin1",password="123456").json()
    login_two=user_api.login(username="admin",password="auto12345").json()
    assert login_one['code']==login_two['code'],f'期望相同，实际不同'
    assert login_one['msg']==login_two['msg'],f'期望相同，实际不同'