# -*- coding: utf-8 -*-
"""
===================================
基金映射服务单元测试
===================================
"""

import time
import unittest
import importlib.util
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from pathlib import Path

import pandas as pd

MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "services" / "fund_mapping.py"
SPEC = importlib.util.spec_from_file_location("fund_mapping_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
fund_mapping = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fund_mapping)


class FundMappingTestCase(unittest.TestCase):
    """fund_mapping 测试"""

    def tearDown(self) -> None:
        fund_mapping._mapping_cache.clear()
        fund_mapping._fund_metadata_cache.clear()
        fund_mapping._fund_name_cache = None
        fund_mapping._fund_name_cache_time = 0.0

    def test_get_fund_etf_mapping_returns_none_when_query_timeout(
        self,
    ) -> None:
        """动态映射超时应快速降级返回 None。"""
        fund_mapping._mapping_cache.clear()

        with patch.dict(fund_mapping.FUND_ETF_STATIC_MAP, {}, clear=True):
            with patch.object(fund_mapping, "_query_fund_mapping_via_akshare") as mock_query:
                def _slow_query(_: str):
                    time.sleep(0.2)
                    return ("510300", "测试基金", "测试ETF")

                mock_query.side_effect = _slow_query

                with patch.object(fund_mapping, "FUND_MAPPING_TIMEOUT_SECONDS", 0.01):
                    result = fund_mapping.get_fund_etf_mapping("999998")

        self.assertIsNone(result)
        self.assertEqual(mock_query.call_count, 1)

    def test_get_fund_etf_mapping_is_cached(
        self,
    ) -> None:
        """相同基金重复映射应命中缓存。"""
        fund_mapping._mapping_cache.clear()

        with patch.dict(fund_mapping.FUND_ETF_STATIC_MAP, {}, clear=True):
            with patch.object(fund_mapping, "_query_fund_mapping_via_akshare") as mock_query:
                mock_query.return_value = ("510300", "测试基金", "测试ETF")

                first = fund_mapping.get_fund_etf_mapping("999997")
                second = fund_mapping.get_fund_etf_mapping("999997")

        self.assertEqual(first, ("510300", "测试基金", "测试ETF"))
        self.assertEqual(second, ("510300", "测试基金", "测试ETF"))
        self.assertEqual(mock_query.call_count, 1)

    def test_normalize_fund_name_for_matching_strips_generic_terms(self) -> None:
        """基金全称中的通用词不应参与 ETF 主题匹配。"""
        normalized = fund_mapping._normalize_fund_name_for_matching(
            "中航机遇领航混合型发起式证券投资基金C"
        )

        self.assertEqual(normalized, "中航机遇领航")

    @patch.dict("sys.modules", {
        "akshare": SimpleNamespace(
            fund_individual_basic_info_xq=lambda symbol: pd.DataFrame([
                ["基金全称", "中航机遇领航混合型发起式证券投资基金"],
                ["基金类型", "混合型-偏股"],
                ["业绩比较基准", "沪深300指数收益率*60%+中债综合指数收益率*40%"],
            ]),
            fund_etf_spot_em=lambda: pd.DataFrame(columns=["代码", "名称", "成交额"]),
        )
    })
    def test_active_mixed_fund_skips_etf_mapping(self) -> None:
        """主动混合基金应优先走无映射逻辑，而不是被通用词误映射。"""
        result = fund_mapping._query_fund_mapping_via_akshare("018957")
        self.assertIsNone(result)

    def test_get_fund_name_concurrent_calls_share_single_metadata_fetch(self) -> None:
        """并发获取基金名称时，应通过锁和缓存避免重复打底层接口。"""
        call_count = 0

        def _fund_info(symbol: str):
            nonlocal call_count
            call_count += 1
            time.sleep(0.05)
            return pd.DataFrame([
                ["基金简称", "并发测试基金"],
                ["基金全称", "并发测试基金全称"],
            ])

        fake_akshare = SimpleNamespace(
            fund_individual_basic_info_xq=_fund_info,
            fund_name_em=lambda: pd.DataFrame(columns=["基金代码", "基金简称"]),
        )

        with patch.dict("sys.modules", {"akshare": fake_akshare}):
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [
                    executor.submit(fund_mapping.get_fund_name, "099999")
                    for _ in range(4)
                ]
                results = [future.result(timeout=1) for future in futures]

        self.assertEqual(results, ["并发测试基金全称"] * 4)
        self.assertEqual(call_count, 1)

    def test_resolve_code_returns_fund_identity_for_unmapped_otc_fund(self) -> None:
        """未映射场外基金也应返回 fund_name/analysis_name，避免下游重复查名。"""
        with patch.object(fund_mapping, "get_fund_etf_mapping", return_value=None):
            with patch.object(fund_mapping, "get_fund_name", return_value="中航机遇领航混合型发起式证券投资基金"):
                result = fund_mapping.resolve_code("018957")

        self.assertEqual(
            result,
            (
                "018957",
                "中航机遇领航混合型发起式证券投资基金",
                "中航机遇领航混合型发起式证券投资基金",
                "场外基金 018957(中航机遇领航混合型发起式证券投资基金) 未映射ETF，直接按基金净值路径分析",
            ),
        )


if __name__ == "__main__":
    unittest.main()
