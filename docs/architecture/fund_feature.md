# 基金分析功能 - 修订版架构设计文档

> **维护者**：Thebearcoding  
> **最后更新**：2026-03-14  
> **状态**：Phase 0+1 完成，Phase 2-6 方案重拆中  
> **说明**：本版用于替换旧的 Phase 2-4 路线，重点修正持久化归属、`report_type` 语义、历史适配层和异步接入点 4 个阻断问题。

---

## 1. 功能定位

本功能为 DSA（Daily Stock Analysis）系统扩展**场外基金（OTC Fund）分析能力**。

核心思路保持不变：

**场外基金没有盘口数据 -> 映射到对应 ETF -> 复用股票技术面/深度分析能力 -> 输出基金维度建议**

但是后续能力扩展必须满足两个前提：

1. **不能破坏现有股票链路**
2. **不能混淆“标的类型”和“报告格式”两个维度**

同步快速分析目标链路如下：

```text
用户输入基金代码（如 012414）
        │
        ▼
fund_mapping.resolve_code()
        │
        ├─ input_code = 012414
        ├─ analysis_code = 516980
        └─ mapping_note = "场外基金映射到 ETF 分析"
        ▼
StockService.get_history_data(analysis_code)
        ▼
StockTrendAnalyzer.analyze()
        ▼
FundAdviceService
  - 规则判断
  - action/confidence/strategy
  - 可选 deep payload 合并
  - 可选持久化
        ▼
/api/v1/funds/{fund_code}/advice
        ▼
FundAdvicePage
```

异步 deep 分析目标链路如下：

```text
POST /api/v1/funds/analyze
        ▼
共享 AnalysisTaskQueue
        ▼
FundAdviceService.analyze_and_persist()
        ▼
写入单条 fund_advice 历史记录
        ▼
SSE / task status
        ▼
FundAdvicePage 历史侧栏 / 详情页
```

---

## 2. 当前基线与问题修正

### 2.1 当前已具备能力

| 能力 | 当前状态 |
|------|----------|
| 场外基金 -> ETF 映射 | ✅ 已有 |
| 技术面规则建议 | ✅ 已有 |
| deep 模式调用股票分析服务 | ✅ 已有，但调用链粗糙 |
| 同步基金接口 | ✅ `GET /api/v1/funds/{fund_code}/advice` |
| 基金独立页面 | ✅ 已有，但 UI 未融入主站 |

### 2.2 旧路线的问题

| 问题 | 旧方案风险 | 修订方向 |
|------|------------|----------|
| `report_type` 被拿来区分基金/股票 | 破坏现有格式语义 | 新增 `asset_type` / `analysis_kind` |
| deep 模式已走股票 pipeline 并自动写历史 | 容易一请求两条记录 | 持久化统一由基金入口负责 |
| 历史链路全是 stock-shaped | 直接复用会导致 detail/markdown/UI 错位 | 先加基金专用 read model |
| 异步入口写到 `task_service.py` | 实际 Web API 不会生效 | 改为接入 `task_queue.py` |

### 2.3 本次修订原则

1. **保留现有股票 API、历史、SSE 契约**
2. **基金先走独立 API 读模型，内部共享通用基础设施**
3. **数据库优先做增量扩展，不做破坏式迁移**
4. **fast/deep 最终都只落一条基金主记录**

---

## 3. 设计目标与非目标

### 3.1 目标

1. 支持基金 fast/deep 结果统一持久化
2. 支持基金历史列表、详情和 Markdown
3. 支持基金 deep 分析异步化，复用现有任务队列和 SSE
4. 前端基金页重构为与主站一致的 Dark Dock 风格
5. 保持股票主链路兼容，不影响 `HomePage`、`/api/v1/history`、`/api/v1/analysis`

### 3.2 非目标

1. 本阶段**不**把股票和基金历史详情强行合并为一个完全统一的前端组件
2. 本阶段**不**把基金记录直接纳入现有股票回测链路
3. 本阶段**不**新增新的基础设施服务或独立任务系统
4. 本阶段**不**改动基金映射核心策略，仍以 ETF 映射为主

