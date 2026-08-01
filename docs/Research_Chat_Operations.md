# Research Chat 运行与回滚

研究对话使用独立的 `/v1/research-chat/` SSE 路径，不会替换新闻 AI 的 JSON 调用链，也不会自动交易。

启用顺序：`RESEARCH_CHAT_ENABLED`、`RESEARCH_CHAT_SSE_ENABLED`、`RESEARCH_CHAT_REASONING_VISIBLE`、`RESEARCH_CHAT_TOOL_CALLING_ENABLED`、`RESEARCH_CHAT_CLARIFICATION_ENABLED`、`RESEARCH_CHAT_DECISION_OUTPUT_ENABLED`。每一项均默认 `false`；关闭任一项立即退回前一层能力。

代理必须禁用该路径的 buffering、cache 与 gzip，并设置 `X-Accel-Buffering: no`。研究流失败时先关闭 `RESEARCH_CHAT_SSE_ENABLED`；若需要完全回滚，关闭 `RESEARCH_CHAT_ENABLED`。这不会影响行情、持仓、新闻 AI 或正式决策报告。

研究流不保存 `reasoning_content`、完整 prompt 或 API Key。最终回答、结构化工具摘要、Turn 状态与受控 DecisionReport 才会审计入库。
