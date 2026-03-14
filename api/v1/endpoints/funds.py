# -*- coding: utf-8 -*-
"""
===================================
基金建议接口
===================================

职责：
1. 提供 GET /api/v1/funds/{fund_code}/advice 接口
2. 返回基金（含场外基金映射 ETF 后）的策略建议
"""

import logging
import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.funds import FundAdviceResponse
from src.services.fund_advice_service import FundAdviceService

logger = logging.getLogger(__name__)

router = APIRouter()


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
) -> FundAdviceResponse:
    """
    获取基金策略建议。

    Args:
        fund_code: 基金代码（6位数字）
        days: 历史数据天数
        mode: 分析模式
    """
    normalized_code = fund_code.strip()
    if not re.match(r"^\d{6}$", normalized_code):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "message": "基金代码格式错误，请输入 6 位数字代码",
            },
        )

    try:
        service = FundAdviceService()
        result = service.get_advice(normalized_code, days=days, mode=mode)
    except Exception as e:
        logger.error(f"获取基金建议失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"获取基金建议失败: {str(e)}",
            },
        )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"未找到基金 {normalized_code} 的可用数据",
            },
        )

    return FundAdviceResponse(**result)
