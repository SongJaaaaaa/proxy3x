<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import type { Upstream } from '@/types/dashboard'
import { monthsFromNowLocal, unixToLocalInput } from '@/lib/format'
import Modal from '@/components/ui/Modal.vue'
import Field from '@/components/ui/Field.vue'
import Button from '@/components/ui/Button.vue'
import Icon from '@/components/ui/Icon.vue'
import DatePicker from '@/components/ui/DatePicker.vue'

/**
 * 新增/编辑 SOCKS5 弹框（对应 stitch proxy3x_6）。
 * - 新增：SOCKS5 节点(socks5://账号:密码@IP:端口) + 备注 + 额度(GB, 0=无限制)。
 * - 编辑：仅备注 + 额度（节点行已不可改，与后端 PUT 接口一致）。
 * 失败原因内联显示。提交逻辑由父组件处理（emit submit）。
 */
const props = defineProps<{ open: boolean; editing?: Upstream | null; busy?: boolean }>()
const emit = defineEmits<{
  close: []
  submit: [payload: { line: string; remark: string; quota_gb: number; expires_at: string }]
}>()

const form = reactive({ line: '', remark: '', quota_gb: 0, expires_at: '' })
const error = ref('')

watch(
  () => props.open,
  (v) => {
    if (v) {
      error.value = ''
      if (props.editing) {
        form.line = ''
        form.remark = props.editing.remark
        form.quota_gb = props.editing.quota_gb
        form.expires_at = unixToLocalInput(props.editing.expires_at)
      } else {
        form.line = ''
        form.remark = ''
        form.quota_gb = 0
        form.expires_at = monthsFromNowLocal(1)
      }
    }
  },
)

function setError(msg: string) {
  error.value = msg
}
defineExpose({ setError })

function submit() {
  error.value = ''
  if (!props.editing && !form.line.trim()) {
    error.value = '请填写至少一条节点'
    return
  }
  emit('submit', {
    line: form.line.trim(),
    remark: form.remark.trim(),
    quota_gb: Number(form.quota_gb) || 0,
    expires_at: form.expires_at,
  })
}
</script>

<template>
  <Modal
    :open="open"
    :title="editing ? '编辑 SOCKS5' : '新增 SOCKS5'"
    :icon="editing ? 'edit' : 'add_circle'"
    icon-tone="purple"
    @close="emit('close')"
  >
    <!-- 系统提示 -->
    <div class="rounded-lg border border-primary/20 bg-primary/5 p-3 flex gap-3">
      <Icon name="info" :size="20" class="text-primary shrink-0 mt-0.5" />
      <div class="font-body-md text-sm text-on-surface-variant leading-relaxed">
        <p class="font-semibold text-on-surface mb-0.5">系统提示</p>
        <template v-if="editing">仅可修改备注、额度与到期时间。额度为 0 表示无限制（不显示进度）。</template>
        <template v-else
          >当前版本只支持 SOCKS5。添加后可点击检测确认连通性。</template
        >
      </div>
    </div>

    <Field v-if="!editing" label="SOCKS5 节点" required hint="格式：socks5://账号:密码@IP:端口">
      <textarea
        v-model="form.line"
        class="control min-h-[120px]"
        placeholder="socks5://user:pass@192.168.1.100:1080"
      ></textarea>
    </Field>

    <div class="grid grid-cols-2 gap-4">
      <Field label="备注">
        <input v-model="form.remark" class="control" placeholder="例如：主 SOCKS5 出口" />
      </Field>
      <Field label="额度 (GB)" hint="0 为无限制">
        <input v-model.number="form.quota_gb" type="number" min="0" step="1" class="control" placeholder="0" />
      </Field>
      <Field label="到期时间">
        <DatePicker v-model="form.expires_at" placeholder="点击选择到期日期" />
      </Field>
    </div>

    <p v-if="error" class="font-body-md text-sm text-error">{{ error }}</p>

    <template #footer>
      <Button variant="ghost" @click="emit('close')">取消</Button>
      <Button variant="primary" :loading="busy" @click="submit">确认</Button>
    </template>
  </Modal>
</template>
