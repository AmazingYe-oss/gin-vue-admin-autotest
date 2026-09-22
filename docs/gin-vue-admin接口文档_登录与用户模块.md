# gin-vue-admin 接口文档 —— 登录与用户模块

> - 生成日期：2026-09-20
> - 文档依据：`~/interview-project/gin-vue-admin/server` 源码 + `gin-vue-admin-autotest` 实测
> - 覆盖范围：`base`（登录/验证码）与 `user`（用户 CRUD）两个模块，与自动化测试覆盖范围一致
> - 源码版本要点：SQLite 存储、未启用 Redis / 多点登录（`use-multipoint: false`）

---

## 1. 通用约定

### 1.1 基础信息

| 项目 | 值 |
|---|---|
| 服务地址 | `http://localhost:8888`（`config.yaml` → `system.addr: 8888`） |
| 路由前缀 | 无（`router-prefix: ""`） |
| 请求格式 | `Content-Type: application/json`（除特别说明外均为 JSON 请求体） |
| 默认账号 | `admin / 123456` |

### 1.2 统一响应结构

所有业务接口返回：

```json
{ "code": 0, "data": {}, "msg": "成功" }
```

| 字段 | 类型 | 说明 |
|---|---|---|
| code | int | 业务码，见下表 |
| data | object | 业务数据，失败时通常为 `{}` 或 `null` |
| msg | string | 提示文案（**排查问题的第一入口**） |

**业务码表**（源码：`model/common/response/response.go`）：

| code | 常量 | 含义 |
|---|---|---|
| 0 | SUCCESS | 成功 |
| 7 | ERROR | 业务失败（参数校验、账号密码错、无权限等） |
| 10001 | PASSWORD_CHANGE_REQUIRED | 登录成功但必须修改初始/过期密码 |

### 1.3 两层错误模型（重要）

| 错误类型 | HTTP 状态 | 响应体 | 示例 |
|---|---|---|---|
| 业务失败 | **200** | `{code: 7, msg: "..."}` | 密码错误、字段为空、参数不合法 |
| 鉴权失败 | **401** | `{code: 7, msg: "..."}` | 不带 token、token 过期、签名被篡改 |

> 判断依据：`response.Result()` 恒用 `http.StatusOK`；`response.NoAuth()` 恒用 `http.StatusUnauthorized`。
> 测试断言建议：先断言 HTTP 层（status_code），再断言业务层（code / msg）。

### 1.4 鉴权机制（JWT + x-token）

凭证为 JWT 字符串（`eyJ` 开头），携带方式（源码：`utils/claims.go GetToken`）：

```
1. 优先读请求头  x-token: eyJhbGciOi...
2. 请求头没有 → 回退读同名 cookie  x-token
3. 都没有 → 401 {"code":7,"msg":"未登录或非法访问，请登录"}
```

**401 场景与文案**（源码：`middleware/jwt.go`）：

| 场景 | msg |
|---|---|
| 无凭证 | 未登录或非法访问，请登录 |
| token 进入黑名单（多点登录被踢） | 您的帐户异地登陆或令牌失效 |
| token 过期 | 登录已过期，请重新登录 |
| token 签名/格式非法（如被篡改） | 具体 JWT 解析错误信息 |

**注意**：登录接口成功时除返回 token 外，还会 `Set-Cookie: x-token`（Path=/，与 token 同过期时间）。
因此浏览器/共享 Session 在登录后**仅凭 cookie 即可通过鉴权**——这是后端真实行为，测试时须防"测试污染"。

### 1.5 分页约定（`model/common/request/common.go PageInfo`）

| 参数 | 必填 | 实测行为 |
|---|---|---|
| page | 是 | **传 0 直接报错** `Page值不能为空`；传负数不报错但返回空列表 |
| pageSize | 是 | **无上限**（实测 10000 也原样返回，未被截断） |

分页响应统一为 `PageResult`：`{ "list": [...], "total": 100, "page": 1, "pageSize": 10 }`

