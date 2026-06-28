<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { useSocksFactoryStore } from '@/stores/socksFactory'
import { usePolling } from '@/composables/usePolling'
import { fromUnix, gb, latency, speed } from '@/lib/format'
import { ApiError } from '@/api/errors'
import type { SocksEndpoint } from '@/types/dashboard'
import AppShell from '@/components/layout/AppShell.vue'
import Button from '@/components/ui/Button.vue'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import ProgressBar from '@/components/ui/ProgressBar.vue'
import SocksEndpointFormDialog from '@/components/domain/dialogs/SocksEndpointFormDialog.vue'

const route = useRoute()
const router = useRouter()
const store = useSocksFactoryStore()
const sourceId = computed(() => Number(route.params.id || 0))

const keyword = ref('')
const status = ref<'all' | 'on' | 'off'>('all')
const busy = ref('')
const speedAll = ref(false)
const speedProgress = ref({ done: 0, total: 0 })
const editOpen = ref(false)
const editing = ref<SocksEndpoint | null>(null)
const editRef = ref<InstanceType<typeof SocksEndpointFormDialog> | null>(null)

async function load() {
  if (!sourceId.value) return
  try {
    await store.loadSource(sourceId.value)
  } catch {
    router.push('/socks-sources')
  }
}

onMounted(load)
usePolling(load, 12000)
watch(sourceId, load)

const source = computed(() => store.current)
const endpoints = computed(() => {
  const s = source.value
  const k = keyword.value.trim().toLowerCase()
  if (!s) return []
  return s.endpoints.filter((e) => {
    const okStatus =
      status.value === 'all' ||
      (status.value === 'on' && e.enabled && !e.expired) ||
      (status.value === 'off' && (!e.enabled || e.expired))
    const text = `${e.remark} ${e.node_name} ${e.protocol} ${e.server} ${e.listen_port}`.toLowerCase()
    return okStatus && (!k || text.includes(k))
  })
})

const protocolStats = computed(() => {
  const map = new Map<string, number>()
  for (const e of source.value?.endpoints || []) {
    const k = e.protocol || 'unknown'
    map.set(k, (map.get(k) || 0) + 1)
  }
  return [...map.entries()].map(([name, count]) => ({ name, count }))
})

const usageBars = computed(() =>
  (source.value?.endpoints || [])
    .slice()
    .sort((a, b) => b.used_bytes - a.used_bytes)
    .slice(0, 8),
)

async function refreshSource() {
  if (!source.value) return
  busy.value = 'refresh'
  try {
    const r = await store.refreshSource(source.value.id)
    toast.success(r.message || '刷新完成')
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '刷新失败')
  } finally {
    busy.value = ''
  }
}

async function generateSource() {
  if (!source.value) return
  busy.value = 'generate'
  try {
    const r = await store.generateSource(source.value.id)
    toast.success(r.message || '生成完成')
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '生成失败')
  } finally {
    busy.value = ''
  }
}

async function syncUsage() {
  if (!source.value) return
  busy.value = 'sync'
  try {
    const r = await store.syncUsage(source.value.id)
    toast.success(r.message || '同步完成')
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '同步失败')
  } finally {
    busy.value = ''
  }
}

async function copyAll() {
  if (!source.value) return
  try {
    const text = await store.copySource(source.value.id)
    await navigator.clipboard.writeText(text)
    toast.success(`已复制 ${text ? text.split('\n').length : 0} 条 SOCKS5`)
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '复制失败')
  }
}

async function copyOne(item: SocksEndpoint) {
  try {
    const data = await store.revealEndpoint(item.id)
    await navigator.clipboard.writeText(data.uri)
    toast.success('已复制 SOCKS5')
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '复制失败')
  }
}

async function toggleOne(item: SocksEndpoint) {
  if (!source.value) return
  busy.value = `ep-${item.id}`
  try {
    const enabled = !item.enabled
    const r = await store.toggleEndpoint(item.id, enabled, source.value.id)
    toast.success(r.message || '已保存')
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '操作失败')
  } finally {
    busy.value = ''
  }
}

