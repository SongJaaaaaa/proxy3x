# router/ & lib/ & composables/

## router/
`index.ts` —— 路由表 + 全局登录守卫。
- `/login` 公开；其余需登录，未登录跳 `/login`。
- 注册 `client` 的 401 钩子：会话过期时任何请求都把用户弹回登录页。
- `createWebHistory`（后端 SPA fallback，深链接可用）。

## lib/
纯函数工具，无副作用、无业务状态。
- `utils.ts` —— `cn()` 合并 Tailwind class（shadcn 标准）。
- `format.ts` —— `gb()`/`percent()`/`usageTone()`/`fromUnix()`：用量与时间的展示格式化。

## composables/
- `usePolling.ts` —— 定时执行 + 标签页可见性感知（隐藏暂停、恢复即刷）；组件卸载自动清理。
  用于 Dashboard/Packages/Upstreams 的周期刷新。
