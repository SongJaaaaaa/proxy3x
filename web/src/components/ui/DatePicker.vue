<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { onClickOutside, useEventListener } from '@vueuse/core'
import Icon from './Icon.vue'

/**
 * DatePicker —— 自定义日历弹层（暗色玻璃风，无第三方 UI 依赖）。
 * v-model 绑定 'YYYY-MM-DDTHH:mm' 字符串（与原 datetime-local 一致），空串表示未设置。
 * 点击触发器 teleport 弹出：月历网格 + 上/下月 + 时:分选择；点击外部 / Esc 关闭。
 */
const props = withDefaults(
  defineProps<{ modelValue: string; placeholder?: string }>(),
  { placeholder: '选择日期时间' },
)
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const pad = (n: number) => String(n).padStart(2, '0')

/** 解析 model 为 {y,m(0-based),d,h,min}，无效返回 null。 */
function parse(v: string) {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(v || '')
  if (!m) return null
  return { y: +m[1], mo: +m[2] - 1, d: +m[3], h: +m[4], min: +m[5] }
}

const open = ref(false)
const triggerRef = ref<HTMLElement | null>(null)
const popRef = ref<HTMLElement | null>(null)
const pos = ref({ top: 0, left: 0, width: 0 })

// 当前展示的年/月
const today = new Date()
const viewYear = ref(today.getFullYear())
const viewMonth = ref(today.getMonth())
// 已选时间（时/分），默认 23:59 作为到期时间
const hour = ref(23)
const minute = ref(59)

const selected = computed(() => parse(props.modelValue))

// 触发器显示文本
const display = computed(() => {
  const p = selected.value
  if (!p) return ''
  return `${p.y}-${pad(p.mo + 1)}-${pad(p.d)} ${pad(p.h)}:${pad(p.min)}`
})

// 同步外部值到内部展示月份与时分
watch(
  () => props.modelValue,
  (v) => {
    const p = parse(v)
    if (p) {
      viewYear.value = p.y
      viewMonth.value = p.mo
      hour.value = p.h
      minute.value = p.min
    }
  },
  { immediate: true },
)

const weekdays = ['一', '二', '三', '四', '五', '六', '日']

// 42 格日历（周一起始，含上/下月补位）
const cells = computed(() => {
  const first = new Date(viewYear.value, viewMonth.value, 1)
  const offset = (first.getDay() + 6) % 7 // 周一为 0
  const start = new Date(viewYear.value, viewMonth.value, 1 - offset)
  const out: { date: Date; inMonth: boolean }[] = []
  for (let i = 0; i < 42; i++) {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i)
    out.push({ date: d, inMonth: d.getMonth() === viewMonth.value })
  }
  return out
})

const monthLabel = computed(() => `${viewYear.value} 年 ${viewMonth.value + 1} 月`)

function isSameDay(d: Date, p: ReturnType<typeof parse>) {
  return !!p && d.getFullYear() === p.y && d.getMonth() === p.mo && d.getDate() === p.d
}
function isToday(d: Date) {
  const n = new Date()
  return d.getFullYear() === n.getFullYear() && d.getMonth() === n.getMonth() && d.getDate() === n.getDate()
}

function emitValue(y: number, mo: number, d: number) {
  emit('update:modelValue', `${y}-${pad(mo + 1)}-${pad(d)}T${pad(hour.value)}:${pad(minute.value)}`)
}

function pickDay(d: Date) {
  viewYear.value = d.getFullYear()
  viewMonth.value = d.getMonth()
  emitValue(d.getFullYear(), d.getMonth(), d.getDate())
}

function onTimeChange() {
  const p = selected.value
  if (p) emitValue(p.y, p.mo, p.d)
}

function prevMonth() {
  if (viewMonth.value === 0) {
    viewMonth.value = 11
    viewYear.value--
  } else viewMonth.value--
}
function nextMonth() {
  if (viewMonth.value === 11) {
    viewMonth.value = 0
    viewYear.value++
  } else viewMonth.value++
}
function pickToday() {
  const n = new Date()
  viewYear.value = n.getFullYear()
  viewMonth.value = n.getMonth()
  emitValue(n.getFullYear(), n.getMonth(), n.getDate())
}
function clear() {
  emit('update:modelValue', '')
}

function updatePos() {
  const el = triggerRef.value
  if (!el) return
  const r = el.getBoundingClientRect()
  const popH = 360 // 估算高度，用于判断上下翻转
  const below = window.innerHeight - r.bottom
  const top = below < popH && r.top > popH ? r.top - popH - 8 : r.bottom + 8
  pos.value = { top, left: r.left, width: r.width }
}

async function toggle() {
  open.value = !open.value
  if (open.value) {
    const p = selected.value
    if (p) {
      viewYear.value = p.y
      viewMonth.value = p.mo
    }
    await nextTick()
    updatePos()
  }
}

