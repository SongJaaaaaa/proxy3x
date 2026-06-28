<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { useDashboardStore } from '@/stores/dashboard'
import { usePolling } from '@/composables/usePolling'
import type { Upstream } from '@/types/dashboard'
import { ApiError } from '@/api/errors'
import { stateLegend, stateText, stateTip, stateTone } from '@/lib/nodeStatus'
import AppShell from '@/components/layout/AppShell.vue'
import Button from '@/components/ui/Button.vue'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import Pagination from '@/components/ui/Pagination.vue'
import UpstreamCard from '@/components/domain/UpstreamCard.vue'
import UpstreamFormDialog from '@/components/domain/dialogs/UpstreamFormDialog.vue'
import UpstreamDetailDialog from '@/components/domain/dialogs/UpstreamDetailDialog.vue'
import ConfirmDialog from '@/components/domain/dialogs/ConfirmDialog.vue'

/**
 * SOCKS5 上游页（对应 stitch proxy3x_4）。卡片网格 + 顶部在线/异常统计 + 新增 SOCKS5。
 * 检测/编辑/删除走 store（调接口后 refresh）。
 */
const store = useDashboardStore()
usePolling(() => store.refresh(), 15000)

// 搜索：按备注 / 名称(IP) / 分配对象 过滤
const keyword = ref('')
const statusFilter = ref<'valid' | 'invalid' | 'all'>('valid')
const filteredUpstreams = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  return store.upstreams.filter((u) => {
    const matchStatus =
      statusFilter.value === 'all' ||
      (statusFilter.value === 'valid' && !u.expired && u.status !== '不可用') ||
      (statusFilter.value === 'invalid' && (u.expired || u.status === '不可用'))
    const matchKeyword =
      !k ||
      (u.remark || '').toLowerCase().includes(k) ||
      (u.host || '').toLowerCase().includes(k) ||
      (u.assigned_to || '').toLowerCase().includes(k)
    return matchStatus && matchKeyword
  })
})

// 分页：默认每页 8 个，可调（基于过滤后结果）
const page = ref(1)
const pageSize = ref(8)
const pagedUpstreams = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredUpstreams.value.slice(start, start + pageSize.value)
})
watch([keyword, statusFilter], () => {
  page.value = 1
})
watch([() => filteredUpstreams.value.length, pageSize], () => {
  const tp = Math.max(1, Math.ceil(filteredUpstreams.value.length / pageSize.value))
  if (page.value > tp) page.value = tp
})

const formOpen = ref(false)
const editing = ref<Upstream | null>(null)
const formRef = ref<InstanceType<typeof UpstreamFormDialog> | null>(null)
const submitting = ref(false)
const checkingId = ref<number | null>(null)
const speedTestingId = ref<number | null>(null)
const speedTestingAll = ref(false)
const speedProgress = ref({ done: 0, total: 0 })

const confirmOpen = ref(false)
const removing = ref<Upstream | null>(null)
const removingBusy = ref(false)

// 查看详情
const detailOpen = ref(false)
const viewing = ref<Upstream | null>(null)
function openView(u: Upstream) {
  viewing.value = u
  detailOpen.value = true
}

// 一键检测（当前筛选结果，限制并发）
const checkingAll = ref(false)
const checkProgress = ref({ done: 0, total: 0 })
async function onCheckAll() {
  const list = filteredUpstreams.value.slice()
  if (!list.length || checkingAll.value) return
  checkingAll.value = true
  checkProgress.value = { done: 0, total: list.length }
  let ok = 0
  let fail = 0
  const concurrency = 4
  let cursor = 0
  async function worker() {
    while (cursor < list.length) {
      const u = list[cursor++]
      try {
        const r = await store.checkUpstream(u.id)
        r.ok ? ok++ : fail++
      } catch {
        fail++
      } finally {
        checkProgress.value.done++
      }
    }
  }
  try {
    await Promise.all(Array.from({ length: Math.min(concurrency, list.length) }, () => worker()))
    toast.success(`检测完成：可用 ${ok}，失败 ${fail}`)
  } finally {
    checkingAll.value = false
  }
}

function openCreate() {
  editing.value = null
  formOpen.value = true
}
function openEdit(u: Upstream) {
  editing.value = u
  formOpen.value = true
}

