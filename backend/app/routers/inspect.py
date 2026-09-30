"""定期检验接口：维护检验任务的归属、状态流转、转派交接与检验员工作台。

越权类操作（非归属机构、转派后原负责人改动、未指派先处置）统一返回 403，
响应体 detail 讲清拦截原因，前端据此展示受控提示。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.identity import IdentityError, identity_service
from app.services.inspect import OwnershipError, InspectService

router = APIRouter(prefix="/api/inspect", tags=["定期检验"])

service = InspectService()

COLUMNS = ["检验编号", "检验对象", "检验类别", "检验机构", "计划检验日", "检验人员", "检验日期", "检验状态"]
STATUSES = ["待报检", "检验中", "已出具", "已退回"]
SCOPES = {"all", "mine", "unassigned"}


def resolve_identity(x_inspector_id: str | None) -> dict[str, Any]:
    try:
        return identity_service.resolve(x_inspector_id)
    except IdentityError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/roster")
def roster() -> dict[str, Any]:
    """检验员名册与机构清单：归属指派下拉和右上角身份切换共用。"""
    inspectors = identity_service.list_inspectors()
    return {"orgs": identity_service.list_orgs(), "inspectors": inspectors}


@router.get("/ownership")
def ownership_snapshot() -> dict[str, Any]:
    """归属快照：运营概览待检验数、工作台、列表三处共用同一份口径。"""
    return service.ownership_summary()


@router.get("/workbench")
def workbench(x_inspector_id: str | None = Header(default=None)) -> dict[str, Any]:
    """检验员工作台：我的待办、本机构任务、待指派清单与归属计数。"""
    operator = resolve_identity(x_inspector_id)
    return service.workbench(operator)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出定期检验清单：返回当前归属快照下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "inspect", "total": total, "items": items}


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按检验编号检索"),
    status: str | None = Query(default=None, description="待报检、检验中、已出具、已退回"),
    scope: str = Query(default="all", description="all 全部 / mine 本机构 / unassigned 待指派"),
    page: int = 1,
    size: int = 20,
    x_inspector_id: str | None = Header(default=None),
) -> PageResult[dict]:
    """按检验编号、状态与归属范围过滤任务；每条任务附带 can_modify 与受控原因。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    if scope not in SCOPES:
        raise HTTPException(status_code=400, detail=f"归属范围 {scope} 不支持，可选 all / mine / unassigned")
    operator = identity_service.find_inspector(x_inspector_id) if x_inspector_id else None
    items, total = service.list_entries(
        operator=operator, keyword=keyword, status=status, scope=scope, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条检验任务明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"检验任务 {entry_id} 不存在或已归档")
    return entry


@router.get("/{entry_id}/history")
def get_history(entry_id: int) -> dict[str, Any]:
    """归属变更历史与交接记录：转派轨迹、检验结论与任务事件一并返回。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"检验任务 {entry_id} 不存在或已归档")
    return {
        "entry_id": entry_id,
        "检验编号": entry.get("检验编号"),
        "检验结论": entry.get("检验结论", ""),
        "events": entry.get("events", []),
        "assign_log": service.history(entry_id),
    }


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条检验任务，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="检验任务已登记", entry=entry)


@router.post("/{entry_id}/assign", response_model=ActionResult)
def assign_entry(
    entry_id: int,
    payload: EntryPayload,
    x_inspector_id: str | None = Header(default=None),
) -> ActionResult:
    """指派或转派归属：目标必须是名册内在岗检验员，事由必填，转派自动留痕。"""
    operator = resolve_identity(x_inspector_id)
    target_id = str(payload.values.get("inspector_id") or "").strip()
    reason = str(payload.values.get("reason") or "").strip()
    entry, message = service.assign(
        entry_id, operator, target_inspector_id=target_id, reason=reason
    )
    if entry is None:
        return ActionResult(ok=False, message=message)
    decorated = service.decorate(entry, operator)
    return ActionResult(ok=True, message=message, entry=decorated)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(
    entry_id: int,
    payload: EntryPayload,
    x_inspector_id: str | None = Header(default=None),
) -> ActionResult:
    """对单条任务执行提交报检、确认出具、退回重检；非归属机构提交返回 403 并说明原因。"""
    operator = resolve_identity(x_inspector_id)
    action = str(payload.values.get("action") or "").strip()
    try:
        entry, message = service.run_action(entry_id, action, operator)
    except OwnershipError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=service.decorate(entry, operator))
