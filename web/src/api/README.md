# api/ —— 后端通信层（唯一出口）

业务代码**不直接 fetch**，一律通过这一层。后端契约只在这里落地。

- `client.ts` —— `http.get/post/put/del` 封装：
  - 路径前缀 `/api`，`credentials:'include'` 携带 HttpOnly 会话 cookie。
  - 解析 `{ok, message, data}` 信封；`ok===false` 或非 2xx 抛 `ApiError`。
  - HTTP 401 触发 `onUnauthorized`（router 注册 → 跳登录页）。
- `endpoints.ts` —— 每个函数对应 `server/app.py` 的一条路由。**唯一写 URL/method 的地方**。
- `errors.ts` —— `ApiError`（带 `status`，用于 401 判断）。

## 设计约定

契约变更时只需改 `endpoints.ts` 与 `types/`，不影响 stores/views。
新增接口：在 `endpoints.ts` 加函数 + 在 `types/` 加类型，store 调用即可。