> ⚠️ **2026-09-21 实测修正**：本文档初版写「pageSize ≤100，超出截为 100、≤0 取默认值」——**实测不成立**。
> 实测：`pageSize=500` 返回 500、`pageSize=10000` 返回 10000，均未截断；
> `page=0` 是**必填校验失败**（code=7 `Page值不能为空`），而不是"自动取 1"；
> `page=-5,pageSize=-5` 不报错，返回 `{"list":[],"total":2,"page":-5,"pageSize":-5}` —— 分页参数原样回显。
> 结论：本版本 gva 的分页**没有兜底纠正逻辑**，参数非法就直接报错或返回空。
> 写分页用例时应覆盖：page=0（报错）、负数（空列表）、超大 pageSize（不截断）。

---

## 2. 基础模块 /base（无需鉴权）

### 2.1 登录

```
POST /base/login
```

**请求体**（`model/system/request/sys_user.go Login`）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| username | string | 是 | 用户名（**注意：此处全小写**） |
| password | string | 是 | 密码 |
| captcha | string | 条件 | 验证码（触发验证码策略时必填） |
| captchaId | string | 条件 | 验证码 ID（同上） |

**处理流程**（`api/v1/system/sys_user.go Login`）：

```
1. 参数绑定与必填校验（空值 → "Username值不能为空" / "Password值不能为空"）
2. 账号锁定检查（开启时，锁定 → "账号已锁定，请 N 分钟后再试"）
3. 验证码检查（按 IP 计数，触发阈值才要求）
4. 凭证校验（用户不存在与密码错误返回同一文案，防用户枚举）
5. 用户冻结检查（enable≠1 → "用户被禁止登录"）→ 签发 token
```

**成功响应**（200）：

```json
{
  "code": 0,
  "data": {
    "user": { "ID": 1, "userName": "admin", "nickName": "超级管理员", "...": "见附录 SysUser" },
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "expiresAt": 1758364800000,
    "needChangePassword": false
  },
  "msg": "登录成功"
}
```

| 字段 | 说明 |
|---|---|
| token | JWT，放入后续请求头 `x-token` |
| expiresAt | 过期时间，**毫秒级** Unix 时间戳 |
| needChangePassword | true 时前端应强制跳转改密页 |

同时响应头包含 `Set-Cookie: x-token=eyJ...`。

**失败响应**（均为 HTTP 200 + code 7）：

| 场景 | msg |
|---|---|
| username 为空 | Username值不能为空 |
| password 为空 | Password值不能为空 |
| 验证码错误/缺失（触发时） | 验证码错误 |
| 用户不存在 或 密码错误 | **用户名不存在或者密码错误**（两者文案完全相同，安全设计） |
| 用户被冻结 | 用户被禁止登录 |
| 账号被锁定 | 账号已锁定，请 N 分钟后再试 |

**⚠️ 字段名大小写陷阱**：登录请求用 `username`（全小写），而 SysUser 对象序列化为 `userName`（大写 N）——同一系统两处风格不同，写断言时务必核对。

### 2.2 获取验证码

```
POST /base/captcha
```

**请求体**：无（按请求方 IP 判断是否需要验证码）

**成功响应**：

```json
{
  "code": 0,
  "data": {
    "captchaId": "xxxxxx",
    "picPath": "data:image/png;base64,...",
    "captchaLength": 6,
    "openCaptcha": false
  },
  "msg": "成功"
}
```

> 当前环境安全配置中 `captchaOpen` 已调至极大值（详见附录 4.3），常规登录**无需验证码**；仅连续登录失败达到阈值后触发。

---

## 3. 用户模块 /user（均需鉴权）

| 方法 | 路径 | 用途 | 操作记录 |
|---|---|---|---|
| GET | /user/getUserInfo | 获取自身信息 | 否 |
| POST | /user/getUserList | 分页获取用户列表 | 否 |
| POST | /user/admin_register | 管理员注册账号 | 是 |
| POST | /user/changePassword | 修改自己的密码 | 是 |
| POST | /user/resetPassword | 重置指定用户密码 | 是 |
| DELETE | /user/deleteUser | 删除用户 | 是 |
| PUT | /user/setUserInfo | 设置（他人）用户信息 | 是 |
| PUT | /user/setSelfInfo | 设置自身信息 | 是 |
| POST | /user/setUserAuthority | 设置自己的角色 | 是 |
| POST | /user/setUserAuthorities | 设置指定用户的角色组 | 是 |
| POST | /user/setUserDepartments | 设置用户归属部门 | 是 |
| POST | /user/setUserPositions | 设置用户岗位 | 是 |
| PUT | /user/setSelfSetting | 设置自身界面配置 | 是 |

