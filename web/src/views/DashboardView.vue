<script setup lang="ts">
import { computed } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { usePolling } from '@/composables/usePolling'
import { gb } from '@/lib/format'
import AppShell from '@/components/layout/AppShell.vue'
import StatCard from '@/components/domain/StatCard.vue'
import UsageChart from '@/components/domain/UsageChart.vue'
import EventLog from '@/components/domain/EventLog.vue'

/**
 * 总览页（对应 stitch proxy3x_3）。4 张汇总卡 + 套餐用量柱状图 + 操作日志。
 * 每 10 秒轮询刷新（标签页隐藏时暂停）。
 */
const store = useDashboardStore()
usePolling(() => store.refresh(), 10000)

const s = computed(() => store.summary)
</script>

<template>
  <AppShell title="总览" subtitle="系统运行状态总览">
    <!-- 汇总卡 -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-panel-gap">
      <StatCard icon="inventory_2" tone="blue" label="套餐数" :value="String(s?.package_count ?? 0)" />
      <StatCard icon="lan" tone="green" label="SOCKS5 数" :value="String(s?.upstream_count ?? 0)" />
      <StatCard
        icon="data_usage"
        tone="purple"
        label="总用量 / 总额度"
        :value="gb(s?.total_used_gb, 1)"
        :unit="`/ ${gb(s?.total_limit_gb, 0)}`"
      />
      <StatCard icon="route" tone="red" label="链式用量" :value="gb(s?.total_used_gb, 1)" />
    </div>

    <!-- 用量图表（整行） -->
    <UsageChart :packages="store.packages" />

    <!-- 操作日志（整行，可搜索） -->
    <EventLog :events="store.events" />
  </AppShell>
</template>
