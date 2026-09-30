"""定期检验业务规则：状态流转、任务归属、转派留痕与筛选口径都收在这里。

归属模型（单一数据源）：每条任务上的 owner_org / owner_id / owner_name 记录当前归属，
与「检验机构」「检验人员」展示字段保持同值；assign_log 表记录全部归属变更。
工作台待办、运营概览待检验数、定期检验列表三处都从这份归属快照取数。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.identity import IdentityError, identity_service
from app.store import store

MODULE = "inspect"
LOG_MODULE = "assign_log"
REQUIRED_FIELDS = ["检验编号", "检验对象", "检验类别"]
# 归属三件套：机构 + 人员编号 + 人员姓名，任一缺失都视为未指派
OWNER_FIELDS = ("owner_org", "owner_id", "owner_name")
STATUS_ORDER = ["待报检", "检验中", "已出具", "已退回"]
ACTION_RULES = {"提交报检": "检验中", "确认出具": "已出具", "退回重检": "已退回"}
NEGATIVE_ACTIONS = ["退回重检"]
# 各动作落库时一并保留的检验结论，交接后仍可追溯
ACTION_CONCLUSIONS = {
    "确认出具": "合格（出具时由归属检验员确认）",
    "退回重检": "不符合要求，退回重检",
}


class OwnershipError(Exception):
    """归属或权限不满足：未指派、非归属机构、原负责人越权改动等。"""


def now_label() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def is_assigned(entry: dict[str, Any]) -> bool:
    return all(str(entry.get(field) or "").strip() for field in OWNER_FIELDS)


def append_event(entry: dict[str, Any], text: str) -> None:
    entry.setdefault("events", []).append({"时间": now_label(), "说明": text})


class InspectService:
    # ---------- 归属快照：三处页面共用同一份口径 ----------
    def ownership_summary(self) -> dict[str, Any]:
        rows = store.rows(MODULE)
        by_org: dict[str, dict[str, int]] = {}
        unassigned = 0
        for row in rows:
            if not is_assigned(row):
                unassigned += 1
                continue
            org = str(row["owner_org"])
            bucket = by_org.setdefault(org, {"total": 0, "pending": 0})
            bucket["total"] += 1
            if row.get("pending"):
                bucket["pending"] += 1
        return {
            "total": len(rows),
            "pending": sum(1 for row in rows if row.get("pending")),
            "unassigned": unassigned,
            "by_org": [{"org": org, **counts} for org, counts in sorted(by_org.items())],
        }

    def decorate(self, entry: dict[str, Any], operator: dict[str, Any] | None) -> dict[str, Any]:
        """给单条任务附上归属视角，列表直接下发，前端不需要再自行判断。"""
        assigned = is_assigned(entry)
        operator_org = str((operator or {}).get("检验机构") or "")
        can_modify = bool(
            assigned
            and operator is not None
            and str(entry["owner_org"]) == operator_org
        )
        if not assigned:
            deny_reason = "任务尚未指派归属机构与检验人员，需先指派才能处置"
        elif operator is None:
            deny_reason = "未选择检验人员身份，仅可查看"
        elif not can_modify:
            deny_reason = (
                f"受控查看：任务归属{entry['owner_org']}，"
                f"{operator.get('姓名')}（{operator_org}）不可变更，仅归属机构检验员可处置"
            )
        else:
            deny_reason = ""
        result = dict(entry)
        result["assigned"] = assigned
        result["can_modify"] = can_modify
        result["deny_reason"] = deny_reason
        result["owned_by_me"] = bool(
            operator is not None and str(entry.get("owner_id") or "") == str(operator.get("人员编号"))
        )
        return result

    # ---------- 查询 ----------
    def list_entries(
        self,
        *,
        operator: dict[str, Any] | None = None,
        keyword: str | None = None,
        status: str | None = None,
        scope: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("检验编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if scope == "mine":
            rows = [row for row in rows if self._belongs_to_org(row, operator)]
        elif scope == "unassigned":
            rows = [row for row in rows if not is_assigned(row)]
        total = len(rows)
        start = max(page - 1, 0) * size
        page_rows = [self.decorate(row, operator) for row in rows[start:start + size]]
        return page_rows, total

    @staticmethod
    def _belongs_to_org(row: dict[str, Any], operator: dict[str, Any] | None) -> bool:
        return bool(
            is_assigned(row)
            and operator is not None
            and str(row["owner_org"]) == str(operator.get("检验机构"))
        )

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def history(self, entry_id: int) -> list[dict[str, Any]]:
        return [dict(row) for row in store.rows(LOG_MODULE) if int(row.get("task_id", 0)) == entry_id]

    # ---------- 登记 ----------
    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["计划检验日"] = str(values.get("计划检验日") or "").strip()
        entry["检验日期"] = ""
        entry["检验状态"] = STATUS_ORDER[0]
        entry["检验结论"] = ""
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["events"] = []
        # 登记时可直接指定归属机构；人员允许留空，进入待指派清单
        org = str(values.get("检验机构") or "").strip()
        person_name = str(values.get("检验人员") or "").strip()
        entry["检验机构"] = org
        entry["检验人员"] = person_name
        entry["owner_org"] = org
        entry["owner_name"] = person_name
        entry["owner_id"] = ""
        if org and person_name:
            inspector = identity_service.find_by_name(person_name, org)
            if inspector is not None:
                entry["owner_id"] = str(inspector["人员编号"])
                self._write_log(entry, "首次指派", "", "", org, person_name,
                                "登记任务时按机构名册绑定归属", "登记人")
        rows.append(entry)
        return entry, []

    # ---------- 归属变更（指派/转派）----------
    def assign(
        self,
        entry_id: int,
        operator: dict[str, Any],
        *,
        target_inspector_id: str,
        reason: str,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"检验任务 {entry_id} 不存在或已归档"
        target = identity_service.find_inspector(target_inspector_id)
        if target is None:
            return None, f"目标检验人员 {target_inspector_id} 不在检验员名册中，无法转派"
        reason = reason.strip()
        if not reason:
            return None, "归属变更必须填写事由，交接记录需要可追溯"

        old_org = str(entry.get("owner_org") or "")
        old_name = str(entry.get("owner_name") or "")
        new_org = str(target["检验机构"])
        new_name = str(target["姓名"])

        if old_org == new_org and old_name == new_name and is_assigned(entry):
            return None, f"任务已归属{new_org} {new_name}，归属未发生变化"

        change_type = "首次指派" if not old_org else "转派"
        # 转派：原负责人在归属落库的一刻即失去改动权限；跨机构时历史任务仍挂原机构口径由日志保留
        entry["owner_org"] = new_org
        entry["owner_id"] = str(target["人员编号"])
        entry["owner_name"] = new_name
        entry["检验机构"] = new_org
        entry["检验人员"] = new_name
        self._write_log(
            entry, change_type, old_org, old_name, new_org, new_name, reason,
            str(operator.get("姓名")),
        )
        append_event(
            entry,
            f"{change_type}：{old_org or '未指派'} {old_name or '—'} → {new_org} {new_name}（{reason}）",
        )
        return entry, (
            f"已{change_type}：{new_org} {new_name} 承接任务，"
            + ("原负责人不再具备改动权限，历史记录与检验结论已随任务保留" if change_type == "转派" else "任务已进入承接人待办")
        )

    def _write_log(
        self,
        entry: dict[str, Any],
        change_type: str,
        old_org: str,
        old_name: str,
        new_org: str,
        new_name: str,
        reason: str,
        actor: str,
    ) -> None:
        logs = store.rows(LOG_MODULE)
        logs.append({
            "id": max((int(row.get("id", 0)) for row in logs), default=0) + 1,
            "task_id": entry["id"],
            "检验编号": entry.get("检验编号", ""),
            "变更类型": change_type,
            "原归属机构": old_org,
            "原负责人": old_name,
            "新归属机构": new_org,
            "新负责人": new_name,
            "事由": reason,
            "操作人": actor,
            "时间": now_label(),
        })

    # ---------- 状态动作：归属校验在最前面拦 ----------
    def run_action(
        self,
        entry_id: int,
        action: str,
        operator: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"检验任务 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于定期检验可执行范围"
        if not is_assigned(entry):
            raise OwnershipError("该任务尚未指派归属机构与检验人员，需先完成指派才能处置")
        operator_org = str(operator.get("检验机构") or "")
        if str(entry["owner_org"]) != operator_org:
            # 归属机构不一致即越权：转派后原负责人在另一机构，提交会在此被拦下
            raise OwnershipError(
                f"越权拦截：任务归属{entry['owner_org']}（负责人 {entry['owner_name']}），"
                f"{operator.get('姓名')}（{operator_org}）只能查看，不能{action}；"
                "如任务已转派，原负责人不再具备改动权限，请由归属机构检验员办理"
            )
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1] and target != "已出具"
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        entry["检验状态"] = target
        if action == "确认出具":
            entry["检验日期"] = now_label()[:10]
        conclusion = ACTION_CONCLUSIONS.get(action)
        if conclusion:
            # 检验结论随任务保留，转派/交接后仍挂在任务上
            entry["检验结论"] = conclusion
        append_event(entry, f"{operator.get('姓名')} 执行「{action}」，状态变更为{target}")
        return entry, f"检验任务已{action}"

    # ---------- 检验员工作台 ----------
    def workbench(self, operator: dict[str, Any]) -> dict[str, Any]:
        """工作台待办：只取归属当前检验员所在机构、且仍在检验流程中的任务。"""
        rows = store.rows(MODULE)
        org = str(operator.get("检验机构"))
        mine = [row for row in rows if self._belongs_to_org(row, operator)]
        my_tasks = [
            self.decorate(row, operator)
            for row in mine if str(row.get("owner_id")) == str(operator.get("人员编号"))
        ]
        org_tasks = [
            self.decorate(row, operator)
            for row in mine if str(row.get("owner_id")) != str(operator.get("人员编号"))
        ]
        unassigned = [self.decorate(row, operator) for row in rows if not is_assigned(row)]
        pending = sum(1 for row in mine if row.get("pending"))
        return {
            "identity": {
                "人员编号": operator.get("人员编号"),
                "姓名": operator.get("姓名"),
                "检验机构": org,
                "检验类别": operator.get("检验类别"),
                "岗位": operator.get("岗位"),
            },
            "counters": {
                "org_pending": pending,
                "my_tasks": len(my_tasks),
                "org_tasks": len(org_tasks),
                "unassigned": len(unassigned),
            },
            "my_tasks": my_tasks,
            "org_tasks": org_tasks,
            "unassigned": unassigned,
            "summary": self.ownership_summary(),
        }


inspect_service = InspectService()