### 3.1 获取自身信息

```
GET /user/getUserInfo
Headers: x-token: <token>
```

**请求参数**：无（用户身份从 JWT 中提取）

**成功响应**：

```json
{ "code": 0, "data": { "userInfo": { "ID": 1, "userName": "admin", "...": "" } }, "msg": "获取成功" }
```

> ⚠️ 实测坑位：数据包在 `data.userInfo` 这一层，不是 `data.user`（`gin.H{"userInfo": ...}`）。

### 3.2 分页获取用户列表

```
POST /user/getUserList
Headers: x-token: <token>
```

**请求体**（`request.GetUserList`，嵌入 PageInfo）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | int | 是 | 页码 |
| pageSize | int | 是 | 每页大小（≤100） |
| keyword | string | 否 | 关键字 |
| username / nickName / phone / email | string | 否 | 精确筛选 |
| orderKey | string | 否 | 排序字段 |
| desc | bool | 否 | 排序方式，false 升序（默认）/ true 降序 |

**成功响应**：`data` 为 PageResult：`{ list: [SysUser...], total, page, pageSize }`，msg 为 `获取成功`。

### 3.3 注册用户（管理员）

```
POST /user/admin_register
Headers: x-token: <token>
```

**请求体**（`request.Register`）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| userName | string | **是** | **注意大写 N**（与登录接口不同！） |
| passWord | string | **是** | **注意大写 W**；需满足密码复杂度（默认≥8位） |
| nickName | string | **是** | **实测：不传报 `NickName值不能为空`**（本文档初版误标为"否，默认系统用户"） |
| authorityId | uint | **是** | **实测：不传报 `AuthorityId值不能为空`**（初版误标为"否，默认 888"） |
| authorityIds | []uint | 否 | 多角色 ID |
| enable | int | 否 | 1 正常 / 2 冻结 |
| phone / email | string | 否 | 联系方式 |
| headerImg | string | 否 | 头像链接 |

> ⚠️ **2026-09-21 实测修正**：必填校验来自 `utils.RegisterVerify = {Username, NickName, Password, AuthorityId}`，
> 四个字段缺一不可，且**校验顺序在** `gorm` 默认值生效**之前**，所以"默认系统用户""默认 888"都到不了。
> 实测证据：缺 nickName → `NickName值不能为空`；缺 authorityId → `AuthorityId值不能为空`；缺 userName → `Username值不能为空`。
>
> 另外注意：**`page=0` 报的是 `Page值不能为空`**，说明必填校验把 0 当作"空值"——写用例时"传 0"和"不传"是同一类失败。

**成功响应**：`data: { user: SysUser }`，msg 为 `注册成功`。

### 3.4 修改自己的密码

```
POST /user/changePassword
Headers: x-token: <token>
```

**请求体**（`request.ChangePasswordReq`）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| password | string | 是 | 原密码 |
| newPassword | string | 是 | 新密码，需过复杂度校验 |

> 用户 ID 从 JWT 提取（防越权改他人密码）。原密码错误时 msg 为 `修改失败，原密码与当前账户不符`；成功为 `修改成功`。改密后建议重新登录。

### 3.5 重置指定用户密码

```
POST /user/resetPassword
Headers: x-token: <token>
```

**请求体**（`request.ResetPassword`）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| ID | uint | 是 | 目标用户 ID（**大写 ID**） |
| password | string | 是 | 新密码，需过复杂度校验 |

成功 msg 为 `重置成功`。

### 3.6 删除用户

```
DELETE /user/deleteUser
Headers: x-token: <token>
```

**请求体**：`{ "id": 2 }`（GetById 结构，**小写 id**）

