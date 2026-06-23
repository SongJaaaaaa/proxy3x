# types/ —— 后端 payload 的 TS 镜像

后端（`server/app.py`）返回结构的客户端类型定义。**这是客户端侧的契约真相**——
后端字段变化时，先改这里。

- `api.ts` —— `Envelope<T>`：统一响应信封 `{ok, message?, data?}`。
- `dashboard.ts` —— `Summary` / `Package` / `Upstream` / `EventItem` / `DashboardData`
  及各创建/编辑入参。字段与 `dashboard_data()` / `upstream_public()` / `package_usage()` 对应。
- `auth.ts` —— 登录入参与 `/api/me` 返回。

## 注意

- `Upstream.quota_gb`（额度）、`quota_bytes`、`usage_percent` 是本次为修复家宽进度新增，
  对应后端 `app.py` 的 `upstream_public` / `dashboard_data` 改动。
- `username`/`password` 是**已遮罩**字符串，前端不应期望拿到明文。
