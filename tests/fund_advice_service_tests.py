# -*- coding: utf-8 -*-
"""
===================================
基金建议服务层单元测试
===================================
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.services.fund_advice_service import FundAdviceService
from src.stock_analyzer import (
    BuySignal,
    MACDStatus,
    RSIStatus,
    StockTrendAnalyzer,
    TrendAnalysisResult,
    TrendStatus,
    VolumeStatus,
)


def _build_rows(days: int = 120, start_price: float = 1.0, step: float = 0.002):
    rows = []
    start = datetime(2025, 1, 1)
    for i in range(days):
        close = start_price + i * step
        rows.append(
            {
                "date": (start + timedelta(days=i)).strftime("%Y-%m-%d"),
                "open": close * 0.995,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 100000 + i * 200,
                "amount": close * (100000 + i * 200),
                "change_percent": 0.5,
            }
        )
    return rows


class FundAdviceServiceTestCase(unittest.TestCase):
    """FundAdviceService 测试"""

    def test_get_advice_returns_none_when_no_data(self) -> None:
        stock_service = MagicMock()
        stock_service.get_history_data.return_value = {"data": []}

        analyzer = StockTrendAnalyzer()
        service = FundAdviceService(stock_service=stock_service, analyzer=analyzer)

        result = service.get_advice("017811")
        self.assertIsNone(result)

    def test_get_advice_prefers_wait_in_bearish_guard_state(self) -> None:
        stock_service = MagicMock()
        stock_service.get_history_data.return_value = {
            "stock_code": "017811",
            "analysis_code": "510300",
            "mapped_from": "017811",
            "mapping_note": "场外基金 017811 -> 510300",
            "stock_name": "测试基金（对应ETF: 510300）",
            "data_source": "unit_test",
            "data": _build_rows(days=120, start_price=1.2, step=-0.0015),
        }

        analysis_result = TrendAnalysisResult(
            code="510300",
            trend_status=TrendStatus.BEAR,
            ma5=1.01,
            ma10=1.03,
            ma20=1.06,
            ma60=1.10,
            current_price=0.98,
            buy_signal=BuySignal.WAIT,
            signal_score=33,
            volume_status=VolumeStatus.HEAVY_VOLUME_DOWN,
            volume_ratio_5d=1.7,
            macd_status=MACDStatus.BEARISH,
            macd_signal="空头排列",
            rsi_status=RSIStatus.WEAK,
            rsi_signal="弱势震荡",
            signal_reasons=["趋势偏弱"],
            risk_factors=["放量下跌"],
        )

        analyzer = StockTrendAnalyzer()
        analyzer.analyze = MagicMock(return_value=analysis_result)

        service = FundAdviceService(stock_service=stock_service, analyzer=analyzer)
        result = service.get_advice("017811")

        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "wait")
        self.assertEqual(result["action_label"], "防守观望")
        self.assertEqual(result["confidence_level"], "低")
        self.assertEqual(result["analysis_code"], "510300")
        self.assertEqual(result["mapped_from"], "017811")

    def test_get_advice_returns_buy_for_bullish_signal(self) -> None:
        stock_service = MagicMock()
        stock_service.get_history_data.return_value = {
            "stock_code": "017811",
            "analysis_code": "159915",
            "mapped_from": "017811",
            "mapping_note": "场外基金 017811 -> 159915",
            "stock_name": "测试基金（对应ETF: 创业板ETF）",
            "data_source": "unit_test",
            "data": _build_rows(days=120, start_price=1.0, step=0.002),
        }

        analysis_result = TrendAnalysisResult(
            code="159915",
            trend_status=TrendStatus.BULL,
            ma5=1.20,
            ma10=1.18,
            ma20=1.15,
            ma60=1.08,
            current_price=1.21,
            buy_signal=BuySignal.BUY,
            signal_score=68,
            volume_status=VolumeStatus.SHRINK_VOLUME_DOWN,
            volume_ratio_5d=0.72,
            macd_status=MACDStatus.GOLDEN_CROSS,
            macd_signal="金叉",
            rsi_status=RSIStatus.STRONG_BUY,
            rsi_signal="强势区间",
            signal_reasons=["多头排列"],
            risk_factors=[],
        )

        analyzer = StockTrendAnalyzer()
        analyzer.analyze = MagicMock(return_value=analysis_result)

        service = FundAdviceService(stock_service=stock_service, analyzer=analyzer)
        result = service.get_advice("017811")

        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "buy")
        self.assertGreaterEqual(result["confidence_score"], 60)
        self.assertIn("strategy", result)
        self.assertIn("buy_zone", result["strategy"])
        self.assertIn("rule_assessment", result)

    def test_get_advice_returns_low_confidence_when_history_insufficient(self) -> None:
        stock_service = MagicMock()
        stock_service.get_history_data.return_value = {
            "stock_code": "024915",
            "analysis_code": "024915",
            "mapped_from": None,
            "mapping_note": None,
            "stock_name": "测试基金024915",
            "data_source": "unit_test",
            "data": _build_rows(days=1, start_price=1.2345, step=0.0),
        }

        service = FundAdviceService(stock_service=stock_service, analyzer=StockTrendAnalyzer())
        result = service.get_advice("024915")

        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "wait")
        self.assertEqual(result["confidence_level"], "低")
        self.assertEqual(result["analysis_code"], "024915")
        self.assertGreaterEqual(result["signal_score"], 0)

    def test_get_advice_fast_mode_skips_deep_pipeline(self) -> None:
        stock_service = MagicMock()
        stock_service.get_history_data.return_value = {
            "stock_code": "017811",
            "analysis_code": "159915",
            "mapped_from": "017811",
            "mapping_note": "场外基金 017811 -> 159915",
            "stock_name": "测试基金（对应ETF: 创业板ETF）",
            "data_source": "unit_test",
            "data": _build_rows(days=120, start_price=1.0, step=0.002),
        }

        analysis_result = TrendAnalysisResult(
            code="159915",
            trend_status=TrendStatus.BULL,
            ma5=1.20,
            ma10=1.18,
            ma20=1.15,
            ma60=1.08,
            current_price=1.21,
            buy_signal=BuySignal.BUY,
            signal_score=68,
            volume_status=VolumeStatus.SHRINK_VOLUME_DOWN,
            volume_ratio_5d=0.72,
            macd_status=MACDStatus.GOLDEN_CROSS,
            macd_signal="金叉",
            rsi_status=RSIStatus.STRONG_BUY,
            rsi_signal="强势区间",
            signal_reasons=["多头排列"],
            risk_factors=[],
        )

        analyzer = StockTrendAnalyzer()
        analyzer.analyze = MagicMock(return_value=analysis_result)
        deep_analyzer = MagicMock()

        service = FundAdviceService(
            stock_service=stock_service,
            analyzer=analyzer,
            analysis_service=deep_analyzer,
        )
        result = service.get_advice("017811", mode="fast")

        self.assertIsNotNone(result)
        self.assertEqual(result["analysis_mode"], "fast")
        self.assertIsNone(result["deep_analysis"])
        deep_analyzer.analyze_stock.assert_not_called()

    def test_get_advice_deep_mode_returns_deep_payload(self) -> None:
        stock_service = MagicMock()
        stock_service.get_history_data.return_value = {
            "stock_code": "017811",
            "analysis_code": "159915",
            "mapped_from": "017811",
            "mapping_note": "场外基金 017811 -> 159915",
            "stock_name": "测试基金（对应ETF: 创业板ETF）",
            "data_source": "unit_test",
            "data": _build_rows(days=120, start_price=1.0, step=0.002),
        }

        analysis_result = TrendAnalysisResult(
            code="159915",
            trend_status=TrendStatus.BULL,
            ma5=1.20,
            ma10=1.18,
            ma20=1.15,
            ma60=1.08,
            current_price=1.21,
            buy_signal=BuySignal.BUY,
            signal_score=68,
            volume_status=VolumeStatus.SHRINK_VOLUME_DOWN,
            volume_ratio_5d=0.72,
            macd_status=MACDStatus.GOLDEN_CROSS,
            macd_signal="金叉",
            rsi_status=RSIStatus.STRONG_BUY,
            rsi_signal="强势区间",
            signal_reasons=["多头排列"],
            risk_factors=[],
        )

        analyzer = StockTrendAnalyzer()
        analyzer.analyze = MagicMock(return_value=analysis_result)

        deep_analyzer = MagicMock()
        deep_analyzer.analyze_stock.return_value = {
            "stock_code": "159915",
            "stock_name": "创业板ETF",
            "report": {
                "meta": {},
                "summary": {
                    "analysis_summary": "深度模式看多",
                    "operation_advice": "持有",
                    "trend_prediction": "震荡上行",
                    "sentiment_score": 66,
                    "sentiment_label": "乐观",
                },
                "strategy": {
                    "ideal_buy": 1.11,
                    "secondary_buy": 1.08,
                    "stop_loss": 1.02,
                    "take_profit": 1.24,
                },
                "details": {
                    "news_summary": "消息面中性偏多",
                    "technical_analysis": "均线多头",
                    "fundamental_analysis": "资金面稳定",
                    "risk_warning": "短线波动",
                },
            },
        }

        service = FundAdviceService(
            stock_service=stock_service,
            analyzer=analyzer,
            analysis_service=deep_analyzer,
        )
        result = service.get_advice("017811", mode="deep")

        self.assertIsNotNone(result)
        self.assertEqual(result["analysis_mode"], "deep")
        self.assertIsNotNone(result["deep_analysis"])
        self.assertEqual(result["deep_analysis"]["status"], "completed")
        self.assertEqual(result["deep_analysis"]["summary"]["analysis_summary"], "深度模式看多")
        deep_analyzer.analyze_stock.assert_called_once()

    def test_get_advice_deep_mode_falls_back_when_pipeline_failed(self) -> None:
        stock_service = MagicMock()
        stock_service.get_history_data.return_value = {
            "stock_code": "017811",
            "analysis_code": "510300",
            "mapped_from": "017811",
            "mapping_note": "场外基金 017811 -> 510300",
            "stock_name": "测试基金（对应ETF: 510300）",
            "data_source": "unit_test",
            "data": _build_rows(days=120, start_price=1.2, step=-0.0015),
        }

        analysis_result = TrendAnalysisResult(
            code="510300",
            trend_status=TrendStatus.BEAR,
            ma5=1.01,
            ma10=1.03,
            ma20=1.06,
            ma60=1.10,
            current_price=0.98,
            buy_signal=BuySignal.WAIT,
            signal_score=33,
            volume_status=VolumeStatus.HEAVY_VOLUME_DOWN,
            volume_ratio_5d=1.7,
            macd_status=MACDStatus.BEARISH,
            macd_signal="空头排列",
            rsi_status=RSIStatus.WEAK,
            rsi_signal="弱势震荡",
            signal_reasons=["趋势偏弱"],
            risk_factors=["放量下跌"],
        )

        analyzer = StockTrendAnalyzer()
        analyzer.analyze = MagicMock(return_value=analysis_result)

        deep_analyzer = MagicMock()
        deep_analyzer.analyze_stock.return_value = None

        service = FundAdviceService(
            stock_service=stock_service,
            analyzer=analyzer,
            analysis_service=deep_analyzer,
        )
        result = service.get_advice("017811", mode="deep")

        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "wait")
        self.assertEqual(result["analysis_mode"], "deep")
        self.assertEqual(result["deep_analysis"]["status"], "failed")
        self.assertTrue(result["deep_analysis"]["error"])

    @patch("src.services.fund_advice_service.DatabaseManager.get_instance")
    def test_analyze_and_persist_sends_notification_after_save(self, mock_get_db) -> None:
        mock_db = MagicMock()
        mock_db.save_fund_advice_history.return_value = 123
        mock_get_db.return_value = mock_db

        notifier = MagicMock()
        notifier.is_available.return_value = True
        notifier.generate_fund_advice_report.return_value = "fund-report"
        notifier.send.return_value = True

        service = FundAdviceService(notifier=notifier)
        service.get_advice = MagicMock(
            return_value={
                "fund_code": "018957",
                "fund_name": "中航机遇领航混合型发起式证券投资基金",
                "input_name": "中航机遇领航混合型发起式证券投资基金",
                "analysis_code": "018957",
                "analysis_name": "中航机遇领航混合型发起式证券投资基金",
                "analysis_mode": "fast",
                "action": "hold",
                "action_label": "持有观察",
                "confidence_score": 68,
                "confidence_level": "中",
                "current_price": 1.23,
                "trend_status": "震荡上行",
                "buy_signal": "hold",
                "signal_score": 61,
                "ma5": 1.21,
                "ma10": 1.2,
                "ma20": 1.18,
                "ma60": 1.12,
                "volume_status": "unavailable",
                "volume_ratio_5d": 0.0,
                "macd": {"status": "金叉"},
                "rsi": {"status": "偏强"},
                "strategy": {
                    "buy_zone": {"low": 1.18, "high": 1.2},
                    "add_zone": {"low": 1.2, "high": 1.22},
                    "stop_loss": 1.1,
                    "take_profit": 1.3,
                    "position_advice": "分批观察建仓",
                },
                "reasons": ["净值站上 MA20"],
                "risk_factors": ["披露持仓为季度快照"],
                "rule_assessment": {
                    "entry_rule": "前大后小，金叉就搞",
                    "exit_rule": "前高后低，转弱就跑",
                    "entry_ready": True,
                    "exit_triggered": False,
                    "comment": "净值趋势改善中",
                },
                "analysis_context": {"analysis_path": "fund_nav"},
                "deep_analysis": None,
            }
        )

        result = service.analyze_and_persist("018957", days=120, mode="fast", query_id="q-1")

        self.assertIsNotNone(result)
        self.assertEqual(result["record_id"], 123)
        notifier.generate_fund_advice_report.assert_called_once()
        notifier.send.assert_called_once_with("fund-report")

    @patch("src.services.fund_advice_service.DatabaseManager.get_instance")
    def test_analyze_and_persist_ignores_notification_failure(self, mock_get_db) -> None:
        mock_db = MagicMock()
        mock_db.save_fund_advice_history.return_value = 124
        mock_get_db.return_value = mock_db

        notifier = MagicMock()
        notifier.is_available.return_value = True
        notifier.generate_fund_advice_report.return_value = "fund-report"
        notifier.send.side_effect = RuntimeError("feishu down")

        service = FundAdviceService(notifier=notifier)
        service.get_advice = MagicMock(
            return_value={
                "fund_code": "018957",
                "fund_name": "中航机遇领航混合型发起式证券投资基金",
                "input_name": "中航机遇领航混合型发起式证券投资基金",
                "analysis_code": "018957",
                "analysis_name": "中航机遇领航混合型发起式证券投资基金",
                "analysis_mode": "fast",
                "action": "wait",
                "action_label": "防守观望",
                "confidence_score": 55,
                "confidence_level": "中",
                "current_price": 1.2,
                "trend_status": "震荡",
                "buy_signal": "wait",
                "signal_score": 48,
                "ma5": 1.2,
                "ma10": 1.19,
                "ma20": 1.18,
                "ma60": 1.15,
                "volume_status": "unavailable",
                "volume_ratio_5d": 0.0,
                "macd": {"status": "等待"},
                "rsi": {"status": "中性"},
                "strategy": {
                    "buy_zone": {"low": 1.15, "high": 1.18},
                    "add_zone": {"low": 1.18, "high": 1.2},
                    "stop_loss": 1.08,
                    "take_profit": 1.28,
                    "position_advice": "继续观察",
                },
                "reasons": ["趋势未完全确认"],
                "risk_factors": ["主题波动较大"],
                "rule_assessment": {
                    "entry_rule": "前大后小，金叉就搞",
                    "exit_rule": "前高后低，转弱就跑",
                    "entry_ready": False,
                    "exit_triggered": False,
                    "comment": "规则条件暂未满足",
                },
                "analysis_context": {"analysis_path": "fund_nav"},
                "deep_analysis": None,
            }
        )

        result = service.analyze_and_persist("018957", days=120, mode="fast", query_id="q-2")

        self.assertIsNotNone(result)
        self.assertEqual(result["record_id"], 124)


if __name__ == "__main__":
    unittest.main()
