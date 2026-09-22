from conftest import post_login,take_token
import requests


def test_get_user_list(base_url):
    token=take_token(base_url)
    r=requests.post(url=base_url+"/user/getUserList",json={"page":1,"pageSize":10},headers={"x-token": token})
    assert r.status_code==200, f" HTTP状态码异常: {r.status_code} "
    r_json=r.json()
    assert r_json['code']==0, f"业务码应为0，实际状态码为{r.json()['code']}"

def test_take_token(base_url):
    r=post_login(base_url)
    assert r.status_code==200, f" HTTP状态码异常: {r.status_code} "
    r_json=r.json()
    assert r_json['code']==0, f"业务码应为0，实际状态码为{r.json()['code']}"
    token=r_json["data"]["token"]
    token_3=token[:3]
    assert token.startswith('eyJ'),f"token首字母应为'eyJ',实际为{token_3}"
    