# gin-vue-admin 接口自动化测试

基于 pytest + requests + Allure 的接口自动化测试工程，被测系统为 [gin-vue-admin](https://github.com/flipped-aurora/gin-vue-admin)。

## 项目结构

```
.
├── config/settings.py          # 全局配置（环境变量可覆盖）
├── api/                        # 接口层：只管"怎么调接口"
│   └── user_api.py             #   用户模块接口封装
├── data/                       # 数据层：测试数据（YAML）
│   └── login_cases.yaml
├── tests/                      # 用例层：只管"业务对不对"
│   ├── test_02_first_api.py    #   基础请求与断言
│   ├── test_03_parametrize.py  #   数据驱动
│   ├── test_04_fixture.py      #   fixture 注入
│   ├── test_05_token.py        #   token 依赖
│   ├── test_06_user_crud.py    #   CRUD + 数据清理
│   └── test_07_security.py     #   安全断言
├── conftest.py                 # fixture 仓库 + 日志配置
├── pytest.ini                  # pytest 配置与用例分级标记
└── docs/学习进度.md             # 学习进度与目标树
```

**分层原则**：用例层不出现 URL，接口层不做断言。接口变了只改 `api/`，业务变了只改 `tests/`。

## 快速开始

```bash
# 1. 准备环境
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. 启动被测系统（gva，默认监听 8888）
#    本机已部署时跳过此步

# 3. 跑测试
.venv/bin/pytest                    # 全量
.venv/bin/pytest -m smoke           # 只跑冒烟
.venv/bin/pytest -m "not smoke"     # 排除冒烟
```

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `AUTOTEST_BASE_URL` | `http://localhost:8888` | 被测服务地址 |
| `AUTOTEST_USERNAME` | `admin` | 登录账号 |
| `AUTOTEST_PASSWORD` | `123456` | 登录密码 |
| `AUTOTEST_USER_PASSWORD` | `Auto@12345` | 新建用户密码（须 ≥8 位） |
| `AUTOTEST_TIMEOUT` | `5` | 请求超时（秒） |

换环境不用改代码：

```bash
AUTOTEST_BASE_URL=http://10.0.0.5:8888 .venv/bin/pytest
```

## Allure 报告

```bash
.venv/bin/pytest --alluredir=allure-results --clean-alluredir
allure generate allure-results -o allure-report --clean
cd allure-report && python3 -m http.server 9999   # 浏览器访问 localhost:9999
```

> 报告用 XHR 读数据，必须走 HTTP，直接双击 `index.html` 会白屏。

## 测试数据管理

- 自动化创建的用户以 `autotest_` 前缀 + 毫秒时间戳命名，避免冲突
- 通过 `cleanup_user` fixture 在 **teardown** 中清理，用例失败也会执行
- 检查残留：

```bash
.venv/bin/python -c "
import requests
s=requests.Session()
t=s.post('http://localhost:8888/base/login',json={'username':'admin','password':'123456'},timeout=5).json()['data']['token']
r=s.post('http://localhost:8888/user/getUserList',headers={'x-token':t},timeout=5,json={'page':1,'pageSize':100,'username':'autotest_'})
print('残留:', r.json()['data']['total'])
"
```

## 接口契约

见 `docs/gin-vue-admin接口文档_登录与用户模块.md`（字段名、实测行为、已知坑位）。

写用例前先查契约，不要凭记忆猜字段——本项目字段大小写风格不统一：
`username`（登录） / `userName`、`passWord`（注册） / `ID`、`id`（不同接口）。
