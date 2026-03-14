# -*- coding: utf-8 -*-
"""
===================================
基金建议相关模型
===================================

职责：
1. 定义基金建议响应模型
2. 定义基金策略和规则判断结构
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class PriceZone(BaseModel):
    """价格区间"""

    low: float = Field(..., description="区间下沿")
    high: float = Field(..., description="区间上沿")
    description: str = Field(..., description="区间说明")


class FundStrategy(BaseModel):
    """基金策略位"""

    buy_zone: PriceZone = Field(..., description="建议买入区间")
    add_zone: PriceZone = Field(..., description="建议加仓区间")
    stop_loss: float = Field(..., description="止损位")
    take_profit: float = Field(..., description="止盈位")
    position_advice: str = Field(..., description="仓位建议")


class RuleAssessment(BaseModel):
    """规则判定结果"""

    entry_rule: str = Field(..., description="入场规则")
    exit_rule: str = Field(..., description="离场规则")
    entry_ready: bool = Field(..., description="是否满足入场条件")
    exit_triggered: bool = Field(..., description="是否触发离场条件")
    comment: str = Field(..., description="规则解释")


class MACDSnapshot(BaseModel):
    """MACD 快照"""

    dif: float = Field(..., description="DIF")
    dea: float = Field(..., description="DEA")
    bar: float = Field(..., description="柱状图")
    status: str = Field(..., description="MACD 状态")
    signal: str = Field(..., description="MACD 信号解释")


class RSISnapshot(BaseModel):
    """RSI 快照"""

    rsi6: float = Field(..., description="RSI6")
    rsi12: float = Field(..., description="RSI12")
    rsi24: float = Field(..., description="RSI24")
    status: str = Field(..., description="RSI 状态")
    signal: str = Field(..., description="RSI 信号解释")


class DeepAnalysisSummary(BaseModel):
    """深度分析摘要"""

    analysis_summary: Optional[str] = Field(None, description="综合结论")
    operation_advice: Optional[str] = Field(None, description="操作建议")
    trend_prediction: Optional[str] = Field(None, description="趋势预测")
    sentiment_score: Optional[int] = Field(None, ge=0, le=100, description="情绪评分")
    sentiment_label: Optional[str] = Field(None, description="情绪标签")


class DeepAnalysisStrategy(BaseModel):
    """深度分析策略位"""

    ideal_buy: Optional[float] = Field(None, description="理想买点")
    secondary_buy: Optional[float] = Field(None, description="次级买点")
    stop_loss: Optional[float] = Field(None, description="止损位")
    take_profit: Optional[float] = Field(None, description="止盈位")


class DeepAnalysisDetails(BaseModel):
    """深度分析明细"""

    news_summary: Optional[str] = Field(None, description="新闻情报摘要")
    technical_analysis: Optional[str] = Field(None, description="技术面分析")
    fundamental_analysis: Optional[str] = Field(None, description="基本面分析")
    risk_warning: Optional[str] = Field(None, description="风险提示")


class DeepAnalysisPayload(BaseModel):
    """深度分析结果"""

    requested: bool = Field(..., description="是否请求深度分析")
    status: str = Field(..., description="执行状态：completed/failed")
    source: str = Field(..., description="深度分析来源")
    report_type: Optional[str] = Field(None, description="报告类型")
    stock_code: Optional[str] = Field(None, description="深度分析使用的代码")
    stock_name: Optional[str] = Field(None, description="深度分析名称")
    summary: DeepAnalysisSummary = Field(..., description="深度分析摘要")
    strategy: DeepAnalysisStrategy = Field(..., description="深度分析策略位")
    details: DeepAnalysisDetails = Field(..., description="深度分析明细")
    error: Optional[str] = Field(None, description="失败原因")


class FundAdviceResponse(BaseModel):
    """基金建议响应"""

    fund_code: str = Field(..., description="输入基金代码")
    analysis_code: str = Field(..., description="实际分析代码（映射 ETF 后）")
    mapped_from: Optional[str] = Field(None, description="映射前代码")
    mapping_note: Optional[str] = Field(None, description="映射说明")
    fund_name: Optional[str] = Field(None, description="展示名称")
    latest_date: str = Field(..., description="最新交易日")
    data_source: Optional[str] = Field(None, description="数据来源")

    action: str = Field(..., description="动作代码: buy/hold/wait/reduce")
    action_label: str = Field(..., description="动作中文说明")
    confidence_level: str = Field(..., description="置信度等级：高/中/低")
    confidence_score: int = Field(..., ge=0, le=100, description="置信度分数")

    trend_status: str = Field(..., description="趋势状态")
    buy_signal: str = Field(..., description="分析器买卖信号")
    signal_score: int = Field(..., ge=0, le=100, description="分析器综合评分")

    current_price: float = Field(..., description="当前价格")
    ma5: float = Field(..., description="MA5")
    ma10: float = Field(..., description="MA10")
    ma20: float = Field(..., description="MA20")
    ma60: float = Field(..., description="MA60")
    volume_status: str = Field(..., description="量能状态")
    volume_ratio_5d: float = Field(..., description="量比（相对5日均量）")

    macd: MACDSnapshot = Field(..., description="MACD 指标快照")
    rsi: RSISnapshot = Field(..., description="RSI 指标快照")
    rule_assessment: RuleAssessment = Field(..., description="交易规则评估")
    strategy: FundStrategy = Field(..., description="策略位建议")

    reasons: List[str] = Field(default_factory=list, description="正向依据")
    risk_factors: List[str] = Field(default_factory=list, description="风险提示")
    analysis_mode: str = Field(..., description="分析模式：fast/deep")
    deep_analysis: Optional[DeepAnalysisPayload] = Field(None, description="深度分析结果（深度模式下返回）")
    generated_at: str = Field(..., description="生成时间")
