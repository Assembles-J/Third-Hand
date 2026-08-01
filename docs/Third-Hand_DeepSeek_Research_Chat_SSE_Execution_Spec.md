# Third-Hand DeepSeek 研究对话与 SSE 推理流工程执行规范

> 文档状态：可直接交给编码 Agent 执行  
> 文档版本：v1.0  
> 基线日期：2026-07-31  
> 配套文档：`docs/Third-Hand_AI_Decision_Execution_Roadmap.md`  
> 推荐仓库路径：`docs/Third-Hand_DeepSeek_Research_Chat_SSE_Execution_Spec.md`

---

## 1. 文档目的

本文定义 Third-Hand 中“研究对话 Agent”的工程边界与实施路线，目标是实现：

- DeepSeek 思考模式；
- SSE 流式展示；
- 多轮研究对话；
- 只读工具调用；
- 信息不足时主动向用户请求结构化补充；
- 将统一决策上下文、证据、规则和历史结果带入对话；
- 最终输出经过程序风控验证的结构化决策候选。

本文不允许 Agent 把普通聊天接口包装成所谓“智能投顾”，也不允许将模型原始推理文本直接当成交易依据。

本系统的职责分工必须始终保持：

```text
真实数据与数据库       -> 提供事实
EvidenceEngine         -> 生成可追溯证据
ActionPolicyEngine     -> 产生合法动作候选
DeepSeek Research Chat -> 理解问题、调用工具、权衡证据、解释冲突
DecisionGuard          -> 阻止越权、非法动作和不完整结论
PositionSizingEngine   -> 计算股数、目标仓位和风险预算
用户                   -> 决定是否采用建议
```

---

## 2. 与主决策路线的关系

本项目不得建立第二套独立投资分析体系。

研究对话必须复用主决策路线中的：

```text
DecisionContext
DataQualitySummary
EvidenceItem
ActionCandidate
DecisionReport
DecisionGuard
PositionSizingResult
```

研究对话只负责：

1. 根据用户问题选择需要读取的上下文；
2. 调用受控的只读研究工具；
3. 识别证据之间的支持、冲突和缺失；
4. 用自然语言解释系统结论；
5. 在确实缺少关键用户参数时暂停并请求补充；
6. 将模型提出的动作候选交给程序决策链重新验证。

研究对话不得自行维护：

- 独立技术指标算法；
- 独立风险算法；
- 独立持仓计算；
- 独立建议数量算法；
- 与 `DecisionContext` 不一致的行情快照；
- 与主决策链不同的动作枚举。

---

## 3. 当前代码基线与改造原则

当前 `backend/app/llm_client.py` 的 `DeepSeekClient.chat_json()` 适合新闻、公告等后台结构化任务，具备：

- 同步 HTTP 请求；
- JSON Object 输出；
- 超时、重试、并发限制和熔断；
- token 与延迟记录；
- `thinking` 开关。

该方法必须保留，不允许为了聊天流式能力进行破坏性重写。

新的研究对话能力必须采用独立异步客户端：

```text
现有 DeepSeekClient.chat_json()
    继续服务新闻、公告、后台结构化任务

新增 DeepSeekStreamClient.stream_chat()
    只服务研究对话、SSE、思考模式和工具调用
```

Android 当前使用 Retrofit、OkHttp 与 Compose。研究流不得强行塞入普通 Retrofit JSON DTO 请求，应增加独立 SSE Repository。

---

## 4. 官方 API 事实约束

实现必须遵循当前 DeepSeek 官方协议，不得依赖模型名称猜测或第三方 SDK 私有行为。

截至本文基线日期，关键约束如下：

1. `/chat/completions` 是无状态 API，多轮对话历史由 Third-Hand 自行持久化和拼接。
2. 思考模式通过 `thinking.type=enabled` 启用，并可使用 `reasoning_effort=high|max`。
3. 思考模式通过 `reasoning_content` 返回推理内容，通过 `content` 返回最终回答。
4. 思考模式下 `temperature`、`top_p`、`presence_penalty`、`frequency_penalty` 不产生有效控制作用，不应传入。
5. 思考模式支持工具调用。
6. 当某一轮发生工具调用时，后续继续该工具调用链时必须正确回传相关 `reasoning_content`；错误拼接可能导致上游 400。
7. 普通多轮对话中，如果前一轮没有工具调用，不应为了“让模型记住推理”长期回传旧 `reasoning_content`。
8. `stream=true` 时，客户端必须分别拼接 `delta.reasoning_content`、`delta.content` 和分块工具调用参数。

模型名、弃用安排和能力可能变化，必须从环境变量配置，不得写死到业务代码。

建议配置：

```env
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_REASONING_MODEL=deepseek-v4-pro
RESEARCH_CHAT_THINKING_ENABLED=true
RESEARCH_CHAT_REASONING_EFFORT=high
```

---

## 5. 产品模式边界

Third-Hand 必须明确区分两种 AI 模式。

### 5.1 快速结构化模式

用途：

- 新闻和公告分类；
- 事件摘要；
- 待核验项提取；
- 后台异步批处理；
- 固定 JSON Schema 输出。

技术要求：

```text
模型：DEEPSEEK_MODEL
thinking：disabled
stream：false
工具调用：禁用
输出：Pydantic Schema
```

### 5.2 研究对话模式

用途：

- 用户针对持仓、行情、事件和系统结论进行追问；
- 深入比较技术面、事件面、市场环境和个人规则；
- 模型按需调用只读工具；
- 信息不足时请求用户补充；
- 输出可读解释和结构化候选。

