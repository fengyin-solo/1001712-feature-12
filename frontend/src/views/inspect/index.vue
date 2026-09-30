<template>
  <section class="page" data-module="inspect">
    <header class="page-head">
      <div>
        <h2>定期检验管理</h2>
        <p class="page-desc">
          检验任务绑定检验类别、检验机构与检验人员。仅归属本机构的检验员可变更任务，
          其他机构人员受控查看；归属变更后工作台待办与运营概览待检验数同步更新。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="exportRows">导出定期检验清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card" :class="{ highlight: item.highlight }">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div v-if="!session.current" class="notice-bar warn">
      未选择检验人员身份：当前只能查看任务，任何变更与转派都会被拦截。请在右上角选择身份后操作。
    </div>

    <div class="filter-bar">
      <div class="scope-tabs">
        <button
          v-for="item in scopeOptions"
          :key="item.value"
          class="btn"
          :class="{ primary: scope === item.value }"
          type="button"
          @click="switchScope(item.value)"
        >
          {{ item.label }}<span v-if="item.value === 'unassigned' && ownership">（{{ ownership.unassigned }}）</span>
        </button>
      </div>
      <label class="filter-item">
        <span>检验状态</span>
        <select v-model="statusFilter" @change="reload">
          <option value="">全部状态</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>检验编号</span>
        <input v-model="keyword" placeholder="按检验编号检索" @keyup.enter="reload" />
      </label>
      <button class="btn" type="button" @click="reload">查询</button>
    </div>

    <div v-if="errorMessage" class="notice-bar warn">{{ errorMessage }}</div>

    <TaskTable
      ref="tableRef"
      :rows="rows"
      :inspectors="session.inspectors"
      :allow-assign="scope === 'unassigned'"
      @action="runAction"
      @changed="reload"
    />

    <footer class="page-foot">
      <span>共 {{ total }} 条定期检验记录 · 当前归属范围：{{ scopeLabel }}</span>
      <span v-if="session.current">当前身份：{{ session.current.姓名 }}（{{ session.current.检验机构 }}）</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { postAction, request } from '@/api/client'
import { useSessionStore } from '@/stores/session'
import TaskTable from '@/views/inspect/TaskTable.vue'

type Row = Record<string, unknown>
type Ownership = {
  total: number
  pending: number
  unassigned: number
  by_org: { org: string; total: number; pending: number }[]
}

const ENDPOINT = '/api/inspect'
const statuses = ['待报检', '检验中', '已出具', '已退回']
const scopeOptions = [
  { value: 'all', label: '全部任务' },
  { value: 'mine', label: '本机构归属' },
  { value: 'unassigned', label: '待指派' },
] as const

const session = useSessionStore()
const tableRef = ref<InstanceType<typeof TaskTable> | null>(null)
const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const scope = ref<(typeof scopeOptions)[number]['value']>('all')
const ownership = ref<Ownership | null>(null)

const scopeLabel = computed(() => scopeOptions.find((item) => item.value === scope.value)?.label ?? '')

const stats = computed(() => {
  const byOrg = ownership.value?.by_org ?? []
  const cards = [
    { label: '检验任务总数', value: ownership.value?.total ?? 0, highlight: false },
    { label: '待检验（全机构）', value: ownership.value?.pending ?? 0, highlight: false },
    { label: '待指派（归属为空）', value: ownership.value?.unassigned ?? 0, highlight: true },
  ]
  for (const item of byOrg) {
    cards.push({ label: `待检验 · ${item.org}`, value: item.pending, highlight: false })
  }
  return cards
})

function switchScope(next: typeof scope.value) {
  scope.value = next
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const result = await postAction(`${ENDPOINT}/${row.id}/actions`, { values: { action } })
    if (!result.ok) {
      throw new Error(result.message)
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '定期检验操作未生效'
  }
}

async function loadOwnership() {
  try {
    const response = await request(`${ENDPOINT}/ownership`)
    if (response.ok) {
      ownership.value = await response.json()
    }
  } catch {
    // 归属卡片取不到时不阻塞列表
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  if (statusFilter.value) query.set('status', statusFilter.value)
  query.set('scope', scope.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload?.detail ?? '检验任务列表读取失败')
    }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '定期检验列表读取失败'
  }
  await loadOwnership()
}

onMounted(async () => {
  await session.loadRoster()
  await reload()
})
</script>

<style scoped>
.notice-bar { border-radius: 8px; padding: 10px 12px; font-size: 13px; margin-bottom: 12px; }
.notice-bar.warn { background: #fff7ed; border: 1px solid #fdba74; color: #9a3412; }
.scope-tabs { display: flex; gap: 6px; align-items: center; }
.stat-card.highlight { border-color: #f59e0b; background: #fffbeb; }
.filter-item select { border: 1px solid var(--border); border-radius: 6px; padding: 5px 8px; font-size: 13px; }
</style>
