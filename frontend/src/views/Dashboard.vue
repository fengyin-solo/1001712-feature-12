<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常；其中「待检验」「待指派」与检验员工作台、定期检验列表取同一份归属。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card" :class="{ highlight: card.label === '待检验' }">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value" :class="{ warn: card.label === '待指派' && card.value > 0 }">{{ card.value }}</strong>
      </article>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th><th v-if="inspectRow">待检验</th><th v-if="inspectRow">待指派</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
          <td v-if="inspectRow">{{ row.name === 'inspect' ? inspectRow.pending_inspect : '—' }}</td>
          <td v-if="inspectRow">
            <span v-if="row.name === 'inspect'" :class="{ 'unassigned-num': (inspectRow.unassigned ?? 0) > 0 }">{{ inspectRow.unassigned ?? 0 }}</span>
            <span v-else>—</span>
          </td>
        </tr>
      </tbody>
    </table>

    <section v-if="inspectRow" class="ownership-section">
      <h3>定期检验归属分布</h3>
      <p class="section-hint">转派后此处的待检验数会随归属实时变动；检验员工作台与定期检验管理页展示的是同一组数字。</p>
      <table class="data-table">
        <thead>
          <tr><th>检验机构</th><th>在册检验人员</th><th>任务总数</th><th>待检验</th></tr>
        </thead>
        <tbody>
          <tr v-for="org in inspectRow.ownership" :key="org.name">
            <td>{{ org.name }}</td>
            <td>{{ org.inspectors.join('、') }}</td>
            <td>{{ org.total }}</td>
            <td :class="{ 'pending-num': org.pending > 0 }">{{ org.pending }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type OrgOwnership = { name: string; inspectors: string[]; total: number; pending: number }
type ModuleRow = {
  name: string
  created: number
  pending: number
  abnormal: number
  pending_inspect?: number
  unassigned?: number
  ownership?: OrgOwnership[]
}
type Overview = {
  cards: { label: string; value: number }[]
  modules: ModuleRow[]
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<ModuleRow[]>([])

const inspectRow = computed(() => moduleRows.value.find((row) => row.name === 'inspect') ?? null)

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch {
    cards.value = [{ label: '业务模块', value: 0 }, { label: '今日新增', value: 0 }]
    moduleRows.value = []
  }
})
</script>

<style scoped>
.stat-card.highlight {
  border-color: #93c5fd;
  background: #f0f7ff;
}
.warn {
  color: #c2410c;
}
.ownership-section {
  margin-top: 18px;
}
.ownership-section h3 {
  font-size: 15px;
  margin: 8px 0 4px;
}
.section-hint {
  color: var(--muted);
  font-size: 12px;
  margin: 0 0 8px;
}
.pending-num {
  color: #1d4ed8;
  font-weight: 600;
}
.unassigned-num {
  color: #c2410c;
  font-weight: 600;
}
</style>
