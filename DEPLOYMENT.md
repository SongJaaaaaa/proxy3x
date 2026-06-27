# proxy3x 部署指南（在新服务器上配置部署）

proxy3x 是给现有 **3x-ui** 链式代理服务用的轻量管理面板：后端纯 Python 标准库，前端 Vue 3 + Vite。它不重装 3x-ui，只读取并调用现有 3x-ui 面板 API，负责家宽池、用户套餐、订阅生成、额度巡检和中文看板。

> 前提：目标服务器上已经装好并运行 3x-ui（链式代理），proxy3x 依赖它的面板 API 和数据库。

---

## 1. 架构与端口

| 组件 | 说明 | 默认地址 |
| --- | --- | --- |
| proxy3x 后端 | `server/app.py`，Python 标准库，无第三方依赖 | `127.0.0.1:32180` |
| proxy3x 前端 | `web/`（Vue3+Vite），构建为静态文件由后端托管 | 同源 `/`，调用 `/api/*` |
| 3x-ui 面板 | 既有服务，被 proxy3x 调用 | `127.0.0.1:32080` |
| 订阅 SOCKS 工厂 | proxy3x 解析订阅并生成 sing-box 配置 | 默认 `33001-33999` |
| 反向代理 | Nginx/Caddy 终止 TLS，转发到后端 | 公网 443 |

请求链路：浏览器 → 反代(443, TLS) → proxy3x 后端(32180) → 读取 3x-ui API/数据库。

---

## 2. 目录约定（服务器侧，可用环境变量覆盖）

后端通过环境变量读取路径，默认值如下（见 `server/app.py` 顶部常量）：

```
PROXY3X_APP_DIR     默认 /opt/3x-ui-manager        # 后端代码 + 前端产物 + 数据
PROXY3X_CHAIN_DIR   默认 /opt/3x-ui-chain          # 3x-ui 数据库/订阅运行数据
PROXY3X_PANEL_URL   默认 http://127.0.0.1:32080    # 3x-ui 面板地址
PROXY3X_SERVER                 公网节点域名（订阅里用）
PROXY3X_ALT_SUBSCRIPTION_DOMAIN 备用订阅域名
PROXY3X_SHADOWROCKET_NODE_SERVER VLESS 节点服务器 IP
PROXY3X_REALITY_SNI            REALITY SNI
PROXY3X_SOCKS_PORT_START       订阅 SOCKS5 起始端口，默认 33001
PROXY3X_SOCKS_PORT_END         订阅 SOCKS5 结束端口，默认 33999
PROXY3X_SING_BOX_API_LISTEN    sing-box stats API 监听，默认 127.0.0.1:33000
PROXY3X_SING_BOX_SERVICE       sing-box systemd 服务名，默认 proxy3x-socks-factory
PROXY3X_STATSQUERY_BIN         统计查询命令，默认 xray
```

对应的关键文件：

```
$PROXY3X_APP_DIR/app.py                      后端入口
$PROXY3X_APP_DIR/frontend/                   前端构建产物（index.html + assets/*）
$PROXY3X_APP_DIR/data/manager.db             proxy3x 管理数据（⚠ 切勿覆盖/删除）
$PROXY3X_APP_DIR/manager-credentials.json    面板登录凭据（哈希）
$PROXY3X_APP_DIR/manager-credentials.txt     首次初始化生成的明文初始密码
$PROXY3X_CHAIN_DIR/db/x-ui.db                3x-ui 原始库（流量统计来源）
$PROXY3X_CHAIN_DIR/subscriptions/            Clash/Shadowrocket 订阅文件
$PROXY3X_CHAIN_DIR/socks-factory/sing-box.json 订阅 SOCKS 工厂生成的 sing-box 配置
```

订阅 SOCKS 工厂说明：

- 面板中“订阅 SOCKS”可添加多个订阅链接，刷新后解析节点。
- 每个节点可生成一个独立 SOCKS5 入口，默认一个月到期，端口从 `PROXY3X_SOCKS_PORT_START` 开始分配。
- 如果订阅源填写了总流量额度，生成时会按解析节点数量平均分给每个 SOCKS5。
- proxy3x 负责写出 `socks-factory/sing-box.json`，线上需用 sing-box 加载该配置并监听对应端口。
- 生成、启停、额度变更后，proxy3x 会尽力重启 `PROXY3X_SING_BOX_SERVICE` 让配置生效。
- V1 基础统计字段已入库，生成配置会打开 sing-box 本地 stats API；详情页“同步统计”会调用 `PROXY3X_STATSQUERY_BIN api statsquery` 写回 `upload_bytes/download_bytes`。

sing-box 服务示例：

```ini
# /etc/systemd/system/proxy3x-socks-factory.service
[Unit]
Description=proxy3x socks factory sing-box
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/local/bin/sing-box run -c /opt/3x-ui-chain/socks-factory/sing-box.json
Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
```

---

## 3. 部署前端（构建静态产物）

