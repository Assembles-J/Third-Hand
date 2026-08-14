# Third-Hand Research Local-First Gateway v1.4 实施说明

## 1. 目标

把“AI / Research 数据必须 Local-First”落实为统一代码边界：

```text
AI / Research request
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

远程 Provider 是补缺/刷新手段，不是 AI 每次推理的默认数据平面。

## 2. Snapshot 契约

每份 ResearchDataSnapshot 保存：

- snapshot_id
- data_type / symbol / query_hash / schema_version
- payload_hash
- provider / source_reference
- as_of / available_at / fetched_at / expires_at
- coverage_keys
- freshness_status
- usage_scope = RESEARCH_ONLY

Query identity 只由 data_type + symbol + params + schema_version 决定；TTL、stale fallback 和请求 coverage 不分裂同一份数据身份，因此扩展请求只补缺失 coverage。

## 3. 硬规则

### Fresh local

```text
cache_status = LOCAL_FRESH_HIT
remote_call_count = 0
```

这是自动测试硬断言。

### Remote refresh

Provider adapter 必须先把 DataFrame/Decimal/自定义对象转换成严格 JSON。Gateway 不使用 `default=str` 兜底；原始 provider 对象不能直接进入 AI。

远程成功后必须：persist → repository reread → coverage validate → return。

### Failure

- stale/incomplete local + remote fail + allow_stale_on_error：`STALE_LOCAL_FALLBACK`；
- 无本地 + remote fail：直接 error；
- 不伪造 freshness，不把 stale 当 fresh。

## 4. Audit

新增：

```text
research_data_snapshots
research_data_fetch_attempts
```

访问审计记录 cache status、remote_call_count、missing coverage、provider、snapshot id、错误与时间。

## 5. Research Chat 历史越权清理

旧版本暴露 `paper_add_position` / `paper_reduce_position`，并可从 ToolExecutor 直接写 paper ledger。v1.4 同时删除 tool definition 与执行分支。

其余既有只读 tool 名称保持兼容，不做无关 rename。

正式交易唯一路径仍然是：

```text
current-version DecisionReport
        ↓
next eligible observed quote
        ↓
paper execution governance
```

## 6. 验收

- fresh local → provider 调用严格为 0；
- 只缺一个 coverage key → provider 只收到这一缺口；
- remote result → 先落库后返回；
- stale fallback 显式标记；
- no-local remote failure 抛错；
- raw/unserializable payload 在落库前拒绝；
- Research Chat 不再存在直接 paper trade tool；
- 使用旧 trade tool name → unknown_tool 且账本不变。

## 7. 后续

Company Intelligence、L3/L4 深度研究、财务/行业 provider adapter、AKShare Registry 都必须通过该 Gateway。动态数据继续固定 RESEARCH_ONLY，除非另行走版本化 point-in-time Promotion 流程。