技术要求：

```text
模型：DEEPSEEK_REASONING_MODEL
thinking：enabled
reasoning_effort：high，复杂工具链可 max
stream：true
工具调用：仅注册白名单
最终动作：必须经过 DecisionGuard
最终数量：必须由 PositionSizingEngine 计算
```

### 5.3 禁止混用

禁止：

- 新闻后台任务使用研究聊天 Prompt；
- 研究聊天直接读取新闻标题后自由判断买卖；
- 将 `reasoning_content` 保存为正式决策依据；
- 使用聊天历史替代数据库事实；
- 将用户自然语言中的现金、成本等未经确认的数据覆盖正式数据。

---

## 6. 总体架构

必须实现如下数据流：

```text
Android ResearchChatScreen
          |
          | POST SSE
          v
ResearchChatRoutes
          |
          v
ResearchChatOrchestrator
    |         |          |
    |         |          +--> ClarificationService
    |         +-------------> ResearchToolRegistry
    +-----------------------> DeepSeekStreamClient
                                  |
                                  v
                         DeepSeek /chat/completions

ResearchToolRegistry
    |
    +--> DecisionContextBuilder
    +--> EvidenceEngine
    +--> TradePlanRepository
    +--> RecommendationEvaluationRepository
    +--> DecisionHistoryRepository

模型最终候选
    |
    v
DecisionGuard
    |
    v
PositionSizingEngine
    |
    v
DecisionReportAssembler
    |
    v
SSE decision 事件 + 数据库存档
```

---

## 7. 新增目录与模块职责

在 `backend/app/research_chat/` 增加：

```text
__init__.py
models.py
repository.py
context_builder.py
prompt_builder.py
stream_client.py
stream_parser.py
tool_registry.py
tool_executor.py
clarification.py
guard.py
orchestrator.py
sse.py
routes.py
errors.py
metrics.py
```

职责必须严格限定。

### 7.1 `models.py`

定义：

- 会话 DTO；
- 消息 DTO；
- Turn 状态；
- SSE 领域事件；
- Tool Call；
- Clarification Request；
- Final Research Output。

不得访问数据库，不得调用模型。

### 7.2 `repository.py`

只负责：

- 会话、消息、Turn、工具调用和澄清记录持久化；
- 乐观状态检查；
- 幂等读取和更新。

不得构造 Prompt，不得判断交易动作。

### 7.3 `context_builder.py`

只负责从主决策体系中读取并压缩：

- `DecisionContext`；
- 当前 `DecisionReport`；
- 相关 `EvidenceItem`；
- 用户规则和交易计划；
- 历史建议评估。

不得重新计算技术指标或风险。

### 7.4 `stream_client.py`

只负责：

- 调用 DeepSeek；
- 处理上游 SSE；
- 产出标准 `LlmStreamEvent`；
- 上游超时、重试和连接关闭。

不得包含业务 Prompt 和交易逻辑。

### 7.5 `stream_parser.py`

负责：

- 解析 `data:` 行；
- 处理 `[DONE]`；
- 拼接 `reasoning_content`；
- 拼接 `content`；
- 按 `tool_call.index` 拼接工具名称和 arguments；
- 校验最终工具调用 JSON。

### 7.6 `tool_registry.py`

负责：

- 工具白名单；
- JSON Schema；
- 工具版本；
- 权限等级；
- 最大返回尺寸。

### 7.7 `tool_executor.py`

只执行已经注册的只读工具，并将原始结果转为有限大小、可追溯的摘要。

### 7.8 `clarification.py`

负责：

- 校验是否真的需要用户补充；
- 限制问题数量；
- 保存待回答问题；
- 恢复暂停 Turn。

### 7.9 `guard.py`

研究对话专用边界检查：

- 是否越权调用工具；
- 是否输出了程序不允许的动作；
- 是否把模型数量直接当作最终数量；
- 是否引用不存在的证据 ID；
- 是否在数据不足时强行给结论。

### 7.10 `orchestrator.py`

唯一允许编排以下流程的模块：

```text
建立 Turn
读取上下文
调用模型
转发流式事件
执行工具
回传工具结果
处理澄清
校验最终结构
调用 DecisionGuard
调用 PositionSizingEngine
保存最终结果
完成 Turn
```

---

## 8. 数据模型

所有 Pydantic 模型必须使用：

```python
model_config = ConfigDict(extra="forbid")
```

### 8.1 会话

```python
class ResearchChatSession(BaseModel):
    id: str
    title: str
    primary_symbol: str | None
    status: Literal["active", "archived"]
    created_at: datetime
    updated_at: datetime
```

### 8.2 消息

```python
class ResearchChatMessage(BaseModel):
    id: str
    session_id: str
    turn_id: str
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    content_type: Literal[
        "user_text",
        "assistant_answer",
        "tool_result",
        "clarification_answer",
    ]
    created_at: datetime
```

默认不把完整原始推理保存为消息。

### 8.3 Turn

```python
class ResearchChatTurn(BaseModel):
    id: str
    session_id: str
    status: Literal[
        "pending",
        "building_context",
        "streaming",
        "waiting_tool",
        "waiting_user",
        "validating",
        "completed",
        "cancelled",
        "failed",
        "expired",
    ]
    model: str
    prompt_version: str
    context_id: str | None
    context_hash: str | None
    started_at: datetime | None
    completed_at: datetime | None
    error_code: str | None
    error_message: str | None
```

### 8.4 最终模型结构