---

## 4. 概念模型与命名规则

旧方案的核心问题，是把不同维度的信息塞进同一个字段。修订后统一按下面 4 个概念拆分。

### 4.1 四个核心维度

| 维度 | 字段 | 示例值 | 说明 |
|------|------|--------|------|
| 标的类型 | `asset_type` | `stock` / `fund` | 用户看的是什么资产 |
| 分析类型 | `analysis_kind` | `stock_analysis` / `fund_advice` | 这条记录是什么业务结果 |
| 报告格式 | `report_type` | `simple` / `full` / `brief` | 输出格式或内容深度，沿用现有股票语义 |
| 分析模式 | `analysis_mode` | `fast` / `deep` | 基金建议自身的模式选择 |

### 4.2 关键约束

1. `report_type` **继续只表示报告格式**，不再承担标的类型语义
2. `asset_type="fund"` 与 `analysis_kind="fund_advice"` 必须一起出现
3. `analysis_mode` 只描述基金建议的 fast/deep，不描述同步/异步
4. 同步/异步属于执行方式，不持久化为核心业务字段

### 4.3 代码身份规则

基金场景在业务语义上必须同时保留两套身份：

| 字段 | 例子 | 用途 |
|------|------|------|
| `input_code` | `012414` | 用户输入的基金代码 |
| `input_name` | `某某半导体混合` | 用户看到的基金名称 |
| `analysis_code` | `516980` | 实际分析用 ETF 代码 |
| `analysis_name` | `芯片 ETF` | 实际分析标的名称 |

数据库与兼容性规则：

1. `AnalysisHistory.code/name` 继续保留，**直接承担 `analysis_code/analysis_name` 的职责**
2. Phase 2A 只新增 `input_code/input_name`，不额外新增与 `code/name` 永久重复的 `analysis_code/analysis_name` 列
3. 前端展示基金历史时，优先展示 `input_code/input_name`
4. API 和 `raw_result` 仍可显式返回 `analysis_code/analysis_name`，但它们来自 `code/name` 的映射结果

这样能避免：

- 历史列表展示 ETF 代码而不是基金代码
- 老逻辑用基金代码查不到行情
- 回测、新闻、上下文提取直接失效

---

## 5. 目标架构

### 5.1 同步 fast / deep 入口

仍保留现有：

- `GET /api/v1/funds/{fund_code}/advice`

但内部职责调整为：

```text
funds.py
  -> FundAdviceService.get_advice(..., persist=False)
     -> 映射 ETF
     -> 计算技术面建议
     -> mode=deep 时调用 AnalysisService(..., persist_history=False, send_notification=False)
     -> 合并 deep payload
     -> 返回响应
```

说明：

1. 同步接口默认只返回结果，不自动入历史
2. 如果未来需要“同步也入历史”，由显式参数或单独入口触发，不隐式修改现有行为
3. deep 模式调用股票分析服务时，必须支持 `persist_history=False`
4. 基金 Web 页面要有历史闭环时，默认不再直接依赖 `GET /advice`，而是切到 `POST /api/v1/funds/analyze`

### 5.2 持久化入口

新增服务职责，不新增平行系统：

- 在 `src/services/fund_advice_service.py` 内新增 `analyze_and_persist(...)`

统一持久化职责：

```text
FundAdviceService.analyze_and_persist()
  -> get_advice(..., persist=False)
  -> 生成 fund_advice 快照
  -> 写入 AnalysisHistory 单条基金记录
  -> 返回 record_id + payload
```

### 5.3 异步入口

新增：

- `POST /api/v1/funds/analyze`

内部不接 `task_service.py`，而是复用现有 `AnalysisTaskQueue`：

```text
POST /api/v1/funds/analyze
  -> AnalysisTaskQueue.submit_task(asset_type="fund", analysis_kind="fund_advice", ...)
  -> worker 调 FundAdviceService.analyze_and_persist()
  -> SSE / status 返回基金任务状态
```

### 5.4 基金对应股票抓取能力

这部分能力很重要，但必须先定义“完整”到底是什么意思。

本方案只承诺以下 3 类公开可得能力：

