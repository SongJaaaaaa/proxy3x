# 订阅 SOCKS 多节点与模块拆分改造计划

## 背景

当前项目已经支持订阅 SOCKS 导入、节点生成、SOCKS5 池、用户套餐和 Clash/Shadowrocket 订阅输出。近期测试中已经修复了部分增删改查、生成 SOCKS5、线上订阅 500 等问题。

接下来要做的是把「订阅 SOCKS 节点」真正作为可售卖套餐的上游节点来源，并支持一个用户套餐绑定多个订阅 SOCKS 生成的节点。同时，后端目前大量逻辑集中在 `server/app.py`，继续堆功能会降低可读性和排查效率，因此需要同步做一次模块拆分。

## 改造目标

1. 用户套餐新增、编辑时，可以从订阅 SOCKS 生成的节点中多选、全选、搜索选择。
2. 一个用户套餐可以绑定多个上游 SOCKS 节点，并在订阅中输出多个可用节点。
3. Clash 节点名称以「订阅 SOCKS 中的节点名称」为准，不再统一显示成简单固定名称。
4. 对外订阅只暴露本站域名和本站转发端口，不暴露真实上游 IP、上游域名、上游账号、密码、token。
5. 生成的 Clash/Shadowrocket 节点应该走本站中转，再由服务端按套餐绑定关系转发到对应上游。
6. 修复使用订阅生成 SOCKS5 绑定用户套餐后，Clash 导入成功但节点测试超时的问题。
7. 保留已有单上游套餐数据的兼容能力，避免线上旧套餐直接失效。
8. 拆分后端模块，让数据库、订阅解析、SOCKS 工厂、套餐、面板/路由配置各自独立。

## 当前状态

- 本地前端端口已从 `5173` 改为 `52180`，避免和本地分销系统冲突。
- 线上服务已部署到 `/opt/3x-ui-manager`，链式代理运行目录为 `/opt/3x-ui-chain`。
- 线上订阅 500 问题已修复，原因是 `sqlite3.Row` 被当成普通 dict 使用。
- 当前工作区存在未提交的 `server/app.py` 改动，里面已经开始做多上游绑定，但还没有完成闭环。
- 下一步不要直接部署当前未完成代码，需要先收口设计、拆模块、补齐前后端和验证。

## 数据模型计划

新增套餐绑定表：

