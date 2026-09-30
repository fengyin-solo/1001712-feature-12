<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>检验员工作台</h2>
        <p class="page-desc">
          待办与运营概览、定期检验列表取同一份归属：只展示归属本机构的任务，待指派任务单独列出。
        </p>
      </div>
      <button class="btn ghost" type="button" @click="reload">刷新归属</button>
    </header>

    <div v-if="!identity" class="notice-bar warn">
      尚未选择检验人员身份，工作台无法判断任务归属。请在右上角选择一名在岗检验员，归属将随刷新与重新打开保持一致。
    </div>

    <template v-else>
      <div class="identity-banner">
        <span>{{ identity.姓名 }}（{{ identity.人员编号 }}）</span>
        <span>{{ identity.检验机构 }}</span>
        <span>承接类别：{{ identity.检验类别 }}</span>
        <span>{{ identity.岗位 }}</span>
      </div>

      <div class="stat-row">
        <article class="stat-card">
          <span class="stat-label">本机构待检验</span>
          <strong class="stat-value">{{ counters.org_pending }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">指派给我的任务</span>
          <strong class="stat-value">{{ counters.my_tasks }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">本机构其他同事任务</span>
          <strong class="stat-value">{{ counters.org_tasks }}</strong>
        </article>
        <article class="stat-card highlight">
          <span class="stat-label">待指派（归属为空）</span>
          <strong class="stat-value">{{ counters.unassigned }}</strong>
        </article>
      </div>

      <div v-if="errorMessage" class="notice-bar warn">{{ errorMessage }}</div>

      <section class="board-section">
        <h3>我的待办（归属我本人）</h3>
        <TaskTable :rows="myTasks" :inspectors="session.inspectors" @action="runAction" @changed="reload" />
      </section>

      <section class="board-section">
        <h3>本机构任务（可查看，仅负责人本人可变更）</h3>
        <TaskTable :rows="orgTasks" :inspectors="session.inspectors" @action="runAction" @changed="reload" />
      </section>

      <section class="board-section">
        <h3>待指派任务（归属机构与负责人均为空）</h3>
        <TaskTable :rows="unassigned" :inspectors="session.inspectors" :allow-assign="true" @changed="reload" />
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { fetchJson, postAction } from '@/api/client'
import { useSessionStore } from '@/stores/session'
import TaskTable from '@/views/inspect/TaskTable.vue'

type TaskRow = Record<string, unknown>
type Workbench = {
  identity: { 人员编号: string; 姓名: string; 检验机构: string; 检验类别: string; 岗位: string }
  counters: { org_pending: number; my_tasks: number; org_tasks: number; unassigned: number }
  my_tasks: TaskRow[]
  org_tasks: TaskRow[]
  unassigned: TaskRow[]
}

const session = useSessionStore()
const identity = ref<Workbench['identity'] | null>(null)
const counters = ref({ org_pending: 0, my_tasks: 0, org_tasks: 0, unassigned: 0 })
const myTasks = ref<TaskRow[]>([])
const orgTasks = ref<TaskRow[]>([])
const unassigned = ref<TaskRow[]>([])
const errorMessage = ref('')

async function reload() {
  errorMessage.value = ''
  if (!session.inspectorId) {
    identity.value = null
    return
  }
  try {
    const payload = await fetchJson<Workbench>('/api/inspect/workbench')
    identity.value = payload.identity
    counters.value = payload.counters
    myTasks.value = payload.my_tasks
    orgTasks.value = payload.org_tasks
    unassigned.value = payload.unassigned
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '工作台加载失败'
  }
}

async function runAction(action: string, row: TaskRow) {
  errorMessage.value = ''
  try {
    await postAction(`/api/inspect/${row.id}/actions`, { values: { action } })
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '操作未生效'
  }
}

watch(() => session.inspectorId, () => void reload())
onMounted(async () => {
  await session.loadRoster()
  await reload()
})
</script>

<style scoped>
.notice-bar { border-radius: 8px; padding: 10px 12px; font-size: 13px; margin-bottom: 12px; }
.notice-bar.warn { background: #fff7ed; border: 1px solid #fdba74; color: #9a3412; }
.identity-banner {
  display: flex; gap: 16px; flex-wrap: wrap;
  background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px;
  padding: 8px 12px; font-size: 13px; margin-bottom: 12px;
}
.stat-card.highlight { border-color: #f59e0b; background: #fffbeb; }
.board-section { margin-bottom: 18px; }
.board-section h3 { font-size: 14px; margin: 8px 0; }
</style>
