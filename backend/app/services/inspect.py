"""定期检验业务规则：任务归属、权限校验、状态流转与交接留痕都收在这里。

归属模型（三处页面共用同一份数据）：
- 每条检验任务绑定「检验类别 + 检验机构（归属机构）+ 检验人员（当前负责人）」。
- 只有归属本机构的检验人员才能变更任务；归属为空的任务进入「待指派」，可被任一在册检验员认领/指派。
- 转派只改当前归属，历史日志与检验结论按快照保留，历史记录仍挂在原机构名下。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "inspect"
REQUIRED_FIELDS = ["检验编号", "检验对象", "检验类别"]
STATUS_ORDER = ["待报检", "检验中", "已出具", "已退回"]
ACTION_RULES = {"提交报检": "检验中", "确认出具": "已出具", "退回重检": "已退回"}
# 合法流转：已出具是终态；已退回须整改后重新提交报检。
# 即使前端按钮做了收敛，服务端仍按这张表拦截，绕过页面直接调接口也改不了终态任务。
ALLOWED_TRANSITIONS: dict[str, dict[str, str]] = {
    "待报检": {"提交报检": "检验中"},
    "检验中": {"确认出具": "已出具", "退回重检": "已退回"},
    "已退回": {"提交报检": "检验中"},
    "已出具": {},
}
NEGATIVE_ACTIONS = ["退回重检"]
# 待检验口径：除已出具外都还需要检验机构跟进（含退回重检）。
PENDING_STATUSES = {"待报检", "检验中", "已退回"}
CONCLUSION_ACTIONS = {"确认出具", "退回重检"}

# 受控目录：可登记的检验类别，以及各检验机构在册的检验人员。
INSPECT_CATEGORIES = ["年度检验", "全面检验", "定期自行检查", "监督检验"]
INSPECTORS: dict[str, list[str]] = {
    "市特种设备检验检测院": ["张建国", "李文静", "王海涛"],
    "华东压力容器检验中心": ["陈晓峰", "刘雅琴"],
    "省机电设备检验所": ["赵明辉", "孙丽娟"],
}

# 归属字段为空时统一展示的占位文案，前端也用它判断「待指派」。
UNASSIGNED_ORG = "待指派"
UNASSIGNED_INSPECTOR = "待指派"


def person_org(inspector: str | None) -> str | None:
    """按姓名反查检验员所属机构；不在册返回 None。"""
    name = str(inspector or "").strip()
    if not name:
        return None
    for org, members in INSPECTORS.items():
        if name in members:
            return org
    return None


def is_unassigned(entry: dict[str, Any]) -> bool:
    return not owning_org(entry) or not assignee_of(entry)


def owning_org(entry: dict[str, Any]) -> str:
    return str(entry.get("检验机构") or "").strip()


def assignee_of(entry: dict[str, Any]) -> str:
    return str(entry.get("检验人员") or "").strip()


class InspectService:
    # ----- 目录 -----
    def directory(self) -> dict[str, Any]:
        """检验类别与机构-人员目录，前端下拉与权限判断都取这里。"""
        return {
            "categories": list(INSPECT_CATEGORIES),
            "organizations": [
                {"name": org, "inspectors": list(members)}
                for org, members in INSPECTORS.items()
            ],
        }

    # ----- 查询 -----
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        org: str | None = None,
        inspector: str | None = None,
        unassigned: bool = False,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("检验编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if org:
            rows = [row for row in rows if owning_org(row) == org]
        if inspector:
            rows = [row for row in rows if assignee_of(row) == inspector]
        if unassigned:
            rows = [row for row in rows if is_unassigned(row)]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    # ----- 归属汇总：检验员工作台、运营概览、检验列表三处共用 -----
    def ownership_summary(self) -> dict[str, Any]:
        rows = store.rows(MODULE)
        organizations: list[dict[str, Any]] = []
        for org in INSPECTORS:
            org_rows = [row for row in rows if owning_org(row) == org]
            organizations.append({
                "name": org,
                "inspectors": list(INSPECTORS[org]),
                "total": len(org_rows),
                "pending": sum(1 for row in org_rows if row.get("status") in PENDING_STATUSES),
            })
        return {
            "total": len(rows),
            "pending": sum(1 for row in rows if row.get("status") in PENDING_STATUSES),
            "unassigned": sum(1 for row in rows if is_unassigned(row)),
            "organizations": organizations,
        }

    def workbench(self, inspector: str) -> dict[str, Any]:
        """检验员工作台：我的待办、本机构待检验、全机构待指派，同一份归属实时计算。"""
        org = person_org(inspector)
        if org is None:
            return {
                "inspector": inspector,
                "org": None,
                "message": f"当前身份「{inspector}」不在检验机构在册人员目录中，没有可办理的归属任务",
                "todo": [],
                "org_pending": [],
                "unassigned": [],
                "summary": self.ownership_summary(),
            }
        rows = store.rows(MODULE)
        return {
            "inspector": inspector,
            "org": org,
            "message": "",
            "todo": [
                row for row in rows
                if owning_org(row) == org
                and assignee_of(row) == inspector
                and row.get("status") in PENDING_STATUSES
            ],
            "org_pending": [
                row for row in rows
                if owning_org(row) == org and row.get("status") in PENDING_STATUSES
            ],
            "unassigned": [row for row in rows if is_unassigned(row)],
            "summary": self.ownership_summary(),
        }

    # ----- 权限 -----
    def authorize(self, entry: dict[str, Any], inspector: str) -> tuple[bool, str]:
        """判断当前检验员能否变更该任务；不允许时把原因讲清楚。"""
        actor = str(inspector or "").strip()
        actor_org = person_org(actor)
        if actor_org is None:
            return False, (
                f"当前身份「{actor or '未选择'}」不属于任何检验机构的在册检验人员，"
                "该任务处于受控状态，仅可查看，不能变更"
            )
        if is_unassigned(entry):
            return False, (
                "该任务尚未绑定归属机构与检验人员（待指派），"
                "请先指派归属后再办理；在册检验员均可对其发起指派"
            )
        org = owning_org(entry)
        current = assignee_of(entry)
        if actor_org != org:
            return False, (
                f"越权拦截：该任务归属{org}，当前身份{actor}（{actor_org}）不属于归属机构，"
                "仅可查看任务内容，不能执行任何变更"
            )
        if current and current != actor:
            return False, (
                f"任务已转派给{org}的{current}，原负责人{actor}不能再改动该任务；"
                f"如需变更请联系当前负责人{current}办理"
            )
        return True, ""

    # ----- 留痕 -----
    def _log(
        self,
        entry: dict[str, Any],
        *,
        actor: str,
        actor_org: str | None,
        action: str,
        detail: str,
    ) -> None:
        """追加一条流转记录；归属机构、负责人、检验结论都按当时快照保存。

        这样转派之后，旧记录仍挂在原机构与原负责人名下，检验结论也不会被覆盖。
        """
        entry.setdefault("logs", []).append({
            "time": _now_text(),
            "operator": actor,
            "operator_org": actor_org or "",
            "action": action,
            "detail": detail,
            "owning_org": owning_org(entry) or UNASSIGNED_ORG,
            "assignee": assignee_of(entry) or UNASSIGNED_INSPECTOR,
            "conclusion": str(entry.get("检验结论") or ""),
        })

    # ----- 写操作 -----
    def create_entry(
        self, values: dict[str, Any], actor: str
    ) -> tuple[dict[str, Any] | None, str]:
        actor = str(actor or "").strip()
        actor_org = person_org(actor)
        if actor_org is None:
            return None, (
                f"当前身份「{actor or '未选择'}」不在检验机构在册人员目录中，"
                "不能登记检验任务，请先切换到在册检验员身份"
            )
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        category = str(values.get("检验类别") or "").strip()
        if category not in INSPECT_CATEGORIES:
            return None, f"检验类别「{category}」不在受控目录中，请选择：{'、'.join(INSPECT_CATEGORIES)}"

        target_org = str(values.get("检验机构") or "").strip()
        target_inspector = str(values.get("检验人员") or "").strip()
        if bool(target_org) != bool(target_inspector):
            return None, "归属机构与检验人员必须成对绑定，不能只填其中一项"
        if target_org:
            if target_org not in INSPECTORS:
                return None, f"检验机构「{target_org}」不在受控目录中"
            if target_inspector not in INSPECTORS[target_org]:
                return None, f"检验人员{target_inspector}不属于{target_org}，不能绑定到该机构名下"

        rows = store.rows(MODULE)
        if any(str(row.get("检验编号") or "").strip() == str(values.get("检验编号")).strip() for row in rows):
            return None, f"检验编号{values.get('检验编号')}已存在，不能重复登记"

        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in ["检验编号", "检验对象", "检验类别", "计划检验日", "检验日期"]:
            entry[field] = str(values.get(field) or "").strip() or None
        entry["检验机构"] = target_org or None
        entry["检验人员"] = target_inspector or None
        entry["检验结论"] = None
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["logs"] = []
        rows.append(entry)
        if target_org:
            self._log(
                entry, actor=actor, actor_org=actor_org, action="登记任务",
                detail=f"登记建档，类别{category}，归属{target_org}，负责人{target_inspector}",
            )
        else:
            self._log(
                entry, actor=actor, actor_org=actor_org, action="登记任务",
                detail=f"登记建档，类别{category}，归属暂未指派",
            )
        return entry, ""

    def run_action(
        self,
        entry_id: int,
        action: str,
        inspector: str,
        conclusion: str | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"检验任务 {entry_id} 不存在或已归档"
        allowed, reason = self.authorize(entry, inspector)
        if not allowed:
            return None, reason
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于定期检验可执行范围"
        current_status = str(entry.get("status") or "")
        allowed_actions = ALLOWED_TRANSITIONS.get(current_status, {})
        if action not in allowed_actions:
            if current_status == "已出具":
                return None, (
                    "任务已出具结论并归档，不能再执行状态变更；"
                    "如结论有误须按复验流程另登记任务"
                )
            return None, f"任务当前为「{current_status}」状态，不能执行{action}"
        target = allowed_actions[action]
        if entry.get("status") == target:
            return None, f"任务当前已是「{target}」状态，无需重复{action}"

        conclusion = str(conclusion or "").strip()
        if action in CONCLUSION_ACTIONS and not conclusion:
            label = "检验结论"
            return None, f"{action}前必须填写{label}，交接时结论需随任务一并保留"

        previous = entry.get("status")
        entry["status"] = target
        entry["pending"] = target in PENDING_STATUSES
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        if conclusion:
            entry["检验结论"] = conclusion
        detail = f"{previous} → {target}"
        if conclusion:
            detail += f"；检验结论：{conclusion}"
        self._log(
            entry, actor=inspector, actor_org=person_org(inspector),
            action=action, detail=detail,
        )
        return entry, f"检验任务已{action}"

    def assign(
        self,
        entry_id: int,
        *,
        actor: str,
        target_org: str,
        target_inspector: str,
        note: str | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        """指派（归属为空时）或转派（已有归属时）。

        - 待指派任务：任一在册检验员都可发起指派。
        - 已有归属：必须是当前归属机构的当前负责人；原负责人已无权转派。
        - 只改当前归属字段；logs 与检验结论原样保留，旧日志快照仍挂原机构名下。
        """
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"检验任务 {entry_id} 不存在或已归档"
        actor = str(actor or "").strip()
        actor_org = person_org(actor)
        if actor_org is None:
            return None, (
                f"当前身份「{actor or '未选择'}」不在检验机构在册人员目录中，"
                "不能指派或转派检验任务"
            )
        target_org = str(target_org or "").strip()
        target_inspector = str(target_inspector or "").strip()
        if not target_org or not target_inspector:
            return None, "必须同时指定归属机构与检验人员"
        if target_org not in INSPECTORS:
            return None, f"检验机构「{target_org}」不在受控目录中"
        if target_inspector not in INSPECTORS[target_org]:
            return None, f"检验人员{target_inspector}不属于{target_org}，不能归属到该机构"

        previously_unassigned = is_unassigned(entry)
        if not previously_unassigned:
            allowed, reason = self.authorize(entry, actor)
            if not allowed:
                return None, reason

        old_org = owning_org(entry) or UNASSIGNED_ORG
        old_inspector = assignee_of(entry) or UNASSIGNED_INSPECTOR
        if (
            not previously_unassigned
            and old_org == target_org
            and old_inspector == target_inspector
        ):
            return None, f"任务已归属{target_org}的{target_inspector}，归属没有变化"

        entry["检验机构"] = target_org
        entry["检验人员"] = target_inspector
        action = "指派归属" if previously_unassigned else "转派归属"
        detail = f"{old_org}/{old_inspector} → {target_org}/{target_inspector}"
        if str(note or "").strip():
            detail += f"；交接说明：{str(note).strip()}"
        detail += "；历史记录与检验结论按原归属一并保留"
        self._log(entry, actor=actor, actor_org=actor_org, action=action, detail=detail)
        message = (
            f"任务已指派给{target_org}的{target_inspector}"
            if previously_unassigned
            else f"任务已由{old_org}/{old_inspector}转派给{target_org}/{target_inspector}"
        )
        return entry, message


def _now_text() -> str:
    """轻量时间戳：真实项目会换成统一的时间工具/数据库默认值。"""
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M")


inspect_service = InspectService()
