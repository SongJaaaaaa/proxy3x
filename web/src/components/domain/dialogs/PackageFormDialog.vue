<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { Package, Upstream } from '@/types/dashboard'
import { monthsFromNowLocal, unixToLocalInput } from '@/lib/format'
import Modal from '@/components/ui/Modal.vue'
import Field from '@/components/ui/Field.vue'
import Button from '@/components/ui/Button.vue'
import Icon from '@/components/ui/Icon.vue'
import DatePicker from '@/components/ui/DatePicker.vue'

/**
 * 新增/编辑用户套餐弹框（对应 stitch proxy3x_5）。
 * 字段：用户名、订阅名(仅新增)、总额度、绑定 SOCKS5、到期时间、备注。
 * 失败原因内联显示。提交由父组件处理。
 */
const props = defineProps<{ open: boolean; editing?: Package | null; upstreams: Upstream[]; busy?: boolean }>()
const emit = defineEmits<{
  close: []
  submit: [
    payload: {
      name: string
      sub_id: string
      total_gb: number
      residential_gb: number
      upstream_ids: number[]
      expires_at: string
      notes: string
    },
  ]
}>()

const form = reactive({
  name: '',
  sub_id: '',
  total_gb: 500,
  residential_gb: 0,
  upstream_ids: [] as number[],
  expires_at: '',
  notes: '',
})
const error = ref('')
const upstreamKeyword = ref('')

const availableUpstreams = computed(() => props.upstreams.filter((u) => !u.expired && u.status !== '不可用'))
const filteredUpstreams = computed(() => {
  const k = upstreamKeyword.value.trim().toLowerCase()
  if (!k) return availableUpstreams.value
  return availableUpstreams.value.filter((u) =>
    `${u.socks5_name || ''} ${u.source_node_name || ''} ${u.display_name || ''} ${u.remark || ''} ${u.host || ''} ${u.assigned_to || ''}`
      .toLowerCase()
      .includes(k),
  )
})
const selectedSet = computed(() => new Set(form.upstream_ids))
const allFilteredSelected = computed(
  () => filteredUpstreams.value.length > 0 && filteredUpstreams.value.every((u) => selectedSet.value.has(u.id)),
)

watch(
  () => props.open,
  (v) => {
    if (!v) return
    error.value = ''
    const e = props.editing
    form.name = e?.name ?? ''
    form.sub_id = e?.sub_id ?? ''
    form.total_gb = e?.total_gb ?? 500
    form.residential_gb = e?.residential_gb ?? 0
    form.upstream_ids = e?.upstream_ids?.length ? [...e.upstream_ids] : e?.upstream_id ? [e.upstream_id] : []
    form.notes = e?.notes ?? ''
    upstreamKeyword.value = ''
    // 新增时默认一个月后；编辑时回填已有到期时间（留空 = 永久有效）。
    form.expires_at = e ? unixToLocalInput(e.expires_at) : monthsFromNowLocal(1)
  },
)

function setError(msg: string) {
  error.value = msg
}
defineExpose({ setError })

function upstreamName(u: Upstream) {
  return u.socks5_name || u.remark || u.host || `SOCKS5 #${u.id}`
}

function nodeName(u: Upstream) {
  return u.source_node_name || u.display_name || u.host || '未匹配订阅节点'
}

function toggleUpstream(id: number) {
  form.upstream_ids = selectedSet.value.has(id)
    ? form.upstream_ids.filter((item) => item !== id)
    : [...form.upstream_ids, id]
}

function toggleAllFiltered() {
  const ids = filteredUpstreams.value.map((u) => u.id)
  if (!ids.length) return
  if (allFilteredSelected.value) {
    form.upstream_ids = form.upstream_ids.filter((id) => !ids.includes(id))
    return
  }
  form.upstream_ids = Array.from(new Set([...form.upstream_ids, ...ids]))
}

function submit() {
  error.value = ''
  if (!form.name.trim()) return (error.value = '请填写用户名')
  if (!props.editing && !form.sub_id.trim()) return (error.value = '请填写订阅名')
  if (!form.upstream_ids.length) return (error.value = '请选择至少一个 SOCKS5 节点')
  emit('submit', {
    name: form.name.trim(),
    sub_id: form.sub_id.trim(),
    total_gb: Number(form.total_gb) || 0,
    residential_gb: Number(form.residential_gb) || 0,
    upstream_ids: form.upstream_ids,
    expires_at: form.expires_at,
    notes: form.notes.trim(),
  })
}
</script>