| 来源类型 | 典型场景 | 完整度语义 | 是否可视为实时真实持仓 |
|----------|----------|------------|------------------------|
| `etf_constituents` | 已映射到场内 ETF | 高，接近完整成分股列表 | 否，仍以公开成分口径为准 |
| `index_constituents_proxy` | 能确认跟踪指数，但拿不到 ETF 成分股 | 中，属于指数代理持仓 | 否 |
| `fund_disclosed_holdings` | 主动基金 / 场外基金公开披露持仓 | 低到中，只是披露快照 | 否 |

必须明确：

1. **场外主动基金通常拿不到“今日完整真实持仓”**
2. **ETF / 指数基金更适合做“对应股票抓取”**
3. **主动基金首版只能展示“最新披露持仓快照”，不能伪装成实时仓位**

推荐抓取优先级：

```text
fund_code
  -> 如果已映射 ETF 且能拿到 ETF 成分股
       => 返回 etf_constituents
  -> 否则，如果能确认跟踪指数且能拿到指数成分股
       => 返回 index_constituents_proxy
  -> 否则，如果能拿到公募基金披露持仓
       => 返回 fund_disclosed_holdings
  -> 否则
       => 返回 unavailable
```

首版能力边界：

1. fast 模式下，持仓股列表只作为说明性信息展示，不直接参与技术面打分
2. deep 模式下，可把前 N 大权重股票作为扩展上下文，用于新闻搜索、板块解释和风险提示
3. 所有返回都必须带 `source_type`、`as_of_date`、`completeness`，避免前端误导用户

建议新增接口：

- `GET /api/v1/funds/{fund_code}/holdings`
- `GET /api/v1/funds/history/{record_id}/holdings`

建议响应结构：

```python
class FundHoldingsResponse(BaseModel):
    fund_code: str
    fund_name: str | None
    analysis_code: str | None
    source_type: str  # etf_constituents / index_constituents_proxy / fund_disclosed_holdings / unavailable
    completeness: str  # high / medium / low / unavailable
    as_of_date: str | None
    is_realtime: bool
    items: list[FundHoldingItem]
```

其中：

- `is_realtime` 首版固定应为 `False`
- `items` 至少包含 `stock_code` / `stock_name` / `weight` / `rank`

---

## 6. 持久化设计

### 6.1 持久化归属

**原则：一条基金请求，只允许一个持久化 owner。**

修订后 owner 如下：

| 场景 | owner |
|------|-------|
| 股票同步/异步分析 | 维持现有股票 pipeline |
| 基金 fast 分析 | `FundAdviceService.analyze_and_persist()` |
| 基金 deep 分析 | 仍由 `FundAdviceService.analyze_and_persist()` 负责最终写入 |

这意味着：

1. `AnalysisService.analyze_stock()` 需要新增 `persist_history: bool = True`
2. `persist_history` 必须继续向下传到 `StockAnalysisPipeline.process_single_stock()` 及其内部实际 `save_analysis_history()` 调用点
3. deep 基金分析内部调用股票分析服务时，必须同时传 `persist_history=False` 和 `send_notification=False`
4. 最终只由基金入口写一条 `fund_advice` 主记录

建议在实现文档中明确传播链：

```text
AnalysisService.analyze_stock(persist_history=...)
  -> StockAnalysisPipeline.process_single_stock(...)
    -> pipeline 内部 analyze_stock(...)
      -> db.save_analysis_history(...)  # 仅在 persist_history=True 时执行
```

### 6.2 AnalysisHistory 扩展方案

在现有 `AnalysisHistory` 表上做最小增量扩展，新增字段：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `asset_type` | `String(16)` | `stock` | 标的类型 |
| `analysis_kind` | `String(32)` | `stock_analysis` | 分析业务类型 |
| `analysis_mode` | `String(16)` | `NULL` | `fast` / `deep` |
| `input_code` | `String(16)` | `NULL` | 用户输入基金代码 |
| `input_name` | `String(128)` | `NULL` | 用户输入基金名称 |

字段填充规则：

