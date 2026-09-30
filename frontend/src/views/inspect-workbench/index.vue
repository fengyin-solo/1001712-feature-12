<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>检验员工作台</h2>
        <p class="page-desc">按当前登录检验员的归属汇总待办；数据与定期检验列表、运营概览取同一份归属，转派后刷新页面结果一致。</p>
      </div>
      <button class="btn" type="button" @click="reload">刷新待办</button>
    </header>

    <div class="identity-banner" :class="{ restricted: !store.isRegisteredInspector }">
      <template v-if="store.isRegisteredInspector">
        {{ store.operator }}，你归属<strong>{{ store.org }}</strong>。这里只列出归属你本人待办与本机构待检验任务；其他机构任务不在本台展示。
      </template>
      <template v-else>
        当前身份「{{ store.operator }}」不是在册检验员，没有可办理的归属任务；可在右上角切换到在册检验员身份。
      </template>
    </div>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">我的待办</span>
        <strong class="stat-value">{{ data?.todo.length ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">本机构待检验</span>
        <strong class="stat-value">{{ data?.org_pending.length ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">待指派（全机构）</span>
        <strong class="stat-value warn">{{ data?.unassigned.length ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">全平台待检验</span>
        <strong class="stat-value">{{ data?.summary.pending ?? 0 }}</strong>
      </article>
    </div>

    <section class="board-section">
      <h3>我的待办（{{ data?.todo.length ?? 0 }}）</h3>
      <table class="data-table">
        <thead>
          <tr><th>检验编号</th><th>检验对象</th><th>检验类别</th><th>状态</th><th>计划检验日</th><th>归属</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in data?.todo ?? []" :key="row.id">
            <td>{{ row['检验编号'] }}</td>
            <td>{{ row['检验对象'] }}</td>
            <td>{{ row['检验类别'] }}</td>
            <td>{{ row.status }}</td>
            <td>{{ row['计划检验日'] ?? '—' }}</td>
            <td>{{ row['检验机构'] }} / {{ row['检验人员'] }}</td>
          </tr>
          <tr v-if="!data?.todo.length"><td colspan="6" class="empty-state">暂无分配给你的待办任务</td></tr>
        </tbody>
      </table>
    </section>

    <section class="board-section">
      <h3>本机构待检验（{{ data?.org_pending.length ?? 0 }}）</h3>
      <p class="section-hint">归属{{ store.org }}、尚未出具结论的任务；仅当前负责人本人可办理，转派后任务会在原负责人待办中消失。</p>
      <table class="data-table">
        <thead>
          <tr><th>检验编号</th><th>检验对象</th><th>检验类别</th><th>状态</th><th>负责人</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in data?.org_pending ?? []" :key="row.id">
            <td>{{ row['检验编号'] }}</td>
            <td>{{ row['检验对象'] }}</td>
            <td>{{ row['检验类别'] }}</td>
            <td>{{ row.status }}</td>
            <td :class="{ 'mine-cell': row['检验人员'] === store.operator }">{{ row['检验人员'] }}</td>
          </tr>
          <tr v-if="!data?.org_pending.length"><td colspan="5" class="empty-state">本机构暂无待检验任务</td></tr>
        </tbody>
      </table>
    </section>

    <section class="board-section">
      <h3>待指派任务（{{ data?.unassigned.length ?? 0 }}）</h3>
      <table class="data-table">
        <thead>
          <tr><th>检验编号</th><th>检验对象</th><th>检验类别</th><th>计划检验日</th><th>状态</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in data?.unassigned ?? []" :key="row.id">
            <td>{{ row['检验编号'] }}</td>
            <td>{{ row['检验对象'] }}</td>
            <td>{{ row['检验类别'] }}</td>
            <td>{{ row['计划检验日'] ?? '—' }}</td>
            <td><span class="unassigned-tag">待指派</span></td>
          </tr>
          <tr v-if="!data?.unassigned.length"><td colspan="5" class="empty-state">没有悬置未指派的任务</td></tr>
        </tbody>
      </table>
      <p class="goto-hint">需要指派或办理？前往 <RouterLink to="/inspect">定期检验管理</RouterLink>。</p>
    </section>

    <section class="board-section">
      <h3>各机构待检验分布（与运营概览同源）</h3>
      <table class="data-table">
        <thead>
          <tr><th>检验机构</th><th>在册检验人员</th><th>任务总数</th><th>待检验</th></tr>
        </thead>
        <tbody>
          <tr v-for="org in data?.summary.organizations ?? []" :key="org.name" :class="{ 'mine-org': org.name === store.org }">
            <td>{{ org.name }}</td>
            <td>{{ org.inspectors.join('、') }}</td>
            <td>{{ org.total }}</td>
            <td>{{ org.pending }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <footer class="page-foot">
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { watch } from 'vue'
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type WorkbenchRow = {
  id: number
  status: string
  '检验编号': string
  '检验对象': string
  '检验类别': string
  '检验机构'?: string | null
  '检验人员'?: string | null
  '计划检验日'?: string | null
}
type WorkbenchData = {
  inspector: string
  org: string | null
  message: string
  todo: WorkbenchRow[]
  org_pending: WorkbenchRow[]
  unassigned: WorkbenchRow[]
  summary: {
    total: number
    pending: number
    unassigned: number
    organizations: { name: string; inspectors: string[]; total: number; pending: number }[]
  }
}

const store = useSessionStore()
const data = ref<WorkbenchData | null>(null)
const errorMessage = ref('')

async function reload() {
  errorMessage.value = ''
  try {
    const response = await request(`/api/inspect/workbench?inspector=${encodeURIComponent(store.operator)}`)
    if (!response.ok) throw new Error('工作台数据读取失败')
    data.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '工作台数据读取失败'
  }
}

// 切换检验员身份后立刻按新归属刷新；同时挂载时也拉一次。
watch(() => store.operator, reload)
onMounted(async () => {
  await store.loadDirectory()
  await reload()
})
</script>

<style scoped>
.identity-banner {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1e40af;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  margin-bottom: 12px;
}
.identity-banner.restricted {
  background: #fef3f2;
  border-color: #fecdca;
  color: #b42318;
}
.board-section {
  margin-bottom: 18px;
}
.board-section h3 {
  font-size: 15px;
  margin: 8px 0 6px;
}
.section-hint,
.goto-hint {
  color: var(--muted);
  font-size: 12px;
  margin: 4px 0;
}
.warn {
  color: #c2410c;
}
.mine-cell {
  color: #15803d;
  font-weight: 600;
}
.mine-org {
  background: #f0fdf4;
}
.unassigned-tag {
  display: inline-block;
  background: #fff7ed;
  color: #c2410c;
  border: 1px solid #fed7aa;
  border-radius: 10px;
  padding: 1px 8px;
  font-size: 12px;
}
</style>
