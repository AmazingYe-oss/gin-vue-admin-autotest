#!/usr/bin/env bash
# =============================================================================
# ci/start-gva.sh —— 拉起一个「可登录」的 gva 实例（CI 与本地通用）
#
# 为什么不能只写一条 docker run：
#   gva 的种子数据（admin 用户、安全配置、菜单、casbin 规则等）只在
#   /init/initdb 这个"安装向导"接口里写入，而该接口要求启动时 GVA_DB == nil。
#   所以正确顺序是：
#     置空 db-type 启动 → 调 initdb 灌数据 → 关验证码 → 才能登录
#   跳过其中任何一步，测试都会因「用户名不存在」或「验证码错误」而全红。
#
# 用法：
#   GVA_IMAGE=<registry>/<ns>/gva-server:<tag> bash ci/start-gva.sh
#
# 环境变量：
#   GVA_IMAGE            必填，被测镜像（必须含 tag）
#   GVA_PORT             宿主机端口，默认 8888
#   GVA_CONTAINER        容器名，默认 gva-autotest
#   GVA_ADMIN_PASSWORD   初始化管理员密码，默认 123456
# =============================================================================
set -euo pipefail

# CI 诊断：失败时打印真实原因（行号 + 退出码）。排查完成后可移除。
trap 'code=$?; [ "$code" -ne 0 ] && printf "\n[诊断] 脚本在第 %s 行失败，退出码 %s\n" "$LINENO" "$code" >&2' ERR

GVA_IMAGE="${GVA_IMAGE:?必须设置 GVA_IMAGE，例如 <registry>/<ns>/gva-server:<tag>}"
GVA_PORT="${GVA_PORT:-8888}"
GVA_CONTAINER="${GVA_CONTAINER:-gva-autotest}"
GVA_ADMIN_PASSWORD="${GVA_ADMIN_PASSWORD:-123456}"
GVA_DB_NAME="gva"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GVA_CONFIG="${REPO_ROOT}/ci/gva-config.yaml"

WORK_DIR="$(mktemp -d)"
DATA_DIR="${WORK_DIR}/data"
CONFIG_DIR="${WORK_DIR}/config"
mkdir -p "${DATA_DIR}" "${CONFIG_DIR}"
cp "${GVA_CONFIG}" "${CONFIG_DIR}/config.yaml"
chmod u+w "${CONFIG_DIR}/config.yaml"

# ---------------------------------------------------------------- 权限说明
# 镜像内 gva 以非 root 的 app 用户（uid=1000）运行，而它需要对 /app/data 写入
# SQLite 文件。绑定挂载（bind mount）不改变目录属主，因此宿主目录的属主/权限
# 必须让 uid=1000 可写，否则初始化会失败：
#     {"code":7,"msg":"自动创建数据库失败..."}（宿主 data 目录里始终是空的）
#
# 本机 uid 恰好是 1000，所以不 chmod 也能跑 —— 但 GitHub runner 的 uid 是 1001，
# 不 chmod 就必然失败。这类"本地能跑、CI 报错"的差异极难排查，因此这里显式放开。
#
# 注意：用命名卷（named volume）不能替代本步骤 —— 命名卷默认 root:root 755，
# 实测同样失败。
chmod 777 "${DATA_DIR}"

log()  { printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
fail() { printf '\n[失败] %s\n' "$*" >&2; }

abort() {
  fail "$1"
  echo "--- 容器日志（最后 40 行）---"
  docker logs "${GVA_CONTAINER}" 2>&1 | tail -40 || true
  docker rm -f "${GVA_CONTAINER}" >/dev/null 2>&1 || true
  exit 1
}

log "启动容器 ${GVA_CONTAINER} ← ${GVA_IMAGE}"
docker rm -f "${GVA_CONTAINER}" >/dev/null 2>&1 || true
docker run -d --name "${GVA_CONTAINER}" \
  -p "${GVA_PORT}:8888" \
  -v "${CONFIG_DIR}:/app/config" \
  -v "${DATA_DIR}:/app/data" \
  "${GVA_IMAGE}" >/dev/null

log "等待 /health 就绪（最多 120 秒）"
ready=false
for i in $(seq 1 60); do
  if curl -fsS --connect-timeout 2 "http://127.0.0.1:${GVA_PORT}/health" >/dev/null 2>&1; then
    log "服务已就绪（第 ${i} 次探测）"
    ready=true
    break
  fi
  sleep 2
done
[ "${ready}" = "true" ] || abort "服务在 120 秒内未就绪"

log "初始化数据库（POST /init/initdb）"
init_resp="$(curl -fsS -X POST "http://127.0.0.1:${GVA_PORT}/init/initdb" \
  -H 'Content-Type: application/json' \
  -d "{\"adminPassword\":\"${GVA_ADMIN_PASSWORD}\",\"dbType\":\"sqlite\",\"dbName\":\"${GVA_DB_NAME}\",\"dbPath\":\"/app/data\"}")"
echo "  ${init_resp}"
case "${init_resp}" in
  *'"code":0'*) ;;
  *) abort "initdb 未返回成功" ;;
esac

log "关闭登录验证码（sys_security_config.captcha_open）"
PYTHON_BIN="$(command -v python3 || command -v python || true)"
[ -n "${PYTHON_BIN}" ] || abort "CI 环境里找不到 python3 或 python，无法关闭验证码"
log "使用解释器：${PYTHON_BIN}"

"${PYTHON_BIN}" - "${DATA_DIR}/${GVA_DB_NAME}.db" <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
con.execute("UPDATE sys_security_config SET captcha_open = 9999999999999 WHERE id = 1")
con.commit()
row = con.execute("SELECT captcha_open FROM sys_security_config WHERE id = 1").fetchone()
con.close()
print(f"  captcha_open = {row[0]}")
PY

log "验证 admin 可登录"
login_resp="$(curl -fsS -X POST "http://127.0.0.1:${GVA_PORT}/base/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"admin\",\"password\":\"${GVA_ADMIN_PASSWORD}\"}")"
case "${login_resp}" in
  *'"code":0'*) echo "  登录成功，已取得 token" ;;
  *) abort "admin 登录失败：$(echo "${login_resp}" | head -c 200)" ;;
esac

log "gva 就绪 → http://127.0.0.1:${GVA_PORT}"
echo "  （占用端口 ${GVA_PORT}，容器 ${GVA_CONTAINER}，数据目录 ${DATA_DIR}）"