```sql
CREATE TABLE IF NOT EXISTS package_bindings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  package_id INTEGER NOT NULL,
  upstream_id INTEGER NOT NULL,
  port INTEGER NOT NULL,
  email TEXT NOT NULL,
  inbound_id INTEGER,
  entry_json TEXT,
  sort_order INTEGER DEFAULT 0,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

说明：

- `packages` 继续保留旧字段 `upstream_id`、`direct_port`、`direct_entry_json`，用于兼容旧套餐。
- 新套餐优先读取 `package_bindings`。
- 旧套餐在初始化或编辑时迁移到 `package_bindings`。
- 每个绑定节点拥有独立入口端口、独立 email、独立 inbound，方便统计和路由。

## 后端模块拆分计划

目标是让 `server/app.py` 只负责应用启动、路由注册和少量胶水逻辑。

建议拆分为：

| 模块 | 职责 |
| --- | --- |
| `server/db.py` | SQLite 连接、初始化表、迁移、事务辅助 |
| `server/panel.py` | 3x-ui 面板登录、凭据读取、inbound 增删改查 |
| `server/subscriptions.py` | 订阅 SOCKS 解析、刷新、节点入库、订阅输出 |
| `server/socks_factory.py` | sing-box SOCKS 工厂配置生成、启停、端口分配 |
| `server/packages.py` | 用户套餐创建、编辑、删除、绑定节点、流量统计 |
| `server/routing.py` | Xray/sing-box 路由规则生成、按 inboundTag 绑定 outbound |
| `server/app.py` | Flask/FastAPI 路由入口、错误响应、静态资源 |

拆分原则：

- 先搬代码，不改变业务行为。
- 每次只拆一个职责块，拆完马上做语法检查。
- 业务逻辑保持简洁直接，不为了极端异常数据写过重防御。
- 真实报错优先打日志，方便线上复现，不靠猜测堆判断。

## 后端功能计划

1. 套餐创建
   - 接收 `upstream_ids: number[]`。
   - 为空时可使用默认可用上游，或按前端选择要求处理。
   - 为每个上游生成一个套餐绑定入口。
   - 写入 `package_bindings`。
   - 同步生成 3x-ui inbound 和服务端路由。

2. 套餐编辑
   - 支持重新选择多个上游。
   - 新增的上游生成新的 binding。
   - 移除的上游停用或删除对应 inbound。
   - 保留未变化绑定的端口和节点信息，避免用户订阅频繁变化。

3. 套餐删除
   - 删除套餐下所有 binding 对应的 inbound。
   - 删除 `package_bindings`。
   - 重新生成路由配置。
   - 不再因为 Windows 本地没有 `/opt/3x-ui-chain` 而把已完成操作误报失败。

4. 流量统计
   - 多 binding 套餐需要汇总所有 binding 的上/下行。
   - 兼容旧套餐单入口统计。
   - `Subscription-Userinfo` 返回套餐总用量和套餐总额度。

5. 路由生成
   - 每个 binding 使用独立 `inboundTag`。
   - 每个上游 SOCKS 节点对应独立 outbound。
   - routing rule 按 `inboundTag -> outboundTag` 精确绑定。
   - 生成失败时写清楚日志，避免只提示泛化错误。

6. 订阅输出
   - Clash YAML 中的 `name` 使用订阅 SOCKS 节点名称。
   - `server` 使用本站域名，例如 `proxy3x.sjiaa.cc.cd` 或配置中的公开域名。
   - `port` 使用本站分配的套餐入口端口。
   - 不输出真实上游 IP、上游端口、上游账号密码。

## 前端功能计划

1. `PackageFormDialog.vue`
   - 单选上游改为多选上游。
   - 支持搜索、全选、取消全选。
   - 显示已选择数量。
   - 新增和编辑都提交 `upstream_ids`。

2. `PackagesView.vue`
   - 创建套餐、编辑套餐时传递多节点绑定数据。
   - 表格中的快速绑定入口改成多节点模式，或先移除单选绑定入口，避免误导。

3. `PackageTable.vue`
   - 套餐列表显示已绑定节点数量。
   - 可以显示前几个节点名称，超出后显示 `+N`。

4. `types/dashboard.ts`
   - 新增 `PackageBinding` 类型。
   - `Package` 增加 `bindings`、`upstream_ids`。
   - `Upstream` 增加 `display_name`。
   - 创建/编辑参数增加 `upstream_ids?: number[]`。

## 线上与本地差异处理

本地 Windows 没有 `/opt/3x-ui-chain`，所以涉及 sing-box、systemd、线上路由重载的代码需要区分：

- 本地可以完成数据库、前端、接口、订阅文本生成测试。
- 真实 SOCKS 节点连通性、端口监听、systemd 重启必须在线上 Linux 测试。
- 本地不要因为不存在 `/opt/3x-ui-chain` 把数据库操作、套餐保存误判为失败。
- 线上失败时优先看服务日志和生成配置，而不是继续加大量兼容判断。

## 验证计划

本地验证：

```powershell
& 'D:\Python\python.exe' -c "import ast, pathlib; ast.parse(pathlib.Path(r'D:\test项目\proxy3x\server\app.py').read_text(encoding='utf-8')); print('app.py syntax ok')"
& 'D:\nvm\v22.22.0\npm.cmd' run build
```

线上验证：

```bash
python3 -m py_compile /opt/3x-ui-manager/*.py
systemctl restart proxy3x-manager
systemctl status proxy3x-manager --no-pager
systemctl status proxy3x-socks-factory --no-pager
journalctl -u proxy3x-manager -n 120 --no-pager
journalctl -u proxy3x-socks-factory -n 120 --no-pager
```

业务验证：

1. 导入订阅 SOCKS。
2. 从订阅节点生成 SOCKS5。
3. 在 SOCKS5 池里测试节点。
4. 新增用户套餐，选择多个订阅 SOCKS 节点。
5. 打开用户订阅 URL，确认 Clash YAML 能返回 200。
6. 确认 Clash 节点名称等于订阅 SOCKS 节点名称。
7. 确认 YAML 中没有真实上游 IP 和上游凭据。
8. Clash Verge 导入订阅，测试每个节点连通性。
9. 删除套餐，确认对应入口端口和路由被清理。

## 执行顺序

1. 先保存当前未完成改动的状态，确认不误删。
2. 新建后端模块文件，先做无行为变化的代码搬迁。
3. 完成数据库迁移和 `package_bindings` 读写。
4. 完成套餐新增、编辑、删除的多上游绑定。
5. 完成路由生成和订阅输出名称调整。
6. 完成前端多选、全选、展示绑定节点。
7. 本地构建和接口检查。
8. 提交 Git。
9. 发布线上。
10. 线上真实连通性测试。

## 风险点

- 多节点套餐会生成多个入口端口，如果路由没有同步刷新，Clash 导入成功但节点会超时。
- 如果订阅输出误用了上游 host，会暴露真实 IP 或上游服务信息。
- 如果编辑套餐时重建所有 binding，用户侧节点端口会变化，可能影响已导入客户端。
- 如果本地 Windows 执行线上路径操作，容易出现 `[WinError 5] 拒绝访问` 或路径不存在，需要把这类操作限制到线上环境。
- 线上服务重启前必须先做语法检查，避免把管理面板重启挂掉。

## 完成标准

- 用户套餐支持多个订阅 SOCKS 节点。
- Clash/Shadowrocket 订阅输出多个节点，节点名称来自订阅 SOCKS 原始节点名称。
- 用户订阅不暴露真实上游 IP、账号、密码、token。
- Clash Verge 导入后节点可用，不再只是导入成功但测试超时。
- 新增、编辑、删除套餐不会误报 `/opt/3x-ui-chain` 权限错误。
- 后端核心逻辑从单个 `app.py` 拆分为清晰模块，后续排查和扩展更容易。
