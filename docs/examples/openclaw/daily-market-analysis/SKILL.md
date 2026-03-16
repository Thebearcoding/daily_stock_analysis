---
name: daily-market-analysis
description: 调用 daily_stock_analysis API 进行金融分析。当用户询问股票、基金、基金持仓、ETF 或策略问答时使用。支持股票分析、基金 advice、基金持仓、基金深度分析与 Agent 策略问答。
metadata:
  {"openclaw": {"requires": {"env": ["DSA_BASE_URL"]}, "primaryEnv": "DSA_BASE_URL"}}
---

## 触发条件

当用户请求以下任一内容时，使用本 Skill：

- 分析股票，如「分析 600519」「看看 AAPL」「分析 hk00700」
- 分析基金，如「分析基金 018957」「018957 现在能不能买」
- 查询基金持仓，如「018957 持仓」「这只基金前十大是什么」
- 策略问答，如「用缠论分析 600519」「从交易纪律角度看 018957」

## 资产识别规则

1. 用户明确说了“基金 / 场外基金 / ETF / 持仓 / 净值”
   - 按基金处理

2. 用户给的是 `hk00700`、`AAPL`、`TSLA`、`SPX` 这类代码
   - 按股票处理

3. 用户给的是纯 6 位数字
   - 如果上下文有“基金”字样，按基金处理
   - 如果上下文有“股票”字样，按股票处理
   - 如果上下文不明确，先追问：这是股票还是基金？

4. 用户明显在问“怎么看 / 为什么 / 用什么策略”
   - 优先调用 Agent 对话接口

## 工作流程

### A. 股票分析

适用：

- `600519`
- `AAPL`
- `hk00700`

请求：

```json
POST {DSA_BASE_URL}/api/v1/analysis/analyze
{
  "stock_code": "<股票代码>",
  "report_type": "detailed",
  "force_refresh": true,
  "async_mode": false
}
```

结果提取：

- `report.summary.analysis_summary`
- `report.summary.operation_advice`
- `report.summary.trend_prediction`
- `report.summary.sentiment_score`
- `report.strategy.ideal_buy`
- `report.strategy.stop_loss`
- `report.strategy.take_profit`

### B. 基金快速建议

适用：

- 用户想快速看基金结论
- 不需要落历史
- 不需要异步任务

请求：

```text
GET {DSA_BASE_URL}/api/v1/funds/{fund_code}/advice?mode=fast&days=120
```

结果提取：

- `fund_name`
- `analysis_code`
- `action`
- `action_label`
- `confidence_score`
- `reasons`
- `risk_factors`
- `strategy`

### C. 基金持仓

适用：

- 用户问持仓
- 用户问主题暴露
- 用户问前十大

请求：

```text
GET {DSA_BASE_URL}/api/v1/funds/{fund_code}/holdings
```

结果提取：

- `source_type`
- `completeness`
- `as_of_date`
- `is_realtime`
- `items`

说明：

- 这是披露持仓快照，不是实时仓位
- 若 `source_type=unavailable`，直接说明当前暂无可用持仓数据

### D. 基金深度分析 / 持久化

适用：

- 用户要求深度分析
- 用户要求保存记录
- 用户接受异步结果

先提交：

```text
POST {DSA_BASE_URL}/api/v1/funds/analyze?fund_code={fund_code}&mode=deep&days=120&async_mode=true
```

返回 `task_id` 后轮询：

```text
GET {DSA_BASE_URL}/api/v1/funds/status/{task_id}
```

直到：

- `status=completed`
- 或 `status=failed`

完成后优先返回：

- `record_id`
- `analysis_code`
- `analysis_mode`
- `result`

### E. Agent 策略问答

适用：

- 用户要“用某种策略”看标的
- 用户问题更自然语言
- 用户不是只要结构化结论

请求：

```json
POST {DSA_BASE_URL}/api/v1/agent/chat
{
  "message": "<用户原始问题>",
  "session_id": "openclaw-finance-session"
}
```

要求：

- DSA 已启用 `AGENT_MODE=true`

## 输出要求

回答必须简洁、结构清楚，优先给出：

1. 标的是什么
2. 当前动作建议
3. 主要依据
4. 风险提示
5. 若有策略位，再给买入/止损/止盈

如果是基金持仓问题，必须明确说明：

- 当前是披露持仓快照
- 不是实时仓位

## 错误处理

- 连接失败：提示检查 `DSA_BASE_URL` 和 DSA 服务状态
- `400/422`：提示参数或代码格式错误
- `404`：提示未找到可用数据
- `409`：提示已有同标的任务在运行
- `500`：提示查看 DSA 日志

## 重要限制

- 不要擅自把 6 位数字默认当股票
- 不要把基金披露持仓说成实时持仓
- 不要把基金 advice 和股票分析结果混为一个结构
