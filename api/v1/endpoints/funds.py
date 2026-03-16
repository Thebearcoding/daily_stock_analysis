# -*- coding: utf-8 -*-
"""
===================================
基金建议接口
===================================

职责：
1. GET  /api/v1/funds/{fund_code}/advice — 同步无状态建议（不入历史）
2. POST /api/v1/funds/analyze             — 分析并持久化（Phase 2B + Phase 4 async）
3. GET  /api/v1/funds/status/{task_id}    — 基金任务状态（Phase 4）
4. GET  /api/v1/funds/tasks               — 基金任务列表（Phase 4）
5. GET  /api/v1/funds/tasks/stream        — 基金任务 SSE 流（Phase 4）
6. GET  /api/v1/funds/history             — 基金历史列表（Phase 3）
7. GET  /api/v1/funds/history/{record_id} — 基金历史详情（Phase 3）
8. GET  /api/v1/funds/{fund_code}/holdings — 基金持仓（Phase 3B）
9. GET  /api/v1/funds/history/{record_id}/holdings — 历史关联持仓（Phase 3B）
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.funds import (
    FundAdviceResponse,
    FundHistoryDetailResponse,
    FundHistoryListResponse,
    FundHoldingsResponse,
    FundTaskAccepted,
    FundTaskInfo,
    FundTaskListResponse,
    FundTaskStatus,
)
from src.services.fund_advice_service import FundAdviceService
from src.services.fund_holdings_service import FundHoldingsService
from src.services.history_service import HistoryService
from src.services.task_queue import (
    get_task_queue,
    DuplicateTaskError,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 模块级单例（与上游 stock endpoint 模式一致）
_fund_advice_service: FundAdviceService | None = None
_history_service: HistoryService | None = None
_holdings_service: FundHoldingsService | None = None


def get_fund_advice_service() -> FundAdviceService:
    """FastAPI 依赖注入：返回 FundAdviceService 单例。"""
    global _fund_advice_service
    if _fund_advice_service is None:
        _fund_advice_service = FundAdviceService()
    return _fund_advice_service


def get_history_service() -> HistoryService:
    """FastAPI 依赖注入：返回 HistoryService 单例。"""
    global _history_service
    if _history_service is None:
        _history_service = HistoryService()
    return _history_service


def _validate_fund_code(fund_code: str) -> str:
    """统一校验基金代码格式。"""
    normalized = fund_code.strip()
    if not re.match(r"^\d{6}$", normalized):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "message": "基金代码格式错误，请输入 6 位数字代码",
            },
        )
    return normalized


# ── 1. 同步无状态建议 ──


@router.get(
    "/{fund_code}/advice",
    response_model=FundAdviceResponse,
    responses={
        200: {"description": "基金建议数据"},
        404: {"description": "基金数据不存在", "model": ErrorResponse},
        422: {"description": "参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取基金策略建议",
    description="基于均线、MACD、RSI 与量能返回基金建议；可选深度模式附加新闻+LLM 分析。",
)
def get_fund_advice(
    fund_code: str,
    days: int = Query(120, ge=60, le=365, description="分析历史天数"),
    mode: Literal["fast", "deep"] = Query("fast", description="分析模式：fast 快速规则 / deep 深度分析"),
    service: FundAdviceService = Depends(get_fund_advice_service),
) -> FundAdviceResponse:
    """获取基金策略建议（同步无状态，不入历史）。"""
    normalized_code = _validate_fund_code(fund_code)

    try:
        result = service.get_advice(normalized_code, days=days, mode=mode)
    except Exception as e:
        logger.error(f"获取基金建议失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"获取基金建议失败: {str(e)}"},
        )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": f"未找到基金 {normalized_code} 的可用数据"},
        )

    return FundAdviceResponse(**result)


# ── 2. 分析并持久化（Phase 2B + Phase 4 async） ──


@router.post(
    "/analyze",
    summary="分析基金并持久化",
    description="分析基金并将结果写入历史记录。async_mode=True 时提交异步任务返回 202。",
    responses={
        200: {"description": "分析成功并已入历史（同步模式）"},
        202: {"description": "异步任务已接受", "model": FundTaskAccepted},
        404: {"description": "基金数据不存在", "model": ErrorResponse},
        409: {"description": "基金正在分析中", "model": ErrorResponse},
        422: {"description": "参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
)
def analyze_fund(
    fund_code: str = Query(..., description="基金代码（6 位数字）"),
    days: int = Query(120, ge=60, le=365, description="分析历史天数"),
    mode: Literal["fast", "deep"] = Query("fast", description="分析模式"),
    async_mode: bool = Query(False, description="是否异步执行（True 返回 202）"),
    service: FundAdviceService = Depends(get_fund_advice_service),
):
    """分析基金并持久化。async_mode=True 时提交异步任务。"""
    normalized_code = _validate_fund_code(fund_code)

    # 异步模式：提交任务队列
    if async_mode:
        return _handle_fund_async(normalized_code, mode, days)

    # 同步模式：原有逻辑不变
    try:
        result = service.analyze_and_persist(
            fund_code=normalized_code, days=days, mode=mode
        )
    except Exception as e:
        logger.error(f"基金分析持久化失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"基金分析失败: {str(e)}"},
        )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": f"未找到基金 {normalized_code} 的可用数据"},
        )

    return result


def _handle_fund_async(fund_code: str, mode: str, days: int) -> JSONResponse:
    """处理基金异步分析请求。"""
    task_queue = get_task_queue()
    try:
        task_info = task_queue.submit_task(
            stock_code=fund_code,
            stock_name=None,
            asset_type="fund",
            analysis_mode=mode,
            days=days,
        )
        return JSONResponse(
            status_code=202,
            content=FundTaskAccepted(
                task_id=task_info.task_id,
                status="pending",
                message=f"基金分析任务已加入队列: {fund_code} (mode={mode})",
            ).model_dump(),
        )
    except DuplicateTaskError as e:
        return JSONResponse(
            status_code=409,
            content={
                "error": "duplicate_task",
                "message": str(e),
                "fund_code": e.stock_code,
                "existing_task_id": e.existing_task_id,
            },
        )


# ── 3. 基金任务状态（Phase 4） ──


@router.get(
    "/status/{task_id}",
    response_model=FundTaskStatus,
    summary="查询基金分析任务状态",
    description="根据 task_id 查询基金任务状态。先查内存队列，再查 DB 历史。",
    responses={
        200: {"description": "任务状态"},
        404: {"description": "任务不存在", "model": ErrorResponse},
    },
)
def get_fund_task_status(task_id: str) -> FundTaskStatus:
    """查询基金任务状态（fund-shaped fallback）。"""
    # 1. 先查内存队列
    task_queue = get_task_queue()
    task = task_queue.get_task(task_id)

    if task and task.asset_type == "fund":
        # 未完成的任务：直接返回内存态 metadata
        if task.status.value != "completed":
            return FundTaskStatus(
                task_id=task.task_id,
                status=task.status.value,
                progress=task.progress,
                fund_code=task.stock_code,
                analysis_mode=task.analysis_mode,
                error=task.error,
                created_at=task.created_at.isoformat(),
            )
        # 已完成的任务：优先走 DB fallback 拿完整 payload
        db_result = _fund_task_db_fallback(task_id)
        if db_result:
            return db_result
        # DB 还没写入（极短窗口）：兜底用内存 result
        return FundTaskStatus(
            task_id=task.task_id,
            status="completed",
            progress=100,
            fund_code=task.stock_code,
            analysis_mode=task.analysis_mode,
            result=task.result,
            created_at=task.created_at.isoformat(),
        )

    # 2. DB fallback: 查 analysis_history (asset_type='fund')
    result = _fund_task_db_fallback(task_id)
    if result:
        return result

    raise HTTPException(
        status_code=404,
        detail={"error": "not_found", "message": f"基金任务 {task_id} 不存在或已过期"},
    )


def _fund_task_db_fallback(task_id: str) -> Optional[FundTaskStatus]:
    """从 DB 查询已完成的基金任务，组装 fund-shaped 响应。"""
    try:
        from src.storage import DatabaseManager
        from src.utils.data_processing import parse_json_field

        db = DatabaseManager.get_instance()
        records = db.get_analysis_history(query_id=task_id, asset_type="fund", limit=1)
        if not records:
            return None

        record = records[0]
        raw = parse_json_field(record.raw_result)

        return FundTaskStatus(
            task_id=task_id,
            status="completed",
            progress=100,
            fund_code=record.input_code or record.code,
            analysis_code=record.code,
            analysis_mode=(raw or {}).get("analysis_mode"),
            record_id=record.id,
            result=raw,
            created_at=record.created_at.isoformat() if record.created_at else None,
        )
    except Exception as e:
        logger.error(f"基金任务 DB fallback 失败: {e}", exc_info=True)
        return None


# ── 4. 基金任务列表（Phase 4） ──


@router.get(
    "/tasks",
    response_model=FundTaskListResponse,
    summary="获取基金任务列表",
    description="获取当前所有基金分析任务（仅 fund 类型）。",
)
def get_fund_task_list(
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
) -> FundTaskListResponse:
    """获取基金任务列表（fund-only）。"""
    task_queue = get_task_queue()
    all_tasks = task_queue.list_all_tasks(limit=100)
    fund_tasks = [t for t in all_tasks if t.asset_type == "fund"]

    pending = sum(1 for t in fund_tasks if t.status.value == "pending")
    processing = sum(1 for t in fund_tasks if t.status.value == "processing")

    task_infos = [
        FundTaskInfo(
            task_id=t.task_id,
            fund_code=t.stock_code,
            fund_name=t.stock_name,
            asset_type=t.asset_type,
            analysis_mode=t.analysis_mode,
            status=t.status.value,
            progress=t.progress,
            message=t.message,
            error=t.error,
            created_at=t.created_at.isoformat(),
            started_at=t.started_at.isoformat() if t.started_at else None,
            completed_at=t.completed_at.isoformat() if t.completed_at else None,
        )
        for t in fund_tasks[:limit]
    ]

    return FundTaskListResponse(
        total=len(fund_tasks),
        pending=pending,
        processing=processing,
        tasks=task_infos,
    )


# ── 5. 基金任务 SSE 流（Phase 4） ──


@router.get(
    "/tasks/stream",
    summary="基金任务 SSE 流",
    description="通过 SSE 实时推送基金任务状态变化（仅 fund 类型）。",
    responses={200: {"description": "SSE 事件流", "content": {"text/event-stream": {}}}},
)
async def fund_task_stream():
    """基金任务 SSE 流（fund-only）。"""
    async def event_generator():
        task_queue = get_task_queue()
        event_queue: asyncio.Queue = asyncio.Queue()

        yield _format_sse_event("connected", {"message": "Connected to fund task stream"})

        # 发送当前进行中的基金任务
        pending_tasks = task_queue.list_pending_tasks()
        for task in pending_tasks:
            if task.asset_type == "fund":
                yield _format_sse_event("task_created", task.to_dict())

        task_queue.subscribe(event_queue)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=30)
                    # 只转发 fund 类型事件
                    if event.get("data", {}).get("asset_type") == "fund":
                        yield _format_sse_event(event["type"], event["data"])
                except asyncio.TimeoutError:
                    yield _format_sse_event("heartbeat", {"timestamp": datetime.now().isoformat()})
        except asyncio.CancelledError:
            pass
        finally:
            task_queue.unsubscribe(event_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


def _format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """格式化 SSE 事件。"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── 6. 基金历史列表（Phase 3） ──


