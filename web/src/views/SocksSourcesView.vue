<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { useSocksFactoryStore } from '@/stores/socksFactory'
import { usePolling } from '@/composables/usePolling'
import { fromUnix, gb } from '@/lib/format'
import { ApiError } from '@/api/errors'
import type { SocksSource } from '@/types/dashboard'
import AppShell from '@/components/layout/AppShell.vue'
import Button from '@/components/ui/Button.vue'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import ProgressBar from '@/components/ui/ProgressBar.vue'
import SocksSourceFormDialog from '@/components/domain/dialogs/SocksSourceFormDialog.vue'
import ConfirmDialog from '@/components/domain/dialogs/ConfirmDialog.vue'

const store = useSocksFactoryStore()
const router = useRouter()
usePolling(() => store.refreshList(), 12000)

const formOpen = ref(false)
const formRef = ref<InstanceType<typeof SocksSourceFormDialog> | null>(null)
const editing = ref<SocksSource | null>(null)
const submitting = ref(false)
const busyId = ref<number | null>(null)
const confirmOpen = ref(false)
const removing = ref<SocksSource | null>(null)

const keyword = ref('')
const sources = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return store.sources
  return store.sources.filter((s) => `${s.name} ${s.url}`.toLowerCase().includes(k))
})

const topSources = computed(() => sources.value.slice(0, 3))

function openCreate() {
  editing.value = null
  formOpen.value = true
}

function openEdit(item: SocksSource) {
  editing.value = item
  formOpen.value = true
}

async function submit(payload: { name: string; url: string; expires_at: string }) {
  submitting.value = true
  try {
    const r = editing.value ? await store.updateSource(editing.value.id, payload) : await store.createSource(payload)
    toast.success(r.message || '已保存')
    formOpen.value = false
    const id = editing.value?.id || ((r.data as { id?: number } | undefined)?.id)
    if (id && !editing.value) router.push(`/socks-sources/${id}`)
  } catch (e) {
    formRef.value?.setError(e instanceof ApiError ? e.message : '操作失败')
  } finally {
    submitting.value = false
  }
}

async function refresh(item: SocksSource) {
  busyId.value = item.id
  try {
    const r = await store.refreshSource(item.id)
    toast.success(r.message || '刷新完成')
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '刷新失败')
  } finally {
    busyId.value = null
  }
}

async function generate(item: SocksSource) {
  busyId.value = item.id
  try {
    const r = await store.generateSource(item.id)
    toast.success(r.message || '生成完成')
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '生成失败')
  } finally {
    busyId.value = null
  }
}

async function toggle(item: SocksSource) {
  busyId.value = item.id
  try {
    const enabled = !item.enabled
    const r = await store.toggleSource(item.id, enabled)
    toast.success(r.message || '已保存')
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '操作失败')
  } finally {
    busyId.value = null
  }
}

async function copyAll(item: SocksSource) {
  try {
    const text = await store.copySource(item.id)
    await navigator.clipboard.writeText(text)
    toast.success(`已复制 ${text ? text.split('\n').length : 0} 条 SOCKS5`)
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '复制失败')
  }
}

function askRemove(item: SocksSource) {
  removing.value = item
  confirmOpen.value = true
}

async function remove() {
  if (!removing.value) return
  busyId.value = removing.value.id
  try {
    await store.deleteSource(removing.value.id)
    toast.success('已删除订阅源')
    confirmOpen.value = false
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '删除失败')
  } finally {
    busyId.value = null
  }
}
</script>