| 场景 | `code` | `name` | `input_code` | `input_name` |
|------|--------|--------|--------------|--------------|
| 股票 | 股票代码 | 股票名 | `NULL` | `NULL` |
| 基金 | ETF 代码 | ETF 名 | 基金代码 | 基金名称 |

### 6.3 领域约束执行

文档中的约束不能只停留在说明层，Phase 2A 需要补一个统一约束入口。

建议：

1. 在基金写入入口新增 `validate_analysis_identity(...)` 或同类 helper
2. 对 `analysis_kind="fund_advice"` 强制校验：
   - `asset_type == "fund"`
   - `input_code is not None`
   - `code != ""`
3. 对 `analysis_kind="stock_analysis"` 强制校验：
   - `asset_type == "stock"`
4. 不建议把约束散落在各 endpoint；应集中在 writer / repository 层做单点兜底

### 6.4 `report_type` 的使用规则

基金记录中：

| `analysis_mode` | `report_type` |
|-----------------|---------------|
| `fast` | `simple` |
| `deep` | `full` |

说明：

1. `report_type` 表示结果深度，不表示 fund vs stock
2. API 层如果继续对外暴露 `detailed`，只在 schema alias 层转换，不进数据库

### 6.5 `raw_result` 存储结构

基金记录的 `raw_result` 不再假装是股票 `AnalysisResult`，而是存基金专用快照：

```json
{
  "asset_type": "fund",
  "analysis_kind": "fund_advice",
  "analysis_mode": "deep",
  "input_code": "012414",
  "input_name": "xx基金",
  "analysis_code": "516980",
  "analysis_name": "芯片ETF",
  "mapping_note": "场外基金映射到ETF分析",
  "advice": {
    "action": "wait",
    "confidence_score": 62,
    "strategy": {},
    "reasons": [],
    "risk_factors": []
  },
  "deep_analysis": {
    "status": "completed",
    "summary": {},
    "details": {}
  }
}
```

这样 `HistoryService` 可以明确按 `analysis_kind` 分支解析，而不是再走股票 `AnalysisResult` 重建逻辑。

### 6.6 持仓快照存储

基金对应股票不建议直接塞进 `AnalysisHistory.raw_result` 主体里长期维护，否则：

1. JSON 体积会迅速变大
2. 列表页和详情页都要重复解析大块持仓数据
3. 后续做“按持仓股筛选基金记录”时没有结构化能力

建议新增独立表：

`fund_holdings_snapshot`

建议字段：

| 字段 | 说明 |
|------|------|
| `id` | 主键 |
| `analysis_history_id` | 关联到基金历史记录，可为空 |
| `fund_code` | 输入基金代码 |
| `fund_name` | 输入基金名称 |
| `analysis_code` | 实际分析代码（通常为 ETF 代码） |
| `source_type` | `etf_constituents` / `index_constituents_proxy` / `fund_disclosed_holdings` |
| `completeness` | `high` / `medium` / `low` |
| `as_of_date` | 披露/成分日期 |
| `stock_code` | 成分股代码 |
| `stock_name` | 成分股名称 |
| `weight` | 权重 |
| `rank` | 排名 |
| `fetched_at` | 抓取时间 |

设计约束：

1. 每次抓取按 `(fund_code, source_type, as_of_date)` 形成一组快照
2. 如果是随分析一起持久化，写入后可通过 `analysis_history_id` 关联
3. 如果只是临时预览接口，也允许不绑定 `analysis_history_id`

---

## 7. 历史读模型设计

### 7.1 为什么不直接复用 `/api/v1/history`

当前 `/api/v1/history` 的 detail / markdown / news / 前端组件都默认 stock-shaped。直接塞基金记录会导致：

1. `stock_code/stock_name` 语义混乱
2. Markdown 仍尝试按股票模板重建
3. Detail 页组件字段对不上
4. Chat follow-up 默认按股票上下文发起

因此本阶段采用**表复用、读模型分离**：

- 数据落同一张 `AnalysisHistory`
- 读取走基金专用 schema 和 endpoint

### 7.2 基金历史接口

新增：

