# views/ —— 页面（路由级组件）

每个文件对应一条路由。视图负责编排：调 store、开关弹框、弹 toast；不写底层 fetch。

- `LoginView.vue` —— 登录页（stitch proxy3x_1）。玻璃卡，失败原因内联。
- `DashboardView.vue` —— 总览（stitch proxy3x_3）。4 张 StatCard + UsageChart + EventLog，10s 轮询。
- `PackagesView.vue` —— 用户套餐（stitch proxy3x_2）。表格 + 新增用户/额度巡检/刷新订阅 + 编辑/删除/绑定家宽。
- `UpstreamsView.vue` —— 家宽池（stitch proxy3x_4）。卡片网格 + 新增家宽 + 检测/编辑/删除。

## 约定

- 数据来自 `useDashboardStore`；操作调 store action（其内部 refresh）。
- 轮询用 `usePolling`（标签页隐藏时暂停），随组件卸载自动清理。
- 成功/失败统一用 `vue-sonner` 的 `toast`；表单类失败优先内联到弹框（`setError`）。