async function onSubmit(payload: { line: string; remark: string; quota_gb: number; expires_at: string }) {
  submitting.value = true
  try {
    if (editing.value) {
      await store.updateUpstream(editing.value.id, {
        remark: payload.remark,
        quota_gb: payload.quota_gb,
        expires_at: payload.expires_at,
      })
      toast.success('已保存 SOCKS5')
    } else {
      await store.createUpstream({
        line: payload.line,
        remark: payload.remark,
        quota_gb: payload.quota_gb,
        expires_at: payload.expires_at,
      })
      toast.success('SOCKS5 已保存')
    }
    formOpen.value = false
  } catch (e) {
    formRef.value?.setError(e instanceof ApiError ? e.message : '操作失败')
  } finally {
    submitting.value = false
  }
}

async function onCheck(u: Upstream) {
  checkingId.value = u.id
  try {
    const r = await store.checkUpstream(u.id)
    r.ok ? toast.success(r.message || '检测完成') : toast.error(r.message || '检测失败')
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '检测失败')
  } finally {
    checkingId.value = null
  }
}

async function onSpeedTest(u: Upstream) {
  speedTestingId.value = u.id
  try {
    const r = await store.speedTestUpstream(u.id)
    r.ok ? toast.success(r.message || '测速完成') : toast.error(r.message || '测速失败')
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '测速失败')
  } finally {
    speedTestingId.value = null
  }
}

async function onSpeedTestAll() {
  const list = filteredUpstreams.value.filter((u) => !u.expired)
  if (!list.length || speedTestingAll.value) return
  speedTestingAll.value = true
  speedProgress.value = { done: 0, total: list.length }
  let ok = 0
  let fail = 0
  const concurrency = 3
  let cursor = 0
  async function worker() {
    while (cursor < list.length) {
      const u = list[cursor++]
      try {
        const r = await store.speedTestUpstream(u.id)
        r.ok ? ok++ : fail++
      } catch {
        fail++
      } finally {
        speedProgress.value.done++
      }
    }
  }
  try {
    await Promise.all(Array.from({ length: Math.min(concurrency, list.length) }, () => worker()))
    toast.success(`测速完成：可用 ${ok}，失败 ${fail}`)
  } finally {
    speedTestingAll.value = false
  }
}

function askRemove(u: Upstream) {
  removing.value = u
  confirmOpen.value = true
}
async function onRemove() {
  if (!removing.value) return
  removingBusy.value = true
  try {
    await store.deleteUpstream(removing.value.id)
    toast.success('已删除 SOCKS5')
    confirmOpen.value = false
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '删除失败')
  } finally {
    removingBusy.value = false
  }
}
</script>