- `GET /api/v1/funds/history`
- `GET /api/v1/funds/history/{record_id}`
- `GET /api/v1/funds/history/{record_id}/markdown`
- `GET /api/v1/funds/history/{record_id}/holdings`

首版不新增：

- `GET /api/v1/funds/history/{record_id}/news`

原因：

1. 基金 deep 场景的新闻目前只是 deep payload 的一部分
2. 现有 news intel 存储和查询逻辑仍以股票 query context 为主
3. 先把历史主链路打通，再决定是否做基金新闻子资源

### 7.3 历史列表项 schema

建议新增 `FundHistoryItem`：

| 字段 | 说明 |
|------|------|
| `id` | 主键 |
| `query_id` | 查询链路 ID |
| `fund_code` | 输入基金代码 |
| `fund_name` | 输入基金名称 |
| `analysis_code` | 实际分析 ETF 代码 |
| `analysis_name` | 实际分析 ETF 名称 |
| `analysis_mode` | `fast/deep` |
| `report_type` | `simple/full` |
| `action` | `buy/hold/wait/reduce` |
| `confidence_score` | 置信度 |
| `created_at` | 创建时间 |

首版实现说明：

1. `action` 和 `confidence_score` 首版可由 `_record_to_fund_list_item()` 从 `raw_result` 解析得到
2. 基金历史列表默认分页较小（建议 `limit <= 20`），该解析成本可接受
3. 如果后续需要按 `action/confidence_score` 排序或筛选，再在 Phase 3B 或 Phase 4 增加冗余列，避免过早扩表

### 7.4 历史详情 schema

建议新增 `FundHistoryDetailResponse`：

```python
class FundHistoryDetailResponse(BaseModel):
    meta: FundHistoryMeta
    summary: FundAdviceSummary
    strategy: FundStrategy
    indicators: FundIndicatorSnapshot
    holdings: FundHoldingsResponse | None
    deep_analysis: DeepAnalysisPayload | None
    markdown_available: bool
```

关键点：

1. 基金 detail 不复用 `AnalysisReport`
2. `HistoryService` 内部新增 fund adapter，而不是修改股票 adapter 的返回结构
3. `get_markdown_report()` 为基金记录新增独立生成器，不走 `_rebuild_analysis_result()`
4. `holdings` 可为空，表示该记录没有抓到可展示的对应股票快照

### 7.5 历史服务改造点

建议在 `src/services/history_service.py` 中增加：

- `_record_to_fund_detail_dict(record)`
- `_record_to_fund_list_item(record)`
- `_generate_fund_markdown(record)`

而不是继续把基金记录塞进：

- `_record_to_detail_dict()`
- `_rebuild_analysis_result()`

原因很简单：基金记录不是股票 `AnalysisResult`，硬塞只会不断堆兼容分支。

---

## 8. 异步任务与 SSE 设计

### 8.1 共享 `AnalysisTaskQueue`

Web API 当前真实异步执行链路是：

- `api/v1/endpoints/analysis.py`
- `src/services/task_queue.py`

因此基金异步必须接入 `AnalysisTaskQueue`，而不是 `task_service.py`。

### 8.2 TaskInfo 扩展字段

建议为共享任务结构新增：

| 字段 | 示例 | 说明 |
|------|------|------|
| `asset_type` | `fund` | 任务标的类型 |
| `analysis_kind` | `fund_advice` | 任务业务类型 |
| `input_code` | `012414` | 用户输入基金代码 |
| `display_name` | `xx基金` | 列表展示名 |
| `analysis_mode` | `deep` | fast/deep |
| `record_id` | `1234` | 成功后写入的历史 ID |

兼容原则：

1. 股票任务默认 `asset_type="stock"`、`analysis_kind="stock_analysis"`
2. 旧前端如果不认识新字段，不应报错
3. SSE 原事件类型 `task_created/task_started/task_completed/task_failed` 保持不变

### 8.3 队列执行分支

`AnalysisTaskQueue._execute_task()` 当前是股票逻辑直写，不建议直接在里面继续堆 `if/elif`。

建议 Phase 4 先做一层轻量重构，再接基金分支：

