<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">特种设备点检运维平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向锅炉、压力容器、起重机械、电梯等特种设备的台账建档、日常点检、润滑保养、定期检验与隐患整改的一体化运维后台。</span>
        <div class="identity-box">
          <label class="identity-item">
            <span>检验机构</span>
            <select :value="store.org" @change="onOrgChange">
              <option v-for="org in store.directory.organizations" :key="org.name" :value="org.name">{{ org.name }}</option>
            </select>
          </label>
          <label class="identity-item">
            <span>检验人员</span>
            <select :value="store.operator" @change="onInspectorChange">
              <option v-for="name in inspectorsOfOrg" :key="name" :value="name">{{ name }}</option>
            </select>
          </label>
          <span class="head-user" :class="{ controlled: !store.isRegisteredInspector }">
            当前身份：{{ store.operator }} · {{ store.org }}
          </span>
        </div>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'

import { useSessionStore } from '@/stores/session'

const store = useSessionStore()

const navItems = [{ label: "运营概览", path: "/" }, { label: "检验员工作台", path: "/inspect-workbench" }, { label: "锅炉设备", path: "/boiler" }, { label: "压力容器", path: "/vessel" }, { label: "压力管道", path: "/pressurepipe" }, { label: "起重机械", path: "/crane" }, { label: "电梯设备", path: "/elevator" }, { label: "场内机动车辆", path: "/forklift" }, { label: "点检计划", path: "/plan" }, { label: "点检记录", path: "/spotcheck" }, { label: "润滑保养", path: "/lubricate" }, { label: "定期检验", path: "/inspect" }, { label: "检验报告", path: "/report" }, { label: "隐患登记", path: "/hazard" }, { label: "整改闭环", path: "/rectify" }, { label: "使用登记", path: "/register" }, { label: "作业人员", path: "/operator" }, { label: "备件器材", path: "/spare" }, { label: "维保合同", path: "/contract" }, { label: "费用结算", path: "/settle" }]

const inspectorsOfOrg = computed(() => store.currentOrg?.inspectors ?? [])

function onOrgChange(event: Event) {
  store.setOrg((event.target as HTMLSelectElement).value)
}

function onInspectorChange(event: Event) {
  store.setInspector((event.target as HTMLSelectElement).value)
}

onMounted(() => {
  void store.loadDirectory()
})
</script>

<style scoped>
.identity-box {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}
.identity-item {
  display: flex;
  flex-direction: column;
  font-size: 12px;
  color: var(--muted);
  gap: 2px;
}
.identity-item select {
  font-size: 12px;
  padding: 3px 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: #fff;
}
.head-user.controlled {
  color: #b42318;
}
</style>