模型最终阶段应输出可校验 JSON，不得只输出散文。

```python
class ResearchModelOutput(BaseModel):
    answer_summary: str
    thesis_status: Literal[
        "strengthened",
        "unchanged",
        "weakened",
        "invalidated",
        "insufficient_data",
    ]
    candidate_action: Literal[
        "OPEN",
        "ADD",
        "HOLD",
        "WATCH",
        "REDUCE",
        "EXIT",
        "BLOCKED",
    ]
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]
    missing_evidence: list[str]
    requested_followups: list[str]
    model_uncertainty: Literal["low", "medium", "high"]
```

该结果仍不是最终 `DecisionReport`。

---

## 9. SSE 领域协议

Third-Hand 不得把 DeepSeek 原始 SSE 直接透传给 Android。

统一格式：

```text
event: <event_type>
id: <monotonic_event_id>
data: <single-line JSON>

```

所有 `data` 必须是单行 JSON，UTF-8 编码。

### 9.1 事件列表

允许事件：

```text
session
phase
reasoning_delta
answer_delta
evidence
tool_started
tool_completed
tool_failed
clarification_required
decision
usage
warning
error
done
heartbeat
```

禁止随意新增未版本化事件。

### 9.2 `session`

```json
{
  "protocol_version": "research-sse-v1",
  "session_id": "uuid",
  "turn_id": "uuid",
  "model": "configured-model",
  "thinking_enabled": true
}
```

### 9.3 `phase`

```json
{
  "phase": "building_context",
  "label": "正在整理持仓、行情、技术指标和事件证据"
}
```

允许阶段：

```text
building_context
calling_model
executing_tool
waiting_user
validating_output
sizing_position
assembling_report
```

### 9.4 `reasoning_delta`

```json
{
  "text": "正在比较当前仓位上限与风险预算……",
  "ephemeral": true
}
```

边界：

- 仅用于当前界面实时展示；
- 默认折叠；
- 不作为正式证据；
- 不参与历史绩效统计；
- 服务端默认不长期持久化；
- 前端必须标注“模型临时思考，不是正式结论”。

### 9.5 `answer_delta`

```json
{
  "text": "当前系统证据显示……"
}
```

该文本可在 Turn 完成后合并为最终回答保存。

### 9.6 `evidence`

```json
{
  "id": "position.above_limit",
  "category": "position",
  "direction": "negative",
  "strength": 0.8,
  "summary": "当前持仓占比 18.2%，超过个人上限 15%",
  "source": "decision_context",
  "as_of": "2026-07-31T15:00:00+08:00"
}
```

证据必须来自 `EvidenceEngine`，模型不得自行创造证据 ID。

### 9.7 工具事件

```json
{
  "tool_call_id": "call_xxx",
  "tool": "get_technical_snapshot",
  "label": "读取技术指标"
}
```

工具完成只返回摘要，不返回未裁剪的原始数据库内容。

### 9.8 `clarification_required`

```json
{
  "reason": "缺少风险预算，无法计算建议数量",
  "questions": [
    {
      "id": "risk_budget_percent",
      "label": "单次风险预算占总资产比例",
      "type": "single_select",
      "options": ["0.5%", "1%", "2%", "暂不设置"],
      "required": true
    }
  ]
}
```

每次最多 3 个问题。

### 9.9 `decision`

```json
{
  "decision_report_id": "uuid",
  "status": "READY",
  "action": "REDUCE",
  "suggested_quantity": 300,
  "target_quantity": 700,
  "automatic_execution": false,
  "guard_status": "passed"
}
```

`decision` 只能在 `DecisionGuard` 和 `PositionSizingEngine` 完成后发送。

### 9.10 `error`

```json
{
  "code": "upstream_timeout",
  "message": "研究服务暂时超时，已保留本轮问题。",
  "retryable": true
}
```

### 9.11 `done`

```json
{
  "turn_id": "uuid",
  "status": "completed",
  "finish_reason": "stop",
  "duration_ms": 12800
}
```

所有正常、失败、取消和等待用户的流都必须以终止事件结束。

---

## 10. 推理内容的边界

### 10.1 允许展示

允许实时展示来自上游的 `reasoning_content`，但必须满足：

- 默认关闭长期保存；
- 默认折叠；
- 明确标注为临时思考；
- 不允许前端将其复制到正式决策字段；
- 不允许作为交易建议的唯一依据；
- 不允许从中抽取股数直接执行。

### 10.2 正式分析过程

正式可审计过程必须由系统生成：

```json
{
  "stage": "technical_review",
  "status": "completed",
  "summary": "20 日均线低于 60 日均线，当前处于中期偏弱结构",
  "evidence_ids": ["technical.sma20_below_sma60"],
  "source_versions": {"technical": "technical-v2"}
}
```

正式轨迹与原始推理必须在数据结构上完全分离。

### 10.3 保存策略

默认保存：

- 用户问题；
- 最终回答；
- 工具名称和参数摘要；
- 工具结果摘要；
- 引用证据；
- Clarification；
- DecisionReport；
- token、延迟和错误。

默认不保存：

- 完整 `reasoning_content`；
- 完整系统 Prompt；
- 上游工具原始大对象；
- API Key；
- 与结论无关的模型中间草稿。

如需诊断，可通过短期 Debug 开关保存脱敏推理，保留期不得超过 24 小时，生产环境默认关闭。

---

## 11. Tool Calling 边界

### 11.1 第一阶段允许工具

