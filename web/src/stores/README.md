# stores/ —— Pinia 状态

- `auth.ts` —— 登录态与用户名。会话靠 HttpOnly cookie，store 只缓存 `isAuthenticated`/`username`；
  `fetchMe()` 启动时校验，`login()`/`logout()` 维护状态。
- `dashboard.ts` —— **单一数据源**。持有 `/api/dashboard` 全量（summary/packages/upstreams/events）
  及 `loading`/`error`。

## 核心约定：变更后 refetch

所有写操作（创建/编辑/删除/巡检/检测）= 调 `api` → `await refresh()`，**不做乐观更新**。
数据源一次请求拿全量、成本低，refetch 让状态永远与后端一致，省去缓存失效逻辑，最易维护。

派生：`upstreamOnline`/`upstreamError`（家宽在线/异常计数，供家宽页统计）。
