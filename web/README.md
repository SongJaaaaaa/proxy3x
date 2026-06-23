# proxy3x 管理面板前端（web）

proxy3x 链式代理管理面板的**独立前端工程**。前后端分离：本工程只通过 `/api/*`
与 Python 后端（`../server/app.py`，端口 32180）通信，不直接访问数据库。

技术栈：**Vue 3 + TypeScript + Vite + Tailwind + shadcn 风格自研组件**。
视觉风格沿用 stitch 生成的「Cyber-Proxy Management」暗色科技风（玻璃面板 + 霓虹描边 + 蓝绿紫强调色）。

## 开发 / 构建

```bash
# 安装依赖（Node 22）
npm install

# 本地开发：默认代理 /api 到 127.0.0.1:32180
npm run dev
# 对着线上后端调试：
VITE_API_TARGET=https://proxy3x.sjiaa.cc.cd npm run dev

# 类型检查 + 构建（产物到 dist/）
npm run build
```

## 部署

构建产物 `dist/` 覆盖服务器 `/opt/3x-ui-manager/frontend/`（`index.html` + `assets/*`）。
后端 `serve_static` 已做 SPA fallback，深链接可用。

> ⚠️ 部署只覆盖前端静态文件，**绝不覆盖** `data/manager.db` 与 `x-ui.db`。

## 目录与分层

严格单向依赖：`views → stores → api/endpoints → api/client`。
UI 原语（`components/ui`）与业务组件（`components/domain`）分离。

```
src/
├── main.ts / App.vue / style.css   # 启动、根组件（含全局 toast）、主题样式
├── router/        路由表 + 登录守卫
├── lib/           纯工具：cn()、GB/百分比/日期格式化
├── api/           唯一后端出口：client(fetch封装) + endpoints(契约) + errors
├── types/         后端 payload 的 TS 镜像（契约变更先改这里）
├── stores/        Pinia：auth（登录态）、dashboard（单一数据源）
├── composables/   usePolling（可见性感知轮询）
├── components/
│   ├── ui/        通用原语：Icon/Button/Badge/ProgressBar/Modal/Field
│   ├── layout/    AppShell（框架）/ NavSidebar（侧边栏）
│   └── domain/    业务组件 + dialogs/（新增编辑/确认弹框）
└── views/         5 个页面：Login/Dashboard/Packages/Upstreams
```

各文件夹下有独立 `README.md` 说明职责与设计约定。

## 关键设计约定

- **单一数据源**：`stores/dashboard.ts` 持有 `/api/dashboard` 全量数据。所有变更
  操作 = 调接口后 `await refresh()`，不做乐观更新 —— 数据源廉价，refetch 保证正确。
- **唯一后端出口**：业务代码不直接 `fetch`，统一走 `api/endpoints.ts`。契约变更
  只动 `endpoints.ts` + `types/`。
- **遮罩账号只读**：后端已返回遮罩后的账号/密码，前端纯展示，**不解码、不加显示按钮**。
- **家宽用量进度**：分母是后端 `quota_gb`（家宽额度）。`quota_gb=0` 表示未设额度，
  `usage_percent` 为 null，进度条不绘制。这修复了旧版「家宽进度不准」（旧版无额度字段）。
```