```text
_execute_task()
  -> _run_stock_task(...)
  -> _run_fund_task(...)
```

然后再按 `asset_type` 分发：

```text
if asset_type == "stock":
    _run_stock_task(...)
elif asset_type == "fund":
    _run_fund_task(...)
```

注意：

1. 不能让基金任务走股票 `AnalysisResultResponse`
2. 基金任务完成后应返回 `record_id` 和基金 detail 摘要
3. 去重 key 建议按 `asset_type + input_code` 控制

### 8.4 异步 API

新增：

- `POST /api/v1/funds/analyze`
- `GET /api/v1/funds/status/{task_id}`
- `GET /api/v1/funds/tasks`
- `GET /api/v1/funds/tasks/stream`

实现策略：

1. API surface 放在 `funds.py`
2. 底层仍复用 `AnalysisTaskQueue`
3. 建议参考股票分析接口保留 `async_mode` 语义：基金页面的 fast 分析也走 `POST /api/v1/funds/analyze`，但可同步返回并持久化；deep 默认走异步
4. `GET /api/v1/funds/{fund_code}/advice` 保留为无状态预览/调试接口，不承担历史写入职责
5. 如果后续需要统一，可再考虑把 stock/fund 合并到通用任务 schema

---

## 9. 前端重构设计

### 9.1 总体策略

基金页最终目标是融入现有 Dark Dock 风格，但**不直接复用股票详情组件**。

原因：

1. 股票 `ReportSummary` / `ReportDetails` / `HistoryList` 目前绑定 stock schema
2. 基金 detail 有映射信息、规则判定、deep payload，不是同一数据结构
3. 如果强复用，会把前端也拖成大量条件分支

### 9.2 页面结构

建议的 `FundAdvicePage` 结构：

```text
左侧：
- FundTaskPanel
- FundHistoryList

顶部：
- 基金代码输入
- mode 切换
- days 选择
- 异步提交按钮

右侧：
- FundAdviceSummaryCard
- IndicatorCard (MA / MACD / RSI / 量能)
- StrategyCard
- HoldingsPanel
- DeepAnalysisCard
- MarkdownDrawer
```

### 9.3 可复用范围

可复用：

- 布局壳层
- Dock 导航
- `TaskPanel` 的容器交互思路
- 通用弹窗、抽屉、加载态、错误态

不建议直接复用：

- `ReportSummary`
- `ReportDetails`
- `ReportMarkdown`
- `HistoryList`

### 9.4 Chat follow-up 策略

AI 追问建议放到最后一期处理。

在基金历史 detail 中要传的上下文至少包括：

- `asset_type=fund`
- `fund_code`
- `fund_name`
- `analysis_code`
- `analysis_name`
- `mapping_note`
- `previous_fund_advice`
- `previous_deep_analysis_summary`

因此本期前端建议：

1. 先把 Chat 按钮隐藏或标记为未接入
2. 等基金历史 detail 和 agent context 定义稳定后再启用

---

## 10. 分阶段实施路线图

### ✅ Phase 0: 修复合并残留

- `HomePage.tsx` 恢复上游 clean 版本

### ✅ Phase 1: 后端基础设施对齐

- `fund_mapping.py`: 重复 key / ThreadPool 泄漏 / OTC 误判 / 缓存过期
- `fund_advice_service.py`: 提取公共方法 / 置信度语义 / MACD 文档化
- `funds.py`: FastAPI DI

### 🔲 Phase 2A: 领域模型与表结构修正

目标：先修正概念模型，避免继续在错误字段上叠功能。

改动：

- `AnalysisHistory` 增加 `asset_type` / `analysis_kind` / `analysis_mode`
- 增加 `input_code` / `input_name`
- stock 路径默认回填 `asset_type=stock`、`analysis_kind=stock_analysis`
- 文档和 schema 中明确 `report_type` 只表示格式深度
- 新增一次性 schema migration 脚本；不能依赖 `Base.metadata.create_all()` 自动修改旧表

产出：

- 数据模型稳定
- stock 路径完全兼容

### 🔲 Phase 2B: 基金持久化单 owner 落地

