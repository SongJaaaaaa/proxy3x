<script setup lang="ts">
import { ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import type { Upstream, UpstreamReveal } from '@/types/dashboard'
import { useDashboardStore } from '@/stores/dashboard'
import { ApiError } from '@/api/errors'
import Modal from '@/components/ui/Modal.vue'
import Icon from '@/components/ui/Icon.vue'

/**
 * 家宽详情弹窗 —— 打开时拉取 /api/upstreams/{id}/reveal 的明文信息，
 * 展示完整 socks5 连接信息（含真实账号密码）并支持一键复制。
 */
const props = defineProps<{ open: boolean; item: Upstream | null }>()
const emit = defineEmits<{ close: [] }>()

const store = useDashboardStore()
const loading = ref(false)
const error = ref('')
const data = ref<UpstreamReveal | null>(null)

watch(
  () => props.open,
  async (v) => {
    if (!v || !props.item) return
    error.value = ''
    data.value = null
    loading.value = true
    try {
      data.value = (await store.revealUpstream(props.item.id)) ?? null
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : '获取详情失败'
    } finally {
      loading.value = false
    }
  },
)

async function copy(text: string, label: string) {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    toast.success(`已复制${label}`)
  } catch {
    toast.error('复制失败，请手动复制')
  }
}

const rows = () =>
  data.value
    ? [
        { label: '备注', value: data.value.remark || '—', copy: false },
        { label: '协议', value: data.value.protocol || '—', copy: false },
        { label: '主机 IP', value: data.value.host, copy: true },
        { label: '端口', value: String(data.value.port), copy: true },
        { label: '账号', value: data.value.username, copy: true },
        { label: '密码', value: data.value.password, copy: true },
      ]
    : []
</script>

<template>
  <Modal :open="open" title="家宽完整信息" icon="visibility" icon-tone="purple" @close="emit('close')">
    <div v-if="loading" class="py-10 flex flex-col items-center gap-3 text-outline">
      <Icon name="progress_activity" :size="32" class="animate-spin" />
      <span class="font-body-md text-sm">正在读取明文信息…</span>
    </div>

    <p v-else-if="error" class="py-8 text-center font-body-md text-sm text-error">{{ error }}</p>

    <template v-else-if="data">
      <!-- 字段列表 -->
      <div class="flex flex-col gap-2">
        <div
          v-for="r in rows()"
          :key="r.label"
          class="flex items-center gap-3 bg-surface-container-lowest/50 rounded-lg px-3 py-2 border border-outline-variant/20"
        >
          <span class="w-16 shrink-0 font-label-sm text-label-sm text-outline">{{ r.label }}</span>
          <span class="flex-1 min-w-0 font-code-xs text-code-xs text-on-surface font-mono break-all">{{ r.value }}</span>
          <button
            v-if="r.copy"
            class="shrink-0 w-8 h-8 rounded border border-outline-variant/50 text-on-surface-variant hover:text-primary hover:border-primary/50 flex items-center justify-center transition-colors"
            title="复制"
            @click="copy(r.value, r.label)"
          >
            <Icon name="content_copy" :size="15" />
          </button>
        </div>
      </div>

      <!-- 连接串 -->
      <div class="mt-3">
        <p class="font-label-sm text-label-sm text-outline mb-1.5">连接串 (URI)</p>
        <div class="flex items-center gap-2 bg-surface-container-lowest/50 rounded-lg px-3 py-2 border border-primary/20">
          <span class="flex-1 min-w-0 font-code-xs text-code-xs text-primary font-mono break-all">{{ data.uri }}</span>
          <button
            class="shrink-0 w-8 h-8 rounded border border-primary/40 text-primary hover:bg-primary/10 flex items-center justify-center transition-colors"
            title="复制连接串"
            @click="copy(data.uri, '连接串')"
          >
            <Icon name="content_copy" :size="15" />
          </button>
        </div>
      </div>

      <!-- IP:端口:账号:密码 一行 -->
      <div class="mt-3">
        <p class="font-label-sm text-label-sm text-outline mb-1.5">IP:端口:账号:密码</p>
        <div class="flex items-center gap-2 bg-surface-container-lowest/50 rounded-lg px-3 py-2 border border-outline-variant/20">
          <span class="flex-1 min-w-0 font-code-xs text-code-xs text-on-surface-variant font-mono break-all">{{ data.line }}</span>
          <button
            class="shrink-0 w-8 h-8 rounded border border-outline-variant/50 text-on-surface-variant hover:text-primary hover:border-primary/50 flex items-center justify-center transition-colors"
            title="复制"
            @click="copy(data.line, '一行格式')"
          >
            <Icon name="content_copy" :size="15" />
          </button>
        </div>
      </div>
    </template>

    <template #footer>
      <button
        class="h-9 px-4 rounded-lg text-sm font-label-sm bg-primary/15 text-secondary-fixed-dim hover:bg-primary/25 transition-colors"
        @click="emit('close')"
      >
        关闭
      </button>
    </template>
  </Modal>
</template>
