import { defineStore } from 'pinia'

import { fetchJson } from '@/api/client'

export type OrgDirectory = {
  name: string
  inspectors: string[]
}

export type InspectDirectory = {
  categories: string[]
  organizations: OrgDirectory[]
}

const IDENTITY_KEY = 'inspect-identity'
// 目录未加载时的兜底，保证首屏也能渲染默认身份；加载后以后端受控目录为准。
const FALLBACK_DIRECTORY: InspectDirectory = {
  categories: ['年度检验', '全面检验', '定期自行检查', '监督检验'],
  organizations: [
    { name: '市特种设备检验检测院', inspectors: ['张建国', '李文静', '王海涛'] },
    { name: '华东压力容器检验中心', inspectors: ['陈晓峰', '刘雅琴'] },
    { name: '省机电设备检验所', inspectors: ['赵明辉', '孙丽娟'] },
  ],
}

function restoreIdentity(): { org: string; inspector: string } {
  const fallback = { org: FALLBACK_DIRECTORY.organizations[0].name, inspector: '张建国' }
  try {
    const raw = window.localStorage.getItem(IDENTITY_KEY)
    if (!raw) return fallback
    const parsed = JSON.parse(raw) as { org?: string; inspector?: string }
    if (parsed.org && parsed.inspector) {
      return { org: parsed.org, inspector: parsed.inspector }
    }
  } catch {
    // 本地缓存损坏时回退默认身份，不影响页面打开
  }
  return fallback
}

export const useSessionStore = defineStore('session', {
  state: () => {
    const identity = restoreIdentity()
    return {
      operator: identity.inspector,
      shiftLabel: '白班 08:00-20:00',
      scope: '特种设备点检运维平台',
      org: identity.org,
      directory: FALLBACK_DIRECTORY as InspectDirectory,
      directoryLoaded: false,
    }
  },
  getters: {
    canOperate: (state) => state.operator.length > 0,
    currentOrg(state): OrgDirectory | undefined {
      return state.directory.organizations.find((item) => item.name === state.org)
    },
    // 当前身份是否为在册检验员；非在册人员只能查看受控任务。
    isRegisteredInspector(state): boolean {
      const org = state.directory.organizations.find((item) => item.name === state.org)
      return Boolean(org && org.inspectors.includes(state.operator))
    },
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    setOrg(org: string) {
      // 切换机构后，负责人默认落到该机构第一位检验员，避免出现“人不属于机构”的身份组合。
      const target = this.directory.organizations.find((item) => item.name === org)
      this.org = org
      if (target && !target.inspectors.includes(this.operator)) {
        this.operator = target.inspectors[0] ?? ''
      }
      this.persist()
    },
    setInspector(inspector: string) {
      this.operator = inspector
      this.persist()
    },
    persist() {
      try {
        window.localStorage.setItem(IDENTITY_KEY, JSON.stringify({ org: this.org, inspector: this.operator }))
      } catch {
        // 隐私模式等场景下写不进缓存就只保存在内存里
      }
    },
    async loadDirectory() {
      if (this.directoryLoaded) return
      try {
        const payload = await fetchJson<InspectDirectory>('/api/inspect/directory')
        this.directory = payload
        // 校正持久化身份：机构或人员已不在受控目录时回退到第一位在册人员。
        const org = payload.organizations.find((item) => item.name === this.org)
        if (!org) {
          this.org = payload.organizations[0]?.name ?? ''
          this.operator = payload.organizations[0]?.inspectors[0] ?? ''
        } else if (!org.inspectors.includes(this.operator)) {
          this.operator = org.inspectors[0] ?? ''
        }
        this.directoryLoaded = true
        this.persist()
      } catch {
        // 后端暂不可用时沿用兜底目录，页面仍可打开
      }
    },
  },
})