目标：把“deep 已自动写股票历史”的隐式行为收回来。

改动：

- `AnalysisService.analyze_stock(..., persist_history=True)`
- `persist_history` 继续向 pipeline 写库点传播
- deep 内部调用同时固定 `send_notification=False`
- `FundAdviceService` 新增 `analyze_and_persist()`
- fast / deep 最终都写单条 `fund_advice` 记录

验收标准：

- 同一笔 deep 基金请求只生成 1 条基金历史
- 不再额外生成 ETF 风格重复记录

### 🔲 Phase 3: 基金历史专用读模型

目标：打通基金历史列表、详情和 Markdown。

改动：

- `api/v1/endpoints/funds.py` 新增 history routes
- `api/v1/schemas/funds.py` 增加 history schemas
- `history_service.py` 增加基金 record adapter
- `FundAdvicePage` 初步接入历史列表和详情

验收标准：

- 基金历史页能展示 `fund_code + fund_name`
- detail 页能展示 mapping、rule_assessment、strategy、deep_analysis
- markdown 使用基金模板生成成功

### 🔲 Phase 3B: 基金对应股票抓取

目标：给基金页和历史详情补上“对应股票/成分股”能力，但不夸大为实时完整持仓。

改动：

- 新增 `FundHoldingsService`
- 新增 `GET /api/v1/funds/{fund_code}/holdings`
- 新增 `GET /api/v1/funds/history/{record_id}/holdings`
- 新增 `fund_holdings_snapshot` 表
- Deep 模式可把 top holdings 作为扩展上下文传给 LLM

验收标准：

- ETF / 指数基金能稳定返回对应成分股列表
- 主动基金如果只有披露持仓，也能明确标注“披露快照”
- 前端能展示 `source_type / as_of_date / completeness`

### 🔲 Phase 4: 基金异步任务接入共享队列

目标：让 deep 分析不再阻塞前端。

改动：

- `task_queue.py` 先拆 `_run_stock_task()` / `_run_fund_task()`
- `task_queue.py` 扩展 asset_type / analysis_kind / analysis_mode
- `funds.py` 新增 `POST /api/v1/funds/analyze`
- 新增 fund task status/list/stream API
- 前端基金页统一改为调用 analyze 接口；fast 也能落历史，deep 走状态轮询/SSE

验收标准：

- 提交基金 deep 任务立即返回 task_id
- SSE 可收到基金任务事件
- 任务完成后可直接打开对应历史记录

### 🔲 Phase 5: 前端 Dark Dock 重构

目标：把基金页融入主站交互体验。

改动：

- `FundAdvicePage.tsx` 重构为 Dock 风格
- 新增 `FundHistoryList` / `FundAdviceSummaryCard` / `FundMarkdownDrawer`
- 优化移动端布局和加载态

验收标准：

- 桌面/移动端都可正常使用
- 支持输入、任务、历史、详情完整闭环

### 🔲 Phase 6: Agent 追问与可选通知

目标：把基金历史接入后续问答与通知链路。

改动：

- Chat follow-up context 增加 fund 语义
- 视情况扩展通知推送模板

说明：

1. 该阶段不阻塞 Phase 2-5
2. 没有上下文模型前，不要提前把 Chat 按钮接进页面

---

## 11. 迁移顺序、风险与回滚

### 11.1 推荐落地顺序

1. 先加表字段和默认值
2. 先执行一次性 schema migration，而不是依赖 `create_all()`
3. 再改 `AnalysisService/pipeline` 的 `persist_history`
4. 再实现基金单 owner 持久化
5. 再补基金历史读模型
6. 最后接入异步和前端

迁移方式建议：

1. 当前项目只有 `Base.metadata.create_all()`，它**不会修改已有表结构**
2. Phase 2A 建议采用项目内的一次性 idempotent migration 脚本，执行 `ALTER TABLE ... ADD COLUMN`
3. 在没有统一 migration 基础设施前，不建议为了这一个需求引入 Alembic