| 场景 | HTTP | code | msg |
|---|---|---|---|
| 删除自己 | 200 | 7 | 删除失败, 无法删除自己。 |
| 成功 | 200 | 0 | 删除成功 |
| **删除不存在的 id** | 200 | **0** | **删除成功** ← ⚠️ 缺陷 |
| 不传 id | 200 | 7 | ID值不能为空 |

> ⚠️ **2026-09-21 实测确认的缺陷**（同批 autotest 用例已用 `xfail` 记录）：
> `DELETE /user/deleteUser` 传一个**不存在**的 id（实测 999999999），服务端返回 `{"code":0,"msg":"删除成功"}`。
> 正确行为应报错（"用户不存在"）。现状下前端会提示"删除成功"，用户以为删掉了，实际什么都没发生
> —— **数据一致性问题，且属于"只读接口测不出来"的那类 bug**。
> 建议：向 gva 提 issue；测试侧保留 `@pytest.mark.xfail` 用例，修复后会自动 XPASS 提醒改断言。

### 3.7 设置用户信息（管理员改他人）

```
PUT /user/setUserInfo
Headers: x-token: <token>
```

**请求体**（`request.ChangeUserInfo`）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| ID | uint | 是 | 目标用户 ID |
| nickName / phone / email / headerImg | string | 否 | 基本信息 |
| enable | int | 否 | 1 正常 / 2 冻结 |
| authorityIds | []uint | 否 | 非空时同时替换该用户的角色组 |

成功 msg 为 `设置成功`。

### 3.8 设置自身信息

```
PUT /user/setSelfInfo
Headers: x-token: <token>
```

请求体同 3.7，但 **ID 由 JWT 决定**，传入的 ID 会被忽略（防越权）。成功 msg 为 `设置成功`。

### 3.9 设置自己的角色

```
POST /user/setUserAuthority
Headers: x-token: <token>
```

**请求体**：`{ "authorityId": 888 }`

> 特殊行为：修改的是**当前登录用户自己**的角色；因角色变更后 JWT claims 失效，
> 响应头会返回 `new-token` 和 `new-expires-at`，客户端应替换本地 token。
> 成功 msg 为 `修改成功`。

> ⚠️ **测试危险警告（2026-09-21 实测）**：该接口会**真实改写调用者自己的角色**，属于破坏性操作。
> 实测环境 admin(ID=1) 有 3 个角色（888 普通用户 / 8881 普通用户子角色 / 9528 测试角色），
> 调用后 `sys_user_authority` 表**未变化**（主角色本就是 888），所以本次未造成破坏；
> 但若传入与当前主角色不同的值，**会改变账号权限**，且可能因此丢失菜单/接口访问权。
> **建议**：测试该接口时用**临时创建的账号**，不要用 admin 直接测。
> 实测同时确认：`new-token` / `new-expires-at` 两个响应头**确实存在**，且 `new-expires-at` 是 **10 位秒级**时间戳
> （与登录返回的 13 位毫秒级 `expiresAt` 不同，文档 §4.5 第 5 条已记录）。

### 3.10 设置指定用户的角色组

```
POST /user/setUserAuthorities
Headers: x-token: <token>
```

**请求体**：`{ "ID": 2, "authorityIds": [888, 8881] }`。成功 msg 为 `修改成功`。

### 3.11 设置用户归属部门

```
POST /user/setUserDepartments
Headers: x-token: <token>
```

**请求体**（`request.SetUserDepartments`）：

| 字段 | 类型 | 说明 |
|---|---|---|
| ID | uint | 用户 ID |
| deptIds | []uint | 归属部门 ID 集合（数据可见范围） |
| primaryDeptId | uint | 主部门 ID（数据归属），为 0 时取集合首个 |

成功 msg 为 `设置成功`。

### 3.12 设置用户岗位

```
POST /user/setUserPositions
Headers: x-token: <token>
```

**请求体**：`{ "ID": 2, "positionIds": [1, 2] }`。成功 msg 为 `设置成功`。

### 3.13 设置自身界面配置

```
PUT /user/setSelfSetting
Headers: x-token: <token>
```

**请求体**：任意 JSON 对象（`map[string]interface{}`，存储于 `origin_setting` 字段）。成功 msg 为 `设置成功`。

---

## 4. 附录

