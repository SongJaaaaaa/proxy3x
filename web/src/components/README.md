# components/ —— 组件分层

- `ui/` —— 通用原语，无业务逻辑，可在任意页面复用：
  `Icon`（Material Symbols）、`Button`、`Badge`、`ProgressBar`、`Modal`（玻璃弹框外壳）、`Field`（表单字段）。
- `layout/` —— 页面框架：`AppShell`（侧边栏 + 顶部条 + 内容插槽）、`NavSidebar`（导航 + 退出）。
- `domain/` —— 与 proxy3x 业务耦合的组件：
  - `StatCard` 总览汇总卡、`UsageChart` 套餐用量柱状图、`EventLog` 操作日志
  - `PackageTable` 用户套餐密集表格（首列/操作列固定）
  - `UpstreamCard` 家宽卡片（**保留卡片样式**，含额度进度条）
  - `dialogs/` —— `PackageFormDialog` / `UpstreamFormDialog`（新增+编辑复用）/ `ConfirmDialog`

## 约定

- `ui/` 与 `domain/` 不互混；`ui/` 不 import store 或 api。
- 业务组件不直接调 api：通过 emit 事件，由 `views/` 调 store。
- 视觉对齐 stitch 参考图（`../../../stitch_proxy3x_admin_dashboard/`），token 在 `tailwind.config.ts`。