### 11.2 风险清单

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| `persist_history=False` 误伤股票链路 | 股票历史丢失 | 默认值保持 `True`，先补回归测试 |
| 基金记录 `code`/`input_code` 使用不一致 | 历史展示错位 | 文档固定字段语义，adapter 单点处理 |
| 主动基金持仓披露不完整/不实时 | 用户误以为是实时完整仓位 | API 和 UI 强制返回 `source_type/completeness/as_of_date` |
| SSE schema 扩展影响旧前端 | 任务流解析异常 | 新字段只追加，不改旧字段 |
| 基金 Markdown 复用股票模板失败 | 导出内容错乱 | 基金单独模板，不走股票 rebuild |
| deep 分析依赖 LLM | 任务失败或慢 | 保持 `deep_analysis.status=failed` 的降级语义 |

### 11.3 回滚策略

本方案采用**增量回滚**：

1. 数据库字段是 additive migration，可保留不删
2. 如基金历史链路异常，可先关闭基金历史入口，保留同步 `GET /advice`
3. 如异步链路异常，可回退到同步 deep，不影响 fast 模式
4. 股票相关 API、history、task queue 主行为应始终保持可用

---

## 12. 验证矩阵

### 12.1 后端

优先执行：

```bash
./scripts/ci_gate.sh
```

至少需要补的自动化覆盖：

1. `FundAdviceService` fast/deep 持久化单测
2. deep 模式仅写 1 条基金历史的回归测试
3. `HistoryService` 基金 adapter 单测
4. `FundHoldingsService` 数据来源分支单测（ETF / 指数代理 / 披露持仓）
5. `task_queue` 基金任务流转单测
6. `POST /api/v1/funds/analyze`、fund history API、fund holdings API 集成测试

### 12.2 前端

默认执行：

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build
```

建议增加：

1. `FundAdvicePage` 组件测试
2. 基金历史列表/详情切换测试
3. 基金任务状态流 UI 测试

---

## 13. 文件索引

| 文件 | 职责 |
|------|------|
| [`src/services/fund_mapping.py`](../../src/services/fund_mapping.py) | 基金 -> ETF 映射 |
| [`src/services/fund_advice_service.py`](../../src/services/fund_advice_service.py) | 基金建议生成与持久化 owner |
| [`src/services/fund_holdings_service.py`](../../src/services/fund_holdings_service.py) | 基金对应股票/成分股抓取服务（待新增） |
| [`src/services/analysis_service.py`](../../src/services/analysis_service.py) | 股票 deep 分析服务，需支持 `persist_history=False` |
| [`src/services/history_service.py`](../../src/services/history_service.py) | 股票/基金历史 read model adapter |
| [`src/services/task_queue.py`](../../src/services/task_queue.py) | Web API 异步任务队列 |
| [`src/storage.py`](../../src/storage.py) | `AnalysisHistory` 表结构与存储实现 |
| [`api/v1/endpoints/funds.py`](../../api/v1/endpoints/funds.py) | 基金同步/异步/history API |
| [`api/v1/schemas/funds.py`](../../api/v1/schemas/funds.py) | 基金响应与历史 schema |
| [`apps/dsa-web/src/pages/FundAdvicePage.tsx`](../../apps/dsa-web/src/pages/FundAdvicePage.tsx) | 基金页面 |
| [`apps/dsa-web/src/api/funds.ts`](../../apps/dsa-web/src/api/funds.ts) | 基金前端 API Client |
| [`apps/dsa-web/src/types/funds.ts`](../../apps/dsa-web/src/types/funds.ts) | 基金 TS 类型 |
| [`tests/fund_advice_service_tests.py`](../../tests/fund_advice_service_tests.py) | 现有基金服务测试 |
| [`tests/fund_mapping_tests.py`](../../tests/fund_mapping_tests.py) | 现有基金映射测试 |

---

## 14. 本版结论

后续基金能力扩展的关键不是“继续复用股票链路”，而是：

1. **复用基础能力，但保留基金自己的业务语义**
2. **持久化只认一个 owner**
3. **共享任务队列，但不给股票 schema 强塞基金 payload**
4. **先把后端领域模型和历史链路做对，再做 UI 统一**

按本版路线推进，才能避免继续在错误抽象上补功能。
