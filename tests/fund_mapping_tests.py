# -*- coding: utf-8 -*-
"""
===================================
基金映射服务单元测试
===================================
"""

import time
import unittest
from unittest.mock import patch

from src.services import fund_mapping


class FundMappingTestCase(unittest.TestCase):
    """fund_mapping 测试"""

    def tearDown(self) -> None:
        fund_mapping.get_fund_etf_mapping.cache_clear()

    @patch.dict("src.services.fund_mapping.FUND_ETF_STATIC_MAP", {}, clear=True)
    @patch("src.services.fund_mapping._query_fund_mapping_via_akshare")
    def test_get_fund_etf_mapping_returns_none_when_query_timeout(
        self,
        mock_query,
    ) -> None:
        """动态映射超时应快速降级返回 None。"""
        fund_mapping.get_fund_etf_mapping.cache_clear()

        def _slow_query(_: str):
            time.sleep(0.2)
            return ("510300", "测试基金", "测试ETF")

        mock_query.side_effect = _slow_query

        with patch.object(fund_mapping, "FUND_MAPPING_TIMEOUT_SECONDS", 0.01):
            result = fund_mapping.get_fund_etf_mapping("999998")

        self.assertIsNone(result)
        self.assertEqual(mock_query.call_count, 1)

    @patch.dict("src.services.fund_mapping.FUND_ETF_STATIC_MAP", {}, clear=True)
    @patch("src.services.fund_mapping._query_fund_mapping_via_akshare")
    def test_get_fund_etf_mapping_is_cached(
        self,
        mock_query,
    ) -> None:
        """相同基金重复映射应命中缓存。"""
        fund_mapping.get_fund_etf_mapping.cache_clear()

        mock_query.return_value = ("510300", "测试基金", "测试ETF")

        first = fund_mapping.get_fund_etf_mapping("999997")
        second = fund_mapping.get_fund_etf_mapping("999997")

        self.assertEqual(first, ("510300", "测试基金", "测试ETF"))
        self.assertEqual(second, ("510300", "测试基金", "测试ETF"))
        self.assertEqual(mock_query.call_count, 1)


if __name__ == "__main__":
    unittest.main()
