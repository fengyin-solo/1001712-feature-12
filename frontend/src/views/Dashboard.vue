<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常；待检验数与检验员工作台、定期检验列表取同一份归属。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card" :class="{ highlight: card.label.includes('待检验') }">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
        <span v-if="card.unassigned" class="stat-extra">待指派 {{ card.unassigned }} 条</span>
      </article>
    </div>

    <section class="org-section">
      <h3>定期检验归属概览（按检验机构）</h3>
      <table class="data-table">
        <thead>
          <tr><th>检验机构</th><th>任务总数</th><th>待检验数</th><th>占全部待检验</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in orgRows" :key="row.org">
            <td>{{ row.org }}</td>
            <td>{{ row.total }}</td>
            <td><strong>{{ row.pending }}</strong></td>
            <td>{{ pendingShare(row.pending) }}</td>
          </tr>
          <tr class="unassigned-row">
            <td>待指派（归属为空）</td>
            <td>{{ ownership?.unassigned ?? 0 }}</td>
            <td>—</td>
            <td>需指派承接机构</td>
          </tr>
        </tbody>
      </table>
      <p class="caption">
        口径说明：此处数字由 /api/inspect/ownership 统一计算，检验员工作台与定期检验列表刷新后展示一致；
        转派一旦提交，待检验数立即在三处同步。
      </p>
    </section>

    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name" :class="{ focus: row.name === 'inspect' }">
          <td>{{ moduleLabel(row.name) }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type Overview = {
  cards: { label: string; value: number; unassigned?: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
  inspect_ownership: {
    total: number
    pending: number
    unassigned: number
    by_org: { org: string; total: number; pending: number }[]
  }
}

const MODULE_LABELS: Record<string, string> = {
  inspect: '定期检验（按归属统计见上表）',
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])
const ownership = ref<Overview['inspect_ownership'] | null>(null)

const orgRows = ref<{ org: string; total: number; pending: number }[]>([])

function moduleLabel(name: string) {
  return MODULE_LABELS[name] ?? name
}

function pendingShare(pending: number) {
  const totalPending = ownership.value?.pending || 0
  if (!totalPending) return '0%'
  return `${Math.round((pending / totalPending) * 100)}%`
}

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
    ownership.value = payload.inspect_ownership
    orgRows.value = payload.inspect_ownership.by_org
  } catch {
    cards.value = [{ label: '业务模块', value: 0 }, { label: '今日新增', value: 0 }]
    moduleRows.value = []
  }
})
</script>

<style scoped>
.stat-card.highlight { border-color: #f59e0b; background: #fffbeb; }
.stat-extra { display: block; font-size: 12px; color: #b54708; margin-top: 2px; }
.org-section { margin-bottom: 16px; }
.org-section h3 { font-size: 14px; margin: 8px 0; }
.unassigned-row td { color: #b54708; background: #fffaeb; }
tr.focus td:first-child { font-weight: 600; }
.caption { font-size: 12px; color: var(--muted); margin: 6px 0 0; }
</style>
