# -*- coding: utf-8 -*-
"""
===================================
基金净值分析器 (Fund NAV Analyzer)
===================================

职责：
1. 基于基金净值序列做轻量技术分析（不依赖 volume/amount/realtime quote）
2. 输出与 StockTrendAnalyzer 对齐的结构化结果
3. 为 FundAdviceService NAV path 提供分析能力

设计原则：
- 输出体验像股票策略
- 底层信号根据基金净值现实做适配
- 不伪装成股票成交数据
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FundNavAnalysisResult:
    """基金净值分析结果"""

    code: str

    # 最新净值
    current_nav: float = 0.0

    # 均线
    ma5: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0
    ma60: float = 0.0

    # MACD (基于净值 close)
    macd_dif: float = 0.0
    macd_dea: float = 0.0
    macd_bar: float = 0.0
    macd_status: str = "数据不足"
    macd_signal: str = ""

    # RSI
    rsi_6: float = 50.0
    rsi_12: float = 50.0
    rsi_24: float = 50.0
    rsi_status: str = "中性"
    rsi_signal: str = ""

    # 收益率
    return_20d: float = 0.0
    return_60d: float = 0.0
    return_120d: float = 0.0

    # 风险指标
    volatility_20d: float = 0.0
    max_drawdown_120d: float = 0.0

    # 趋势
    trend_status: str = "盘整"
    ma_alignment: str = ""
    trend_strength: float = 50.0

    # 信号
    buy_signal: str = "观望"
    signal_score: int = 50
    signal_reasons: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)

    # 乖离率
    bias_ma5: float = 0.0
    bias_ma10: float = 0.0
    bias_ma20: float = 0.0


class FundNavAnalyzer:
    """
    基金净值分析器

    基于基金净值序列做技术分析，不依赖 volume/amount：
    - MA 均线趋势判断
    - MACD 金叉/死叉
    - RSI 超买超卖
    - 区间收益率
    - 波动率与最大回撤
    """

    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9

    def analyze(self, df: pd.DataFrame, code: str) -> FundNavAnalysisResult:
        """
        分析基金净值序列。

        Args:
            df: 必须包含 'date' 和 'close' 列
            code: 基金代码

        Returns:
            FundNavAnalysisResult
        """
        result = FundNavAnalysisResult(code=code)

        if df is None or df.empty or len(df) < 10:
            result.risk_factors.append("净值数据不足，无法完成分析")
            return result

        df = df.sort_values("date").reset_index(drop=True)
        close = pd.to_numeric(df["close"], errors="coerce").ffill().bfill()

        if close.isna().all() or len(close) < 10:
            result.risk_factors.append("净值数据无效")
            return result

        # 最新净值
        result.current_nav = float(close.iloc[-1])

        # 均线
        result.ma5 = float(close.rolling(5).mean().iloc[-1]) if len(close) >= 5 else result.current_nav
        result.ma10 = float(close.rolling(10).mean().iloc[-1]) if len(close) >= 10 else result.current_nav
        result.ma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else result.current_nav
        result.ma60 = float(close.rolling(60).mean().iloc[-1]) if len(close) >= 60 else result.ma20

        # 乖离率
        if result.ma5 > 0:
            result.bias_ma5 = (result.current_nav - result.ma5) / result.ma5 * 100
        if result.ma10 > 0:
            result.bias_ma10 = (result.current_nav - result.ma10) / result.ma10 * 100
        if result.ma20 > 0:
            result.bias_ma20 = (result.current_nav - result.ma20) / result.ma20 * 100

        # 趋势判断
        self._analyze_trend(result)

        # MACD
        self._analyze_macd(close, result)

        # RSI
        self._analyze_rsi(close, result)

        # 收益率
        self._calculate_returns(close, result)

        # 波动率 & 最大回撤
        self._calculate_risk_metrics(close, result)

        # 综合评分 & 信号
        self._generate_signal(result)

        return result

    def _analyze_trend(self, result: FundNavAnalysisResult) -> None:
        """基于均线排列判断趋势。"""
        ma5, ma10, ma20 = result.ma5, result.ma10, result.ma20

        if ma5 > ma10 > ma20:
            result.trend_status = "多头排列"
            result.ma_alignment = "MA5>MA10>MA20 多头排列"
            result.trend_strength = 75.0
        elif ma5 > ma10 and ma10 <= ma20:
            result.trend_status = "弱势多头"
            result.ma_alignment = "MA5>MA10 但 MA10≤MA20"
            result.trend_strength = 55.0
        elif ma5 < ma10 < ma20:
            result.trend_status = "空头排列"
            result.ma_alignment = "MA5<MA10<MA20 空头排列"
            result.trend_strength = 25.0
        elif ma5 < ma10 and ma10 >= ma20:
            result.trend_status = "弱势空头"
            result.ma_alignment = "MA5<MA10 但 MA10≥MA20"
            result.trend_strength = 40.0
        else:
            result.trend_status = "盘整"
            result.ma_alignment = "均线缠绕，趋势不明"
            result.trend_strength = 50.0

    def _analyze_macd(self, close: pd.Series, result: FundNavAnalysisResult) -> None:
        """基于净值 close 计算 MACD。"""
        if len(close) < self.MACD_SLOW:
            result.macd_signal = "净值数据不足，MACD 仅作参考"
            return

        ema_fast = close.ewm(span=self.MACD_FAST, adjust=False).mean()
        ema_slow = close.ewm(span=self.MACD_SLOW, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=self.MACD_SIGNAL, adjust=False).mean()
        bar = (dif - dea) * 2

        result.macd_dif = float(dif.iloc[-1])
        result.macd_dea = float(dea.iloc[-1])
        result.macd_bar = float(bar.iloc[-1])

        # 金叉/死叉判断
        if len(dif) >= 2:
            prev_diff = float(dif.iloc[-2] - dea.iloc[-2])
            curr_diff = result.macd_dif - result.macd_dea

            if prev_diff <= 0 and curr_diff > 0:
                if result.macd_dif > 0:
                    result.macd_status = "零轴上金叉"
                    result.macd_signal = "⭐ 零轴上金叉，净值趋势转强"
                else:
                    result.macd_status = "金叉"
                    result.macd_signal = "✅ 金叉，净值短期向好"
            elif prev_diff >= 0 and curr_diff < 0:
                result.macd_status = "死叉"
                result.macd_signal = "❌ 死叉，净值趋势转弱"
            elif result.macd_dif > 0 and result.macd_dea > 0:
                result.macd_status = "多头"
                result.macd_signal = "✓ MACD 多头排列，净值向上"
            elif result.macd_dif < 0 and result.macd_dea < 0:
                result.macd_status = "空头"
                result.macd_signal = "⚠ MACD 空头排列，净值偏弱"
            else:
                result.macd_status = "中性"
                result.macd_signal = "MACD 中性区域"

    def _analyze_rsi(self, close: pd.Series, result: FundNavAnalysisResult) -> None:
        """基于净值 close 计算 RSI。"""
        for period, attr in [(6, "rsi_6"), (12, "rsi_12"), (24, "rsi_24")]:
            if len(close) < period + 1:
                continue
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            avg_gain = gain.rolling(window=period).mean()
            avg_loss = loss.rolling(window=period).mean()
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            rsi = rsi.fillna(50)
            setattr(result, attr, float(rsi.iloc[-1]))

        rsi_mid = result.rsi_12
        if rsi_mid > 70:
            result.rsi_status = "超买"
            result.rsi_signal = f"⚠️ RSI超买({rsi_mid:.1f}>70)，短期回调风险"
        elif rsi_mid > 60:
            result.rsi_status = "强势"
            result.rsi_signal = f"✅ RSI强势({rsi_mid:.1f})，净值动能较强"
        elif rsi_mid >= 40:
            result.rsi_status = "中性"
            result.rsi_signal = f"RSI中性({rsi_mid:.1f})，净值震荡整理"
        elif rsi_mid >= 30:
            result.rsi_status = "弱势"
            result.rsi_signal = f"⚡ RSI弱势({rsi_mid:.1f})，关注净值企稳"
        else:
            result.rsi_status = "超卖"
            result.rsi_signal = f"⭐ RSI超卖({rsi_mid:.1f}<30)，反弹预期增大"

    def _calculate_returns(self, close: pd.Series, result: FundNavAnalysisResult) -> None:
        """计算区间收益率。"""
        current = float(close.iloc[-1])
        for days, attr in [(20, "return_20d"), (60, "return_60d"), (120, "return_120d")]:
            if len(close) > days:
                past_nav = float(close.iloc[-days - 1])
                if past_nav > 0:
                    setattr(result, attr, round((current - past_nav) / past_nav * 100, 2))

    def _calculate_risk_metrics(self, close: pd.Series, result: FundNavAnalysisResult) -> None:
        """计算波动率和最大回撤。"""
        # 20日年化波动率
        if len(close) >= 21:
            daily_returns = close.pct_change().dropna().tail(20)
            if len(daily_returns) > 1:
                result.volatility_20d = round(
                    float(daily_returns.std() * np.sqrt(252) * 100), 2
                )

        # 120日最大回撤
        window = min(len(close), 120)
        nav_window = close.tail(window)
        cummax = nav_window.cummax()
        drawdown = (nav_window - cummax) / cummax
        result.max_drawdown_120d = round(float(drawdown.min() * 100), 2)

    def _generate_signal(self, result: FundNavAnalysisResult) -> None:
        """综合评分 & 买入信号生成。"""
        score = 0
        reasons: List[str] = []
        risks: List[str] = []

        # === 趋势（30 分）===
        trend_scores = {
            "多头排列": 28,
            "弱势多头": 18,
            "盘整": 12,
            "弱势空头": 8,
            "空头排列": 4,
        }
        score += trend_scores.get(result.trend_status, 12)
        if result.trend_status in ("多头排列",):
            reasons.append(f"✅ 净值{result.trend_status}，中期趋势向上")
        elif result.trend_status in ("空头排列",):
            risks.append(f"⚠️ 净值{result.trend_status}，趋势偏弱")

        # === 乖离率（15 分）===
        bias = result.bias_ma5
        if -3 < bias < 2:
            score += 15
            reasons.append(f"✅ 净值贴近 MA5({bias:+.1f}%)，位置适中")
        elif bias < -5:
            score += 8
            risks.append(f"⚠️ 净值偏离 MA5 过大({bias:+.1f}%)")
        elif bias > 5:
            score += 4
            risks.append(f"⚠️ 净值偏高({bias:+.1f}%)，追高风险")
        else:
            score += 10

        # === MACD（15 分）===
        macd_scores = {
            "零轴上金叉": 15,
            "金叉": 12,
            "多头": 8,
            "中性": 5,
            "空头": 2,
            "死叉": 0,
        }
        score += macd_scores.get(result.macd_status, 5)
        if result.macd_status in ("零轴上金叉", "金叉"):
            reasons.append(f"✅ {result.macd_signal}")
        elif result.macd_status in ("死叉",):
            risks.append(f"⚠️ {result.macd_signal}")

        # === RSI（10 分）===
        rsi_scores = {
            "超卖": 10,
            "强势": 8,
            "中性": 5,
            "弱势": 3,
            "超买": 0,
        }
        score += rsi_scores.get(result.rsi_status, 5)
        if result.rsi_status in ("超卖", "强势"):
            reasons.append(f"✅ {result.rsi_signal}")
        elif result.rsi_status == "超买":
            risks.append(f"⚠️ {result.rsi_signal}")

        # === 收益率（15 分）===
        if result.return_20d > 2:
            score += 10
            reasons.append(f"✅ 近 20 日收益 {result.return_20d:+.1f}%，短期正反馈")
        elif result.return_20d > 0:
            score += 7
        elif result.return_20d > -3:
            score += 4
        else:
            score += 0
            risks.append(f"⚠️ 近 20 日下跌 {result.return_20d:.1f}%")

        if result.return_60d > 5:
            score += 5
            reasons.append(f"✅ 近 60 日收益 {result.return_60d:+.1f}%")
        elif result.return_60d < -5:
            risks.append(f"⚠️ 近 60 日下跌 {result.return_60d:.1f}%")

        # === 风险控制（-扣分）===
        if result.max_drawdown_120d < -15:
            score -= 5
            risks.append(f"⚠️ 近期最大回撤 {result.max_drawdown_120d:.1f}%，风控注意")
        if result.volatility_20d > 25:
            score -= 3
            risks.append(f"⚠️ 净值波动率偏高 ({result.volatility_20d:.1f}%)")

        score = max(0, min(100, score))
        result.signal_score = score
        result.signal_reasons = reasons
        result.risk_factors = risks

        # 生成信号
        if score >= 70 and result.trend_status in ("多头排列",):
            result.buy_signal = "买入"
        elif score >= 55 and result.trend_status in ("多头排列", "弱势多头"):
            result.buy_signal = "买入"
        elif score >= 45:
            result.buy_signal = "持有"
        elif score >= 30:
            result.buy_signal = "观望"
        elif result.trend_status in ("空头排列",):
            result.buy_signal = "强烈卖出"
        else:
            result.buy_signal = "卖出"
