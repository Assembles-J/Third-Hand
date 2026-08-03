# Research Chat 运行与回滚

研究对话使用独立的 `/v1/research-chat/` SSE 路径，不会替换新闻 AI 的 JSON 调用链，也不会自动交易。

启用顺序：`RESEARCH_CHAT_ENABLED`、`RESEARCH_CHAT_SSE_ENABLED`、`RESEARCH_CHAT_REASONING_VISIBLE`、`RESEARCH_CHAT_TOOL_CALLING_ENABLED`、`RESEARCH_CHAT_CLARIFICATION_ENABLED`、`RESEARCH_CHAT_DECISION_OUTPUT_ENABLED`。每一项均默认 `false`；关闭任一项立即退回前一层能力。

代理必须禁用该路径的 buffering、cache 与 gzip，并设置 `X-Accel-Buffering: no`。研究流失败时先关闭 `RESEARCH_CHAT_SSE_ENABLED`；若需要完全回滚，关闭 `RESEARCH_CHAT_ENABLED`。这不会影响行情、持仓、新闻 AI 或正式决策报告。

生产环境使用 `/third-hand/` 公网前缀时，Nginx 需要为 SSE 配置独立路径：

```nginx
location ^~ /third-hand/v1/research-chat/ {
    proxy_pass http://third_hand_api/v1/research-chat/;
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_cache off;
    gzip off;
    proxy_read_timeout 180s;
    add_header X-Accel-Buffering no always;
}
```

部署后必须分别校验容器内路径和公网路径：

```bash
curl -fsS http://127.0.0.1:8000/v1/system/ai-capabilities
curl -fsS https://groupim.cn/third-hand/v1/system/ai-capabilities
curl -fsS https://groupim.cn/third-hand/v1/research-chat/sessions
```

第一条成功、后两条 404 时，问题在 Nginx 路径改写，不在 FastAPI 或 DeepSeek。

研究流不保存 `reasoning_content`、完整 prompt 或 API Key。最终回答、结构化工具摘要、Turn 状态与受控 DecisionReport 才会审计入库。
