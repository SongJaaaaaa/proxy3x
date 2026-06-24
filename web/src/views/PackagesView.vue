<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { useDashboardStore } from '@/stores/dashboard'
import { usePolling } from '@/composables/usePolling'
import type { Package } from '@/types/dashboard'
import { ApiError } from '@/api/errors'
import AppShell from '@/components/layout/AppShell.vue'
import Button from '@/components/ui/Button.vue'
import Icon from '@/components/ui/Icon.vue'
import Pagination from '@/components/ui/Pagination.vue'
import PackageTable from '@/components/domain/PackageTable.vue'
import PackageFormDialog from '@/components/domain/dialogs/PackageFormDialog.vue'
import ConfirmDialog from '@/components/domain/dialogs/ConfirmDialog.vue'

/**
 * 用户套餐页（对应 stitch proxy3x_2）。表格 + 顶部 新增用户/额度巡检/刷新订阅。
 * 绑定 SOCKS5 下拉直接保存；编辑/删除走弹框。
 */
const store = useDashboardStore()
usePolling(() => store.refresh(), 15000)

// 搜索 + 状态筛选
const keyword = ref('')
const statusFilter = ref<'all' | 'active' | 'expired' | 'disabled'>('all')

const filteredPackages = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  return store.packages.filter((p) => {
    const matchKw =
      !k ||
      p.name.toLowerCase().includes(k) ||
      p.sub_id.toLowerCase().includes(k) ||
      (p.notes || '').toLowerCase().includes(k)
    const matchStatus =
      statusFilter.value === 'all' ||
      (statusFilter.value === 'expired' && p.expired) ||
      (statusFilter.value === 'active' && p.enabled && !p.expired) ||
      (statusFilter.value === 'disabled' && !p.enabled)
    return matchKw && matchStatus
  })
})

// 分页：默认每页 10 条，可调
const page = ref(1)
const pageSize = ref(10)
const pagedPackages = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredPackages.value.slice(start, start + pageSize.value)
})
// 搜索/筛选变化回到第 1 页
watch([keyword, statusFilter], () => {
  page.value = 1
})
// 数据或每页条数变化时，夹住页码不越界
watch([filteredPackages, pageSize], () => {
  const tp = Math.max(1, Math.ceil(filteredPackages.value.length / pageSize.value))
  if (page.value > tp) page.value = tp
})

const formOpen = ref(false)
const editing = ref<Package | null>(null)
const formRef = ref<InstanceType<typeof PackageFormDialog> | null>(null)
const submitting = ref(false)

const confirmOpen = ref(false)
const removing = ref<Package | null>(null)
const removingBusy = ref(false)

const enforcing = ref(false)
const regenerating = ref(false)

function openCreate() {
  editing.value = null
  formOpen.value = true
}
function openEdit(p: Package) {
  editing.value = p
  formOpen.value = true
}

async function onSubmit(payload: {
  name: string
  sub_id: string
  total_gb: number
  residential_gb: number
  upstream_id: number | null
  expires_at: string
  notes: string
}) {
  submitting.value = true
  try {
    if (editing.value) {
      await store.updatePackage(editing.value.id, {
        name: payload.name,
        total_gb: payload.total_gb,
        residential_gb: payload.residential_gb,
        upstream_id: payload.upstream_id,
        expires_at: payload.expires_at || null,
        notes: payload.notes,
      })
      toast.success('已保存')
    } else {
      const msg = await store.createPackage({
        name: payload.name,
        sub_id: payload.sub_id,
        total_gb: payload.total_gb,
        residential_gb: payload.residential_gb,
        upstream_id: payload.upstream_id,
        expires_at: payload.expires_at || null,
        notes: payload.notes,
      })
      toast.success(msg || '已创建用户')
    }
    formOpen.value = false
  } catch (e) {
    formRef.value?.setError(e instanceof ApiError ? e.message : '操作失败')
  } finally {
    submitting.value = false
  }
}

