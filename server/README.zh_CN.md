# proxy3x 管理面板

proxy3x 是给现有 3x-ui 链式代理服务用的轻量管理面板。它不重装 3x-ui，只读取和调用现有 3x-ui 面板 API，负责家宽池、用户套餐、订阅生成、额度巡检和中文看板。

## 目录

- `/opt/3x-ui-manager/app.py`：管理面板后端。
- `/opt/3x-ui-manager/frontend-src/`：Vue 3 + TypeScript + Element Plus 前端源码。
- `/opt/3x-ui-manager/frontend/`：前端构建产物，由后端静态托管。
- `/opt/3x-ui-manager/data/manager.db`：proxy3x 自己的管理数据。
- `/opt/3x-ui-chain/db/x-ui.db`：3x-ui 原始数据库，流量统计来源。
- `/opt/3x-ui-chain/subscriptions/`：Clash 和 Shadowrocket 订阅文件。
- `/opt/3x-ui-chain/chain-deployment.json`：部署元数据和订阅流量头配置。

## 常用服务

```bash
systemctl status proxy3x-manager --no-pager
systemctl status proxy3x-manager-enforce.timer --no-pager
systemctl status proxy3x-manager-expire.timer --no-pager
systemctl restart proxy3x-manager
python3 /opt/3x-ui-manager/app.py --init
python3 /opt/3x-ui-manager/app.py --enforce
```

## 开发说明

后端只使用 Python 标准库，入口是 `app.py`。前端已经重构为 Vue 3 + TypeScript + Element Plus，源码在 `frontend-src/`，构建后的静态文件输出到 `frontend/`，后端继续从 `frontend/` 托管页面。

本地开发前端：

```bash
cd frontend-src
npm install
npm run dev
```

构建前端：

```bash
cd frontend-src
npm run build
```

`npm run build` 会执行 TypeScript 检查，并把结果写入 `../frontend/`。部署时只需要把 `app.py`、`frontend/`、`rules.yaml`、`subscription_server.py`、`systemd/` 等代码文件更新到服务器；不要覆盖服务器上的 `data/manager.db`、3x-ui 数据库和订阅运行数据。

后端开发：

```bash
python3 app.py --init
python3 app.py
```

线上服务由 systemd 管理，修改后重启 `proxy3x-manager` 即可。前端只是调用现有 `/api/*` 接口，用户套餐、家宽池、流量记录等数据都保存在服务器 SQLite 数据库里，不在前端代码里。

新增用户流程：

1. 在“家宽池”粘贴 `IP:端口:账号:密码`。
2. 填备注和使用人，点击加入。
3. 点击检测，成功后协议会固定为 `http` 或 `socks`。
4. 在“用户套餐”新增用户，选择家宽、总额度、住宅额度和失效时间；失效时间默认一个月后。
5. 面板会创建娱乐入口和住宅入口，并生成 `.yaml` / `.list` 订阅。

额度规则：

- 用户套餐到期后会关闭娱乐和住宅两个节点，套餐状态改为失效。
- 到期巡检由 `proxy3x-manager-expire.timer` 在每天北京时间 `00:00` 和 `12:00` 触发，也可以手动执行 `python3 /opt/3x-ui-manager/app.py --enforce`。
- 住宅流量超过住宅额度后，只关闭住宅节点。
- 总用量超过总额度后，关闭娱乐和住宅两个节点。
- 历史用量来自 3x-ui 的 `client_traffics`，不会因为刷新订阅而清零。

订阅规则：

- Clash 节点名固定为 `🇺🇸 娱乐流量` 和 `🇺🇸 住宅流量`。
- 粘贴规则中的 `性价比机场` 会替换为 `手动选择`。
- Shadowrocket 订阅每行一个 VLESS 节点。

## 注意

家宽账号密码只保存在服务器本地的 SQLite 数据库里，不写入公开订阅。备份或上传代码时不要上传 `/opt/3x-ui-manager/data/manager.db`。
