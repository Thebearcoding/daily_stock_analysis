# openclaw 金融 Skill 集成指南

本文档说明如何把 [openclaw](https://github.com/openclaw/openclaw) 和 daily_stock_analysis（DSA）联动起来，并给出一套适合“飞书里的金融专用 openclaw”部署方式。

目标不是只支持股票，而是让 openclaw 在一个 Skill 里同时处理：

- 股票分析
- 基金分析
- 基金持仓查询
- Agent 策略问答

## 1. 推荐架构

推荐把“金融 openclaw”单独部署成一个实例，而不是和你现有的通用 openclaw 混在一起。

这样做的好处：

- 只加载金融相关 Skill，不会被通用工具/闲聊 Skill 干扰
- 可以绑定一个独立的飞书应用或机器人，避免和现有实例冲突
- 便于把 `DSA_BASE_URL`、超时时间、系统提示词都收敛成金融专用
- 后续如果你要再加基金历史、持仓、回测、通知等能力，不会影响现有 openclaw

推荐拆分：

1. **DSA 服务**
   - 常驻运行
   - 负责股票/基金分析、任务、历史、持仓、通知
   - 本地通常是 `http://127.0.0.1:8000`

2. **openclaw-finance**
   - 一个独立的 openclaw 实例
   - 只加载金融 Skill
   - 只接你自己的飞书金融机器人

3. **飞书金融机器人**
   - 单独建一个飞书应用/机器人
   - 只把消息转给 `openclaw-finance`

## 2. 需要用到的 DSA API

| 接口 | 方法 | 用途 |
|------|------|------|
| `/api/v1/analysis/analyze` | POST | 股票分析主入口 |
| `/api/v1/analysis/status/{task_id}` | GET | 股票异步任务状态 |
| `/api/v1/funds/{fund_code}/advice` | GET | 基金快速建议（不入历史） |
| `/api/v1/funds/analyze` | POST | 基金分析并持久化，支持 `async_mode=true` |
| `/api/v1/funds/status/{task_id}` | GET | 基金异步任务状态 |
| `/api/v1/funds/{fund_code}/holdings` | GET | 基金披露持仓 |
| `/api/v1/agent/chat` | POST | Agent 策略问答 |
| `/api/health` | GET | 健康检查 |

## 3. 资产路由规则

金融 Skill 最容易错的地方是：**6 位数字既可能是股票，也可能是基金。**

推荐路由规则：

1. **明确说“基金 / 场外基金 / ETF / 净值 / 持仓”**
   - 按基金处理

2. **代码是 `hk00700`、`AAPL`、`SPX` 这类**
   - 按股票处理

3. **代码是纯 6 位数字**
   - 如果用户明确提到“基金”，按基金处理
   - 如果用户明确提到“股票”，按股票处理
   - 如果上下文不明确，**先追问一句**：这是股票还是基金？

4. **用户是在问“怎么看 / 用什么策略 / 用缠论看一下”**
   - 优先走 `/api/v1/agent/chat`

## 4. 推荐的 Skill 行为

### 股票

适用场景：

- “分析 600519”
- “看一下 AAPL”
- “帮我分析 hk00700”

推荐调用：

```bash
curl -X POST {DSA_BASE_URL}/api/v1/analysis/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "stock_code": "600519",
    "report_type": "detailed",
    "force_refresh": true,
    "async_mode": false
  }'
```

### 基金快速建议

适用场景：

- “分析基金 018957”
- “看一下 018957 现在能不能买”

推荐调用：

```bash
curl -X GET '{DSA_BASE_URL}/api/v1/funds/018957/advice?mode=fast&days=120'
```

特点：

- 快
- 不入历史
- 不触发通知

### 基金深度分析 / 持久化

适用场景：

- “给我深度分析 018957”
- “分析并保存这只基金”

推荐调用：

```bash
curl -X POST '{DSA_BASE_URL}/api/v1/funds/analyze?fund_code=018957&mode=deep&days=120&async_mode=true'
```

然后轮询：

```bash
curl -X GET '{DSA_BASE_URL}/api/v1/funds/status/{task_id}'
```

### 基金持仓

适用场景：

- “查 018957 的持仓”
- “这个基金前十大持仓是什么”

推荐调用：

```bash
curl -X GET '{DSA_BASE_URL}/api/v1/funds/018957/holdings'
```

注意：

- 当前持仓语义是 **披露快照**
- 不是实时仓位
- 返回里会有：
  - `source_type`
  - `completeness`
  - `as_of_date`
  - `is_realtime=false`

### Agent 策略问答

适用场景：

- “用缠论分析 600519”
- “帮我从交易纪律角度看 018957”
- “用均线策略看看 AAPL”

推荐调用：

```bash
curl -X POST {DSA_BASE_URL}/api/v1/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "用缠论分析 600519",
    "session_id": "openclaw-finance-session"
  }'
```

要求：

- DSA 侧需启用 `AGENT_MODE=true`

## 5. 金融专用 openclaw 配置

推荐不要直接改你现有的 `~/.openclaw/`，而是单独起一个目录，例如：

```text
~/.openclaw-finance/
├── openclaw.json
└── skills/
    └── daily-market-analysis/
        └── SKILL.md
```

### openclaw.json 示例

将下面内容保存为：

`~/.openclaw-finance/openclaw.json`

```json
{
  "skills": {
    "entries": {
      "daily-market-analysis": {
        "enabled": true,
        "env": {
          "DSA_BASE_URL": "http://127.0.0.1:8000"
        }
      }
    }
  }
}
```

说明：

- `DSA_BASE_URL` 指向你的 DSA API
- 最好不要带末尾 `/`
- 如果你有内网域名，也可以换成内网地址

> 如果你是 Docker / 容器方式跑 openclaw-finance，就把这个目录挂进容器里，并让这个实例只读取这套配置。

## 6. 金融专用 SKILL.md 模板

仓库里已经给了一个可直接复用的模板：

- [docs/examples/openclaw/daily-market-analysis/SKILL.md](/Users/athebear/Documents/GitHub/daily_stock_analysis/docs/examples/openclaw/daily-market-analysis/SKILL.md)

推荐把它复制到：

`~/.openclaw-finance/skills/daily-market-analysis/SKILL.md`

## 7. 专门为金融再起一个 openclaw 的建议

如果你本地已经有一个飞书版 openclaw，最稳的做法不是“在原实例里再塞一个金融 Skill”，而是：

### 方案 A：直接起第二个 openclaw 实例

- 原实例：继续做通用问答
- 新实例：只做金融

新实例建议：

- 只挂载 `~/.openclaw-finance/`
- 只加载 `daily-market-analysis` 这一个 Skill
- 单独绑定一个飞书机器人

这是最推荐的方案。

### 方案 B：复用原实例，只新增金融 Skill

也可以，但有几个问题：

- 可能和其他 Skill 抢触发
- 6 位数字容易误判
- 后期你加“回测 / 基金持仓 / 风险提示 / 历史记录”时，路由会越来越复杂

所以如果你是长期用，我建议还是单独起一个金融实例。

## 8. 如何配置飞书

这里分两件事，不要混：

### A. openclaw 自己接飞书会话

这是“用户在飞书里和 openclaw-finance 聊天”。

推荐步骤：

1. 在飞书开发者后台新建一个**新的金融机器人应用**
   - 不要和你现有的 openclaw 共用同一个飞书应用
   - 这样最干净

2. 给这个新应用配置事件订阅 / 机器人消息接收
   - 回调地址指向 **新的 openclaw-finance 实例**
   - 不要指向旧实例

3. 把飞书应用需要的配置填到你的 openclaw-finance 部署环境
   - 变量名沿用你当前那个“已经能跑的飞书 openclaw”实例
   - 最常见的一组通常包括：
     - `APP_ID`
     - `APP_SECRET`
     - `VERIFICATION_TOKEN`
     - `ENCRYPT_KEY`
   - 具体名字取决于你现在 openclaw 的部署方式和版本

4. 把这个新飞书应用安装到你要使用的群或组织里

5. 用飞书给这个“金融机器人”发消息测试：
   - `分析基金 018957`
   - `分析 600519`
   - `查 018957 持仓`

### B. DSA 自己推送分析结果到飞书群

这是“DSA 主动往飞书群发通知”，和 openclaw 会话不是一回事。

如果你希望：

- openclaw 里发起基金分析
- DSA 分析完成后再主动推送一份结果到飞书群

那还需要在 DSA 这边配置：

- `FEISHU_WEBHOOK_URL`

在当前仓库里，这个已经支持，而且基金 `POST /api/v1/funds/analyze` 我已经接上了通知逻辑。

也就是说：

- **openclaw 飞书配置**：负责“聊天入口”
- **DSA 的 `FEISHU_WEBHOOK_URL`**：负责“分析结果主动推送”

这两者可以同时存在，也可以只配其中一个。

## 9. 推荐的最终联动方式

如果你要一个真正可用的“飞书金融助手”，我推荐：

1. 起一个 `openclaw-finance`
2. 给它一个单独的飞书机器人应用
3. 只加载 `daily-market-analysis` 这个 Skill
4. `DSA_BASE_URL` 指向你的本地 DSA 服务
5. 同时给 DSA 配置 `FEISHU_WEBHOOK_URL`

这样你会得到：

- 在飞书里直接问股票/基金
- openclaw 能根据资产类型自动选 API
- 基金能查 advice / holdings / deep analyze
- DSA 分析完成后还能主动往飞书群推送摘要

## 10. 常见问题

### Q1：为什么 6 位数字有时会识别错？

因为 6 位数字既可能是股票，也可能是基金。Skill 里必须优先看上下文是否提到“基金 / 股票 / 持仓 / 净值”。

### Q2：基金为什么建议优先走 `/funds/{code}/advice`？

因为这是最快、最稳的无状态接口，适合 openclaw 即时回答。需要异步、历史、通知时再走 `/api/v1/funds/analyze`。

### Q3：openclaw 和 DSA 都接飞书，会不会冲突？

不会，只要你明确区分：

- openclaw：负责对话入口
- DSA：负责分析结果推送

最稳的是给 openclaw-finance 用一个独立飞书应用，给 DSA 用一个独立飞书群机器人 Webhook。

### Q4：如果 DSA 开了认证怎么办？

当前 DSA API 认证主要是 Cookie 会话式。如果你启用了 `ADMIN_AUTH_ENABLED=true`，openclaw 侧需要带上登录后的 Cookie；若不想处理这层，建议内网部署并保持 API 在可信环境下使用。