async function onBind(p: Package, upstreamId: number | null) {
  try {
    await store.updatePackage(p.id, {
      name: p.name,
      total_gb: p.total_gb,
      residential_gb: p.residential_gb,
      notes: p.notes,
      upstream_id: upstreamId,
      expires_at: p.expires_at || null,
    })
    toast.success('已更新绑定 SOCKS5')
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '更新失败')
    await store.refresh()
  }
}

function askRemove(p: Package) {
  removing.value = p
  confirmOpen.value = true
}
async function onRemove() {
  if (!removing.value) return
  removingBusy.value = true
  try {
    const msg = await store.deletePackage(removing.value.id)
    toast.success(msg || '已删除套餐')
    confirmOpen.value = false
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '删除失败')
  } finally {
    removingBusy.value = false
  }
}

async function onEnforce() {
  enforcing.value = true
  try {
    toast.success(await store.enforce())
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '巡检失败')
  } finally {
    enforcing.value = false
  }
}
async function onRegenerate() {
  regenerating.value = true
  try {
    toast.success(await store.regenerate())
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : '刷新失败')
  } finally {
    regenerating.value = false
  }
}
</script>

<template>
  <AppShell title="用户套餐" subtitle="管理列表">
    <template #actions>
      <Button variant="ghost" :loading="enforcing" @click="onEnforce">
        <Icon name="verified" :size="18" />额度巡检
      </Button>
      <Button variant="ghost" :loading="regenerating" @click="onRegenerate">
        <Icon name="sync" :size="18" />刷新订阅
      </Button>
      <Button variant="primary" @click="openCreate">
        <Icon name="add" :size="18" />新增用户
      </Button>
    </template>

    <!-- 搜索 + 筛选 -->
    <div class="flex items-center gap-3 flex-wrap shrink-0">
      <div class="relative w-72 max-w-full">
        <Icon name="search" :size="18" class="absolute left-3 top-1/2 -translate-y-1/2 text-outline" />
        <input v-model="keyword" class="control pl-9" placeholder="搜索用户 / 订阅 / 备注…" />
      </div>
      <div class="flex items-center gap-1 glass-panel rounded-lg p-1">
        <button
          v-for="opt in [
            { v: 'all', t: '全部' },
            { v: 'active', t: '正常' },
            { v: 'expired', t: '已到期' },
            { v: 'disabled', t: '已停用' },
          ]"
          :key="opt.v"
          class="px-3 h-8 rounded text-sm font-label-sm transition-colors"
          :class="
            statusFilter === opt.v
              ? 'bg-primary-container/30 text-secondary-fixed-dim'
              : 'text-on-surface-variant hover:text-on-surface'
          "
          @click="statusFilter = opt.v as typeof statusFilter"
        >
          {{ opt.t }}
        </button>
      </div>
      <span class="ml-auto font-label-sm text-label-sm text-outline">
        共 {{ filteredPackages.length }} / {{ store.packages.length }} 条
      </span>
    </div>

    <!-- 表格：占满剩余高度，内部滚动 -->
    <div class="flex-1 min-h-0 flex flex-col">
      <PackageTable
        :packages="pagedPackages"
        :upstreams="store.upstreams"
        @edit="openEdit"
        @remove="askRemove"
        @bind="onBind"
      />
    </div>

    <!-- 分页 -->
    <Pagination
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="filteredPackages.length"
      :page-size-options="[10, 20, 50, 100]"
    />

    <PackageFormDialog
      ref="formRef"
      :open="formOpen"
      :editing="editing"
      :upstreams="store.upstreams"
      :busy="submitting"
      @close="formOpen = false"
      @submit="onSubmit"
    />
    <ConfirmDialog
      :open="confirmOpen"
      title="删除用户套餐"
      :message="`确定删除套餐「${removing?.name}」？将删除其订阅文件、入站节点和流量记录，操作不可恢复。`"
      :busy="removingBusy"
      @close="confirmOpen = false"
      @confirm="onRemove"
    />
  </AppShell>
</template>
