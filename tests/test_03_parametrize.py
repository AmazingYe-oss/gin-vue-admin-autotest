import pytest
import requests
from conftest import post_login
import yaml


def load_cases():
    with open("data/login_cases.yaml",encoding="utf-8") as f:
        return yaml.safe_load(f)["login_cases"]

@pytest.mark.parametrize("case",load_cases(),ids=lambda c: c["password"] or "空密码")

def test_login_code(base_url,case):
    password=case["password"]
    expected_code=case["expected_code"]
    r=post_login(base_url,request_body={"username":"admin","password":password})
    assert r.status_code==200, f"HTTP状态码异常: {r.status_code}"
    assert r.json()["code"] == expected_code, f"业务码应为{expected_code}，实际: {r.json()['code']}"