@router.get(
    "/history",
    response_model=FundHistoryListResponse,
    summary="获取基金历史列表",
    description="分页查询基金分析历史记录（仅返回 asset_type=fund 的记录）。",
)
def get_fund_history(
    fund_code: Optional[str] = Query(None, description="基金代码筛选"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页条数"),
    service: HistoryService = Depends(get_history_service),
) -> FundHistoryListResponse:
    """获取基金历史列表。"""
    result = service.get_fund_history_list(
        fund_code=fund_code,
        start_date=start_date,
        end_date=end_date,
        page=page,
        limit=limit,
    )
    return FundHistoryListResponse(**result)


# ── 7. 基金历史详情（Phase 3） ──


@router.get(
    "/history/{record_id}",
    response_model=FundHistoryDetailResponse,
    summary="获取基金历史详情",
    description="根据记录 ID 获取基金分析历史详情。",
    responses={
        200: {"description": "基金历史详情"},
        404: {"description": "记录不存在或不是基金记录", "model": ErrorResponse},
    },
)
def get_fund_history_detail(
    record_id: int,
    service: HistoryService = Depends(get_history_service),
) -> FundHistoryDetailResponse:
    """获取基金历史详情。"""
    result = service.get_fund_history_detail_by_id(record_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": f"未找到记录 {record_id} 或该记录不是基金记录"},
        )
    return FundHistoryDetailResponse(**result)


def get_holdings_service() -> FundHoldingsService:
    """FastAPI 依赖注入：返回 FundHoldingsService 单例。"""
    global _holdings_service
    if _holdings_service is None:
        _holdings_service = FundHoldingsService()
    return _holdings_service


# ── 8. 基金持仓（Phase 3B） ──


@router.get(
    "/{fund_code}/holdings",
    response_model=FundHoldingsResponse,
    summary="获取基金持仓",
    description="获取基金（ETF）成分股/公开持仓。is_realtime 始终为 False。",
    responses={
        200: {"description": "持仓数据"},
        422: {"description": "参数错误", "model": ErrorResponse},
    },
)
def get_fund_holdings(
    fund_code: str,
    service: FundHoldingsService = Depends(get_holdings_service),
) -> FundHoldingsResponse:
    """获取基金持仓。"""
    normalized_code = _validate_fund_code(fund_code)
    result = service.get_holdings_for_fund(normalized_code)
    return FundHoldingsResponse(**result)


# ── 9. 历史记录关联持仓（Phase 3B） ──


@router.get(
    "/history/{record_id}/holdings",
    response_model=FundHoldingsResponse,
    summary="获取历史记录关联的持仓",
    description="获取与基金分析历史记录关联的持仓快照。",
    responses={
        200: {"description": "持仓数据"},
        404: {"description": "记录不存在或不是基金记录", "model": ErrorResponse},
    },
)
def get_history_holdings(
    record_id: int,
    service: FundHoldingsService = Depends(get_holdings_service),
) -> FundHoldingsResponse:
    """获取历史记录关联的持仓。"""
    result = service.get_holdings_for_history_record(record_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": f"未找到记录 {record_id} 或该记录不是基金记录"},
        )
    return FundHoldingsResponse(**result)

