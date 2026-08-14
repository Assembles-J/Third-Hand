# Third-Hand Research Local-First Gateway v1.4 实施说明

## 1. 目标

把设计文档中“AI / Research 数据也必须 Local-First”的原则落实为统一代码边界，而不是依赖每个 Research Tool 自觉缓存。

```text
AI / Research data request
        ↓
ResearchDataGateway
        ↓
lookup persisted local snapshot
        ↓
fresh + schema compatible + coverage complete ?
   ├─ YES → remote_call_count = 0 → return persisted snapshot
   └─ NO  → only missing/expired coverage → provider adapter
                                      ↓
                               normalize + validate
                                      ↓
                                    persist
                                      ↓
                                  reread DB
                                      ↓
                           return persisted snapshot
```

远程数据源是补缺/刷新 adapter，不是 AI 每次推理时的默认数据平面。

## 2. 核心契约

### ResearchDataRequest

身份由以下字段确定：

- `data_type`
- `symbol`
- `params`
- `schema_version`

`max_age_seconds`、是否允许 stale fallback 和 `required_coverage_keys` 不进入 query hash，因此同一份本地数据可以被更严格 TTL 或更大 coverage 的后续请求复用，只补缺失部分。

### ProviderFetchResult

Provider adapter 必须在进入 Gateway 前完成 normalization。Payload/detail 必须是严格 JSON 可序列化对象；不存在 `default=str` 逃生口，因此 pandas DataFrame、Decimal、自定义对象等原始 provider 对象不能穿过边界进入 AI prompt。

### ResearchDataSnapshot

每个快照保存：

- `snapshot_id`
- `data_type`
- `symbol`
- `query_hash`
- `schema_version`
- `payload_hash`
- `provider`
- `source_reference`
- `as_of`
- `available_at`
- `fetched_at`
- `expires_at`
- `coverage_keys`
- `freshness_status`
- `usage_scope=RESEARCH_ONLY`

## 3. Local-First 硬规则

### Fresh local

本地存在且满足 schema / coverage / freshness：

```text
cache_status = LOCAL_FRESH_HIT
remote_call_count = 0
```

这是测试中的硬断言，不是日志建议。

### Missing / incomplete local

Gateway 只把 `missing_coverage_keys` 传给 provider fetcher。Provider 可以读取 previous persisted snapshot 做 merge，但返回的新结果必须包含缺失 coverage。

### Persist before AI

远程 fetch 成功后：

1. 保存 `research_data_snapshots`；
2. 通过 repository 重新读取刚写入的 snapshot；
3. 校验 required coverage；
4. 才返回给调用者。

AI 调用者永远拿不到瞬时 ProviderFetchResult 作为正式 Research 上下文。

### Remote failure

- fresh local 原本不会远程调用；
- stale/incomplete local + remote fail + `allow_stale_on_error=true`：返回 `STALE_LOCAL_FALLBACK`，`freshness_status=stale`，同时保留 provider error；
- 无可用本地 + remote fail：抛出错误，不伪造数据。

## 4. 审计

新增：

```text
research_data_snapshots
research_data_fetch_attempts
```

每次访问记录 cache status、remote_call_count、missing coverage、provider、snapshot id、error 和时间。

## 5. Bootstrap

`bootstrap/v2_routes.py` 注入：

```text
application.research_data_repository_v2
application.research_data_gateway_v2
```

这是迁移期间的 integration seam。v2 domain/application modules 不 import legacy application。

后续 Company Intelligence、财务指标、事件研究和 AKShare Registry 调用必须依赖这个 Gateway。

## 6. Research Chat 历史越权清理

发现旧 Research Chat 工具注册表虽然自称 read-only，却暴露：

```text
paper_add_position
paper_reduce_position
```

`ToolExecutor` 还可以直接调用 `store.execute_paper_trade()`，这与当前治理边界冲突。

v1.4 已从两层删除：

1. LLM tool registry 不再暴露这两个工具；
2. ToolExecutor 删除对应 ledger mutation 实现。

Research Chat 现在只允许：

- 读已持久化行情/日线/风险/事件/Thesis/DecisionReport；
- 请求用户确认日线 refresh；
- 提出 `propose_data_change` 确认建议；
- 请求 clarification。

正式交易唯一路径继续是：

```text
current-version DecisionReport
        ↓
next eligible observed quote
        ↓
paper execution governance
```

## 7. 关键验收测试

- fresh local → provider 函数调用次数严格为 0；
- 只缺一个 coverage key → provider 只接收到这一项；
- remote fetch → 先 persist，再从 repository reread 后返回；
- stale local + provider fail → 明确 stale fallback；
- no local + provider fail → error；
- raw/unserializable provider payload → persistence 前拒绝；
- Research Chat tool definitions 不包含直接 paper trade；
- 使用历史 paper trade tool name → `tool_not_allowed` 且账本不变。

## 8. 下一阶段

1. Company Intelligence schema / repository / service；
2. L3/L4 candidate deep-company workflow；
3. Company/financial provider adapters 全部通过 ResearchDataGateway；
4. AKShare Registry dynamic discovery；
5. 动态 Registry 结果仍固定 `RESEARCH_ONLY`；
6. AI 输出结构化 candidate reactivation proposals，不直接触发交易。