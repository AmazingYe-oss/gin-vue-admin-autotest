import pytest
import requests
from conftest import take_token
import time
USERNAME = f"autotest_{int(time.time() * 1000)}"
USER_REGISTER_PATH="/user/admin_register"
USER_GETINFO_PATH="/user/getUserList"
REQUEST_GETINFO_BODY={"page":1,"pageSize":10,"username":USERNAME}



@pytest.mark.smoke
def test_create_user(base_url,only_name,cleanup_user):
    #登录
    token=take_token(base_url)
    r=requests.post(url=base_url+USER_REGISTER_PATH,headers={"x-token":token},json={"userName":only_name,"passWord":"Auto@12345","nickName":"nick","authorityId": 888})
    assert r.status_code==200,f"HTTP 状态码错误，{r.status_code}"
    r_json=r.json()
    assert r_json['code']==0,f"期望代码为0，实际为{r_json['code']}"