### 4.1 SysUser 对象（JSON 序列化）

源码：`model/system/sys_user.go`。密码字段 `json:"-"` 永不序列化。

| 字段 | 类型 | 说明 |
|---|---|---|
| ID / CreatedAt / UpdatedAt | uint/time | 通用模型字段 |
| uuid | string | 用户 UUID |
| userName | string | 登录名（**大写 N**） |
| nickName | string | 昵称 |
| headerImg | string | 头像 |
| authorityId | uint | 主角色 ID |
| authority / authorities | object/array | 角色对象 |
| deptId / dept / departments | uint/object/array | 部门 |
| positions | array | 岗位 |
| phone / email | string | 联系方式 |
| enable | int | 1 正常 / 2 冻结 |
| originSetting | object | 界面配置 |
| passwordUpdatedAt | string | 密码最后修改时间 |

### 4.2 分页响应 PageResult

```json
{ "list": [], "total": 0, "page": 1, "pageSize": 10 }
```

### 4.3 安全配置（当前环境实测值，SQLite `sys_security_config` 表）

| 配置 | 代码默认 | 当前环境 | 效果 |
|---|---|---|---|
| captchaOpen | 0（每次登录都要验证码） | 9999999999999 | **实际不触发验证码** |
| lockEnable / lockThreshold | false / 5 | false / 5 | 失败锁定未启用 |
| pwdMinLength | 8 | 8 | 新密码至少 8 位 |
| 复杂度（大写/小写/数字/特殊） | 均 false | 均 false | 无强制复杂度 |
| limitEnable（限流） | false | false | 未启用 |

> 代码默认值见 `model/system/sys_security_config.go`；实际运行值以数据库为准（启动加载、保存即热更新）。
> 换新环境部署时，若 captchaOpen=0，登录必须先调 `/base/captcha` 获取验证码。

### 4.4 源码索引

| 内容 | 位置 |
|---|---|
| 路由注册 | `server/router/system/sys_base.go`、`sys_user.go` |
| 登录/用户处理器 | `server/api/v1/system/sys_user.go` |
| 验证码处理器 | `server/api/v1/system/sys_captcha.go` |
| 请求结构 | `server/model/system/request/sys_user.go` |
| 响应结构 | `server/model/system/response/sys_user.go`、`sys_captcha.go` |
| 统一响应/业务码 | `server/model/common/response/response.go`、`common.go` |
| token 获取（header→cookie 回退） | `server/utils/claims.go GetToken` |
| JWT 中间件（401） | `server/middleware/jwt.go` |
| 安全配置 | `server/model/system/sys_security_config.go` |

### 4.5 已知坑位清单（来自 autotest 实测）

1. **登录请求 `username` 全小写，SysUser 序列化 `userName` 大写 N**，注册请求则是 `userName`/`passWord`——三处风格不一致。
2. **getUserInfo 的数据在 `data.userInfo`**，不是 `data.user`。
3. **登录会 Set-Cookie x-token**，且后端鉴权回退读 cookie——用 `requests.Session` 测"未登录"场景时，务必换新会话，否则被 cookie 自动鉴权得到假 200（测试污染）。
4. **篡改 token 返回 401**（HTTP 层直接拒绝），而业务失败是 200 + code 7——断言要分两层写。
5. `expiresAt` 是**毫秒**时间戳（13 位），`new-expires-at` 响应头是**秒**时间戳（10 位，实测确认）。
6. ~~分页 pageSize 超过 100 会被静默截断为 100~~ → **实测推翻**：无上限，10000 也原样返回；`page=0` 是必填报错而非自动取 1（详见 §1.5）。
7. **`admin_register` 的 `nickName` 和 `authorityId` 其实是必填**（源码 `RegisterVerify`），不传报 `NickName值不能为空` / `AuthorityId值不能为空`，gorm 默认值不生效（详见 §3.3）。
8. **`deleteUser` 删不存在的 id 会返回"删除成功"**——真实缺陷，别把它当正常行为写进断言（详见 §3.6）。
9. **`setUserAuthority` 是破坏性操作**，会真实改自己角色；测试请用临时账号（详见 §3.9）。