onClickOutside(popRef, () => (open.value = false), { ignore: [triggerRef] })
useEventListener('keydown', (e: KeyboardEvent) => {
  if (e.key === 'Escape') open.value = false
})
useEventListener('scroll', () => open.value && updatePos(), true)
useEventListener('resize', () => open.value && updatePos())

const hours = Array.from({ length: 24 }, (_, i) => i)
const minutes = Array.from({ length: 60 }, (_, i) => i)
</script>

<template>
  <div>
    <!-- 触发器：复用 .control 外观 -->
    <button
      ref="triggerRef"
      type="button"
      class="control flex items-center justify-between cursor-pointer text-left"
      :class="{ '!border-primary/60': open }"
      @click="toggle"
    >
      <span :class="display ? 'text-on-surface' : 'text-outline'">{{ display || placeholder }}</span>
      <Icon name="calendar_month" :size="18" class="text-on-surface-variant shrink-0" />
    </button>

    <!-- 弹层 -->
    <Teleport to="body">
      <Transition name="dp-fade">
        <div
          v-if="open"
          ref="popRef"
          class="fixed z-[60] glass-panel rounded-xl p-3 shadow-[0_8px_40px_rgba(0,0,0,0.5)]"
          :style="{ top: pos.top + 'px', left: pos.left + 'px', minWidth: Math.max(pos.width, 288) + 'px' }"
        >
          <!-- 月份导航 -->
          <div class="flex items-center justify-between mb-2 px-1">
            <button
              type="button"
              class="w-8 h-8 rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-variant/10 flex items-center justify-center transition-colors"
              @click="prevMonth"
            >
              <Icon name="chevron_left" :size="20" />
            </button>
            <span class="font-label-sm text-sm text-on-surface">{{ monthLabel }}</span>
            <button
              type="button"
              class="w-8 h-8 rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-variant/10 flex items-center justify-center transition-colors"
              @click="nextMonth"
            >
              <Icon name="chevron_right" :size="20" />
            </button>
          </div>

          <!-- 星期表头 -->
          <div class="grid grid-cols-7 gap-1 mb-1">
            <span
              v-for="w in weekdays"
              :key="w"
              class="h-7 flex items-center justify-center font-label-sm text-[11px] text-outline"
            >{{ w }}</span>
          </div>

          <!-- 日期网格 -->
          <div class="grid grid-cols-7 gap-1">
            <button
              v-for="(c, i) in cells"
              :key="i"
              type="button"
              class="h-8 w-8 rounded-lg text-sm font-body-md flex items-center justify-center transition-colors"
              :class="[
                isSameDay(c.date, selected)
                  ? 'bg-primary text-on-primary font-semibold'
                  : c.inMonth
                    ? 'text-on-surface hover:bg-surface-variant/15'
                    : 'text-outline/50 hover:bg-surface-variant/10',
                isToday(c.date) && !isSameDay(c.date, selected) ? 'ring-1 ring-secondary-fixed/50' : '',
              ]"
              @click="pickDay(c.date)"
            >
              {{ c.date.getDate() }}
            </button>
          </div>

          <!-- 时间选择 -->
          <div class="flex items-center gap-2 mt-3 pt-3 border-t border-outline-variant/15">
            <Icon name="schedule" :size="16" class="text-on-surface-variant" />
            <select v-model.number="hour" class="control !h-9 !px-2 !pr-7 flex-1 text-sm" @change="onTimeChange">
              <option v-for="h in hours" :key="h" :value="h">{{ pad(h) }} 时</option>
            </select>
            <select v-model.number="minute" class="control !h-9 !px-2 !pr-7 flex-1 text-sm" @change="onTimeChange">
              <option v-for="m in minutes" :key="m" :value="m">{{ pad(m) }} 分</option>
            </select>
          </div>

          <!-- 底部操作 -->
          <div class="flex items-center justify-between mt-3">
            <div class="flex gap-2">
              <button
                type="button"
                class="h-8 px-3 rounded-lg text-xs font-label-sm text-secondary-fixed hover:bg-secondary-fixed/10 transition-colors"
                @click="pickToday"
              >
                今天
              </button>
              <button
                type="button"
                class="h-8 px-3 rounded-lg text-xs font-label-sm text-on-surface-variant hover:text-error hover:bg-error/10 transition-colors"
                @click="clear"
              >
                清除
              </button>
            </div>
            <button
              type="button"
              class="h-8 px-4 rounded-lg text-xs font-label-sm bg-primary/15 text-secondary-fixed-dim hover:bg-primary/25 transition-colors"
              @click="open = false"
            >
              确定
            </button>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.dp-fade-enter-active,
.dp-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.dp-fade-enter-from,
.dp-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
