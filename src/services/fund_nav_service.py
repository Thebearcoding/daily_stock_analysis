# -*- coding: utf-8 -*-
"""
===================================
基金净值数据服务
===================================

职责：
1. 获取场外开放式基金历史净值（单位净值）
2. 返回标准化结构，供 FundAdviceService 的 NAV path 使用
3. 不依赖股票/ETF 行情接口

数据源：akshare fund_open_fund_info_em
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.services.fund_mapping import execute_fund_data_call, get_fund_name

logger = logging.getLogger(__name__)


class FundNavService:
    """场外基金净值数据服务"""

    def __init__(self) -> None:
        pass

    @staticmethod
    def _safe_float(value: Any, digits: int = 4) -> Optional[float]:
        try:
            return round(float(value), digits)
        except (TypeError, ValueError):
            return None

    def get_nav_history(
        self,
        fund_code: str,
        days: int = 120,
        fund_name: Optional[str] = None,
        analysis_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取场外基金历史净值。

        Args:
            fund_code: 基金代码（6位数字，如 018957）
            days: 获取天数

        Returns:
            标准化结构：
            {
                "fund_code": str,
                "fund_name": str,
                "analysis_code": str,       # == fund_code
                "analysis_name": str,       # == fund_name
                "data_source": str,
                "data": [{"date", "open", "high", "low", "close", "volume", "amount"}, ...]
            }
        """
        resolved_fund_name = fund_name or self._fetch_fund_name(fund_code)
        resolved_analysis_name = analysis_name or resolved_fund_name

        nav_rows = self._fetch_nav_data(fund_code, days)

        return {
            "fund_code": fund_code,
            "fund_name": resolved_fund_name,
            "analysis_code": fund_code,
            "analysis_name": resolved_analysis_name,
            "input_name": resolved_fund_name,
            "mapped_from": None,
            "mapping_note": None,
            "stock_name": resolved_fund_name,
            "data_source": "akshare_fund_nav",
            "data": nav_rows,
        }

    def _fetch_fund_name(self, fund_code: str) -> str:
        """获取基金名称，多种接口降级。"""
        try:
            return get_fund_name(fund_code, allow_placeholder=True) or f"基金{fund_code}"
        except Exception as e:
            logger.warning(f"获取基金名称失败，使用占位名 {fund_code}: {e}")
            logger.info(f"fund_metadata_fallback_name used: {fund_code}")
            return f"基金{fund_code}"

    def _fetch_nav_data(
        self, fund_code: str, days: int
    ) -> List[Dict[str, Any]]:
        """
        获取基金单位净值走势。

        使用 akshare.fund_open_fund_info_em(fund=code, indicator="单位净值走势")
        返回 DataFrame: [净值日期, 单位净值, 日增长率]
        """
        try:
            import akshare as ak

            df = execute_fund_data_call(
                f"fund_open_fund_info_em:{fund_code}",
                lambda: ak.fund_open_fund_info_em(
                    symbol=fund_code, indicator="单位净值走势"
                ),
            )
        except Exception as e:
            logger.warning(f"fund_open_fund_info_em 获取 {fund_code} 净值失败: {e}")
            return []

        if df is None or df.empty:
            logger.warning(f"{fund_code} 净值数据为空")
            return []

        # 列名标准化：akshare 返回的列可能是 [净值日期, 单位净值, 日增长率]
        # 也可能是 [date, nav, growth_rate] — 做兼容
        col_map = {}
        for col in df.columns:
            col_lower = str(col).lower()
            if "日期" in col_lower or col_lower == "date":
                col_map["date"] = col
            elif "单位净值" in col_lower or col_lower == "nav":
                col_map["nav"] = col
            elif "增长率" in col_lower or "growth" in col_lower:
                col_map["growth"] = col

        if "date" not in col_map or "nav" not in col_map:
            # 按位置兜底（akshare 标准返回 3 列）
            cols = list(df.columns)
            if len(cols) >= 2:
                col_map["date"] = cols[0]
                col_map["nav"] = cols[1]
            else:
                logger.warning(f"{fund_code} 净值数据列格式异常: {list(df.columns)}")
                return []

        import pandas as pd

        df["_date"] = pd.to_datetime(df[col_map["date"]], errors="coerce")
        df["_nav"] = pd.to_numeric(df[col_map["nav"]], errors="coerce")
        df = df.dropna(subset=["_date", "_nav"])
        df = df.sort_values("_date", ascending=True)

        # 按 days 截取
        if days > 0:
            cutoff = datetime.now() - timedelta(days=days + 30)  # 留余量
            df = df[df["_date"] >= cutoff]

        rows: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            nav = self._safe_float(row["_nav"])
            if nav is None or nav <= 0:
                continue
            date_val = row["_date"]
            date_str = (
                date_val.strftime("%Y-%m-%d")
                if hasattr(date_val, "strftime")
                else str(date_val)
            )
            rows.append(
                {
                    "date": date_str,
                    "open": nav,
                    "high": nav,
                    "low": nav,
                    "close": nav,
                    "volume": None,
                    "amount": None,
                    "change_percent": None,
                }
            )

        logger.info(f"[FundNavService] {fund_code} 获取到 {len(rows)} 条净值数据")
        return rows