async function speedTestOne(item: SocksEndpoint) {
  if (!source.value) return
  busy.value = `speed-${item.id}`
  try {
    const r = await store.speedTestEndpoint(item.id, source.value.id)
    r.ok ? toast.success(r.message || '测速完成') : toast.error(r.message || '测速失败')
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '测速失败')
  } finally {
    busy.value = ''
  }
}

async function speedTestAll() {
  if (!source.value || speedAll.value) return
  const list = endpoints.value.filter((e) => e.enabled && !e.expired)
  if (!list.length) return
  speedAll.value = true
  speedProgress.value = { done: 0, total: list.length }
  let ok = 0
  let fail = 0
  const concurrency = 3
  let cursor = 0
  async function worker() {
    while (cursor < list.length) {
      const item = list[cursor++]
      try {
        const r = await store.speedTestEndpoint(item.id, source.value!.id)
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
    speedAll.value = false
  }
}

function openEdit(item: SocksEndpoint) {
  editing.value = item
  editOpen.value = true
}

async function submitEndpoint(payload: { quota_gb: number; expires_at: string; remark: string }) {
  if (!editing.value || !source.value) return
  busy.value = 'edit'
  try {
    const r = await store.updateEndpoint(editing.value.id, payload, source.value.id)
    toast.success(r.message || '已保存')
    editOpen.value = false
  } catch (e) {
    editRef.value?.setError(e instanceof ApiError ? e.message : '保存失败')
  } finally {
    busy.value = ''
  }
}
</script>

<template>
  <AppShell :title="source?.name || '订阅详情'" subtitle="这个订阅链接生成出的全部 SOCKS5">
    <template #actions>
      <Button variant="subtle" @click="router.push('/socks-sources')">
        <Icon name="arrow_back" :size="18" />返回
      </Button>
      <Button variant="ghost" :loading="busy === 'refresh'" @click="refreshSource">
        <Icon name="refresh" :size="18" />刷新订阅
      </Button>
      <Button variant="ghost" :loading="busy === 'generate'" @click="generateSource">
        <Icon name="auto_awesome_motion" :size="18" />生成 SOCKS5
      </Button>
      <Button variant="ghost" :loading="busy === 'sync'" @click="syncUsage">
        <Icon name="data_usage" :size="18" />同步统计
      </Button>
      <Button variant="ghost" :loading="speedAll" :disabled="!endpoints.length || Boolean(busy)" @click="speedTestAll">
        <Icon name="speed" :size="18" />
        {{ speedAll ? `测速中 ${speedProgress.done}/${speedProgress.total}` : '一键测速' }}
      </Button>
      <Button variant="primary" @click="copyAll">
        <Icon name="content_copy" :size="18" />复制全部
      </Button>
    </template>

    <template v-if="source">
      <section class="grid grid-cols-2 xl:grid-cols-4 gap-panel-gap">
        <div class="glass-panel rounded-lg p-4">
          <p class="text-sm text-on-surface-variant">解析节点</p>
          <p class="mt-2 text-2xl font-semibold text-on-surface">{{ source.node_count }}</p>
        </div>
        <div class="glass-panel rounded-lg p-4">
          <p class="text-sm text-on-surface-variant">SOCKS5 入口</p>
          <p class="mt-2 text-2xl font-semibold text-on-surface">{{ source.endpoint_count }}</p>
        </div>
        <div class="glass-panel rounded-lg p-4">
          <p class="text-sm text-on-surface-variant">已用流量</p>
          <p class="mt-2 text-2xl font-semibold text-on-surface">{{ gb(source.used_gb, 2) }}</p>
        </div>
        <div class="glass-panel rounded-lg p-4">
          <p class="text-sm text-on-surface-variant">单源额度</p>
          <p class="mt-2 text-2xl font-semibold text-secondary-fixed">{{ gb(source.total_gb, 0) }}</p>
        </div>
      </section>

      <section class="grid grid-cols-1 xl:grid-cols-[0.8fr_1.2fr] gap-panel-gap">
        <div class="glass-panel rounded-lg p-4 flex flex-col gap-4">
          <div>
            <h3 class="font-title-sm text-title-sm text-on-surface">协议分布</h3>
            <p class="mt-1 text-sm text-on-surface-variant">订阅节点按协议统计</p>
          </div>
          <div class="flex flex-col gap-3">
            <div v-for="item in protocolStats" :key="item.name" class="flex items-center gap-3">
              <span class="w-20 text-sm text-on-surface-variant uppercase">{{ item.name }}</span>
              <div class="flex-1 h-2 rounded-full bg-surface-container-high overflow-hidden">
                <div
                  class="h-full rounded-full bg-gradient-to-r from-primary-container to-secondary-fixed"
                  :style="{ width: Math.max(8, (item.count / Math.max(1, source.endpoint_count)) * 100) + '%' }"
                ></div>
              </div>
              <span class="w-10 text-right text-sm text-on-surface">{{ item.count }}</span>
            </div>
          </div>
          <div class="rounded-lg border border-outline-variant/30 bg-surface-container-lowest/50 p-3 text-xs text-outline">
            sing-box 配置文件：/opt/3x-ui-chain/socks-factory/sing-box.json
          </div>
        </div>

        <div class="glass-panel rounded-lg p-4 flex flex-col gap-4">
          <div>
            <h3 class="font-title-sm text-title-sm text-on-surface">用量排行</h3>
            <p class="mt-1 text-sm text-on-surface-variant">基础统计字段，接入 sing-box 统计后会自动反映真实用量</p>
          </div>
          <div class="grid grid-cols-4 md:grid-cols-8 gap-3 h-44 items-end">
            <div v-for="item in usageBars" :key="item.id" class="flex flex-col items-center gap-2 min-w-0">
              <div
                class="w-full rounded-t bg-gradient-to-t from-primary-container to-secondary-fixed"
                :style="{ height: Math.max(8, Math.min(150, item.usage_percent || 0)) + 'px' }"
              ></div>
              <span class="w-full truncate text-center text-[11px] text-outline">{{ item.listen_port }}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="glass-panel rounded-lg p-4 flex flex-col gap-4">
        <div class="flex items-center gap-3 flex-wrap">
          <div class="relative w-80 max-w-full">
            <Icon name="search" :size="18" class="absolute left-3 top-1/2 -translate-y-1/2 text-outline" />
            <input v-model="keyword" class="control pl-9" placeholder="搜索节点名 / 端口 / 协议 / 服务器" />
          </div>
          <div class="flex items-center gap-1 glass-panel rounded-lg p-1">
            <button
              v-for="opt in [
                { v: 'all', t: '全部' },
                { v: 'on', t: '可用' },
                { v: 'off', t: '停用' },
              ]"
              :key="opt.v"
              class="px-3 h-8 rounded text-sm font-label-sm transition-colors"
              :class="status === opt.v ? 'bg-primary-container/30 text-secondary-fixed-dim' : 'text-on-surface-variant hover:text-on-surface'"
              @click="status = opt.v as typeof status"
            >
              {{ opt.t }}
            </button>
          </div>
          <span class="ml-auto text-sm text-outline">显示 {{ endpoints.length }} / {{ source.endpoints.length }}</span>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full min-w-[1160px] text-sm">
            <thead class="text-left text-outline border-b border-outline-variant/30">
              <tr>
                <th class="py-3 px-3">节点</th>
                <th class="py-3 px-3 w-24">协议</th>
                <th class="py-3 px-3 w-28">端口</th>
                <th class="py-3 px-3 w-36">账号</th>
                <th class="py-3 px-3 w-40">延迟 / 速度</th>
                <th class="py-3 px-3 w-56">流量</th>
                <th class="py-3 px-3 w-44">到期</th>
                <th class="py-3 px-3 w-28">状态</th>
                <th class="py-3 px-3 w-44 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in endpoints" :key="item.id" class="border-b border-outline-variant/15 hover:bg-surface-container-lowest/50">
                <td class="py-3 px-3">
                  <p class="font-label-sm text-on-surface truncate max-w-[320px]">{{ item.remark || item.node_name }}</p>
                  <p class="font-code-xs text-[11px] text-outline truncate max-w-[320px]">{{ item.server }}:{{ item.node_port }}</p>
                </td>
                <td class="py-3 px-3">
                  <Badge tone="purple">{{ item.protocol }}</Badge>
                </td>
                <td class="py-3 px-3 font-code-xs text-on-surface">{{ item.listen_port }}</td>
                <td class="py-3 px-3 font-code-xs text-outline">{{ item.username }}</td>
                <td class="py-3 px-3">
                  <div class="flex items-center gap-1.5 text-on-surface-variant">
                    <Icon name="speed" :size="16" class="text-outline" />
                    <span class="font-code-xs text-code-xs">{{ latency(item.latency_ms) }} / {{ speed(item.speed_bps) }}</span>
                  </div>
                </td>
                <td class="py-3 px-3">
                  <div class="flex justify-between text-xs text-on-surface-variant mb-1">
                    <span>{{ gb(item.used_gb, 2) }}</span>
                    <span>{{ item.quota_gb ? gb(item.quota_gb, 0) : '不限' }}</span>
                  </div>
                  <ProgressBar :percent="item.usage_percent" :muted="!item.enabled || item.expired" />
                </td>
                <td class="py-3 px-3 text-on-surface-variant">{{ fromUnix(item.expires_at) }}</td>
                <td class="py-3 px-3">
                  <Badge :tone="item.enabled && !item.expired ? 'green' : 'gray'" dot>
                    {{ item.expired ? '到期' : item.enabled ? '启用' : '停用' }}
                  </Badge>
                </td>
                <td class="py-3 px-3">
                  <div class="flex items-center justify-end gap-1">
                    <button class="p-2 rounded hover:bg-surface-variant/30 text-on-surface-variant" title="复制" @click="copyOne(item)">
                      <Icon name="content_copy" :size="18" />
                    </button>
                    <button class="p-2 rounded hover:bg-surface-variant/30 text-on-surface-variant" title="设置" @click="openEdit(item)">
                      <Icon name="tune" :size="18" />
                    </button>
                    <button class="p-2 rounded hover:bg-surface-variant/30 text-on-surface-variant" title="测速" @click="speedTestOne(item)">
                      <Icon
                        :name="busy === `speed-${item.id}` || speedAll ? 'progress_activity' : 'speed'"
                        :size="18"
                        :class="busy === `speed-${item.id}` || speedAll ? 'animate-spin' : ''"
                      />
                    </button>
                    <button class="p-2 rounded hover:bg-surface-variant/30 text-on-surface-variant" title="启用/停用" @click="toggleOne(item)">
                      <Icon
                        :name="busy === `ep-${item.id}` ? 'progress_activity' : item.enabled ? 'pause_circle' : 'play_circle'"
                        :size="18"
                        :class="busy === `ep-${item.id}` ? 'animate-spin' : ''"
                      />
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="!endpoints.length" class="py-16 flex flex-col items-center gap-3 text-outline">
          <Icon name="lan" :size="42" />
          <p class="text-sm">还没有 SOCKS5，点击右上角生成。</p>
        </div>
      </section>
    </template>

    <div v-else class="glass-panel rounded-lg py-16 flex flex-col items-center gap-3 text-outline">
      <Icon name="progress_activity" :size="42" class="animate-spin" />
      <p class="text-sm">正在加载订阅详情…</p>
    </div>

    <SocksEndpointFormDialog
      ref="editRef"
      :open="editOpen"
      :item="editing"
      :busy="busy === 'edit'"
      @close="editOpen = false"
      @submit="submitEndpoint"
    />
  </AppShell>
</template>
