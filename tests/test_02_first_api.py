import pytest
import requests

def post_login(base_url="http://localhost:8888",path="/base/login",request_body=None):
    if request_body is None:
        request_body={"username":"admin","password":"123456"}
    return requests.post(url=base_url+path,json=request_body)

def test_login_success():
    r=post_login()
    assert r.status_code==200, f" HTTP状态码异常: {r.status_code} "
    assert r.json()['code']==0, f"业务码应为0，实际状态码为{r.json()['code']}"


def test_login_wrong_password():
    r=post_login(request_body={"username":"admin","password":"wrongpassword"})
    assert r.status_code==200, f"HTTP状态码异常: {r.status_code}"
    assert r.json()['code']==7, f"业务码应为7（密码错误），实际: {r.json()['code']}"