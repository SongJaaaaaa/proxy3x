<script setup lang="ts">
import type { Package, Upstream } from '@/types/dashboard'
import { gb, percent, fromUnix } from '@/lib/format'
import { toast } from 'vue-sonner'
import Icon from '@/components/ui/Icon.vue'
import ProgressBar from '@/components/ui/ProgressBar.vue'

/**
 * PackageTable —— 用户套餐密集表格（对应 stitch proxy3x_2）。
 * 列：用户 / 订阅 / 总额度 / 总用量 / 入口用量 /
 *     入口端口 / 绑定 SOCKS5 / 备注 / 操作（含小飞机/Clash 下载）。
 * 首列(用户)与末列(操作)横向滚动时固定（sticky + 不透明背景）。
 * 纵向滚动在表格容器内部（max-h + overflow），不触发整页滚动。
 * 绑定 SOCKS5 在编辑弹窗中多选；表格只做展示。
 */
const props = defineProps<{ packages: Package[]; upstreams: Upstream[] }>()
const emit = defineEmits<{
  edit: [pkg: Package]
  remove: [pkg: Package]
}>()

function upstreamName(id: number | null) {
  if (!id) return '默认 SOCKS5'
  const u = props.upstreams.find((x) => x.id === id)
  if (!u) return '默认 SOCKS5'
  return `${u.display_name || u.remark || u.host}${u.expired ? '（已到期）' : ''}`
}
function bindingNames(pkg: Package) {
  if (pkg.bindings?.length) return pkg.bindings.map((item) => item.display_name || upstreamName(item.upstream_id))
  return pkg.upstream_id ? [upstreamName(pkg.upstream_id)] : []
}
function bindingPorts(pkg: Package) {
  if (pkg.bindings?.length) return pkg.bindings.map((item) => item.port).filter((port): port is number => Boolean(port))
  return [pkg.direct_port, pkg.residential_port].filter((port): port is number => Boolean(port))
}
async function copy(url: string, label: string) {
  try {
    await navigator.clipboard.writeText(url)
    toast.success(`已复制${label}链接`)
  } catch {
    toast.error('复制失败，请手动复制')
  }
}
</script>

