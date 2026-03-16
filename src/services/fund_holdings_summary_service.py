# -*- coding: utf-8 -*-
"""
===================================
基金持仓摘要服务
===================================

职责：
1. 基于已存在的 FundHoldingsService 生成轻量持仓摘要
2. 提供主题识别、集中度判断、风险/依据摘要
3. 用于增强主动基金 NAV path 的建议，不替代净值分析主链路
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.services.fund_holdings_service import FundHoldingsService

logger = logging.getLogger(__name__)


THEME_KEYWORDS: Dict[str, tuple[str, ...]] = {
    "CPO/光模块": (
        "新易盛", "中际旭创", "天孚通信", "华工科技", "太辰光", "光库科技",
        "联特科技", "源杰科技", "德科立", "仕佳光子", "光模块", "CPO",
    ),
    "AI算力硬件": (
        "胜宏科技", "沪电股份", "工业富联", "寒武纪", "海光信息", "景旺电子",
        "生益电子", "算力", "服务器", "PCB",
    ),
    "液冷/温控": (
        "英维克", "高澜股份", "申菱环境", "同飞股份", "液冷", "温控",
    ),
    "半导体": (
        "中芯国际", "北方华创", "中微公司", "韦尔股份", "兆易创新", "卓胜微",
        "寒武纪", "芯片", "半导体", "存储",
    ),
    "军工": (
        "中航", "航发", "航天", "中兵", "军工", "导弹", "舰船",
    ),
    "券商": (
        "中信证券", "东方财富", "国泰海通", "国泰君安", "华泰证券", "广发证券",
        "中金公司", "证券", "券商",
    ),
    "医药": (
        "恒瑞医药", "药明", "迈瑞", "爱尔眼科", "智飞生物", "片仔癀",
        "医药", "生物", "医疗",
    ),
    "新能源": (
        "宁德时代", "隆基绿能", "阳光电源", "亿纬锂能", "德业股份",
        "光伏", "储能", "新能源", "锂电",
    ),
}


class FundHoldingsSummaryService:
    """基金持仓摘要服务。"""

    def __init__(
        self,
        holdings_service: Optional["FundHoldingsService"] = None,
    ) -> None:
        if holdings_service is None:
            from src.services.fund_holdings_service import FundHoldingsService

            holdings_service = FundHoldingsService()
        self.holdings_service = holdings_service

    def get_summary_for_fund(self, fund_code: str) -> Dict[str, Any]:
        """按基金代码生成持仓摘要。"""
        return self.get_summary_for_target(fund_code=fund_code)

    def get_summary_for_target(
        self,
        fund_code: str,
        analysis_code: Optional[str] = None,
        fund_name: Optional[str] = None,
        analysis_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """按已知分析标的生成持仓摘要，analysis_code 缺失时再走映射链。"""
        try:
            if analysis_code:
                items, as_of_date = self.holdings_service._fetch_disclosed_holdings(analysis_code)
                response = {
                    "fund_code": fund_code,
                    "fund_name": fund_name,
                    "analysis_code": analysis_code,
                    "analysis_name": analysis_name,
                    "source_type": "fund_disclosed_holdings" if items else "unavailable",
                    "completeness": "low" if items else "unavailable",
                    "as_of_date": as_of_date,
                    "is_realtime": False,
                    "items": items,
                }
            else:
                response = self.holdings_service.get_holdings_for_fund(
                    fund_code=fund_code,
                    persist_snapshot=False,
                )
        except Exception as exc:
            logger.warning(f"[HoldingsSummary] 获取 {fund_code} 持仓失败: {exc}")
            return self._build_unavailable_summary()

        return self._build_summary_from_response(response)

    @classmethod
    def _build_summary_from_response(cls, response: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """从 holdings 响应构建摘要。"""
        if not response:
            return cls._build_unavailable_summary()

        items = response.get("items") or []
        source_type = response.get("source_type") or "unavailable"
        completeness = response.get("completeness") or "unavailable"
        as_of_date = response.get("as_of_date")

        if source_type == "unavailable" or not items:
            return cls._build_unavailable_summary(
                source_type=source_type,
                completeness=completeness,
                as_of_date=as_of_date,
            )

        normalized = cls._normalize_items(items)
        top_count = len(normalized)
        top1_weight = normalized[0]["weight"] if normalized else 0.0
        top3_weight_sum = round(sum(item["weight"] for item in normalized[:3]), 2)
        top5_weight_sum = round(sum(item["weight"] for item in normalized[:5]), 2)
        top_weight_sum = round(sum(item["weight"] for item in normalized), 2)

        concentration_level = cls._classify_concentration(top1_weight, top5_weight_sum)
        dominant_themes, theme_weights = cls._extract_dominant_themes(normalized)
        holdings_signal = cls._classify_holdings_signal(
            top1_weight=top1_weight,
            top5_weight_sum=top5_weight_sum,
            dominant_themes=dominant_themes,
        )

        reasons = cls._build_reasons(
            dominant_themes=dominant_themes,
            top5_weight_sum=top5_weight_sum,
            concentration_level=concentration_level,
        )
        risks = cls._build_risks(
            top1_weight=top1_weight,
            top5_weight_sum=top5_weight_sum,
            concentration_level=concentration_level,
        )

        return {
            "source_type": source_type,
            "completeness": completeness,
            "as_of_date": as_of_date,
            "is_realtime": False,
            "top_holdings_count": top_count,
            "top_holdings_weight_sum": top_weight_sum,
            "top1_weight": round(top1_weight, 2),
            "top3_weight_sum": top3_weight_sum,
            "top5_weight_sum": top5_weight_sum,
            "concentration_level": concentration_level,
            "dominant_themes": dominant_themes,
            "theme_weights": theme_weights,
            "holdings_signal": holdings_signal,
            "holdings_reasons": reasons,
            "holdings_risks": risks,
        }

    @staticmethod
    def _normalize_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """标准化权重并按排名/权重排序。"""
        normalized: List[Dict[str, Any]] = []
        for item in items:
            try:
                weight = float(item.get("weight") or 0.0)
            except (TypeError, ValueError):
                weight = 0.0
            normalized.append(
                {
                    "stock_code": item.get("stock_code"),
                    "stock_name": str(item.get("stock_name") or "").strip(),
                    "weight": weight,
                    "rank": item.get("rank") or 999,
                }
            )

        normalized.sort(key=lambda row: (row["rank"], -row["weight"]))
        return normalized

    @staticmethod
    def _classify_concentration(top1_weight: float, top5_weight_sum: float) -> str:
        """分类持仓集中度。"""
        if top1_weight >= 15 or top5_weight_sum >= 55:
            return "high"
        if top5_weight_sum >= 35 or top1_weight >= 9:
            return "medium"
        return "low"

    @classmethod
    def _extract_dominant_themes(
        cls,
        items: List[Dict[str, Any]],
    ) -> tuple[List[str], Dict[str, float]]:
        """基于股票名称做轻量主题识别。"""
        theme_weights: Dict[str, float] = {}
        for item in items:
            stock_name = item["stock_name"]
            if not stock_name:
                continue

            for theme, keywords in THEME_KEYWORDS.items():
                if any(keyword in stock_name for keyword in keywords):
                    theme_weights[theme] = round(theme_weights.get(theme, 0.0) + item["weight"], 2)
                    break

        dominant_themes = [
            theme
            for theme, weight in sorted(theme_weights.items(), key=lambda kv: kv[1], reverse=True)
            if weight >= 8
        ][:3]
        return dominant_themes, theme_weights

    @staticmethod
    def _classify_holdings_signal(
        top1_weight: float,
        top5_weight_sum: float,
        dominant_themes: List[str],
    ) -> str:
        """持仓辅助信号：bullish / neutral / cautious。"""
        if dominant_themes and top5_weight_sum >= 35 and top1_weight < 15:
            return "bullish"
        if top1_weight >= 15 or top5_weight_sum >= 60:
            return "cautious"
        return "neutral"

    @staticmethod
    def _build_reasons(
        dominant_themes: List[str],
        top5_weight_sum: float,
        concentration_level: str,
    ) -> List[str]:
        """构建持仓正向依据。"""
        reasons: List[str] = []
        if dominant_themes:
            reasons.append(f"披露持仓主题集中于 {'、'.join(dominant_themes[:2])}")
        if top5_weight_sum >= 40 and concentration_level != "high":
            reasons.append(f"前五大重仓占比 {top5_weight_sum:.1f}%，持仓风格较鲜明")
        return reasons

    @staticmethod
    def _build_risks(
        top1_weight: float,
        top5_weight_sum: float,
        concentration_level: str,
    ) -> List[str]:
        """构建持仓风险提示。"""
        risks: List[str] = ["持仓基于季度披露快照，可能滞后于当前调仓"]
        if concentration_level == "high":
            risks.append(f"前五大重仓占比 {top5_weight_sum:.1f}%，集中度偏高")
        if top1_weight >= 12:
            risks.append(f"单一重仓股占比 {top1_weight:.1f}%，波动放大时回撤风险较高")
        return risks

    @staticmethod
    def _build_unavailable_summary(
        source_type: str = "unavailable",
        completeness: str = "unavailable",
        as_of_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """构建不可用摘要。"""
        return {
            "source_type": source_type,
            "completeness": completeness,
            "as_of_date": as_of_date,
            "is_realtime": False,
            "top_holdings_count": 0,
            "top_holdings_weight_sum": 0.0,
            "top1_weight": 0.0,
            "top3_weight_sum": 0.0,
            "top5_weight_sum": 0.0,
            "concentration_level": "unknown",
            "dominant_themes": [],
            "theme_weights": {},
            "holdings_signal": "unavailable",
            "holdings_reasons": [],
            "holdings_risks": [],
        }
