<template>
  <div>
    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>归属状态</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ display(row, column) }}</td>
          <td>
            <span v-if="row.assigned" class="tag tag-owned">
              {{ row.owner_org }} / {{ row.owner_name }}
            </span>
            <span v-else class="tag tag-unassigned">待指派</span>
          </td>
          <td class="row-actions">
            <template v-if="row.can_modify">
              <button
                v-for="action in actions"
                :key="action"
                class="link"
                type="button"
                @click="$emit('action', action, row)"
              >
                {{ action }}
              </button>
              <button class="link" type="button" @click="openAssign(row)">
                {{ row.assigned ? '转派' : '指派' }}
              </button>
            </template>
            <button class="link muted" type="button" @click="openHistory(row)">
              交接记录
            </button>
            <button
              v-if="!row.can_modify && allowAssign"
              class="link"
              type="button"
              @click="openAssign(row)"
            >
              指派承接
            </button>
            <span v-if="!row.can_modify && !allowAssign" class="lock-hint" :title="String(row.deny_reason ?? '')">
              🔒 受控查看
            </span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无符合条件的检验任务</td>
        </tr>
      </tbody>
    </table>

    <!-- 指派 / 转派弹窗 -->
    <div v-if="assignTarget" class="modal-mask" @click.self="closeAssign">
      <div class="modal">
        <h3>{{ assignTarget.assigned ? '转派检验任务' : '指派检验任务' }}</h3>
        <p class="modal-desc">
          任务 {{ assignTarget['检验编号'] }}（{{ assignTarget['检验类别'] }}）。
          <template v-if="assignTarget.assigned">
            当前归属 {{ assignTarget.owner_org }} · {{ assignTarget.owner_name }}，
            转派后原负责人立即失去改动权限，历史记录与检验结论随任务保留。
          </template>
          <template v-else>归属为空，指派后进入承接人待办。</template>
        </p>
        <label class="form-item">
          <span>承接检验员（按机构分组）</span>
          <select v-model="assignForm.inspectorId">
            <option value="">请选择承接检验员</option>
            <optgroup v-for="org in orgGroups" :key="org" :label="org">
              <option v-for="person in peopleOf(org)" :key="person.人员编号" :value="person.人员编号">
                {{ person.姓名 }} · {{ person.岗位 }}
              </option>
            </optgroup>
          </select>
        </label>
        <label class="form-item">
          <span>归属变更事由（必填，写入交接记录）</span>
          <textarea v-model="assignForm.reason" rows="3" placeholder="例如：设备属地变更 / 请假交接 / 机构排期调整"></textarea>
        </label>
        <div v-if="assignError" class="error-text">{{ assignError }}</div>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="closeAssign">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="confirmAssign">
            {{ submitting ? '提交中…' : '确认归属变更' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 交接记录弹窗 -->
    <div v-if="historyTarget" class="modal-mask" @click.self="historyTarget = null">
      <div class="modal wide">
        <h3>交接记录 · {{ historyTarget['检验编号'] }}</h3>
        <p class="modal-desc">
          当前归属：{{ historyTarget.assigned ? `${historyTarget.owner_org} · ${historyTarget.owner_name}` : '待指派' }}
        </p>
        <div class="history-block">
          <h4>检验结论（随任务保留）</h4>
          <p>{{ historyData['检验结论'] || '暂无结论，出具后在此保留。' }}</p>
        </div>
        <div class="history-block">
          <h4>归属变更轨迹</h4>
          <table class="data-table">
            <thead>
              <tr><th>时间</th><th>变更</th><th>原归属</th><th>新归属</th><th>事由</th><th>操作人</th></tr>
            </thead>
            <tbody>
              <tr v-for="log in historyData.assign_log" :key="String(log.id)">
                <td>{{ log['时间'] }}</td>
                <td>{{ log['变更类型'] }}</td>
                <td>{{ log['原归属机构'] || '—' }} {{ log['原负责人'] }}</td>
                <td>{{ log['新归属机构'] }} {{ log['新负责人'] }}</td>
                <td>{{ log['事由'] }}</td>
                <td>{{ log['操作人'] }}</td>
              </tr>
              <tr v-if="!historyData.assign_log?.length">
                <td colspan="6" class="empty-state">暂无归属变更记录</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="history-block">
          <h4>操作事件</h4>
          <ul v-if="historyData.events?.length" class="event-list">
            <li v-for="(event, index) in historyData.events" :key="index">
              {{ event['时间'] }} · {{ event['说明'] }}
            </li>
          </ul>
          <p v-else class="muted-text">暂无操作事件</p>
        </div>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="historyTarget = null">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

import { postAction, request } from '@/api/client'
import type { Inspector } from '@/stores/session'

const props = defineProps<{
  rows: Record<string, unknown>[]
  inspectors: Inspector[]
  allowAssign?: boolean
}>()

const emit = defineEmits<{
  (e: 'changed'): void
  (e: 'action', action: string, row: Record<string, unknown>): void
}>()

const columns = ['检验编号', '检验对象', '检验类别', '检验机构', '检验人员', '计划检验日', '检验日期', 'status', '检验结论']
const columnLabels: Record<string, string> = { status: '检验状态' }
const actions = ['提交报检', '确认出具', '退回重检']

function display(row: Record<string, unknown>, column: string) {
  if (column === '检验结论') {
    const text = String(row[column] ?? '')
    return text || '—'
  }
  return row[columnLabels[column] ?? column] ?? '—'
}

// ---- 指派 / 转派 ----
const assignTarget = ref<Record<string, unknown> | null>(null)
const assignForm = reactive({ inspectorId: '', reason: '' })
const assignError = ref('')
const submitting = ref(false)

const orgGroups = computed(() => {
  const orgs: string[] = []
  for (const person of props.inspectors) {
    if (!orgs.includes(person.检验机构)) orgs.push(person.检验机构)
  }
  return orgs
})
function peopleOf(org: string) {
  return props.inspectors.filter((person) => person.检验机构 === org)
}

function openAssign(row: Record<string, unknown>) {
  assignTarget.value = row
  assignForm.inspectorId = ''
  assignForm.reason = ''
  assignError.value = ''
}
function closeAssign() {
  assignTarget.value = null
}
async function confirmAssign() {
  if (!assignTarget.value) return
  assignError.value = ''
  if (!assignForm.inspectorId) {
    assignError.value = '请选择承接检验员'
    return
  }
  if (!assignForm.reason.trim()) {
    assignError.value = '归属变更事由必填，交接记录需要可追溯'
    return
  }
  submitting.value = true
  try {
    await postAction(`/api/inspect/${assignTarget.value.id}/assign`, {
      values: { inspector_id: assignForm.inspectorId, reason: assignForm.reason.trim() },
    })
    closeAssign()
    emit('changed')
  } catch (error) {
    assignError.value = error instanceof Error ? error.message : '归属变更失败'
  } finally {
    submitting.value = false
  }
}

// ---- 交接记录 ----
const historyTarget = ref<Record<string, unknown> | null>(null)
const historyData = reactive<{
  '检验结论': string
  assign_log: Record<string, string>[]
  events: { 时间: string; 说明: string }[]
}>({ '检验结论': '', assign_log: [], events: [] })

async function openHistory(row: Record<string, unknown>) {
  historyTarget.value = row
  historyData['检验结论'] = String(row['检验结论'] ?? '')
  historyData.assign_log = []
  historyData.events = []
  try {
    const resp = await request(`/api/inspect/${row.id}/history`)
    if (resp.ok) {
      const payload = await resp.json()
      historyData['检验结论'] = payload['检验结论'] ?? ''
      historyData.assign_log = payload.assign_log ?? []
      historyData.events = payload.events ?? []
    }
  } catch {
    // 历史加载失败不阻塞列表，弹窗内保留空态
  }
}

defineExpose({ openAssign, openHistory })
</script>

<style scoped>
.tag { padding: 2px 8px; border-radius: 10px; font-size: 12px; white-space: nowrap; }
.tag-owned { background: #ecfdf3; border: 1px solid #6ce9a6; color: #027a48; }
.tag-unassigned { background: #fffaeb; border: 1px solid #fec84b; color: #b54708; }
.lock-hint { color: #98a2b3; font-size: 12px; cursor: help; }
.muted { color: #98a2b3; }
.modal-mask {
  position: fixed; inset: 0; background: rgba(16, 24, 40, 0.45);
  display: flex; align-items: center; justify-content: center; z-index: 50;
}
.modal {
  background: #fff; border-radius: 10px; padding: 18px 20px;
  width: 460px; max-height: 86vh; overflow: auto;
}
.modal.wide { width: 760px; }
.modal h3 { margin: 0 0 8px; font-size: 16px; }
.modal-desc { font-size: 13px; color: var(--muted); margin: 0 0 12px; }
.form-item { display: block; margin-bottom: 12px; }
.form-item span { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.form-item select, .form-item textarea {
  width: 100%; border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px; font-size: 13px;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
.history-block { margin-bottom: 14px; }
.history-block h4 { font-size: 13px; margin: 0 0 6px; }
.event-list { margin: 0; padding-left: 18px; font-size: 12px; color: #475467; }
.event-list li { margin-bottom: 4px; }
.muted-text { font-size: 12px; color: var(--muted); }
</style>
