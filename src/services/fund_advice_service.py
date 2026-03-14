# -*- coding: utf-8 -*-
"""
===================================
基金建议服务层
===================================

职责：
1. 复用现有行情获取与技术分析能力，输出基金可执行建议
2. 支持场外基金自动映射 ETF 后分析
3. 提供“前大后小，金叉就搞 / 前高后低，放量就跑”规则判断
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.services.analysis_service import AnalysisService
from src.services.stock_service import StockService
from src.storage import DatabaseManager
from src.stock_analyzer import (
    BuySignal,
    MACDStatus,
    StockTrendAnalyzer,
    TrendAnalysisResult,
    TrendStatus,
    VolumeStatus,
)

logger = logging.getLogger(__name__)


class FundAdviceService:
    """基金投资建议服务"""

    MIN_ANALYSIS_DAYS = 80
    FAST_MODE = "fast"
    DEEP_MODE = "deep"

    def __init__(
        self,
        stock_service: Optional[StockService] = None,
        analyzer: Optional[StockTrendAnalyzer] = None,
        analysis_service: Optional[AnalysisService] = None,
    ):
        self.stock_service = stock_service or StockService()
        self.analyzer = analyzer or StockTrendAnalyzer()
        self.analysis_service = analysis_service or AnalysisService()

    @staticmethod
    def _safe_float(value: Any, digits: int = 4) -> float:
        """安全转换为 float，失败时返回 0。"""
        try:
            return round(float(value), digits)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _safe_optional_float(value: Any, digits: int = 4) -> Optional[float]:
        """安全转换为可空 float，失败时返回 None。"""
        try:
            return round(float(value), digits)
        except (TypeError, ValueError):
            return None

    def _normalize_history_dataframe(self, raw_rows: List[Dict[str, Any]]) -> pd.DataFrame:
        """将历史数据统一为分析所需格式。"""
        if not raw_rows:
            return pd.DataFrame()

        df = pd.DataFrame(raw_rows).copy()
        if df.empty:
            return df

        if "date" not in df.columns or "close" not in df.columns:
            return pd.DataFrame()

        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        for col in ["open", "high", "low", "close", "volume", "amount", "change_percent"]:
            if col not in df.columns:
                df[col] = None
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # 分析器依赖 volume，缺失时回填 0，避免直接失败
        df["volume"] = df["volume"].fillna(0.0)
        df["open"] = df["open"].fillna(df["close"])
        df["high"] = df["high"].fillna(df["close"])
        df["low"] = df["low"].fillna(df["close"])

        df = df.dropna(subset=["date", "close"])
        df = df.sort_values("date", ascending=True).reset_index(drop=True)

        return df

    @staticmethod
    def _default_rule_assessment() -> Dict[str, Any]:
        """规则判定的默认空结构。"""
        return {
            "entry_rule": "前大后小，金叉就搞",
            "exit_rule": "前高后低，放量就跑",
            "entry_ready": False,
            "exit_triggered": False,
            "comment": "数据不足，暂无法完成规则判断",
        }

    def _evaluate_rule_assessment(
        self,
        df: pd.DataFrame,
        result: TrendAnalysisResult,
    ) -> Dict[str, Any]:
        """
        规则评估：
        - 入场：前大后小 + 金叉（含上穿零轴）
        - 离场：前高后低 + 放量 / MACD 转弱

        注意：此处需要最近 3 根 MACD 柱状值来判断柱体趋势，
        但 TrendAnalysisResult 仅保存最新 1 根 bar。
        因此从 DataFrame 重新计算，使用 analyzer 的 MACD 参数保持一致。
        """
        if df.empty or len(df) < 3:
            return self._default_rule_assessment()

        close = pd.to_numeric(df["close"], errors="coerce").ffill().bfill()
        ema_fast = close.ewm(span=self.analyzer.MACD_FAST, adjust=False).mean()
        ema_slow = close.ewm(span=self.analyzer.MACD_SLOW, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=self.analyzer.MACD_SIGNAL, adjust=False).mean()
        bar = (dif - dea) * 2

        bars = bar.tail(3).tolist()
        b1, b2, b3 = bars[0], bars[1], bars[2]

        bearish_shrinking = b1 < b2 < b3 < 0
        bullish_fading = b1 > b2 > b3 > 0

        entry_ready = bearish_shrinking and result.macd_status in {
            MACDStatus.GOLDEN_CROSS_ZERO,
            MACDStatus.GOLDEN_CROSS,
            MACDStatus.CROSSING_UP,
        }

        exit_triggered = bullish_fading and (
            result.volume_status == VolumeStatus.HEAVY_VOLUME_DOWN
            or result.macd_status in {MACDStatus.DEATH_CROSS, MACDStatus.CROSSING_DOWN}
        )

        if entry_ready:
            comment = "MACD柱体前大后小且出现金叉，入场条件成立"
        elif exit_triggered:
            comment = "MACD柱体前高后低并出现放量/转弱，减仓条件成立"
        elif bearish_shrinking:
            comment = "MACD空头动能在衰减，等待金叉确认"
        elif bullish_fading:
            comment = "MACD多头动能在衰减，关注冲高回落风险"
        else:
            comment = "规则条件暂未满足，继续观察"

        return {
            "entry_rule": "前大后小，金叉就搞",
            "exit_rule": "前高后低，放量就跑",
            "entry_ready": bool(entry_ready),
            "exit_triggered": bool(exit_triggered),
            "comment": comment,
        }

    @staticmethod
    def _is_bearish_guard_state(result: TrendAnalysisResult) -> bool:
        """均线空头 + 未站上 MA20，默认防守观望。"""
        return result.trend_status in {TrendStatus.BEAR, TrendStatus.STRONG_BEAR} and (
            result.current_price < result.ma20
        )

    def _derive_action(
        self,
        result: TrendAnalysisResult,
        rule_assessment: Dict[str, Any],
    ) -> Tuple[str, str]:
        """根据综合评分和规则判断给出操作动作。"""
        if rule_assessment.get("exit_triggered") or result.buy_signal in {
            BuySignal.STRONG_SELL,
            BuySignal.SELL,
        }:
            return "reduce", "减仓风控"

        if rule_assessment.get("entry_ready") and result.buy_signal in {
            BuySignal.STRONG_BUY,
            BuySignal.BUY,
        }:
            return "buy", "分批买入"

        if self._is_bearish_guard_state(result):
            return "wait", "防守观望"

        if result.buy_signal in {BuySignal.STRONG_BUY, BuySignal.BUY}:
            return "buy", "逢低布局"

        if result.buy_signal == BuySignal.HOLD:
            return "hold", "持有观察"

        return "wait", "等待确认"

    def _derive_confidence(
        self,
        result: TrendAnalysisResult,
        action: str,
        rule_assessment: Dict[str, Any],
    ) -> Tuple[int, str]:
        """
        生成置信度分数和等级。

        置信度反映的是"建议的确信程度"，而非行情方向。
        空头防守时不应人为拉高置信度，观望=不确定性高。
        """
        confidence_score = int(result.signal_score)

        # 仅当规则明确触发时才适度加分
        if rule_assessment.get("entry_ready") or rule_assessment.get("exit_triggered"):
            confidence_score += 10

        if result.trend_status in {TrendStatus.CONSOLIDATION, TrendStatus.WEAK_BULL, TrendStatus.WEAK_BEAR}:
            confidence_score -= 5

        confidence_score = max(0, min(100, confidence_score))

        if confidence_score >= 75:
            level = "高"
        elif confidence_score >= 55:
            level = "中"
        else:
            level = "低"

        return confidence_score, level

    def _build_strategy(self, result: TrendAnalysisResult, action: str) -> Dict[str, Any]:
        """构建基金仓位与价位建议。"""
        ma5 = result.ma5 if result.ma5 > 0 else result.current_price
        ma10 = result.ma10 if result.ma10 > 0 else result.current_price
        ma20 = result.ma20 if result.ma20 > 0 else result.current_price

        buy_low = min(ma10, ma20)
        buy_high = min(ma5, result.current_price * 1.01)
        if buy_low > buy_high:
            buy_low, buy_high = buy_high, buy_low

        add_center = ma20
        add_low = add_center * 0.99
        add_high = add_center * 1.01

        support_base = min(ma10, ma20)
        stop_loss = support_base * 0.97

        resistance_candidates = sorted(
            [
                level
                for level in result.resistance_levels
                if level > result.current_price
            ]
        )
        take_profit = resistance_candidates[0] if resistance_candidates else result.current_price * 1.08

        position_text = {
            "buy": "试探仓位 20%-30%，站稳 MA20 后再逐步加仓",
            "hold": "维持当前仓位，回踩 MA10 不破可小幅补仓",
            "wait": "空仓或轻仓等待，优先观察站上 MA20 + MACD 金叉",
            "reduce": "减仓至防守仓位，若放量跌破 MA20 继续降仓",
        }.get(action, "控制仓位，等待明确信号")

        return {
            "buy_zone": {
                "low": self._safe_float(buy_low),
                "high": self._safe_float(buy_high),
                "description": "优先在 MA10~MA20 区域分批低吸",
            },
            "add_zone": {
                "low": self._safe_float(add_low),
                "high": self._safe_float(add_high),
                "description": "确认趋势延续后在 MA20 附近加仓",
            },
            "stop_loss": self._safe_float(stop_loss),
            "take_profit": self._safe_float(take_profit),
            "position_advice": position_text,
        }

    def _build_base_advice(
        self,
        fund_code: str,
        history: Dict[str, Any],
        latest_date: str,
    ) -> Dict[str, Any]:
        """
        构建基金建议的公共骨架字典（元信息部分）。
        正常路径和低数据路径共用此结构，避免两处平行维护。
        """
        return {
            "fund_code": fund_code,
            "analysis_code": history.get("analysis_code") or fund_code,
            "mapped_from": history.get("mapped_from"),
            "mapping_note": history.get("mapping_note"),
            "fund_name": history.get("stock_name"),
            "latest_date": latest_date,
            "data_source": history.get("data_source"),
        }

    def _build_low_data_advice(
        self,
        fund_code: str,
        history: Dict[str, Any],
        df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        历史数据不足时给出低置信度兜底建议（避免接口直接 404）。
        """
        latest = df.iloc[-1]
        close_price = self._safe_float(latest.get("close"))
        latest_date = latest["date"].strftime("%Y-%m-%d")
        sample_days = len(df)

        buy_low = self._safe_float(close_price * 0.995)
        buy_high = self._safe_float(close_price * 1.005)
        add_low = self._safe_float(close_price * 0.98)
        add_high = self._safe_float(close_price * 0.99)

        advice = self._build_base_advice(fund_code, history, latest_date)
        advice.update({
            "action": "wait",
            "action_label": "防守观望",
            "confidence_level": "低",
            "confidence_score": 35,
            "trend_status": "数据不足",
            "buy_signal": "观望",
            "signal_score": 35,
            "current_price": close_price,
            "ma5": close_price,
            "ma10": close_price,
            "ma20": close_price,
            "ma60": close_price,
            "volume_status": "量能信息有限",
            "volume_ratio_5d": 0.0,
            "macd": {
                "dif": 0.0, "dea": 0.0, "bar": 0.0,
                "status": "数据不足",
                "signal": "历史数据不足，无法形成有效 MACD 结构",
            },
            "rsi": {
                "rsi6": 50.0, "rsi12": 50.0, "rsi24": 50.0,
                "status": "数据不足",
                "signal": "历史数据不足，RSI 仅作中性参考",
            },
            "rule_assessment": self._default_rule_assessment(),
            "strategy": {
                "buy_zone": {
                    "low": buy_low, "high": buy_high,
                    "description": "仅可小仓试探，等待更多净值样本",
                },
                "add_zone": {
                    "low": add_low, "high": add_high,
                    "description": "建议暂不加仓，待数据完整后再评估",
                },
                "stop_loss": self._safe_float(close_price * 0.95),
                "take_profit": self._safe_float(close_price * 1.05),
                "position_advice": f"样本仅 {sample_days} 天，保持轻仓/空仓观察",
            },
            "reasons": [
                f"仅获取到 {sample_days} 个交易日数据，先以观察为主",
                "当前样本不足以支持高置信技术面策略",
            ],
            "risk_factors": [
                "历史数据不足，当前建议仅作参考",
                "缺少完整趋势周期，容易出现信号失真",
            ],
            "generated_at": datetime.now().isoformat(),
        })
        return advice

    def _build_deep_analysis(self, fund_code: str) -> Dict[str, Any]:
        """调用深度分析流水线，返回可嵌入基金结果的结构化摘要。"""
        deep_payload: Dict[str, Any] = {
            "requested": True,
            "status": "failed",
            "source": "stock_analysis_pipeline",
            "report_type": "detailed",
            "stock_code": None,
            "stock_name": None,
            "summary": {
                "analysis_summary": None,
                "operation_advice": None,
                "trend_prediction": None,
                "sentiment_score": None,
                "sentiment_label": None,
            },
            "strategy": {
                "ideal_buy": None,
                "secondary_buy": None,
                "stop_loss": None,
                "take_profit": None,
            },
            "details": {
                "news_summary": None,
                "technical_analysis": None,
                "fundamental_analysis": None,
                "risk_warning": None,
            },
            "error": None,
        }

        try:
            deep_result = self.analysis_service.analyze_stock(
                stock_code=fund_code,
                report_type="detailed",
                force_refresh=False,
                send_notification=False,
                persist_history=False,
            )
        except Exception as e:
            logger.warning(f"{fund_code} 深度分析执行失败: {e}", exc_info=True)
            deep_payload["error"] = str(e)
            return deep_payload

        if not deep_result:
            deep_payload["error"] = "深度分析未返回结果"
            return deep_payload

        report = deep_result.get("report") or {}
        summary = report.get("summary") or {}
        strategy = report.get("strategy") or {}
        details = report.get("details") or {}

        deep_payload.update(
            {
                "status": "completed",
                "stock_code": deep_result.get("stock_code"),
                "stock_name": deep_result.get("stock_name"),
                "summary": {
                    "analysis_summary": summary.get("analysis_summary"),
                    "operation_advice": summary.get("operation_advice"),
                    "trend_prediction": summary.get("trend_prediction"),
                    "sentiment_score": summary.get("sentiment_score"),
                    "sentiment_label": summary.get("sentiment_label"),
                },
                "strategy": {
                    "ideal_buy": self._safe_optional_float(strategy.get("ideal_buy")),
                    "secondary_buy": self._safe_optional_float(strategy.get("secondary_buy")),
                    "stop_loss": self._safe_optional_float(strategy.get("stop_loss")),
                    "take_profit": self._safe_optional_float(strategy.get("take_profit")),
                },
                "details": {
                    "news_summary": details.get("news_summary"),
                    "technical_analysis": details.get("technical_analysis"),
                    "fundamental_analysis": details.get("fundamental_analysis"),
                    "risk_warning": details.get("risk_warning"),
                },
                "error": None,
            }
        )
        return deep_payload

    def _attach_analysis_mode(
        self,
        advice: Dict[str, Any],
        mode: str,
        fund_code: str,
    ) -> Dict[str, Any]:
        """统一附加模式信息，深度模式下追加深度分析结果。"""
        normalized_mode = self.DEEP_MODE if mode == self.DEEP_MODE else self.FAST_MODE
        advice["analysis_mode"] = normalized_mode
        advice["deep_analysis"] = None

        if normalized_mode == self.DEEP_MODE:
            advice["deep_analysis"] = self._build_deep_analysis(fund_code=fund_code)

        return advice

    def get_advice(self, fund_code: str, days: int = 120, mode: str = FAST_MODE) -> Optional[Dict[str, Any]]:
        """
        获取基金建议。

        Args:
            fund_code: 基金代码（支持场外基金自动映射）
            days: 历史数据天数
            mode: 分析模式（fast/deep）

        Returns:
            建议结果字典，无数据时返回 None
        """
        target_days = max(days, self.MIN_ANALYSIS_DAYS)

        try:
            history = self.stock_service.get_history_data(
                stock_code=fund_code,
                period="daily",
                days=target_days,
                include_name=False,
            )
        except Exception as e:
            logger.error(f"获取基金历史数据失败 {fund_code}: {e}", exc_info=True)
            return None

        raw_rows = history.get("data") or []
        df = self._normalize_history_dataframe(raw_rows)
        if df.empty:
            logger.warning(f"{fund_code} 历史数据不足，无法生成建议")
            return None
        if len(df) < 20:
            logger.warning(f"{fund_code} 历史数据仅 {len(df)} 条，返回低置信兜底建议")
            low_data_advice = self._build_low_data_advice(
                fund_code=fund_code,
                history=history,
                df=df,
            )
            return self._attach_analysis_mode(
                advice=low_data_advice,
                mode=mode,
                fund_code=fund_code,
            )

        analysis_code = history.get("analysis_code") or fund_code
        result = self.analyzer.analyze(df, analysis_code)

        rule_assessment = self._evaluate_rule_assessment(df, result)
        action, action_label = self._derive_action(result, rule_assessment)
        confidence_score, confidence_level = self._derive_confidence(result, action, rule_assessment)
        strategy = self._build_strategy(result, action)

        latest_date = df.iloc[-1]["date"].strftime("%Y-%m-%d")

        reasons = list(result.signal_reasons or [])
        if not reasons:
            reasons = [result.ma_alignment or "趋势信息不足"]

        risks = list(result.risk_factors or [])
        if self._is_bearish_guard_state(result):
            risks.append("均线空头且未站上 MA20，默认防守观望")

        advice = self._build_base_advice(fund_code, history, latest_date)
        advice.update({
            "action": action,
            "action_label": action_label,
            "confidence_level": confidence_level,
            "confidence_score": confidence_score,
            "trend_status": result.trend_status.value,
            "buy_signal": result.buy_signal.value,
            "signal_score": int(result.signal_score),
            "current_price": self._safe_float(result.current_price),
            "ma5": self._safe_float(result.ma5),
            "ma10": self._safe_float(result.ma10),
            "ma20": self._safe_float(result.ma20),
            "ma60": self._safe_float(result.ma60),
            "volume_status": result.volume_status.value,
            "volume_ratio_5d": self._safe_float(result.volume_ratio_5d),
            "macd": {
                "dif": self._safe_float(result.macd_dif),
                "dea": self._safe_float(result.macd_dea),
                "bar": self._safe_float(result.macd_bar),
                "status": result.macd_status.value,
                "signal": result.macd_signal,
            },
            "rsi": {
                "rsi6": self._safe_float(result.rsi_6, digits=2),
                "rsi12": self._safe_float(result.rsi_12, digits=2),
                "rsi24": self._safe_float(result.rsi_24, digits=2),
                "status": result.rsi_status.value,
                "signal": result.rsi_signal,
            },
            "rule_assessment": rule_assessment,
            "strategy": strategy,
            "reasons": list(dict.fromkeys(reasons)),
            "risk_factors": list(dict.fromkeys(risks)),
            "generated_at": datetime.now().isoformat(),
        })
        return self._attach_analysis_mode(
            advice=advice,
            mode=mode,
            fund_code=fund_code,
        )

    # ── Phase 2B: 基金持久化单 owner 入口 ──

    def analyze_and_persist(
        self,
        fund_code: str,
        days: int = 120,
        mode: str = FAST_MODE,
        query_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        分析基金并持久化到 analysis_history。

        这是基金记录的**唯一持久化入口**。
        fast / deep 最终都只写一条 fund_advice 记录。

        Args:
            fund_code: 基金代码
            days: 历史数据天数
            mode: 分析模式 (fast/deep)
            query_id: 查询链路 ID（可选，异步任务会传入）

        Returns:
            包含 record_id 的结果字典，失败返回 None
        """
        if query_id is None:
            query_id = uuid.uuid4().hex

        # Step 1: 获取建议（不写历史）
        advice = self.get_advice(fund_code=fund_code, days=days, mode=mode)
        if advice is None:
            logger.warning(f"[{fund_code}] analyze_and_persist: get_advice 返回 None")
            return None

        # Step 2: 构建基金专用 raw_result 快照
        analysis_code = advice.get("analysis_code") or fund_code
        analysis_name = advice.get("analysis_name") or advice.get("fund_name")
        analysis_mode = advice.get("analysis_mode") or mode

        raw_result = {
            "asset_type": "fund",
            "analysis_kind": "fund_advice",
            "analysis_mode": analysis_mode,
            "input_code": advice.get("fund_code") or fund_code,
            "input_name": advice.get("fund_name"),
            "analysis_code": analysis_code,
            "analysis_name": analysis_name,
            "mapping_note": advice.get("mapping_note"),
            "advice": {
                "action": advice.get("action"),
                "action_label": advice.get("action_label"),
                "confidence_score": advice.get("confidence_score"),
                "confidence_level": advice.get("confidence_level"),
                "strategy": advice.get("strategy"),
                "reasons": advice.get("reasons"),
                "risk_factors": advice.get("risk_factors"),
                "rule_assessment": advice.get("rule_assessment"),
            },
            "indicators": {
                "current_price": advice.get("current_price"),
                "trend_status": advice.get("trend_status"),
                "buy_signal": advice.get("buy_signal"),
                "signal_score": advice.get("signal_score"),
                "ma5": advice.get("ma5"),
                "ma10": advice.get("ma10"),
                "ma20": advice.get("ma20"),
                "ma60": advice.get("ma60"),
                "volume_status": advice.get("volume_status"),
                "volume_ratio_5d": advice.get("volume_ratio_5d"),
                "macd": advice.get("macd"),
                "rsi": advice.get("rsi"),
            },
            "deep_analysis": advice.get("deep_analysis"),
        }

        # Step 3: 掛接操作建议摘要（存到结构化字段便于列表页展示）
        operation_advice = advice.get("action")
        summary_parts = []
        if advice.get("action_label"):
            summary_parts.append(advice["action_label"])
        if advice.get("reasons"):
            summary_parts.append("; ".join(advice["reasons"][:2]))
        analysis_summary = " | ".join(summary_parts) if summary_parts else None

        # Step 4: 写入单条基金历史记录
        db = DatabaseManager.get_instance()
        record_id = db.save_fund_advice_history(
            query_id=query_id,
            fund_code=advice.get("fund_code") or fund_code,
            fund_name=advice.get("fund_name"),
            analysis_code=analysis_code,
            analysis_name=analysis_name,
            analysis_mode=analysis_mode,
            raw_result=raw_result,
            operation_advice=operation_advice,
            analysis_summary=analysis_summary,
        )

        if record_id == 0:
            logger.error(f"[{fund_code}] analyze_and_persist: 保存历史失败")
            return None

        return {
            "record_id": record_id,
            "query_id": query_id,
            "fund_code": advice.get("fund_code") or fund_code,
            "analysis_code": analysis_code,
            "analysis_mode": analysis_mode,
            "action": operation_advice,
            "advice": advice,
        }
