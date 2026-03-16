# -*- coding: utf-8 -*-
"""
===================================
股票数据服务层
===================================

职责：
1. 封装股票数据获取逻辑
2. 提供实时行情和历史数据接口
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple

from src.repositories.stock_repo import StockRepository

logger = logging.getLogger(__name__)


class StockService:
    """
    股票数据服务
    
    封装股票数据获取的业务逻辑
    """
    
    def __init__(self):
        """初始化股票数据服务"""
        self.repo = StockRepository()

    @staticmethod
    def _resolve_analysis_code(
        stock_code: str,
    ) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
        """
        统一解析分析代码。

        场外基金会自动映射到对应 ETF，普通股票/ETF 原样返回。
        """
        try:
            from src.services.fund_mapping import resolve_code

            return resolve_code(stock_code)
        except Exception as e:
            logger.warning(f"基金代码映射失败，回退原始代码 {stock_code}: {e}")
            return stock_code, None, None, None

    @staticmethod
    def _compose_name(
        base_name: Optional[str],
        original_fund_name: Optional[str],
        analysis_code: str,
    ) -> Optional[str]:
        """
        组合展示名称：
        - 基金映射场景：展示“原基金名（对应ETF: xxx）”
        - 非基金映射场景：使用原名称
        """
        if original_fund_name:
            if base_name:
                return f"{original_fund_name}（对应ETF: {base_name}）"
            return f"{original_fund_name}（对应ETF: {analysis_code}）"
        return base_name

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        """安全转换为 float，失败返回 None。"""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    
    def get_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票实时行情
        
        Args:
            stock_code: 股票代码
            
        Returns:
            实时行情数据字典
        """
        analysis_code, original_fund_name, analysis_name, mapping_note = self._resolve_analysis_code(stock_code)

        try:
            # 调用数据获取器获取实时行情
            from data_provider.base import DataFetcherManager
            
            manager = DataFetcherManager()
            quote = manager.get_realtime_quote(analysis_code)

            # 同步读取数据库最新日线，补齐策略字段（MA/量比）并做抓取失败回退
            latest_rows = self.repo.get_latest(analysis_code, days=2)
            latest = latest_rows[0] if latest_rows else None
            previous = latest_rows[1] if len(latest_rows) > 1 else None
            
            if quote is None:
                logger.warning(f"获取 {analysis_code} 实时行情失败，尝试数据库回退")
                if latest is None:
                    return None

                prev_close = previous.close if previous else None
                change = (latest.close - prev_close) if (latest.close is not None and prev_close is not None) else None
                actual_name = manager.get_stock_name(analysis_code) or analysis_name
                name = self._compose_name(
                    base_name=actual_name,
                    original_fund_name=original_fund_name,
                    analysis_code=analysis_code,
                )
                return {
                    "stock_code": stock_code,
                    "analysis_code": analysis_code,
                    "mapped_from": stock_code if analysis_code != stock_code else None,
                    "mapping_note": mapping_note,
                    "stock_name": name,
                    "current_price": latest.close or 0.0,
                    "change": change,
                    "change_percent": latest.pct_chg,
                    "open": latest.open,
                    "high": latest.high,
                    "low": latest.low,
                    "prev_close": prev_close,
                    "volume": latest.volume,
                    "amount": latest.amount,
                    "volume_ratio": latest.volume_ratio,
                    "turnover_rate": None,
                    "pe_ratio": None,
                    "pb_ratio": None,
                    "total_mv": None,
                    "circ_mv": None,
                    "ma5": latest.ma5,
                    "ma10": latest.ma10,
                    "ma20": latest.ma20,
                    "data_source": latest.data_source or "database",
                    "update_time": datetime.now().isoformat(),
                }

            # UnifiedRealtimeQuote 是 dataclass，使用 getattr 安全访问字段
            # 在原有行情字段基础上补充策略常用字段
            actual_name = getattr(quote, "name", None) or analysis_name
            name = self._compose_name(
                base_name=actual_name,
                original_fund_name=original_fund_name,
                analysis_code=analysis_code,
            )
            return {
                "stock_code": stock_code,
                "analysis_code": analysis_code,
                "mapped_from": stock_code if analysis_code != stock_code else None,
                "mapping_note": mapping_note,
                "stock_name": name,
                "current_price": getattr(quote, "price", 0.0) or 0.0,
                "change": getattr(quote, "change_amount", None),
                "change_percent": getattr(quote, "change_pct", None),
                "open": getattr(quote, "open_price", None),
                "high": getattr(quote, "high", None),
                "low": getattr(quote, "low", None),
                "prev_close": getattr(quote, "pre_close", None),
                "volume": getattr(quote, "volume", None),
                "amount": getattr(quote, "amount", None),
                "volume_ratio": getattr(quote, "volume_ratio", None) if getattr(quote, "volume_ratio", None) is not None else (latest.volume_ratio if latest else None),
                "turnover_rate": getattr(quote, "turnover_rate", None),
                "pe_ratio": getattr(quote, "pe_ratio", None),
                "pb_ratio": getattr(quote, "pb_ratio", None),
                "total_mv": getattr(quote, "total_mv", None),
                "circ_mv": getattr(quote, "circ_mv", None),
                "ma5": latest.ma5 if latest else None,
                "ma10": latest.ma10 if latest else None,
                "ma20": latest.ma20 if latest else None,
                "data_source": getattr(getattr(quote, "source", None), "value", None),
                "update_time": datetime.now().isoformat(),
            }
            
        except ImportError:
            logger.warning("DataFetcherManager 未找到，使用占位数据")
            return self._get_placeholder_quote(stock_code, analysis_code, mapping_note)
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}", exc_info=True)
            return None
    
    def get_history_data(
        self,
        stock_code: str,
        period: str = "daily",
        days: int = 30,
        include_name: bool = True,
    ) -> Dict[str, Any]:
        """
        获取股票历史行情
        
        Args:
            stock_code: 股票代码
            period: K 线周期 (daily/weekly/monthly)
            days: 获取天数
            include_name: 是否查询证券名称（关闭可减少外部接口延迟）
            
        Returns:
            历史行情数据字典
            
        Raises:
            ValueError: 当 period 不是 daily 时抛出（weekly/monthly 暂未实现）
        """
        # 验证 period 参数，只支持 daily
        if period != "daily":
            raise ValueError(
                f"暂不支持 '{period}' 周期，目前仅支持 'daily'。"
                "weekly/monthly 聚合功能将在后续版本实现。"
            )
        
        analysis_code, original_fund_name, analysis_name, mapping_note = self._resolve_analysis_code(stock_code)

        df = None
        source = None
        input_name = original_fund_name

        try:
            # 调用数据获取器获取历史数据
            from data_provider.base import DataFetcherManager

            manager = DataFetcherManager()
            try:
                df, source = manager.get_daily_data(analysis_code, days=days)
            except Exception as fetch_error:
                logger.warning(f"获取 {analysis_code} 历史数据失败，尝试数据库回退: {fetch_error}")

            # analysis_name 优先来自映射结果；缺失时在显式请求名称或非映射场景下补查
            if analysis_name is None and (include_name or original_fund_name is None):
                try:
                    analysis_name = manager.get_stock_name(analysis_code)
                except Exception:
                    analysis_name = None

        except ImportError:
            logger.warning("DataFetcherManager 未找到，尝试数据库回退")
        except Exception as e:
            logger.error(f"获取历史数据失败: {e}", exc_info=True)

        data: List[Dict[str, Any]] = []

        # 优先使用实时抓取数据
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                date_val = row.get("date")
                if hasattr(date_val, "strftime"):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    date_str = str(date_val)

                data.append({
                    "date": date_str,
                    "open": self._safe_float(row.get("open")) or 0.0,
                    "high": self._safe_float(row.get("high")) or 0.0,
                    "low": self._safe_float(row.get("low")) or 0.0,
                    "close": self._safe_float(row.get("close")) or 0.0,
                    "volume": self._safe_float(row.get("volume")),
                    "amount": self._safe_float(row.get("amount")),
                    "change_percent": self._safe_float(row.get("pct_chg")),
                    "ma5": self._safe_float(row.get("ma5")),
                    "ma10": self._safe_float(row.get("ma10")),
                    "ma20": self._safe_float(row.get("ma20")),
                    "volume_ratio": self._safe_float(row.get("volume_ratio")),
                })

        # 抓取失败时回退数据库
        if not data:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days * 3)
            records = self.repo.get_range(analysis_code, start_date, end_date)
            source = source or "database"
            for row in records:
                data.append({
                    "date": row.date.strftime("%Y-%m-%d") if row.date else "",
                    "open": row.open or 0.0,
                    "high": row.high or 0.0,
                    "low": row.low or 0.0,
                    "close": row.close or 0.0,
                    "volume": row.volume,
                    "amount": row.amount,
                    "change_percent": row.pct_chg,
                    "ma5": row.ma5,
                    "ma10": row.ma10,
                    "ma20": row.ma20,
                    "volume_ratio": row.volume_ratio,
                })
            if records:
                analysis_name = analysis_name or f"股票{analysis_code}"
            else:
                logger.warning(f"获取 {analysis_code} 历史数据失败")

        stock_name = self._compose_name(
            base_name=analysis_name,
            original_fund_name=input_name,
            analysis_code=analysis_code,
        )

        return {
            "stock_code": stock_code,
            "analysis_code": analysis_code,
            "analysis_name": analysis_name,
            "input_name": input_name,
            "mapped_from": stock_code if analysis_code != stock_code else None,
            "mapping_note": mapping_note,
            "stock_name": stock_name,
            "period": period,
            "data_source": source,
            "data": data,
        }
    
    def _get_placeholder_quote(
        self,
        stock_code: str,
        analysis_code: Optional[str] = None,
        mapping_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取占位行情数据（用于测试）
        
        Args:
            stock_code: 股票代码
            
        Returns:
            占位行情数据
        """
        target_code = analysis_code or stock_code
        return {
            "stock_code": stock_code,
            "analysis_code": target_code,
            "mapped_from": stock_code if target_code != stock_code else None,
            "mapping_note": mapping_note,
            "stock_name": f"股票{stock_code}",
            "current_price": 0.0,
            "change": None,
            "change_percent": None,
            "open": None,
            "high": None,
            "low": None,
            "prev_close": None,
            "volume": None,
            "amount": None,
            "volume_ratio": None,
            "turnover_rate": None,
            "pe_ratio": None,
            "pb_ratio": None,
            "total_mv": None,
            "circ_mv": None,
            "ma5": None,
            "ma10": None,
            "ma20": None,
            "data_source": "placeholder",
            "update_time": datetime.now().isoformat(),
        }