<template>
  <div class="glass-panel rounded-xl overflow-hidden flex flex-col min-h-0 flex-1">
    <!-- 横向 + 纵向滚动都在此容器内部 -->
    <div class="overflow-auto flex-1 min-h-0">
      <table class="w-full border-collapse min-w-[1360px]">
        <thead class="sticky top-0 z-20">
          <tr class="text-left font-label-sm text-label-sm text-on-surface-variant bg-surface-container/95 backdrop-blur border-b border-outline-variant/20">
            <th class="sticky left-0 z-30 bg-surface-container/95 backdrop-blur px-4 py-3">用户</th>
            <th class="px-3 py-3">订阅</th>
            <th class="px-3 py-3">总额度</th>
            <th class="px-3 py-3 w-[130px]">总用量</th>
            <th class="px-3 py-3 w-[130px]">入口用量</th>
            <th class="px-3 py-3 w-[150px]">入口端口</th>
            <th class="px-3 py-3 w-[220px]">绑定 SOCKS5</th>
            <th class="px-3 py-3">到期时间</th>
            <th class="px-3 py-3">备注</th>
            <th class="sticky right-0 z-30 bg-surface-container/95 backdrop-blur px-4 py-3 text-center w-[180px]">操作</th>
          </tr>
        </thead>
        <tbody class="font-body-md text-body-md">
          <tr
            v-for="p in packages"
            :key="p.id"
            class="border-b border-outline-variant/10 hover:bg-surface-variant/[0.05] transition-colors group"
          >
            <!-- 用户（固定列） -->
            <td class="sticky left-0 z-10 bg-surface-container/95 group-hover:bg-surface-container backdrop-blur px-4 py-3">
              <div class="flex items-center gap-2">
                <span
                  class="w-2 h-2 rounded-full shrink-0"
                  :class="p.expired ? 'bg-error' : p.enabled ? 'bg-secondary-fixed' : 'bg-outline'"
                ></span>
                <div class="min-w-0">
                  <p class="text-on-surface truncate">{{ p.name }}</p>
                  <p class="font-code-xs text-[11px] text-outline">ID: {{ p.id }}</p>
                </div>
              </div>
            </td>
            <!-- 订阅 -->
            <td class="px-3 py-3">
              <span class="font-code-xs text-code-xs text-on-surface-variant truncate block max-w-[140px]">{{ p.sub_id }}</span>
            </td>
            <!-- 总额度 -->
            <td class="px-3 py-3 text-on-surface-variant whitespace-nowrap">{{ gb(p.total_gb, 0) }}</td>
            <!-- 用量进度 -->
            <td class="px-3 py-3">
              <div class="flex flex-col gap-1">
                <span class="font-code-xs text-[11px] text-on-surface">{{ gb(p.total_used_gb, 1) }}</span>
                <ProgressBar :percent="percent(p.total_used_gb, p.total_gb)" />
              </div>
            </td>
            <td class="px-3 py-3">
              <div class="flex flex-col gap-1">
                <span class="font-code-xs text-[11px] text-on-surface">{{ gb(p.direct_used_gb, 1) }}</span>
                <ProgressBar :percent="percent(p.direct_used_gb, p.total_gb)" />
              </div>
            </td>
            <!-- 入口端口（长方形圆角边框芯片，单行紧凑） -->
            <td class="px-3 py-3">
              <div class="flex flex-col items-start gap-1">
                <span
                  v-for="port in bindingPorts(p).slice(0, 3)"
                  :key="port"
                  class="px-2 py-0.5 rounded-md border border-primary/30 bg-primary/10 text-primary font-code-xs text-[11px] leading-tight whitespace-nowrap"
                >入口 {{ port }}</span>
                <span v-if="bindingPorts(p).length > 3" class="text-outline text-xs">+{{ bindingPorts(p).length - 3 }}</span>
                <span v-if="!bindingPorts(p).length" class="text-outline text-sm">—</span>
              </div>
            </td>
            <!-- 绑定 SOCKS5 -->
            <td class="px-3 py-3">
              <div class="flex flex-col gap-1 max-w-[220px]">
                <span v-if="bindingNames(p).length" class="text-sm text-on-surface truncate">
                  {{ bindingNames(p).slice(0, 2).join(' / ') }}
                </span>
                <span v-if="bindingNames(p).length > 2" class="text-xs text-outline">
                  另有 {{ bindingNames(p).length - 2 }} 个节点
                </span>
                <span v-if="!bindingNames(p).length" class="text-outline text-sm">未绑定</span>
              </div>
            </td>
            <!-- 到期时间 -->
            <td class="px-3 py-3 whitespace-nowrap">
              <span
                class="font-code-xs text-[11px]"
                :class="p.expired ? 'text-error' : p.expires_at ? 'text-on-surface-variant' : 'text-outline'"
              >
                {{ p.expires_at ? p.expires_at_text || fromUnix(p.expires_at) : '永久' }}
              </span>
            </td>
            <!-- 备注 -->
            <td class="px-3 py-3 text-on-surface-variant truncate max-w-[140px]">{{ p.notes || '—' }}</td>
            <!-- 操作（固定列，加宽：小飞机/Clash/编辑/删除） -->
            <td class="sticky right-0 z-10 bg-surface-container/95 group-hover:bg-surface-container backdrop-blur px-4 py-3 w-[180px]">
              <div class="flex items-center justify-center gap-1.5">
                <a
                  :href="p.shadowrocket_url"
                  target="_blank"
                  class="w-9 h-8 rounded border border-outline-variant/50 text-on-surface-variant hover:text-secondary-fixed hover:border-secondary-fixed/50 flex items-center justify-center transition-colors"
                  title="小飞机订阅(.list)"
                >
                  <Icon name="rocket_launch" :size="16" />
                </a>
                <button
                  class="w-9 h-8 rounded border border-outline-variant/50 text-on-surface-variant hover:text-primary hover:border-primary/50 flex items-center justify-center transition-colors"
                  title="复制 Clash 订阅(.yaml)"
                  @click="copy(p.clash_url, 'Clash')"
                >
                  <Icon name="content_copy" :size="16" />
                </button>
                <button
                  class="w-9 h-8 rounded border border-outline-variant/50 text-on-surface-variant hover:text-primary hover:border-primary/50 flex items-center justify-center transition-colors"
                  title="编辑"
                  @click="emit('edit', p)"
                >
                  <Icon name="edit" :size="16" />
                </button>
                <button
                  class="w-9 h-8 rounded border border-outline-variant/50 text-on-surface-variant hover:text-error hover:border-error/50 flex items-center justify-center transition-colors"
                  title="删除"
                  @click="emit('remove', p)"
                >
                  <Icon name="delete" :size="16" />
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="!packages.length">
            <td colspan="10" class="py-16 text-center text-outline font-body-md text-sm">
              没有匹配的套餐。
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
