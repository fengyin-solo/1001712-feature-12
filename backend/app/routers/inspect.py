"""定期检验接口：维护检验任务的归属、流转、指派/转派与检验员工作台。

权限约定：所有写操作都要在 payload.values 里带 actor（当前检验员姓名）；
归属校验集中在 InspectService.authorize，越权请求返回 200 + ok=False 并讲清原因，
与平台其他模块的 ActionResult 约定保持一致。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.inspect import inspect_service

router = APIRouter(prefix="/api/inspect", tags=["定期检验"])

LIST_FIELDS = ["检验编号", "检验对象", "检验类别", "检验机构", "计划检验日", "检验人员", "检验日期", "检验结论", "检验状态"]
STATUSES = ["待报检", "检验中", "已出具", "已退回"]


@router.get("/directory")
def directory() -> dict[str, Any]:
    """检验类别与机构-检验人员受控目录。"""
    return inspect_service.directory()


@router.get("/ownership-summary")
def ownership_summary() -> dict[str, Any]:
    """归属汇总：工作台、运营概览、列表统计三处取同一份归属。"""
    return inspect_service.ownership_summary()


@router.get("/workbench")
def workbench(inspector: str = Query(..., description="当前登录检验员姓名")) -> dict[str, Any]:
    """检验员工作台：我的待办、本机构待检验、待指派任务。"""
    return inspect_service.workbench(inspector)


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按检验编号检索"),
    status: str | None = Query(default=None, description="待报检、检验中、已出具、已退回"),
    org: str | None = Query(default=None, description="按归属机构过滤"),
    inspector: str | None = Query(default=None, description="按当前负责人过滤"),
    unassigned: bool = Query(default=False, description="只看归属为空、待指派的任务"),
    page: int = 1,
    size: int = 200,
) -> PageResult[dict]:
    """按检验编号、状态与归属过滤定期检验列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = inspect_service.list_entries(
        keyword=keyword,
        status=status,
        org=org,
        inspector=inspector,
        unassigned=unassigned,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条检验任务明细；不存在时给出可读的错误说明。"""
    entry = inspect_service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"检验任务 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条检验任务：校验类别与归属绑定关系，缺字段或越权时说明原因。"""
    actor = str(payload.values.get("actor") or "").strip()
    entry, message = inspect_service.create_entry(payload.values, actor)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message="检验任务已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """执行提交报检、确认出具、退回重检；越权、空结论等都会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    actor = str(payload.values.get("actor") or "").strip()
    conclusion = payload.values.get("conclusion")
    entry, message = inspect_service.run_action(entry_id, action, actor, conclusion)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/assignment", response_model=ActionResult)
def assign_entry(entry_id: int, payload: EntryPayload) -> ActionResult:
    """指派/转派任务归属；转派后原负责人不再有权改动，历史记录与结论保留。"""
    actor = str(payload.values.get("actor") or "").strip()
    target_org = str(payload.values.get("target_org") or "").strip()
    target_inspector = str(payload.values.get("target_inspector") or "").strip()
    note = payload.values.get("note")
    entry, message = inspect_service.assign(
        entry_id,
        actor=actor,
        target_org=target_org,
        target_inspector=target_inspector,
        note=note,
    )
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出定期检验清单：全量数据（含归属与流转记录）。"""
    items, total = inspect_service.list_entries(page=1, size=10000)
    return {"module": "inspect", "total": total, "items": items}