```text
get_decision_context
get_current_decision_report
get_holding
get_account_summary
get_market_quote
get_daily_price_summary
get_technical_snapshot
get_risk_snapshot
get_event_evidence
get_trade_plan
get_personal_rule
get_market_regime
get_relative_strength
get_previous_decisions
get_recommendation_evaluations
request_user_input
```

### 11.2 永久禁止模型直接调用的工具

```text
execute_buy
execute_sell
submit_order
cancel_order
update_holding
delete_holding
save_available_cash
update_personal_rule
update_trade_plan
mark_recommendation_executed
write_database_sql
run_shell
fetch_arbitrary_url
```

### 11.3 工具权限模型

```python
class ToolPolicy(BaseModel):
    name: str
    access: Literal["read", "clarification"]
    max_calls_per_turn: int
    timeout_seconds: float
    max_result_bytes: int
    requires_symbol: bool
    version: str
```

第一阶段只有 `read` 和 `clarification`，不定义 `write`。

### 11.4 工具返回要求

每个工具返回：

```json
{
  "tool": "get_technical_snapshot",
  "version": "v1",
  "status": "ready",
  "as_of": "2026-07-31",
  "source": "daily_price_cache",
  "data": {},
  "evidence_ids": [],
  "warnings": []
}
```

禁止返回：

- ORM 对象；
- 数据库游标；
- 超长日线明细；
- 内部异常堆栈；
- 用户无权查看的其他账户数据。

### 11.5 调用限制

默认限制：

```text
单轮最大工具调用总数：6
同一工具单轮最大调用：2
最大连续工具循环：4
单工具超时：5 秒
单工具结果最大：32 KB
总工具上下文最大：96 KB
```

达到限制后必须停止循环，并输出数据不足或已有证据总结。

---

## 12. 主动澄清工作流

模型不得通过自然语言随意问十几个问题。

唯一合法方式：调用 `request_user_input`。

### 12.1 允许触发的情况

只有缺少以下信息且确实影响结论时才能触发：

- 股票代码或持仓对象不明确；
- 投资周期不明确且不同周期结论会显著不同；
- 可用现金缺失，且用户要求计算加仓数量；
- 最大仓位或风险预算缺失，且用户要求数量；
- 用户提及的买入逻辑无法从已有计划确认；
- 用户要求情景分析但关键条件缺失。

### 12.2 不允许触发的情况

- 系统已经存有答案；
- 只是为了让回答显得专业；
- 可以通过只读工具获得；
- 缺失信息不影响当前问题；
- 模型不知道某个事实但系统证据明确；
- 用户只是询问已有建议原因。

### 12.3 状态流转

```text
streaming
   |
   v
waiting_user
   |
   +--> 用户回答 -> pending -> building_context -> streaming
   |
   +--> 用户取消 -> cancelled
   |
   +--> 超过有效期 -> expired
```

### 12.4 回答接口

```text
POST /v1/research-chat/turns/{turn_id}/clarification
```

请求：

```json
{
  "answers": {
    "risk_budget_percent": "1%"
  }
}
```

服务端必须校验问题 ID、选项、类型和 Turn 状态。

---

## 13. 对话上下文管理

DeepSeek API 无状态，Third-Hand 必须自己拼接上下文。

### 13.1 长期历史

长期历史只包含：

- 用户问题；
- 模型最终回答；
- 必要工具调用摘要；
- 用户澄清回答；
- 决策报告引用。

### 13.2 不进入下一普通轮次

若上一轮没有工具调用，不将旧的完整 `reasoning_content` 带入下一轮。

### 13.3 工具调用链

同一个 Turn 的工具循环中，必须按官方协议保留：

- assistant 的 reasoning_content；
- assistant 的 tool_calls；
- 对应 tool 消息；
- 后续 assistant 调用。

Turn 完成后，应转换为摘要历史，不长期保存完整推理链。

### 13.4 历史压缩

默认：

```text
最近 8 个完整用户轮次
更早历史 -> SessionSummary
当前 DecisionContext -> 单独注入，不从聊天历史推断
```

SessionSummary 必须结构化：

```json
{
  "confirmed_preferences": [],
  "confirmed_constraints": [],
  "previous_questions": [],
  "unresolved_items": []
}
```

不得用模型摘要覆盖正式个人规则或交易计划。

---

## 14. Prompt 结构

Prompt 必须版本化，不得在路由函数中拼长字符串。

推荐：

```text
backend/app/research_chat/prompts/
    system_v1.txt
    final_schema_v1.json
    tool_policy_v1.txt
```

系统 Prompt 必须包含：

1. 角色是研究辅助工具，不是自动交易系统；
2. 只能使用提供的事实和工具；
3. 引用证据必须使用真实 evidence_id；
4. 缺少关键参数时调用 `request_user_input`；
5. 不得虚构实时行情、公告或财务数据；
6. 不得给出未经程序校验的最终股数；
7. 可以提出动作候选，但最终动作由系统 Guard 决定；
8. 最终必须输出符合 Schema 的 JSON；
9. 不得要求、接收或处理券商密码、验证码、Cookie；
10. 自动执行永远为 false。

---

## 15. DeepSeekStreamClient

新增异步客户端，不得复用同步 `httpx.Client` 进行伪流式。

推荐接口：

```python
class DeepSeekStreamClient:
    async def stream_chat(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None,
        model: str,
        reasoning_effort: Literal["high", "max"],
        max_tokens: int,
        request_id: str,
    ) -> AsyncIterator[LlmStreamEvent]:
        ...
```

请求体：

