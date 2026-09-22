from conftest import post_login
def test_login_via_fixture(base_url):               
    r = post_login(base_url)                        
    assert r.status_code == 200, f"HTTP状态码异常: {r.status_code}"
    assert r.json()["code"] == 0, f"业务码应为0，实际: {r.json()['code']}"