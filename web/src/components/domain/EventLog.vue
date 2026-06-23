<script setup lang="ts">
import { computed, ref } from 'vue'
import type { EventItem } from '@/types/dashboard'
import { fromUnix } from '@/lib/format'
import Icon from '@/components/ui/Icon.vue'

/**
 * EventLog —— 操作日志列表（整行展示，可搜索）。
 * 按级别（信息/警告）显示彩色图标与时间戳；顶部搜索框按消息内容过滤。
 */
const props = defineProps<{ events: EventItem[] }>()

const keyword = ref('')
const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return props.events
  return props.events.filter((e) => e.message.toLowerCase().includes(k) || e.level.toLowerCase().includes(k))
})

function tone(level: string) {
  if (level.includes('警告') || level.includes('错误')) return { icon: 'warning', cls: 'text-error' }
  return { icon: 'info', cls: 'text-secondary-fixed' }
}
</script>

<template>
  <div class="glass-panel rounded-xl p-5 flex flex-col gap-3">
    <div class="flex items-center justify-between gap-4">
      <h3 class="font-title-sm text-title-sm text-on-surface shrink-0">操作日志</h3>
      <div class="relative w-64 max-w-full">
        <Icon name="search" :size="18" class="absolute left-3 top-1/2 -translate-y-1/2 text-outline" />
        <input
          v-model="keyword"
          class="control !h-9 pl-9 text-sm"
          placeholder="搜索日志…"
        />
      </div>
    </div>

    <!-- 整行两列网格，行高紧凑 -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-0 max-h-72 overflow-y-auto">
      <div
        v-for="e in filtered"
        :key="e.id"
        class="flex items-start gap-3 py-2.5 border-b border-outline-variant/10"
      >
        <Icon :name="tone(e.level).icon" :size="18" :class="tone(e.level).cls" class="mt-0.5 shrink-0" />
        <div class="min-w-0 flex-1">
          <p class="font-body-md text-sm text-on-surface leading-snug break-words">{{ e.message }}</p>
          <span class="font-code-xs text-[11px] text-outline">{{ fromUnix(e.created_at) }}</span>
        </div>
      </div>
      <div v-if="!filtered.length" class="py-8 text-center text-outline font-body-md text-sm md:col-span-2">
        {{ keyword ? '没有匹配的日志' : '暂无操作记录' }}
      </div>
    </div>
  </div>
</template>
