# -*- coding: utf-8 -*-
"""
===================================
股票服务层单元测试
===================================

职责：
1. 验证基金代码映射后仍能返回策略字段
2. 验证实时/历史接口在抓取失败时可回退数据库
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from src.services.stock_service import StockService


class StockServiceTestCase(unittest.TestCase):
    """StockService 测试"""

    @patch("src.services.stock_service.StockRepository")
    @patch("src.services.fund_mapping.resolve_code")
    @patch("data_provider.base.DataFetcherManager")
    def test_get_realtime_quote_returns_strategy_fields_with_mapping(
        self,
        mock_manager_cls,
        mock_resolve_code,
        mock_repo_cls,
    ) -> None:
        """基金代码映射后，实时接口应包含策略常用字段。"""
        mock_resolve_code.return_value = (
            "516980",
            "测试基金A",
            "场外基金 017811 -> 516980",
        )

        repo_instance = mock_repo_cls.return_value
        repo_instance.get_latest.return_value = [
            SimpleNamespace(
                close=1.20,
                ma5=1.18,
                ma10=1.16,
                ma20=1.14,
                volume_ratio=0.88,
                data_source="EfinanceFetcher",
            ),
            SimpleNamespace(close=1.15),
        ]

        manager = mock_manager_cls.return_value
        manager.get_realtime_quote.return_value = SimpleNamespace(
            code="516980",
            name="证券ETF先锋",
            price=1.23,
            change_amount=0.03,
            change_pct=2.50,
            open_price=1.20,
            high=1.24,
            low=1.18,
            pre_close=1.20,
            volume=1234567,
            amount=123456789.0,
            volume_ratio=1.10,
            turnover_rate=0.82,
            pe_ratio=25.6,
            pb_ratio=2.1,
            total_mv=100000000.0,
            circ_mv=60000000.0,
            source=SimpleNamespace(value="tencent"),
        )

        service = StockService()
        result = service.get_realtime_quote("017811")

        self.assertIsNotNone(result)
        self.assertEqual(result["stock_code"], "017811")
        self.assertEqual(result["analysis_code"], "516980")
        self.assertEqual(result["mapped_from"], "017811")
        self.assertEqual(result["mapping_note"], "场外基金 017811 -> 516980")
        self.assertIn("测试基金A", result["stock_name"])
        self.assertEqual(result["current_price"], 1.23)
        self.assertEqual(result["volume_ratio"], 1.10)
        self.assertEqual(result["ma5"], 1.18)
        self.assertEqual(result["ma10"], 1.16)
        self.assertEqual(result["ma20"], 1.14)
        self.assertEqual(result["data_source"], "tencent")

    @patch("src.services.stock_service.StockRepository")
    @patch("src.services.fund_mapping.resolve_code")
    @patch("data_provider.base.DataFetcherManager")
    def test_get_realtime_quote_fallback_to_db_when_quote_missing(
        self,
        mock_manager_cls,
        mock_resolve_code,
        mock_repo_cls,
    ) -> None:
        """实时抓取失败时应回退数据库，避免接口空响应。"""
        mock_resolve_code.return_value = ("600519", None, None)

        repo_instance = mock_repo_cls.return_value
        repo_instance.get_latest.return_value = [
            SimpleNamespace(
                open=1780.0,
                high=1810.0,
                low=1775.0,
                close=1800.0,
                volume=1000000.0,
                amount=1800000000.0,
                pct_chg=1.12,
                ma5=1792.0,
                ma10=1786.0,
                ma20=1768.0,
                volume_ratio=1.05,
                data_source="database",
            ),
            SimpleNamespace(close=1780.0),
        ]

        manager = mock_manager_cls.return_value
        manager.get_realtime_quote.return_value = None
        manager.get_stock_name.return_value = "贵州茅台"

        service = StockService()
        result = service.get_realtime_quote("600519")

        self.assertIsNotNone(result)
        self.assertEqual(result["stock_code"], "600519")
        self.assertEqual(result["analysis_code"], "600519")
        self.assertEqual(result["current_price"], 1800.0)
        self.assertEqual(result["change"], 20.0)
        self.assertEqual(result["change_percent"], 1.12)
        self.assertEqual(result["ma5"], 1792.0)
        self.assertEqual(result["data_source"], "database")

    @patch("src.services.stock_service.StockRepository")
    @patch("src.services.fund_mapping.resolve_code")
    @patch("data_provider.base.DataFetcherManager")
    def test_get_history_data_includes_strategy_fields_and_mapping(
        self,
        mock_manager_cls,
        mock_resolve_code,
        mock_repo_cls,
    ) -> None:
        """历史接口应返回 MA/量比等策略字段，并返回映射元信息。"""
        mock_resolve_code.return_value = (
            "516980",
            "测试基金A",
            "场外基金 017811 -> 516980",
        )

        repo_instance = mock_repo_cls.return_value
        repo_instance.get_range.return_value = []

        manager = mock_manager_cls.return_value
        manager.get_stock_name.return_value = "证券ETF先锋"
        manager.get_daily_data.return_value = (
            pd.DataFrame(
                [
                    {
                        "date": pd.Timestamp("2026-02-10"),
                        "open": 1.10,
                        "high": 1.20,
                        "low": 1.08,
                        "close": 1.18,
                        "volume": 1000,
                        "amount": 1180,
                        "pct_chg": 1.72,
                        "ma5": 1.15,
                        "ma10": 1.12,
                        "ma20": 1.10,
                        "volume_ratio": 0.95,
                    }
                ]
            ),
            "EfinanceFetcher",
        )

        service = StockService()
        result = service.get_history_data("017811", days=10)

        self.assertEqual(result["stock_code"], "017811")
        self.assertEqual(result["analysis_code"], "516980")
        self.assertEqual(result["mapped_from"], "017811")
        self.assertEqual(result["data_source"], "EfinanceFetcher")
        self.assertIn("测试基金A", result["stock_name"])
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["ma5"], 1.15)
        self.assertEqual(result["data"][0]["volume_ratio"], 0.95)

    @patch("src.services.stock_service.StockRepository")
    @patch("src.services.fund_mapping.resolve_code")
    @patch("data_provider.base.DataFetcherManager")
    def test_get_history_data_fallback_to_db(
        self,
        mock_manager_cls,
        mock_resolve_code,
        mock_repo_cls,
    ) -> None:
        """历史抓取失败时应使用数据库兜底。"""
        mock_resolve_code.return_value = ("600519", None, None)

        manager = mock_manager_cls.return_value
        manager.get_daily_data.side_effect = RuntimeError("network error")
        manager.get_stock_name.return_value = "贵州茅台"

        repo_instance = mock_repo_cls.return_value
        repo_instance.get_range.return_value = [
            SimpleNamespace(
                date=pd.Timestamp("2026-02-11"),
                open=1780.0,
                high=1810.0,
                low=1775.0,
                close=1800.0,
                volume=1000000.0,
                amount=1800000000.0,
                pct_chg=1.12,
                ma5=1792.0,
                ma10=1786.0,
                ma20=1768.0,
                volume_ratio=1.05,
            )
        ]

        service = StockService()
        result = service.get_history_data("600519", days=10)

        self.assertEqual(result["stock_code"], "600519")
        self.assertEqual(result["analysis_code"], "600519")
        self.assertEqual(result["data_source"], "database")
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["close"], 1800.0)
        self.assertEqual(result["data"][0]["ma20"], 1768.0)


if __name__ == "__main__":
    unittest.main()