```python
payload = {
    "model": model,
    "messages": messages,
    "stream": True,
    "max_tokens": max_tokens,
    "thinking": {"type": "enabled"},
    "reasoning_effort": reasoning_effort,
}
if tools:
    payload["tools"] = tools
```

不要设置：

```text
temperature
top_p
presence_penalty
frequency_penalty
response_format=json_object（工具循环阶段）
```

最终结构化输出可以采用：

- 单独最后一轮无工具 JSON 输出；或
- 模型自然语言结束后由第二个快速结构化调用生成 Schema。

推荐第一版采用“两阶段输出”：

```text
阶段 A：思考 + 工具调用 + 流式自然语言解释
阶段 B：使用已有上下文生成严格 JSON ResearchModelOutput
```

阶段 B 不允许再次调用工具，避免无限循环。

---

## 16. Orchestrator 状态机

伪代码：

```python
async def run_turn(session_id, user_message):
    turn = repository.create_turn(...)
    yield session_event(turn)

    context = context_builder.build(...)
    yield phase("building_context")

    messages = prompt_builder.build(...)
    tool_round = 0

    while tool_round <= MAX_TOOL_ROUNDS:
        yield phase("calling_model")
        result = await consume_model_stream(messages)

        if result.clarification_request:
            repository.save_clarification(...)
            repository.mark_waiting_user(turn.id)
            yield clarification_required(...)
            yield done(status="waiting_user")
            return

        if result.tool_calls:
            tool_round += 1
            validated_calls = registry.validate(result.tool_calls)
            tool_messages = await executor.execute(validated_calls)
            messages.extend(result.assistant_tool_message)
            messages.extend(tool_messages)
            continue

        break

    yield phase("validating_output")
    model_output = structured_output_service.generate(...)
    guarded = decision_guard.validate(model_output, context)

    yield phase("sizing_position")
    report = decision_report_service.assemble(guarded, context)

    repository.complete_turn(...)
    yield decision(report)
    yield usage(...)
    yield done(status="completed")
```

### 16.1 严格终止条件

任一条件满足必须停止：

- 工具调用次数达到上限；
- 总运行时间达到上限；
- 客户端断开；
- 用户取消；
- 上游连续失败；
- 输出无法通过 Schema；
- Guard 判定越权；
- 需要用户补充；
- token 预算达到上限。

---

## 17. API 设计

### 17.1 创建会话

```text
POST /v1/research-chat/sessions
```

请求：

```json
{
  "primary_symbol": "01810",
  "title": "小米集团持仓研究"
}
```

### 17.2 会话列表

```text
GET /v1/research-chat/sessions
```

### 17.3 会话详情

```text
GET /v1/research-chat/sessions/{session_id}
```

默认不返回原始推理。

### 17.4 发起流式消息

```text
POST /v1/research-chat/sessions/{session_id}/messages/stream
Accept: text/event-stream
Content-Type: application/json
```

请求：

```json
{
  "message": "为什么系统建议我减仓？",
  "symbol": "01810",
  "client_request_id": "uuid"
}
```

`client_request_id` 必须用于幂等。

### 17.5 回答澄清

```text
POST /v1/research-chat/turns/{turn_id}/clarification
```

### 17.6 取消

```text
POST /v1/research-chat/turns/{turn_id}/cancel
```

### 17.7 获取 Turn

```text
GET /v1/research-chat/turns/{turn_id}
```

用于断线后查询最终状态，不要求重放全部 reasoning delta。

---

## 18. 数据库迁移

第一版新增：

```sql
CREATE TABLE research_chat_sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    primary_symbol TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE research_chat_turns (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    client_request_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    context_id TEXT,
    context_hash TEXT,
    answer_text TEXT NOT NULL DEFAULT '',
    decision_report_id TEXT,
    error_code TEXT,
    error_message TEXT,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    reasoning_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT
);

CREATE INDEX idx_research_chat_turns_session_time
ON research_chat_turns(session_id, created_at DESC);

CREATE TABLE research_chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE research_tool_calls (
    id TEXT PRIMARY KEY,
    turn_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    tool_version TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    result_summary_json TEXT,
    status TEXT NOT NULL,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE research_clarifications (
    id TEXT PRIMARY KEY,
    turn_id TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    questions_json TEXT NOT NULL,
    answers_json TEXT,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    answered_at TEXT
);
```

禁止在数据库中新增 `raw_reasoning_content` 长期字段。

如调试确需短期保存，必须使用独立临时表或日志存储，并设置自动过期。

---

## 19. 幂等、并发和取消

### 19.1 幂等

同一 `client_request_id`：

- 已完成：返回已有 Turn 状态，不再次收费调用模型；
- 运行中：返回冲突或当前 Turn ID；
- 失败且可重试：必须由显式 retry 接口创建新尝试；
- 不允许静默重复提交。

### 19.2 并发

默认：

```text
每个 session 同时运行 Turn：1
每个用户同时运行研究 Turn：2
全服务同时 DeepSeek 研究流：配置控制
```

### 19.3 取消

取消必须：

- 设置 Turn 为 `cancelled`；
- 关闭上游 httpx 流；
- 停止后续工具调用；
- 不生成 DecisionReport；
- 释放并发槽位。

### 19.4 客户端断开

第一版策略：客户端断开即取消当前上游任务。

后续若改为后台继续，必须单独设计事件重放和资源计费，本阶段禁止自行实现。

---

## 20. 超时、重试与熔断

建议默认：

