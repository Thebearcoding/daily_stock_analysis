# -*- coding: utf-8 -*-
"""
===================================
基金建议接口
===================================

职责：
1. GET  /api/v1/funds/{fund_code}/advice — 同步无状态建议（不入历史）
2. POST /api/v1/funds/analyze             — 分析并持久化（Phase 2B）
3. GET  /api/v1/funds/history             — 基金历史列表（Phase 3）
4. GET  /api/v1/funds/history/{record_id} — 基金历史详情（Phase 3）
"""

import logging
import re
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.funds import (
    FundAdviceResponse,
    FundHistoryDetailResponse,
    FundHistoryListResponse,
)
from src.services.fund_advice_service import FundAdviceService
from src.services.history_service import HistoryService

logger = logging.getLogger(__name__)

router = APIRouter()

# 模块级单例（与上游 stock endpoint 模式一致）
_fund_advice_service: FundAdviceService | None = None
_history_service: HistoryService | None = None


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


# ── 2. 分析并持久化（Phase 2B） ──


@router.post(
    "/analyze",
    summary="分析基金并持久化",
    description="分析基金并将结果写入历史记录（单 owner 入口）。",
    responses={
        200: {"description": "分析成功并已入历史"},
        404: {"description": "基金数据不存在", "model": ErrorResponse},
        422: {"description": "参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
)
def analyze_fund(
    fund_code: str = Query(..., description="基金代码（6 位数字）"),
    days: int = Query(120, ge=60, le=365, description="分析历史天数"),
    mode: Literal["fast", "deep"] = Query("fast", description="分析模式"),
    service: FundAdviceService = Depends(get_fund_advice_service),
):
    """分析基金并持久化到 analysis_history。"""
    normalized_code = _validate_fund_code(fund_code)

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


# ── 3. 基金历史列表（Phase 3） ──


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


# ── 4. 基金历史详情（Phase 3） ──


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

