<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import type { Package, Upstream } from '@/types/dashboard'
import { monthsFromNowLocal, unixToLocalInput } from '@/lib/format'
import Modal from '@/components/ui/Modal.vue'
import Field from '@/components/ui/Field.vue'
import Button from '@/components/ui/Button.vue'
import Icon from '@/components/ui/Icon.vue'
import DatePicker from '@/components/ui/DatePicker.vue'

/**
 * 新增/编辑用户套餐弹框（对应 stitch proxy3x_5）。
 * 字段：用户名、订阅名(仅新增)、总额度、住宅额度、绑定家宽、到期时间、备注。
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
      upstream_id: number | null
      expires_at: string
      notes: string
    },
  ]
}>()

const form = reactive({
  name: '',
  sub_id: '',
  total_gb: 100,
  residential_gb: 50,
  upstream_id: null as number | null,
  expires_at: '',
  notes: '',
})
const error = ref('')

watch(
  () => props.open,
  (v) => {
    if (!v) return
    error.value = ''
    const e = props.editing
    form.name = e?.name ?? ''
    form.sub_id = e?.sub_id ?? ''
    form.total_gb = e?.total_gb ?? 100
    form.residential_gb = e?.residential_gb ?? 50
    form.upstream_id = e?.upstream_id ?? null
    form.notes = e?.notes ?? ''
    // 新增时默认一个月后；编辑时回填已有到期时间（留空 = 永久有效）。
    form.expires_at = e ? unixToLocalInput(e.expires_at) : monthsFromNowLocal(1)
  },
)

function setError(msg: string) {
  error.value = msg
}
defineExpose({ setError })

function submit() {
  error.value = ''
  if (!form.name.trim()) return (error.value = '请填写用户名')
  if (!props.editing && !form.sub_id.trim()) return (error.value = '请填写订阅名')
  emit('submit', {
    name: form.name.trim(),
    sub_id: form.sub_id.trim(),
    total_gb: Number(form.total_gb) || 0,
    residential_gb: Number(form.residential_gb) || 0,
    upstream_id: form.upstream_id ? Number(form.upstream_id) : null,
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
        请为新用户分配独立的订阅名（英文、数字、- 、_）。额度将在下个结算周期自动重置。
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
      <Field label="住宅额度 (GB)" required>
        <input v-model.number="form.residential_gb" type="number" min="1" class="control" />
      </Field>
      <Field label="绑定家宽">
        <select v-model="form.upstream_id" class="control">
          <option :value="null">无绑定</option>
          <option v-for="u in upstreams" :key="u.id" :value="u.id">
            {{ u.remark || u.host }} ({{ u.protocol }})
          </option>
        </select>
      </Field>
      <Field label="到期时间">
        <DatePicker v-model="form.expires_at" placeholder="点击选择到期日期" />
        <p class="mt-1 font-label-sm text-[11px] text-outline">留空表示永久有效</p>
      </Field>
    </div>

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
