# DeepSeek AI 分析基础设施

## DeepSeek Tool Calls 与 OpenAI SDK

DeepSeek 的 `/chat/completions` 协议与 OpenAI Chat Completions 兼容；官方示例使用
`openai.OpenAI` 只是一个可选的 SDK 封装。本项目使用 `httpx` 直接请求
`https://api.deepseek.com/chat/completions`，因此代码中不需要、也不应仅为 Tool Calls
引入 `OpenAI` 客户端。

研究对话的协议循环是：发送 `messages` 与 `tools` → 保留模型返回的完整
`assistant.tool_calls`（思考模式还包括 `reasoning_content`）→ 为每个调用追加带相同
`tool_call_id` 的 `tool` 消息 → 再次请求直到没有 `tool_calls`。这些内部上下文记录不在
UI 对话历史中显示，但必须在后续用户轮次回传给 DeepSeek。

## 当前范围

本阶段只加固现有新闻与公告 AI 解读，不把持仓规则分析改成大模型判断，也不增加自动交易。

数据仍负责事实，程序负责校验和缓存，DeepSeek 只负责分类、归纳和提出待核验项。

## 模型配置

默认模型：

- `DEEPSEEK_MODEL=deepseek-v4-flash`：新闻和公告的快速结构化分析；
- `DEEPSEEK_REASONING_MODEL=deepseek-v4-pro`：为后续复杂公告、财报和研究 Agent 预留。

模型名称、API 地址、超时、重试、并发和熔断参数均从环境变量读取，不再写死在代码中。

当前新闻分类请求显式设置 `thinking.type=disabled`。该任务只要求短 JSON，不需要额外思维链；
后续复杂研究任务可以通过独立编排器启用 Pro 和思考模式。

## 输出校验

模型必须返回以下字段：

```json
{
  "event_type": "share_repurchase",
  "impact": "uncertain",
  "summary": "公司披露了回购进展，但输入缺少公告正文。",
  "verify_items": ["核对公告正文中的金额、数量和用途"],
  "confidence": "low"
}
```

后端使用 Pydantic 校验字段、枚举、长度和列表数量。JSON 无效时会有限重试；仍然失败则记录日志，
不写入缓存，也不会用一个空对象伪装成成功。

## 可靠性

`DeepSeekClient` 提供：

- HTTP 超时；
- 408、429 和常见 5xx 的指数退避重试；
- 空响应重试；
- 本地并发限制；
- 连续失败熔断与自动恢复；
- 安全错误日志；
- 响应 ID、模型、token 用量和耗时记录。

日志不会记录 API Key，也不会打印完整新闻、案例或 Prompt。
客户端默认不继承宿主机代理变量；只有确实需要代理时才设置
`DEEPSEEK_TRUST_ENV_PROXY=true`，避免容器意外使用宿主环境中的未知代理。

## 版本化缓存

新缓存表为 `ai_analysis_cache_v2`。缓存键包含：

- 内容哈希；
- 完整输入哈希；
- 模型；
- Prompt 版本；
- Schema 版本；
- 研究规则和个人规则哈希；
- 最近案例上下文哈希。

修改新闻内容、模型、Prompt、规则或案例后都会生成新缓存，不会继续复用旧分析。
旧 `ai_analysis_cache` 表暂时保留，便于回滚，但新代码不会读取旧缓存。

## 生产配置

至少设置：

```env
DEEPSEEK_API_KEY=你的密钥
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_REASONING_MODEL=deepseek-v4-pro
```

修改 `.env` 后重新创建 API 容器：

```bash
docker compose up -d --build api
docker compose logs --tail=200 api
```

如需强制重新分析已有内容，可以提升 `AI_ANALYSIS_PROMPT_VERSION` 或
`AI_ANALYSIS_SCHEMA_VERSION`，无需删除数据库。
