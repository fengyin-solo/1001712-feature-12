"""检验员身份服务：从检验员名册解析当前登录的检验人员与其所属机构。

归属类接口统一通过人员编号（X-Inspector-Id）识别来访者；名册是机构归属的唯一来源，
任务上的归属字段只记录当前快照，避免出现「任务挂在某人名下但名册查无此人」。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "inspector"


class IdentityError(Exception):
    """无法识别当前检验人员（未选择身份或人员已离岗）。"""


class IdentityService:
    def list_inspectors(self) -> list[dict[str, Any]]:
        return store.rows(MODULE)

    def list_orgs(self) -> list[str]:
        orgs: list[str] = []
        for row in self.list_inspectors():
            org = str(row.get("检验机构") or "").strip()
            if org and org not in orgs:
                orgs.append(org)
        return orgs

    def find_inspector(self, inspector_id: str | None) -> dict[str, Any] | None:
        inspector_id = (inspector_id or "").strip()
        if not inspector_id:
            return None
        for row in self.list_inspectors():
            if str(row.get("人员编号")) == inspector_id:
                return row
        return None

    def resolve(self, inspector_id: str | None) -> dict[str, Any]:
        """把请求头里的人员编号解析成身份；缺失或查不到时给出可读原因。"""
        inspector_id = (inspector_id or "").strip()
        if not inspector_id:
            raise IdentityError("未选择检验人员身份，系统无法判断任务归属；请在右上角选择检验员后再操作")
        inspector = self.find_inspector(inspector_id)
        if inspector is None:
            raise IdentityError(f"检验人员 {inspector_id} 不在检验员名册中，归属无法核验")
        if str(inspector.get("人员状态") or "") != "在岗":
            raise IdentityError(f"检验人员 {inspector.get('姓名')} 当前不在岗，不能承接或变更检验任务")
        return inspector

    def find_by_name(self, name: str, org: str) -> dict[str, Any] | None:
        for row in self.list_inspectors():
            if str(row.get("姓名")) == name and str(row.get("检验机构")) == org:
                return row
        return None


identity_service = IdentityService()