```env
RESEARCH_CHAT_CONNECT_TIMEOUT_SECONDS=10
RESEARCH_CHAT_READ_TIMEOUT_SECONDS=90
RESEARCH_CHAT_TOTAL_TIMEOUT_SECONDS=120
RESEARCH_CHAT_TOOL_TIMEOUT_SECONDS=5
RESEARCH_CHAT_MAX_TOOL_CALLS=6
RESEARCH_CHAT_MAX_TOOL_ROUNDS=4
RESEARCH_CHAT_MAX_CONCURRENCY=2
RESEARCH_CHAT_MAX_OUTPUT_TOKENS=12000
RESEARCH_CHAT_HEARTBEAT_SECONDS=15
```

流式请求重试边界：

- 尚未向客户端发送任何模型内容：可重试一次；
- 已发送 `reasoning_delta` 或 `answer_delta`：不得自动重放整个上游请求；
- 连接中断后发送 `error`，由用户显式重试；
- 工具查询可按工具策略单独重试；
- Schema 整理阶段可有限重试一次。

熔断应与后台 `chat_json()` 分开统计，避免聊天高负载把新闻分析完全熔断。

---

## 21. Nginx 与代理配置

SSE 路径必须关闭缓冲和缓存。

示例：

```nginx
location /third-hand/v1/research-chat/ {
    proxy_pass http://api:8000/v1/research-chat/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_buffering off;
    proxy_cache off;
    gzip off;
    proxy_read_timeout 150s;
    proxy_send_timeout 150s;

    add_header X-Accel-Buffering no;
}
```

验收必须确认：

- 首个事件不是请求结束后一次性到达；
- 15 秒心跳可穿过代理；
- Cloudflare 或其他代理没有缓存 SSE；
- 断开连接后后端任务能结束。

---

## 22. Android 客户端

新增依赖：

```kotlin
implementation("com.squareup.okhttp3:okhttp-sse:4.12.0")
```

建议结构：

```text
researchchat/
    ResearchChatScreen.kt
    ResearchChatViewModel.kt
    ResearchChatRepository.kt
    ResearchSseParser.kt
    ResearchChatModels.kt
    ResearchChatState.kt
```

### 22.1 UI 分区

```text
用户消息
研究阶段状态
模型临时思考（默认折叠）
工具调用状态
正式回答
证据列表
操作候选
澄清卡片
错误与重试
```

### 22.2 ViewModel 状态

```kotlin
sealed interface ResearchChatUiState {
    data object Idle : ResearchChatUiState
    data class Streaming(...) : ResearchChatUiState
    data class WaitingForUser(...) : ResearchChatUiState
    data class Completed(...) : ResearchChatUiState
    data class Failed(...) : ResearchChatUiState
}
```

### 22.3 前端边界

- 不在 Android 本地计算建议数量；
- 不从 reasoning 文本正则提取动作；
- 不把页面退出误认为 Turn 成功；
- 不将 SSE 事件顺序作为唯一真相，完成后以 Turn 查询结果校验；
- 不在日志打印完整持仓和推理内容；
- 用户离开页面时明确取消或提示仍在运行，本阶段默认取消。

---

## 23. 安全与隐私

### 23.1 输入拦截

如果用户输入包含：

- 券商密码；
- 短信验证码；
- Cookie；
- Session Token；
- 私钥；
- API Key；

服务端应拒绝保存，并提示用户删除敏感信息。

### 23.2 日志脱敏

日志允许：

```text
session_id
turn_id
model
tool_name
status
token 数量
耗时
错误码
```

日志禁止：

```text
DEEPSEEK_API_KEY
完整 Prompt
完整 reasoning_content
完整持仓对象
工具原始返回
用户敏感输入
```

### 23.3 数据隔离

虽然当前 MVP 可能仍是单用户模型，表结构和 Repository 必须预留 `user_id/account_id` 扩展点。不得通过 session_id 猜测归属。

---

## 24. 决策安全边界

模型输出任何动作后必须执行：

```text
证据 ID 存在性校验
数据新鲜度校验
动作是否在候选集合
个人规则校验
交易计划校验
市场和证券元数据校验
最大仓位校验
现金校验
风险预算校验
最小交易单位校验
数量重新计算
```

若模型输出：

```text
建议加仓 1000 股
```

系统只读取动作候选 `ADD`，忽略模型给出的 1000 股，由 `PositionSizingEngine` 重新计算。

任何情况下：

```json
{"automatic_execution": false}
```

必须由服务端写入，模型不得控制。

---

## 25. 错误码

统一错误码：

```text
session_not_found
turn_conflict
turn_not_waiting_user
invalid_clarification
model_not_configured
upstream_connect_error
upstream_timeout
upstream_rate_limited
upstream_invalid_response
upstream_stream_interrupted
tool_not_allowed
tool_invalid_arguments
tool_timeout
tool_result_too_large
tool_loop_limit
context_unavailable
data_quality_blocked
schema_validation_failed
decision_guard_blocked
client_cancelled
server_overloaded
```

错误消息面向用户，不暴露内部堆栈。

---

## 26. 可观测性与成本控制

每个 Turn 记录：

```text
首事件延迟
首 reasoning token 延迟
首 answer token 延迟
总耗时
工具调用数
每个工具耗时
输入 token
输出 token
reasoning token（若上游提供）
缓存命中情况
最终状态
错误码
```

建议指标：

```text
research_chat_turn_total
research_chat_turn_duration_seconds
research_chat_first_event_seconds
research_chat_tool_calls_total
research_chat_tool_duration_seconds
research_chat_upstream_errors_total
research_chat_cancel_total
research_chat_clarification_total
research_chat_guard_block_total
research_chat_tokens_total
```

