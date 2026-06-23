import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/api/endpoints'
import type {
  CreatePackageBody,
  CreateUpstreamBody,
  DashboardData,
  EventItem,
  Package,
  Summary,
  UpdatePackageBody,
  UpdateUpstreamBody,
  Upstream,
} from '@/types/dashboard'

/**
 * 单一数据源：/api/dashboard 的全量数据。
 * 设计：所有变更操作 = 调接口后 await refresh()，不做乐观更新。
 * 数据源廉价（一次请求拿全量），refetch 保证状态永远正确，最易维护。
 */
export const useDashboardStore = defineStore('dashboard', () => {
  const summary = ref<Summary | null>(null)
  const packages = ref<Package[]>([])
  const upstreams = ref<Upstream[]>([])
  const events = ref<EventItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  /** 在线/异常家宽计数（用于家宽页顶部统计） */
  const upstreamOnline = computed(() => upstreams.value.filter((u) => u.status === '可用').length)
  const upstreamError = computed(() => upstreams.value.filter((u) => u.status === '不可用').length)

  async function refresh() {
    loading.value = true
    error.value = null
    try {
      const res = await api.dashboard()
      const data = res.data as DashboardData
      summary.value = data.summary
      packages.value = data.packages
      upstreams.value = data.upstreams
      events.value = data.events
    } catch (e) {
      error.value = (e as Error).message
      throw e
    } finally {
      loading.value = false
    }
  }

  // —— 变更操作：调接口 → refresh ——
  async function enforce() {
    const r = await api.enforce()
    await refresh()
    return r.message ?? '额度巡检完成'
  }
  async function regenerate() {
    const r = await api.regenerate()
    await refresh()
    return r.message ?? '订阅和路由已刷新'
  }
  async function createPackage(body: CreatePackageBody) {
    const r = await api.createPackage(body)
    await refresh()
    return r.message ?? '已创建用户'
  }
  async function updatePackage(id: number, body: UpdatePackageBody) {
    const r = await api.updatePackage(id, body)
    await refresh()
    return r.message ?? '已保存'
  }
  async function deletePackage(id: number) {
    const r = await api.deletePackage(id)
    await refresh()
    return r.message ?? '已删除套餐'
  }
  async function createUpstream(body: CreateUpstreamBody) {
    const r = await api.createUpstream(body)
    await refresh()
    return r.message ?? '家宽已加入池子'
  }
  async function updateUpstream(id: number, body: UpdateUpstreamBody) {
    const r = await api.updateUpstream(id, body)
    await refresh()
    return r.message ?? '已保存家宽'
  }
  async function checkUpstream(id: number) {
    const r = await api.checkUpstream(id)
    await refresh()
    return r
  }
  async function deleteUpstream(id: number) {
    const r = await api.deleteUpstream(id)
    await refresh()
    return r.message ?? '已删除家宽'
  }
  // 只读：拉取家宽明文信息（不改单一数据源，无需 refresh）
  async function revealUpstream(id: number) {
    const r = await api.revealUpstream(id)
    return r.data
  }

  return {
    summary,
    packages,
    upstreams,
    events,
    loading,
    error,
    upstreamOnline,
    upstreamError,
    refresh,
    enforce,
    regenerate,
    createPackage,
    updatePackage,
    deletePackage,
    createUpstream,
    updateUpstream,
    checkUpstream,
    deleteUpstream,
    revealUpstream,
  }
})
