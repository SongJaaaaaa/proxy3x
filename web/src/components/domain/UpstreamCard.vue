<script setup lang="ts">
import { computed } from 'vue'
import type { Upstream } from '@/types/dashboard'
import { fromUnix, gb, speed } from '@/lib/format'
import Icon from '@/components/ui/Icon.vue'
import Badge from '@/components/ui/Badge.vue'
import ProgressBar from '@/components/ui/ProgressBar.vue'

/**
 * UpstreamCard —— 单个家宽卡片（对应 stitch proxy3x_4）。保留卡片样式。
 * 顶部：备注/IP + 协议徽章 + 状态徽章；中部：遮罩账号；
 * 用量进度条用后端 usage_percent（quota_gb=0 → 显示"未设额度"，不画进度）；
 * 底部：检测 / 编辑 / 删除。
 */
const props = defineProps<{ item: Upstream; busy?: boolean }>()
const emit = defineEmits<{ check: []; speedTest: []; edit: []; remove: []; view: [] }>()

const available = computed(() => props.item.status === '可用')
const failed = computed(() => props.item.status === '不可用')

const protoTone = computed(() => (props.item.protocol.toLowerCase().includes('socks') ? 'purple' : 'blue'))
const statusTone = computed(() => (props.item.expired || failed.value ? 'red' : available.value ? 'green' : 'gray'))

const hasQuota = computed(() => props.item.usage_percent !== null)
const usageText = computed(() =>
  hasQuota.value
    ? `${gb(props.item.used_gb, 1)} / ${gb(props.item.quota_gb, 0)}`
    : `${gb(props.item.used_gb, 1)} / 未设额度`,
)
const dimmed = computed(() => props.item.expired || failed.value || props.item.status === '未检测')
const expireText = computed(() => props.item.expires_at_text || fromUnix(props.item.expires_at))
</script>

<template>
  <div
    class="glass-panel rounded-xl p-5 flex flex-col gap-4 relative group transition-all duration-300"
    :class="props.item.expired || failed ? 'hover:border-error/50' : 'neon-border-hover'"
  >
    <!-- 头部 -->
    <div class="flex justify-between items-start">
      <div class="flex flex-col min-w-0">
        <span class="font-title-sm text-title-sm text-on-surface truncate group-hover:text-primary transition-colors">
          {{ item.remark || item.host }}
        </span>
        <span class="font-code-xs text-code-xs text-outline font-mono mt-1 truncate">{{ item.host }}:{{ item.port }}</span>
      </div>
      <div class="flex flex-col items-end gap-1.5 shrink-0">
        <Badge :tone="protoTone">{{ item.protocol }}</Badge>
        <Badge :tone="statusTone" dot :pulse="available && !item.expired">{{ item.expired ? '已到期' : item.status }}</Badge>
      </div>
    </div>

    <!-- 账号（已遮罩，纯展示） -->
    <div
      class="bg-surface-container-lowest/50 rounded-md p-2 flex items-center gap-2 border border-outline-variant/20"
      :class="{ 'opacity-70': dimmed }"
    >
      <Icon name="badge" :size="16" class="text-outline" />
      <span class="font-code-xs text-code-xs text-on-surface-variant font-mono truncate">
        {{ item.username || '—' }}<template v-if="item.password"> : {{ item.password }}</template>
      </span>
    </div>

    <!-- 到期时间 -->
    <div
      class="bg-surface-container-lowest/40 rounded-md p-2 flex items-center gap-2 border border-outline-variant/20"
      :class="{ 'opacity-70 border-error/20': dimmed }"
    >
      <Icon name="event_busy" :size="16" :class="item.expired ? 'text-error' : 'text-outline'" />
      <span
        class="font-code-xs text-code-xs truncate"
        :class="item.expired ? 'text-error' : 'text-on-surface-variant'"
      >
        到期 {{ expireText }}
      </span>
    </div>

    <!-- 测速 -->
    <div
      class="bg-surface-container-lowest/40 rounded-md p-2 flex items-center gap-2 border border-outline-variant/20"
      :class="{ 'opacity-70': dimmed }"
    >
      <Icon name="speed" :size="16" class="text-outline" />
      <span class="font-code-xs text-code-xs truncate text-on-surface-variant">
        速度 {{ speed(item.speed_bps) }}
      </span>
    </div>

    <!-- 用量进度 -->
    <div class="flex flex-col gap-1.5 mt-2" :class="{ 'opacity-70': dimmed }">
      <div class="flex justify-between items-end">
        <span class="font-label-sm text-[11px] text-outline">流量使用</span>
        <span class="font-code-xs text-code-xs text-on-surface">{{ usageText }}</span>
      </div>
      <ProgressBar :percent="item.usage_percent" :muted="dimmed" />
    </div>

    <!-- 操作 -->
    <div class="flex gap-2 mt-auto pt-2">
      <button
        class="flex-1 h-8 rounded border font-label-sm text-label-sm flex items-center justify-center gap-1 transition-colors bg-surface-container-lowest/30 disabled:opacity-50"
        :class="
          item.status === '未检测'
            ? 'border-primary/50 text-primary hover:bg-primary/10'
            : 'border-outline-variant/50 text-on-surface-variant hover:text-primary hover:border-primary/50'
        "
        :disabled="busy"
        @click="emit('check')"
      >
        <Icon :name="failed ? 'refresh' : item.status === '未检测' ? 'play_arrow' : 'network_ping'" :size="16" />
        {{ failed ? '重试' : item.status === '未检测' ? '开始检测' : '检测' }}
      </button>
      <button
        class="flex-1 h-8 rounded border border-outline-variant/50 text-on-surface-variant hover:text-primary hover:border-primary/50 font-label-sm text-label-sm flex items-center justify-center gap-1 transition-colors bg-surface-container-lowest/30 disabled:opacity-50"
        :disabled="busy"
        @click="emit('speedTest')"
      >
        <Icon name="speed" :size="16" />
        测速
      </button>
      <button
        class="w-10 h-8 rounded border border-outline-variant/50 text-on-surface-variant hover:text-primary hover:border-primary/50 flex items-center justify-center transition-colors bg-surface-container-lowest/30"
        title="查看完整信息"
        @click="emit('view')"
      >
        <Icon name="visibility" :size="16" />
      </button>
      <button
        class="w-10 h-8 rounded border border-outline-variant/50 text-on-surface-variant hover:text-primary hover:border-primary/50 flex items-center justify-center transition-colors bg-surface-container-lowest/30"
        title="编辑额度/备注"
        @click="emit('edit')"
      >
        <Icon name="edit" :size="16" />
      </button>
      <button
        class="w-10 h-8 rounded border border-outline-variant/50 text-on-surface-variant hover:text-error hover:border-error/50 flex items-center justify-center transition-colors bg-surface-container-lowest/30"
        title="删除"
        @click="emit('remove')"
      >
        <Icon name="delete" :size="16" />
      </button>
    </div>
  </div>
</template>
