import { defineStore } from 'pinia'

import { currentInspectorId, fetchJson, setCurrentInspectorId } from '@/api/client'

export type Inspector = {
  人员编号: string
  姓名: string
  检验机构: string
  检验类别: string
  岗位: string
  人员状态: string
}

export const useSessionStore = defineStore('session', {
  state: () => ({
    inspectorId: currentInspectorId(),
    inspectors: [] as Inspector[],
    loaded: false,
  }),
  getters: {
    current(state): Inspector | null {
      return state.inspectors.find((item) => item.人员编号 === state.inspectorId) ?? null
    },
    operator(): string {
      return this.current ? this.current.姓名 : '未选择检验员'
    },
    org(): string {
      return this.current ? this.current.检验机构 : '—'
    },
  },
  actions: {
    async loadRoster(force = false) {
      if (this.loaded && !force) return
      const payload = await fetchJson<{ inspectors: Inspector[] }>('/api/inspect/roster')
      this.inspectors = payload.inspectors
      this.loaded = true
      // 持久化的身份若已不在名册（例如数据重置），回退到未选择，避免冒充
      if (this.inspectorId && !this.current) {
        this.inspectorId = ''
        setCurrentInspectorId('')
      }
    },
    switchInspector(inspectorId: string) {
      this.inspectorId = inspectorId
      setCurrentInspectorId(inspectorId)
    },
  },
})