在本地或服务器上（需 Node 22）：

```bash
cd web
npm install
npm run build      # 执行 vue-tsc 类型检查并构建到 web/dist/
```

把 `web/dist/` 的内容部署到服务器的前端托管目录：

```bash
rsync -av --delete web/dist/ root@SERVER:/opt/3x-ui-manager/frontend/
```

后端 `serve_static` 已做 SPA fallback，深链接可用。前端同源调用 `/api`，生产环境不需要任何代理配置。

> 本地开发前端时，`web/.env.development` 里的 `VITE_API_TARGET` 决定 `/api` 代理目标（默认 `http://127.0.0.1:32180`，也可指向线上后端调试）。

---

## 4. 部署后端

后端只用 Python 3 标准库，无需 `pip install`。

```bash
# 1) 同步代码（不要覆盖 data/ 与凭据文件）
rsync -av --exclude data --exclude 'manager-credentials.*' \
  server/app.py server/rules.yaml server/subscription_server.py \
  root@SERVER:/opt/3x-ui-manager/

# 2) 首次初始化：建库、导入现有套餐、生成订阅，并写出初始管理员密码
python3 /opt/3x-ui-manager/app.py --init
cat /opt/3x-ui-manager/manager-credentials.txt   # 记下 admin 初始密码

# 3) 前台试跑
python3 /opt/3x-ui-manager/app.py --host 127.0.0.1 --port 32180
```

常用命令：

```bash
python3 /opt/3x-ui-manager/app.py            # 启动服务（默认 127.0.0.1:32180）
python3 /opt/3x-ui-manager/app.py --init     # 初始化/导入
python3 /opt/3x-ui-manager/app.py --enforce  # 手动执行额度/到期巡检
```

---

## 5. systemd 守护（推荐）

仓库未附带 systemd 单元文件，可用以下示例。主服务：

```ini
# /etc/systemd/system/proxy3x-manager.service
[Unit]
Description=proxy3x manager
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/3x-ui-manager
ExecStart=/usr/bin/python3 /opt/3x-ui-manager/app.py --host 127.0.0.1 --port 32180
Restart=always
RestartSec=3
# 如需自定义路径/域名，在此追加 Environment=PROXY3X_xxx=...

[Install]
WantedBy=multi-user.target
```

到期/额度巡检定时器（每天 00:00 与 12:00）：

```ini
# /etc/systemd/system/proxy3x-manager-enforce.service
[Unit]
Description=proxy3x quota/expire enforce
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/3x-ui-manager/app.py --enforce
```

```ini
# /etc/systemd/system/proxy3x-manager-enforce.timer
[Unit]
Description=run proxy3x enforce twice daily
[Timer]
OnCalendar=*-*-* 00,12:00:00
Persistent=true
[Install]
WantedBy=timers.target
```

启用：

```bash
systemctl daemon-reload
systemctl enable --now proxy3x-manager.service
systemctl enable --now proxy3x-manager-enforce.timer
systemctl status proxy3x-manager --no-pager
```

---

## 6. 反向代理 + HTTPS

Nginx 示例（把公网域名转发到本地 32180）：

```nginx
server {
    listen 443 ssl http2;
    server_name proxy3x.example.com;

    ssl_certificate     /etc/letsencrypt/live/proxy3x.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/proxy3x.example.com/privkey.pem;

    location / {
        proxy_pass         http://127.0.0.1:32180;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
```

会话 cookie 为 `HttpOnly; SameSite=Lax`，HTTPS 下可正常下发。

---

## 7. 升级（更新代码）

```bash
# 前端
cd web && npm install && npm run build
rsync -av --delete web/dist/ root@SERVER:/opt/3x-ui-manager/frontend/

# 后端
rsync -av --exclude data --exclude 'manager-credentials.*' \
  server/app.py server/rules.yaml server/subscription_server.py root@SERVER:/opt/3x-ui-manager/
systemctl restart proxy3x-manager
```

> ⚠ 升级只覆盖代码与前端静态文件，**绝不覆盖** `data/manager.db`、`x-ui.db`、订阅运行数据与凭据文件。

---

## 8. 验证清单

1. `systemctl status proxy3x-manager` 处于 active(running)。
2. `curl -sS http://127.0.0.1:32180/api/me` 返回 JSON（未登录时 `{"ok":false,...}`）。
3. 浏览器访问公网域名能打开登录页，用 `manager-credentials.txt` 的初始密码登录。
4. 登录后「家宽池/用户套餐」能正常加载数据（说明已成功读取 3x-ui）。
5. `python3 app.py --enforce` 能正常输出 JSON。

---

## 9. 安全注意

- 家宽账号密码只保存在服务器本地 SQLite，不写入公开订阅。
- 备份或上传代码时**不要**上传 `data/manager.db`、`x-ui.db` 和 `manager-credentials.*`。
- 后端只监听 `127.0.0.1`，对外暴露统一经反代 + TLS。