成本边界：

- 默认只在用户主动进入研究对话时调用推理模型；
- 后台新闻分析继续使用快速模型；
- 不为每次行情刷新自动触发研究对话；
- 同一问题重复请求使用幂等键；
- 长历史先压缩再发送；
- 工具返回必须摘要化。

---

## 27. Feature Flags

```env
RESEARCH_CHAT_ENABLED=false
RESEARCH_CHAT_SSE_ENABLED=false
RESEARCH_CHAT_REASONING_VISIBLE=false
RESEARCH_CHAT_TOOL_CALLING_ENABLED=false
RESEARCH_CHAT_CLARIFICATION_ENABLED=false
RESEARCH_CHAT_DECISION_OUTPUT_ENABLED=false
RESEARCH_CHAT_RAW_REASONING_PERSIST=false
```

上线顺序：

```text
SSE 基础
-> reasoning 展示
-> DecisionContext 只读注入
-> 工具调用
-> 主动澄清
-> 决策候选
```

任一阶段异常可关闭对应开关，不影响原有新闻 AI、行情和持仓功能。

---

## 28. 分阶段执行路线

### 阶段 0：保护现状

任务：

- 为现有 `DeepSeekClient.chat_json()` 补回归测试；
- 固定当前新闻 AI Schema 行为；
- 确认现有行情和持仓接口测试通过；
- 新功能默认关闭。

禁止：

- 修改现有 Prompt 行为；
- 将同步客户端直接改为 async；
- 替换原有调用链。

验收：

- 原有测试全部通过；
- 未配置研究聊天时生产行为不变。

建议提交：

```text
test: protect existing DeepSeek JSON analysis behavior
```

### 阶段 1：SSE 协议与假流

任务：

- 建立 `models.py`、`sse.py`、`routes.py`；
- 使用本地假生成器输出 session、phase、answer_delta、done；
- Android 接收并展示；
- 支持取消和心跳。

暂不调用 DeepSeek。

验收：

- 代理后仍逐事件显示；
- 页面退出能够取消；
- 事件 JSON 校验通过；
- 网络中断显示明确错误。

建议提交：

```text
feat: add versioned research chat SSE protocol
```

### 阶段 2：DeepSeek 单轮思考流

任务：

- 新增 `DeepSeekStreamClient`；
- 解析 reasoning 和 answer；
- 无工具单轮对话；
- 记录 token、耗时和错误。

验收：

- reasoning 与 answer 分区显示；
- reasoning 默认不入库；
- 上游超时、429、断流可测试；
- 不影响 `chat_json()`。

建议提交：

```text
feat: stream DeepSeek thinking and answer events
```

### 阶段 3：会话与多轮历史

任务：

- 增加数据库表；
- 保存最终消息和 Turn；
- 拼接多轮历史；
- 建立 SessionSummary；
- 幂等 client_request_id。

验收：

- 服务重启后可恢复会话；
- 同一幂等键不重复调用模型；
- 普通轮次不回传旧 reasoning。

建议提交：

```text
feat: persist research chat sessions and turns
```

### 阶段 4：统一决策上下文注入

任务：

- 接入 `DecisionContextBuilder`；
- 在 Prompt 中注入结构化摘要；
- 展示真实 evidence 事件；
- 禁止聊天自行计算技术指标。

验收：

- 对同一 context_id，聊天与决策页使用相同数据；
- 所有证据 ID 可追踪；
- 缺失数据明确展示。

建议提交：

```text
feat: ground research chat in shared decision context
```

### 阶段 5：只读工具调用

任务：

- 建立工具注册表；
- 支持工具流式状态；
- 正确拼接工具调用链 reasoning_content；
- 限制调用次数、结果大小和超时。

验收：

- 未注册工具被拒绝；
- 工具参数 Schema 错误被拒绝；
- 工具循环达到上限后正常终止；
- 无任何写工具。

建议提交：

```text
feat: add bounded read-only research tool loop
```

### 阶段 6：主动澄清

任务：

- 实现 `request_user_input`；
- 建立 waiting_user 状态；
- Android 展示结构化问题；
- 回答后恢复新一轮分析。

验收：

- 已存在数据不会重复询问；
- 每次最多 3 问；
- 过期问题不可回答；
- 用户取消后不继续调用模型。

建议提交：

```text
feat: pause research turns for structured clarification
```

### 阶段 7：受控决策输出

任务：

- 最终生成 `ResearchModelOutput`；
- 接入 `DecisionGuard`；
- 接入 `PositionSizingEngine`；
- 生成 `DecisionReport`；
- SSE 发送 decision。

验收：

- 模型数量不会直接成为最终数量；
- 证据不足返回 BLOCKED/WATCH；
- 所有最终动作符合动作枚举；
- `automatic_execution=false`；
- 建议可进入纸面跟踪。

建议提交：

```text
feat: validate research chat decisions through guard and sizing
```

### 阶段 8：灰度与运营

任务：

- Feature Flag；
- 管理页指标；
- 成本和失败率统计；
- Shadow 模式；
- 文档和故障手册。

验收：

- 可独立关闭工具、推理展示或决策输出；
- 关闭后原有功能不受影响；
- 有明确回滚步骤。

建议提交：

```text
ops: add research chat controls metrics and rollback guide
```

---

## 29. 测试矩阵

### 29.1 单元测试

必须覆盖：