<template>
  <AppShell title="SOCKS5 链式" subtitle="管理唯一出口上游，用户套餐入口会固定转发到这里。">
    <template #actions>
      <Button
        variant="ghost"
        :loading="checkingAll"
        :disabled="!filteredUpstreams.length || speedTestingAll"
        @click="onCheckAll"
      >
        <Icon name="network_ping" :size="18" />
        {{ checkingAll ? `检测中 ${checkProgress.done}/${checkProgress.total}` : '一键检测' }}
      </Button>
      <Button
        variant="ghost"
        :loading="speedTestingAll"
        :disabled="!filteredUpstreams.length || checkingAll"
        @click="onSpeedTestAll"
      >
        <Icon name="speed" :size="18" />
        {{ speedTestingAll ? `测速中 ${speedProgress.done}/${speedProgress.total}` : '一键测速' }}
      </Button>
      <Button variant="primary" @click="openCreate">
        <Icon name="add" :size="18" />新增 SOCKS5
      </Button>
    </template>

    <!-- 统计 -->
    <div class="flex gap-4">
      <div class="glass-panel px-4 py-2 rounded-lg flex items-center gap-3">
        <div class="w-2 h-2 rounded-full bg-secondary-fixed shadow-[0_0_8px_rgba(36,255,205,0.8)]"></div>
        <span class="font-label-sm text-label-sm text-on-surface-variant">
          在线: <strong class="text-on-surface">{{ store.upstreamOnline }}</strong>
        </span>
      </div>
      <div class="glass-panel px-4 py-2 rounded-lg flex items-center gap-3">
        <div class="w-2 h-2 rounded-full bg-error shadow-[0_0_8px_rgba(255,180,171,0.8)]"></div>
        <span class="font-label-sm text-label-sm text-on-surface-variant">
          异常: <strong class="text-on-surface">{{ store.upstreamError }}</strong>
        </span>
      </div>
    </div>

    <!-- 搜索 -->
    <div v-if="store.upstreams.length" class="flex items-center gap-3 flex-wrap shrink-0">
      <div class="relative w-72 max-w-full">
        <Icon name="search" :size="18" class="absolute left-3 top-1/2 -translate-y-1/2 text-outline" />
        <input v-model="keyword" class="control pl-9" placeholder="搜索备注 / IP / 分配对象…" />
      </div>
      <div class="flex items-center gap-1 glass-panel rounded-lg p-1">
        <button
          v-for="opt in [
            { v: 'valid', t: '有效' },
            { v: 'invalid', t: '无效' },
            { v: 'all', t: '全部' },
          ]"
          :key="opt.v"
          class="px-3 h-8 rounded text-sm font-label-sm transition-colors"
          :class="
            statusFilter === opt.v
              ? 'bg-primary-container/30 text-secondary-fixed-dim'
              : 'text-on-surface-variant hover:text-on-surface'
          "
          @click="statusFilter = opt.v as typeof statusFilter"
        >
          {{ opt.t }}
        </button>
      </div>
      <span class="ml-auto font-label-sm text-label-sm text-outline">
        共 {{ filteredUpstreams.length }} / {{ store.upstreams.length }} 个
      </span>
    </div>
    <div class="flex items-center gap-2 text-xs text-outline flex-wrap">
      <span>状态说明</span>
      <Badge
        v-for="item in stateLegend"
        :key="item.state"
        :tone="stateTone(item.state)"
        dot
        :title="stateTip(item.state)"
      >
        {{ stateText(item.state) }}
      </Badge>
    </div>

    <!-- 卡片网格 -->
    <template v-if="filteredUpstreams.length">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-panel-gap">
        <UpstreamCard
          v-for="u in pagedUpstreams"
          :key="u.id"
          :item="u"
          :busy="checkingId === u.id || speedTestingId === u.id || checkingAll || speedTestingAll"
          @check="onCheck(u)"
          @speed-test="onSpeedTest(u)"
          @edit="openEdit(u)"
          @remove="askRemove(u)"
          @view="openView(u)"
        />
      </div>

      <!-- 分页 -->
      <Pagination
        v-model:page="page"
        v-model:page-size="pageSize"
        :total="filteredUpstreams.length"
        :page-size-options="[8, 16, 32, 64]"
      />
    </template>
    <!-- 搜索无结果 -->
    <div
      v-else-if="store.upstreams.length"
      class="glass-panel rounded-xl py-16 flex flex-col items-center gap-3 text-outline"
    >
      <Icon name="search_off" :size="40" />
      <p class="font-body-md text-sm">{{ keyword ? `没有匹配「${keyword}」的 SOCKS5。` : '当前筛选下没有 SOCKS5。' }}</p>
    </div>
    <!-- 空池 -->
    <div v-else class="glass-panel rounded-xl py-16 flex flex-col items-center gap-3 text-outline">
      <Icon name="lan" :size="40" />
      <p class="font-body-md text-sm">还没有 SOCKS5 上游，点击右上角「新增 SOCKS5」添加节点。</p>
    </div>

    <UpstreamFormDialog
      ref="formRef"
      :open="formOpen"
      :editing="editing"
      :busy="submitting"
      @close="formOpen = false"
      @submit="onSubmit"
    />
    <UpstreamDetailDialog :open="detailOpen" :item="viewing" @close="detailOpen = false" />
    <ConfirmDialog
      :open="confirmOpen"
      title="删除 SOCKS5"
      :message="`确定删除 SOCKS5「${removing?.remark || removing?.host}」？绑定它的套餐将解绑并刷新路由。`"
      :busy="removingBusy"
      @close="confirmOpen = false"
      @confirm="onRemove"
    />
  </AppShell>
</template>
