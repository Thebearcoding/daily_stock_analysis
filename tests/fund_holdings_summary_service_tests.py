# -*- coding: utf-8 -*-
"""
===================================
基金持仓摘要服务单元测试
===================================
"""

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "services"
    / "fund_holdings_summary_service.py"
)
SPEC = importlib.util.spec_from_file_location("fund_holdings_summary_service_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
fund_holdings_summary_service = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fund_holdings_summary_service)


class FundHoldingsSummaryServiceTestCase(unittest.TestCase):
    """fund_holdings_summary_service 测试。"""

    def test_build_summary_extracts_cpo_theme_and_medium_concentration(self) -> None:
        response = {
            "source_type": "fund_disclosed_holdings",
            "completeness": "low",
            "as_of_date": "2025年1季度股票投资明细",
            "items": [
                {"stock_code": "300502", "stock_name": "新易盛", "weight": 9.83, "rank": 1},
                {"stock_code": "300308", "stock_name": "中际旭创", "weight": 9.70, "rank": 2},
                {"stock_code": "300476", "stock_name": "胜宏科技", "weight": 9.53, "rank": 3},
                {"stock_code": "300394", "stock_name": "天孚通信", "weight": 9.12, "rank": 4},
                {"stock_code": "002837", "stock_name": "英维克", "weight": 8.37, "rank": 5},
            ],
        }

        summary = fund_holdings_summary_service.FundHoldingsSummaryService._build_summary_from_response(response)

        self.assertEqual(summary["source_type"], "fund_disclosed_holdings")
        self.assertEqual(summary["concentration_level"], "medium")
        self.assertEqual(summary["holdings_signal"], "bullish")
        self.assertIn("CPO/光模块", summary["dominant_themes"])
        self.assertGreaterEqual(summary["top5_weight_sum"], 45.0)
        self.assertTrue(summary["holdings_reasons"])

    def test_build_summary_marks_high_concentration_as_cautious(self) -> None:
        response = {
            "source_type": "fund_disclosed_holdings",
            "completeness": "low",
            "as_of_date": "2025年1季度股票投资明细",
            "items": [
                {"stock_code": "600030", "stock_name": "中信证券", "weight": 18.20, "rank": 1},
                {"stock_code": "300059", "stock_name": "东方财富", "weight": 14.50, "rank": 2},
                {"stock_code": "601211", "stock_name": "国泰海通", "weight": 12.30, "rank": 3},
                {"stock_code": "601688", "stock_name": "华泰证券", "weight": 10.80, "rank": 4},
                {"stock_code": "600999", "stock_name": "招商证券", "weight": 8.60, "rank": 5},
            ],
        }

        summary = fund_holdings_summary_service.FundHoldingsSummaryService._build_summary_from_response(response)

        self.assertEqual(summary["concentration_level"], "high")
        self.assertEqual(summary["holdings_signal"], "cautious")
        self.assertIn("券商", summary["dominant_themes"])
        self.assertTrue(any("集中度" in risk for risk in summary["holdings_risks"]))


if __name__ == "__main__":
    unittest.main()