- SSE 编码与换行；
- DeepSeek chunk 解析；
- reasoning/content 分离；
- 分块 tool arguments 拼接；
- 工具白名单；
- 工具参数 Schema；
- 调用次数上限；
- Clarification 校验；
- 历史拼接；
- reasoning 保存策略；
- DecisionGuard；
- 模型数量被忽略；
- 幂等；
- 状态机非法流转。

### 29.2 集成测试

使用 `httpx.MockTransport` 或本地假 SSE 上游覆盖：

1. 正常 reasoning + answer；
2. 只有 answer；
3. 多次工具调用；
4. 工具调用参数跨 chunk；
5. 工具超时；
6. request_user_input；
7. 用户回答后恢复；
8. 上游 429；
9. 上游 500；
10. 中途断流；
11. 客户端取消；
12. Schema 无效；
13. Guard 拦截；
14. 幂等重复提交；
15. 服务重启后读取会话。

### 29.3 Android 测试

- 事件顺序解析；
- 断线 UI；
- reasoning 折叠；
- Clarification 卡片；
- 页面离开取消；
- 配置切换；
- 大量 delta 不导致 UI 卡顿；
- 屏幕旋转/重组不重复提交请求。

### 29.4 代理验收

通过生产同等 Nginx/Cloudflare 路径验证：

- 首事件延迟；
- 逐段到达；
- 心跳；
- 120 秒连接；
- 断开释放资源；
- 不缓存。

---

## 30. 稳定性验收标准

上线 `RESEARCH_CHAT_ENABLED=true` 前必须满足：

```text
连续 100 次假上游 SSE 测试无事件解析失败
工具调用非法参数 100% 被拒绝
客户端断开后任务在 5 秒内结束
同一幂等键不会产生第二次模型调用
所有 Turn 都有最终状态
reasoning 默认不长期持久化
原有新闻 AI 回归测试全部通过
研究聊天关闭后原业务完全可用
```

决策输出开启前额外满足：

```text
模型输出数量 100% 不直接采用
缺少价格/持仓/计划时不会生成非法数量
所有 evidence_id 均可在 DecisionContext 中找到
DecisionGuard 拦截测试完整
纸面评估使用建议生成后的数据
```

---

## 31. Agent 实施禁止事项

编码 Agent 不得：

1. 一次性完成全部阶段；
2. 为了减少文件把所有逻辑写进 `main.py`；
3. 删除或重写现有 `chat_json()`；
4. 将 DeepSeek 原始 SSE 直接返回 Android；
5. 增加任意写数据库工具；
6. 让模型直接执行交易；
7. 保存 API Key 或完整 Prompt；
8. 默认长期保存 reasoning_content；
9. 绕过 DecisionContext 直接查询不同时间口径的数据；
10. 在 Android 本地计算操作数量；
11. 未写测试就进入下一阶段；
12. 将功能默认打开；
13. 在已向客户端发送内容后自动重试整个生成请求；
14. 使用聊天历史覆盖正式交易计划和个人规则；
15. 根据模型自然语言正则解析最终动作。

---

## 32. 第一条交给 Agent 的执行指令

以下内容可直接交给 Agent：

```text
请只执行《Third-Hand DeepSeek 研究对话与 SSE 推理流工程执行规范》的阶段 0 和阶段 1，不得提前接入真实 DeepSeek、工具调用、主动澄清或决策输出。

目标：
1. 保护现有 DeepSeekClient.chat_json() 行为并补充回归测试；
2. 建立 backend/app/research_chat 基础目录；
3. 定义 research-sse-v1 事件模型与编码器；
4. 新增假流式 FastAPI 接口；
5. Android 使用 OkHttp SSE 接收并展示 session、phase、answer_delta、heartbeat、error、done；
6. 支持页面退出取消；
7. 所有新功能默认由 RESEARCH_CHAT_ENABLED=false 控制；
8. 不修改现有新闻 AI、持仓、行情、建议和决策行为。

完成后必须提交：
- 修改文件清单；
- 数据流说明；
- 单元测试和集成测试结果；
- 本地运行命令；
- SSE 示例；
- 已知限制；
- 下一阶段不得提前实现的内容。
```

---

## 33. Definition of Done

该研究对话模块只有同时满足以下条件才算完成：

- 与主决策链共享唯一 `DecisionContext`；
- SSE 协议版本化且不透传上游格式；
- 原始推理与正式证据完全分离；
- 工具只有只读与澄清能力；
- 多轮上下文按官方协议正确拼接；
- 工具调用链正确处理 reasoning_content；
- 用户补充可暂停并恢复 Turn；
- 模型输出必须通过 Schema；
- 最终动作必须通过 DecisionGuard；
- 最终数量必须由 PositionSizingEngine 计算；
- 自动执行永久关闭；
- 会话、工具和决策可审计；
- 可通过 Feature Flag 独立关闭；
- 原有功能无回归；
- 具备测试、指标、回滚和故障处理文档。

---

## 34. 官方参考

- DeepSeek API - Thinking Mode：`https://api-docs.deepseek.com/zh-cn/guides/thinking_mode`
- DeepSeek API - Multi-round Chat：`https://api-docs.deepseek.com/zh-cn/guides/multi_round_chat/`
- DeepSeek API - Tool Calls：`https://api-docs.deepseek.com/zh-cn/guides/tool_calls`
- DeepSeek API - Chat Completion：`https://api-docs.deepseek.com/zh-cn/api/create-chat-completion/`
- DeepSeek API - First API Call / Current Models：`https://api-docs.deepseek.com/zh-cn/guides/reasoning_model`

