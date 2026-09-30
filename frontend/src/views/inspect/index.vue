<template>
  <section class="page" data-module="inspect">
    <header class="page-head">
      <div>
        <h2>定期检验管理</h2>
        <p class="page-desc">每条检验任务绑定检验类别、检验机构与检验人员；仅归属本机构的检验人员可变更，其他人员只读并看到受控提示。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记检验任务</button>
        <button class="btn" type="button" @click="exportRows">导出定期检验清单</button>
      </div>
    </header>

    <div class="identity-banner" :class="{ restricted: !store.isRegisteredInspector }">
      <template v-if="store.isRegisteredInspector">
        当前身份：<strong>{{ store.operator }}</strong>（{{ store.org }}）。只能变更归属本机构且由你负责的任务；归属其他机构的任务只读。
      </template>
      <template v-else>
        当前身份「{{ store.operator }}」不属于任何检验机构在册人员，全部任务<strong>只读受控</strong>，不能提交变更。
      </template>
    </div>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value" :class="{ warn: item.warn }">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>检验编号</span>
        <input v-model="keyword" placeholder="按检验编号检索" />
      </label>
      <label class="filter-item">
        <span>检验状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>归属机构</span>
        <select v-model="orgFilter">
          <option value="">全部机构</option>
          <option v-for="org in store.directory.organizations" :key="org.name" :value="org.name">{{ org.name }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <section class="assign-section">
      <h3>待指派（归属为空，{{ unassignedRows.length }} 条）</h3>
      <p class="section-hint">这些任务尚未绑定归属机构与检验人员，任一在册检验员均可查看并发起指派；指派后归属立即同步到检验员工作台与运营概览。</p>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
            <th>归属操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in unassignedRows" :key="String(row.id)">
            <td v-for="column in columns" :key="column">
              <template v-if="column === '检验机构' || column === '检验人员'">
                <span class="unassigned-tag">待指派</span>
              </template>
              <template v-else>{{ display(row, column) }}</template>
            </td>
            <td class="row-actions">
              <button class="link" type="button" @click="openDetail(row)">查看</button>
              <button class="link" type="button" :disabled="!store.isRegisteredInspector" @click="openAssign(row)">
                指派归属
              </button>
              <span v-if="!store.isRegisteredInspector" class="controlled-inline">受控只读</span>
            </td>
          </tr>
          <tr v-if="!unassignedRows.length">
            <td :colspan="columns.length + 1" class="empty-state">没有待指派任务，归属已全部落实</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="task-section">
      <h3>已归属任务（{{ assignedRows.length }} 条）</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
            <th>归属与操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in assignedRows" :key="String(row.id)" :class="{ 'mine-row': canChange(row) }">
            <td v-for="column in columns" :key="column">{{ display(row, column) }}</td>
            <td class="row-actions">
              <button class="link" type="button" @click="openDetail(row)">查看/记录</button>
              <template v-if="canChange(row)">
                <button
                  v-for="action in availableActions(row)"
                  :key="action"
                  class="link"
                  type="button"
                  @click="openAction(action, row)"
                >
                  {{ action }}
                </button>
                <button class="link" type="button" @click="openAssign(row)">转派</button>
              </template>
              <span v-else class="controlled-inline">{{ controlReason(row) }}</span>
            </td>
          </tr>
          <tr v-if="!assignedRows.length">
            <td :colspan="columns.length + 1" class="empty-state">暂无符合条件的已归属检验任务</td>
          </tr>
        </tbody>
      </table>
    </section>

    <footer class="page-foot">
      <span>共 {{ total }} 条检验任务 · 待检验 {{ stats[1].value }} 条（与工作台、运营概览同源）</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="successMessage" class="success-text">{{ successMessage }}</span>
    </footer>

    <!-- 流转动作：确认出具/退回重检必须录检验结论 -->
    <div v-if="dialog.kind" class="modal-mask" @click.self="closeDialog">
      <div class="modal">
        <h3>{{ dialogTitle }}</h3>
        <p class="modal-target">任务 {{ dialog.row?.['检验编号'] }} · 当前归属 {{ dialog.row?.['检验机构'] }} / {{ dialog.row?.['检验人员'] }}</p>

        <template v-if="dialog.kind === 'action'">
          <p class="modal-tip">将以当前身份 <strong>{{ store.operator }}（{{ store.org }}）</strong> 提交，服务端会再次校验归属。</p>
          <label v-if="needConclusion" class="modal-field">
            <span>检验结论 <em>*</em></span>
            <textarea v-model="dialog.conclusion" rows="4" placeholder="填写本次检验结论；交接时将随任务一并保留"></textarea>
          </label>
        </template>

        <template v-else-if="dialog.kind === 'assign'">
          <p class="modal-tip">{{ isReassign ? '转派后原负责人将不能再改动该任务；历史记录与检验结论按原归属保留。' : '归属为空，指派后任务进入新机构待办。' }}</p>
          <label class="modal-field">
            <span>转入检验机构 <em>*</em></span>
            <select v-model="dialog.targetOrg" @change="dialog.targetInspector = ''">
              <option value="" disabled>请选择机构</option>
              <option v-for="org in store.directory.organizations" :key="org.name" :value="org.name">{{ org.name }}</option>
            </select>
          </label>
          <label class="modal-field">
            <span>转入检验人员 <em>*</em></span>
            <select v-model="dialog.targetInspector">
              <option value="" disabled>请选择检验人员</option>
              <option v-for="name in inspectorsOf(dialog.targetOrg)" :key="name" :value="name">{{ name }}</option>
            </select>
          </label>
          <label class="modal-field">
            <span>交接说明</span>
            <textarea v-model="dialog.note" rows="2" placeholder="可选：交接给下一任负责人的说明"></textarea>
          </label>
        </template>

        <template v-else-if="dialog.kind === 'create'">
          <div class="modal-grid">
            <label class="modal-field">
              <span>检验编号 <em>*</em></span>
              <input v-model="createForm['检验编号']" placeholder="如 INSP-2026-0008" />
            </label>
            <label class="modal-field">
              <span>检验对象 <em>*</em></span>
              <input v-model="createForm['检验对象']" placeholder="设备或管道名称" />
            </label>
            <label class="modal-field">
              <span>检验类别 <em>*</em></span>
              <select v-model="createForm['检验类别']">
                <option value="" disabled>请选择类别</option>
                <option v-for="cat in store.directory.categories" :key="cat" :value="cat">{{ cat }}</option>
              </select>
            </label>
            <label class="modal-field">
              <span>计划检验日</span>
              <input v-model="createForm['计划检验日']" type="date" />
            </label>
            <label class="modal-field">
              <span>归属机构（可空）</span>
              <select v-model="createForm['检验机构']" @change="createForm['检验人员'] = ''">
                <option value="">暂不指派（进入待指派）</option>
                <option v-for="org in store.directory.organizations" :key="org.name" :value="org.name">{{ org.name }}</option>
              </select>
            </label>
            <label class="modal-field">
              <span>检验人员（可空）</span>
              <select v-model="createForm['检验人员']">
                <option value="">暂不指派</option>
                <option v-for="name in inspectorsOf(createForm['检验机构'])" :key="name" :value="name">{{ name }}</option>
              </select>
            </label>
          </div>
        </template>

        <div class="modal-actions">
          <button class="btn" type="button" @click="closeDialog">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitDialog">
            {{ submitting ? '提交中…' : '确认提交' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 明细抽屉：归属信息 + 检验结论 + 完整交接历史 -->
    <div v-if="detailRow" class="modal-mask" @click.self="detailRow = null">
      <div class="drawer">
        <h3>检验任务明细 · {{ detailRow['检验编号'] }}</h3>
        <dl class="detail-grid">
          <template v-for="field in detailFields" :key="field">
            <dt>{{ field }}</dt>
            <dd :class="{ 'unassigned-dd': (field === '检验机构' || field === '检验人员') && !detailRow[field] }">
              {{ detailRow[field] || (field === '检验机构' || field === '检验人员' ? '待指派' : '—') }}
            </dd>
          </template>
        </dl>
        <h4>检验结论</h4>
        <p class="conclusion-box">{{ detailRow['检验结论'] || '暂未出具结论（确认出具或退回重检时录入并永久保留）' }}</p>
        <h4>流转与交接历史（{{ detailLogs.length }} 条，历史记录挂在原机构名下）</h4>
        <ul class="log-list">
          <li v-for="(log, idx) in detailLogs" :key="idx" class="log-item">
            <div class="log-head">
              <strong>{{ log.action }}</strong>
              <span>{{ log.time }} · {{ log.operator_org }} / {{ log.operator }}</span>
            </div>
            <div class="log-detail">{{ log.detail }}</div>
            <div class="log-snap">办理时归属：{{ log.owning_org }} / {{ log.assignee }}<template v-if="log.conclusion"> · 结论：{{ log.conclusion }}</template></div>
          </li>
          <li v-if="!detailLogs.length" class="empty-state">该任务暂无流转记录</li>
        </ul>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="detailRow = null">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type LogEntry = {
  time: string
  operator: string
  operator_org: string
  action: string
  detail: string
  owning_org: string
  assignee: string
  conclusion: string
}
type Row = {
  id: number
  status: string
  检验编号: string
  检验对象?: string | null
  检验类别?: string | null
  检验机构?: string | null
  计划检验日?: string | null
  检验人员?: string | null
  检验日期?: string | null
  检验结论?: string | null
  检验状态?: string | null
  logs?: LogEntry[]
  [key: string]: string | number | boolean | null | LogEntry[] | undefined
}

const store = useSessionStore()
const ENDPOINT = '/api/inspect'

const columns = ['检验编号', '检验对象', '检验类别', '检验机构', '计划检验日', '检验人员', '检验状态', '检验结论']
const detailFields = ['检验编号', '检验对象', '检验类别', '检验机构', '检验人员', '计划检验日', '检验日期', '检验状态']
const statuses = ['待报检', '检验中', '已出具', '已退回']

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const successMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const orgFilter = ref('')
const detailRow = ref<Row | null>(null)
const submitting = ref(false)

type DialogState = {
  kind: '' | 'action' | 'assign' | 'create'
  action: string
  row: Row | null
  conclusion: string
  targetOrg: string
  targetInspector: string
  note: string
}

const dialog = reactive<DialogState>({
  kind: '',
  action: '',
  row: null,
  conclusion: '',
  targetOrg: '',
  targetInspector: '',
  note: '',
})

const createForm = reactive<Record<string, string>>({
  检验编号: '',
  检验对象: '',
  检验类别: '',
  计划检验日: '',
  检验机构: '',
  检验人员: '',
})

const stats = computed(() => [
  { label: '检验任务总数', value: rows.value.length, warn: false },
  { label: '待检验（未出具，含退回重检）', value: rows.value.filter((row) => row.status !== '已出具').length, warn: false },
  { label: '待指派', value: unassignedRows.value.length, warn: unassignedRows.value.length > 0 },
  { label: '退回重检', value: rows.value.filter((row) => row.status === '已退回').length, warn: rows.value.some((row) => row.status === '已退回') },
])

const unassignedRows = computed(() => rows.value.filter((row) => !row['检验机构'] || !row['检验人员']))
const assignedRows = computed(() => rows.value.filter((row) => row['检验机构'] && row['检验人员']))

const dialogTitle = computed(() => {
  if (dialog.kind === 'action') return `执行动作：${dialog.action}`
  if (dialog.kind === 'assign') return isReassign.value ? '转派检验任务' : '指派任务归属'
  if (dialog.kind === 'create') return '登记检验任务'
  return ''
})
const needConclusion = computed(() => ['确认出具', '退回重检'].includes(dialog.action))
const isReassign = computed(() => Boolean(dialog.row?.['检验机构'] && dialog.row?.['检验人员']))
const detailLogs = computed<LogEntry[]>(() => (detailRow.value?.logs as LogEntry[] | undefined) ?? [])

function inspectorsOf(org: string): string[] {
  return store.directory.organizations.find((item) => item.name === org)?.inspectors ?? []
}

function display(row: Row, column: string): string {
  if (column === '检验状态') return String(row.status ?? '—')
  const value = row[column]
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

// 前端只做按钮级收敛与提示；真正的归属校验在服务端，绕过页面提交同样会被拦。
function canChange(row: Row): boolean {
  return Boolean(
    store.isRegisteredInspector
      && row['检验机构'] === store.org
      && row['检验人员'] === store.operator
      && ['待报检', '检验中', '已退回'].includes(row.status),
  )
}

function controlReason(row: Row): string {
  if (!store.isRegisteredInspector) return '受控只读：非在册检验人员'
  if (row['检验机构'] !== store.org) return `受控只读：归属${row['检验机构']}`
  if (row['检验人员'] !== store.operator) return `受控只读：负责人${row['检验人员']}`
  if (row.status === '已出具') return '已出具归档'
  return '受控只读'
}

function availableActions(row: Row): string[] {
  if (row.status === '待报检') return ['提交报检']
  if (row.status === '检验中') return ['确认出具', '退回重检']
  if (row.status === '已退回') return ['提交报检']
  return []
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  orgFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  if (!store.isRegisteredInspector) {
    errorMessage.value = '当前身份不是在册检验员，不能登记检验任务'
    return
  }
  Object.assign(createForm, {
    检验编号: '',
    检验对象: '',
    检验类别: '',
    计划检验日: '',
    检验机构: '',
    检验人员: '',
  })
  dialog.kind = 'create'
}

function openAction(action: string, row: Row) {
  dialog.kind = 'action'
  dialog.action = action
  dialog.row = row
  dialog.conclusion = ''
}

function openAssign(row: Row) {
  dialog.kind = 'assign'
  dialog.row = row
  dialog.action = ''
  dialog.targetOrg = row['检验机构'] ?? ''
  dialog.targetInspector = row['检验人员'] ?? ''
  dialog.note = ''
}

function openDetail(row: Row) {
  detailRow.value = row
  void reloadDetail(row.id)
}

function closeDialog() {
  dialog.kind = ''
  dialog.row = null
}

async function reloadDetail(id: number) {
  try {
    const response = await request(`${ENDPOINT}/${id}`)
    if (response.ok) {
      const fresh = (await response.json()) as Row
      detailRow.value = fresh
      const inList = rows.value.find((row) => row.id === id)
      if (inList) Object.assign(inList, fresh)
    }
  } catch {
    // 抽屉保留列表里已有的快照数据
  }
}

async function submitDialog() {
  if (!dialog.row && dialog.kind !== 'create') return
  errorMessage.value = ''
  successMessage.value = ''
  try {
    submitting.value = true
    let response: Response
    if (dialog.kind === 'action') {
      if (needConclusion.value && !dialog.conclusion.trim()) {
        errorMessage.value = '确认出具/退回重检前必须填写检验结论'
        return
      }
      response = await request(`${ENDPOINT}/${dialog.row!.id}/actions`, {
        method: 'POST',
        body: JSON.stringify({
          values: { action: dialog.action, actor: store.operator, conclusion: dialog.conclusion },
        }),
      })
    } else if (dialog.kind === 'assign') {
      if (!dialog.targetOrg || !dialog.targetInspector) {
        errorMessage.value = '必须同时选择转入机构与检验人员'
        return
      }
      response = await request(`${ENDPOINT}/${dialog.row!.id}/assignment`, {
        method: 'POST',
        body: JSON.stringify({
          values: {
            actor: store.operator,
            target_org: dialog.targetOrg,
            target_inspector: dialog.targetInspector,
            note: dialog.note,
          },
        }),
      })
    } else {
      response = await request(ENDPOINT, {
        method: 'POST',
        body: JSON.stringify({
          values: {
            ...createForm,
            检验机构: createForm['检验机构'] || '',
            检验人员: createForm['检验人员'] || '',
            actor: store.operator,
          },
        }),
      })
    }
    const payload = await response.json().catch(() => ({ ok: false, message: '服务端返回格式异常' }))
    if (!response.ok || payload.ok === false) {
      // 越权提交会被服务端拦住，这里原样讲清原因。
      errorMessage.value = payload.message || payload.detail || '操作未生效，请稍后重试'
      return
    }
    successMessage.value = payload.message || '操作已生效'
    closeDialog()
    await reload()
    if (detailRow.value?.id === payload.entry?.id) {
      detailRow.value = payload.entry as Row
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '请求失败'
  } finally {
    submitting.value = false
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (keyword.value) params.set('keyword', keyword.value)
  if (statusFilter.value) params.set('status', statusFilter.value)
  if (orgFilter.value) params.set('org', orgFilter.value)
  params.set('size', '200')
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) throw new Error('检验任务列表读取失败')
    const payload = await response.json()
    rows.value = (payload.items ?? []) as Row[]
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '定期检验列表读取失败'
  }
}

onMounted(reload)
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
.assign-section,
.task-section {
  background: transparent;
  margin-bottom: 16px;
}
.assign-section h3,
.task-section h3 {
  margin: 8px 0 4px;
  font-size: 15px;
}
.section-hint {
  color: var(--muted);
  font-size: 12px;
  margin: 0 0 8px;
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
.stat-value.warn {
  color: #c2410c;
}
.mine-row {
  background: #f0fdf4;
}
.controlled-inline {
  color: var(--muted);
  font-size: 12px;
  margin-left: 4px;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 48px 16px;
  z-index: 50;
}
.modal {
  background: #fff;
  border-radius: 10px;
  width: 520px;
  max-width: 100%;
  padding: 18px 20px;
}
.modal h3 {
  margin: 0 0 6px;
}
.modal-target {
  font-size: 12px;
  color: var(--muted);
  margin: 0 0 10px;
}
.modal-tip {
  font-size: 13px;
  background: #f8fafc;
  border-radius: 6px;
  padding: 8px 10px;
  margin: 0 0 12px;
}
.modal-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.modal-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 10px;
}
.modal-field em {
  color: #b42318;
  font-style: normal;
}
.modal-field input,
.modal-field select,
.modal-field textarea {
  font-size: 13px;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: #1f2937;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
.drawer {
  background: #fff;
  border-radius: 10px;
  width: 680px;
  max-width: 100%;
  padding: 18px 20px;
  max-height: 85vh;
  overflow-y: auto;
}
.detail-grid {
  display: grid;
  grid-template-columns: 110px 1fr 110px 1fr;
  gap: 6px 10px;
  font-size: 13px;
  margin: 8px 0 12px;
}
.detail-grid dt {
  color: var(--muted);
}
.detail-grid dd {
  margin: 0;
}
.unassigned-dd {
  color: #c2410c;
}
.conclusion-box {
  background: #f8fafc;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
  margin: 4px 0 12px;
}
.log-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.log-item {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12px;
}
.log-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}
.log-head span {
  color: var(--muted);
}
.log-detail {
  margin-bottom: 4px;
}
.log-snap {
  color: var(--muted);
  background: #f8fafc;
  border-radius: 4px;
  padding: 3px 6px;
}
.success-text {
  color: #15803d;
}
</style>