<template>
  <Modal
    :open="open"
    :title="editing ? '编辑用户' : '新增用户'"
    :icon="editing ? 'edit' : 'person_add'"
    icon-tone="green"
    @close="emit('close')"
  >
    <!-- 系统提示 -->
    <div class="rounded-lg border border-secondary-fixed/20 bg-secondary-fixed/5 p-3 flex gap-3">
      <Icon name="info" :size="20" class="text-secondary-fixed shrink-0 mt-0.5" />
      <div class="font-body-md text-sm text-on-surface-variant leading-relaxed">
        <p class="font-semibold text-on-surface mb-0.5">系统提示</p>
        创建后会按所选 SOCKS5 生成多个 VLESS/REALITY 入口，默认 500GB、一个月有效。
      </div>
    </div>

    <div class="grid grid-cols-2 gap-4">
      <Field label="用户名" required>
        <input v-model="form.name" class="control" placeholder="输入用户唯一标识" />
      </Field>
      <Field label="订阅名" :required="!editing">
        <input
          v-model="form.sub_id"
          class="control disabled:opacity-50"
          :disabled="!!editing"
          placeholder="例如: pro_tier_1"
        />
      </Field>
      <Field label="总额度 (GB)" required>
        <input v-model.number="form.total_gb" type="number" min="1" class="control" />
      </Field>
      <Field label="到期时间">
        <DatePicker v-model="form.expires_at" placeholder="点击选择到期日期" />
        <p class="mt-1 font-label-sm text-[11px] text-outline">留空表示永久有效</p>
      </Field>
    </div>

    <Field label="绑定 SOCKS5" required>
      <div class="rounded-lg border border-outline-variant/40 bg-surface-container/40 overflow-hidden">
        <div class="flex items-center gap-2 p-2 border-b border-outline-variant/30">
          <div class="relative flex-1 min-w-0">
            <Icon name="search" :size="17" class="absolute left-3 top-1/2 -translate-y-1/2 text-outline" />
            <input v-model="upstreamKeyword" class="control !h-9 pl-9" placeholder="搜索节点名称 / 主机 / 备注" />
          </div>
          <Button variant="ghost" @click="toggleAllFiltered">
            {{ allFilteredSelected ? '取消全选' : '全选' }}
          </Button>
        </div>
        <div class="max-h-56 overflow-auto divide-y divide-outline-variant/20">
          <button
            v-for="u in filteredUpstreams"
            :key="u.id"
            type="button"
            class="w-full px-3 py-2 flex items-center gap-3 text-left hover:bg-surface-variant/10"
            @click="toggleUpstream(u.id)"
          >
            <span
              class="w-4 h-4 rounded border flex items-center justify-center shrink-0"
              :class="selectedSet.has(u.id) ? 'bg-primary border-primary text-on-primary' : 'border-outline text-transparent'"
            >
              <Icon name="check" :size="13" />
            </span>
            <span class="min-w-0 flex-1">
              <span class="block text-sm text-on-surface truncate">SOCKS5：{{ upstreamName(u) }}</span>
              <span class="block text-xs text-on-surface-variant truncate">节点：{{ nodeName(u) }}</span>
              <span class="block font-code-xs text-[11px] text-outline truncate">#{{ u.id }} · {{ u.protocol }} · {{ u.status }}</span>
            </span>
          </button>
          <div v-if="!filteredUpstreams.length" class="px-3 py-6 text-center text-sm text-outline">没有可选 SOCKS5 节点</div>
        </div>
        <div class="px-3 py-2 border-t border-outline-variant/30 text-xs text-outline">
          已选择 {{ form.upstream_ids.length }} 个节点
        </div>
      </div>
    </Field>

    <Field label="备注">
      <input v-model="form.notes" class="control" placeholder="添加内部备注信息..." />
    </Field>

    <p v-if="error" class="font-body-md text-sm text-error">{{ error }}</p>

    <template #footer>
      <Button variant="ghost" @click="emit('close')">取消</Button>
      <Button variant="primary" :loading="busy" @click="submit">确认</Button>
    </template>
  </Modal>
</template>