<template>
  <AppShell title="订阅 SOCKS" subtitle="把多个订阅链接解析成一批独立 SOCKS5 入口">
    <template #actions>
      <Button variant="primary" @click="openCreate">
        <Icon name="add_link" :size="18" />添加订阅
      </Button>
    </template>

    <div class="grid grid-cols-2 xl:grid-cols-4 gap-panel-gap">
      <div class="glass-panel rounded-lg p-4">
        <p class="text-sm text-on-surface-variant">订阅源</p>
        <p class="mt-2 text-2xl font-semibold text-on-surface">{{ store.totalSources }}</p>
      </div>
      <div class="glass-panel rounded-lg p-4">
        <p class="text-sm text-on-surface-variant">解析节点</p>
        <p class="mt-2 text-2xl font-semibold text-on-surface">{{ store.totalNodes }}</p>
      </div>
      <div class="glass-panel rounded-lg p-4">
        <p class="text-sm text-on-surface-variant">SOCKS5 入口</p>
        <p class="mt-2 text-2xl font-semibold text-on-surface">{{ store.totalEndpoints }}</p>
      </div>
      <div class="glass-panel rounded-lg p-4">
        <p class="text-sm text-on-surface-variant">可用入口</p>
        <p class="mt-2 text-2xl font-semibold text-secondary-fixed">{{ store.activeEndpoints }}</p>
      </div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-panel-gap">
      <div class="glass-panel rounded-lg p-4 flex flex-col gap-4">
        <div class="flex items-center gap-3">
          <div class="relative w-80 max-w-full">
            <Icon name="search" :size="18" class="absolute left-3 top-1/2 -translate-y-1/2 text-outline" />
            <input v-model="keyword" class="control pl-9" placeholder="搜索订阅名称或链接" />
          </div>
          <span class="ml-auto text-sm text-outline">共 {{ sources.length }} 个</span>
        </div>

        <div v-if="sources.length" class="grid grid-cols-1 lg:grid-cols-2 gap-panel-gap">
          <article
            v-for="item in sources"
            :key="item.id"
            class="rounded-lg border border-outline-variant/35 bg-surface-container-lowest/50 p-4 flex flex-col gap-4 neon-border-hover"
          >
            <div class="flex items-start gap-3">
              <div class="w-10 h-10 rounded-lg bg-primary-container/15 flex items-center justify-center text-primary shrink-0">
                <Icon name="hub" :size="22" />
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <h3 class="font-title-sm text-title-sm text-on-surface truncate">{{ item.name }}</h3>
                  <Badge :tone="item.enabled ? 'green' : 'gray'" dot>{{ item.enabled ? '启用' : '停用' }}</Badge>
                </div>
                <p class="mt-1 font-code-xs text-[11px] text-outline truncate">{{ item.url }}</p>
              </div>
            </div>

            <div class="grid grid-cols-3 gap-2 text-sm">
              <div class="rounded bg-surface-container/60 p-2">
                <p class="text-outline text-xs">节点</p>
                <p class="text-on-surface font-semibold">{{ item.node_count }}</p>
              </div>
              <div class="rounded bg-surface-container/60 p-2">
                <p class="text-outline text-xs">入口</p>
                <p class="text-on-surface font-semibold">{{ item.endpoint_count }}</p>
              </div>
              <div class="rounded bg-surface-container/60 p-2">
                <p class="text-outline text-xs">总额度</p>
                <p class="text-on-surface font-semibold">{{ item.total_gb ? gb(item.total_gb, 0) : '不限' }}</p>
              </div>
            </div>

            <div class="space-y-2">
              <div class="flex justify-between text-xs text-on-surface-variant">
                <span>已用 {{ gb(item.used_gb, 2) }}</span>
                <span>{{ item.usage_percent === null ? '未设额度' : `${item.usage_percent}%` }}</span>
              </div>
              <ProgressBar :percent="item.usage_percent" :muted="!item.enabled" />
            </div>

            <div class="flex items-center justify-between gap-2">
              <span class="text-xs text-outline">刷新：{{ fromUnix(item.last_refresh_at) }}</span>
              <div class="flex items-center gap-1">
                <button class="p-2 rounded hover:bg-surface-variant/30 text-on-surface-variant" title="刷新订阅" @click="refresh(item)">
                  <Icon :name="busyId === item.id ? 'progress_activity' : 'refresh'" :size="18" :class="busyId === item.id ? 'animate-spin' : ''" />
                </button>
                <button class="p-2 rounded hover:bg-surface-variant/30 text-on-surface-variant" title="生成 SOCKS5" @click="generate(item)">
                  <Icon name="auto_awesome_motion" :size="18" />
                </button>
                <button class="p-2 rounded hover:bg-surface-variant/30 text-on-surface-variant" title="复制全部" @click="copyAll(item)">
                  <Icon name="content_copy" :size="18" />
                </button>
                <button class="p-2 rounded hover:bg-surface-variant/30 text-on-surface-variant" title="启用/停用" @click="toggle(item)">
                  <Icon :name="item.enabled ? 'pause_circle' : 'play_circle'" :size="18" />
                </button>
                <button class="p-2 rounded hover:bg-surface-variant/30 text-on-surface-variant" title="编辑" @click="openEdit(item)">
                  <Icon name="edit" :size="18" />
                </button>
                <button class="p-2 rounded hover:bg-error/10 text-error" title="删除" @click="askRemove(item)">
                  <Icon name="delete" :size="18" />
                </button>
              </div>
            </div>
            <RouterLink
              :to="`/socks-sources/${item.id}`"
              class="h-10 rounded-lg bg-primary-container/15 hover:bg-primary-container/25 text-primary flex items-center justify-center gap-2 font-label-sm"
            >
              <Icon name="open_in_new" :size="18" />查看全部 SOCKS5
            </RouterLink>
          </article>
        </div>

        <div v-else class="rounded-lg border border-outline-variant/30 py-16 flex flex-col items-center gap-3 text-outline">
          <Icon name="hub" :size="42" />
          <p class="text-sm">还没有订阅源，先添加一个订阅链接。</p>
        </div>
      </div>

      <aside class="glass-panel rounded-lg p-4 flex flex-col gap-4">
        <div>
          <h3 class="font-title-sm text-title-sm text-on-surface">活跃订阅</h3>
          <p class="mt-1 text-sm text-on-surface-variant">最近几个订阅源的节点规模和入口数量</p>
        </div>
        <div class="flex flex-col gap-3">
          <RouterLink
            v-for="item in topSources"
            :key="item.id"
            :to="`/socks-sources/${item.id}`"
            class="rounded-lg border border-outline-variant/30 bg-surface-container-lowest/40 p-3 hover:border-primary/40 transition-colors"
          >
            <div class="flex items-center justify-between">
              <span class="font-label-sm text-sm text-on-surface truncate">{{ item.name }}</span>
              <Badge :tone="item.last_error ? 'red' : 'green'" dot>{{ item.last_error ? '异常' : '正常' }}</Badge>
            </div>
            <div class="mt-3 h-20 flex items-end gap-2">
              <div class="flex-1 rounded-t bg-primary-container/40" :style="{ height: Math.max(8, Math.min(76, item.node_count * 2)) + 'px' }"></div>
              <div class="flex-1 rounded-t bg-secondary-fixed/50" :style="{ height: Math.max(8, Math.min(76, item.endpoint_count * 2)) + 'px' }"></div>
            </div>
            <div class="mt-2 flex justify-between text-xs text-outline">
              <span>节点 {{ item.node_count }}</span>
              <span>入口 {{ item.endpoint_count }}</span>
            </div>
          </RouterLink>
        </div>
      </aside>
    </div>

    <SocksSourceFormDialog
      ref="formRef"
      :open="formOpen"
      :editing="editing"
      :busy="submitting"
      @close="formOpen = false"
      @submit="submit"
    />
    <ConfirmDialog
      :open="confirmOpen"
      title="删除订阅源"
      :message="`确定删除「${removing?.name}」？它解析出的节点和 SOCKS5 入口都会删除。`"
      :busy="busyId === removing?.id"
      @close="confirmOpen = false"
      @confirm="remove"
    />
  </AppShell>
</template>
