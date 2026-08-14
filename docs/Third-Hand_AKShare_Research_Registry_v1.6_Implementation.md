# Third-Hand AKShare Research Registry v1.6 实施说明

## 1. 两层权限必须分开

```text
ak.search / interface_info / list_categories
            ↓
      metadata discovery
            ↓
   只能告诉 AI “有哪些接口”

explicit code allowlist
            ↓
 guarded executor
            ↓
 ResearchDataGateway
            ↓
 persisted RESEARCH_ONLY snapshot
```

**搜索到接口 ≠ 获得执行权限。**

## 2. Registry

`AkshareRegistryService` 封装：

- `search(query)`
- `interface_info(interface_name)`
- `list_categories()`

Registry 不修改 allowlist，不产生 formal Evidence，也不调用 ActionPolicy。

## 3. Execution Policy

`AkshareExecutionPolicy` 采用显式 interface allowlist。默认空集合。

禁止：

- 任意 `eval` / `exec`；
- LLM 直接拼 Python；
- 私有/dunder interface；
- search 结果自动加入 allowlist。

## 4. Executor

`AkshareResearchExecutor`：

- 参数只能是受限 JSON 结构；
- 函数名必须显式 allowlisted；
- timeout；
- max rows；
- DataFrame/Series/numpy/date 等在 infrastructure 层规范化；
- 未知 opaque object 拒绝；
- 输出固定 `usage_scope=RESEARCH_ONLY`。

## 5. Local-First Bridge

`AkshareGatewayFetcher` 把 allowlisted interface 包装成 `ResearchDataGateway` provider：

```text
local fresh snapshot
    ↓ YES
remote calls = 0

local miss/stale
    ↓
allowlisted AKShare interface
    ↓
normalize
    ↓
persist + reread
    ↓
AI Research
```

动态 Registry 数据不会绕过 Gateway 直接进入 prompt。

## 6. as_of 语义

Generic Registry executor无法可靠理解任意接口的业务报告期，因此通用 bridge 使用：

```text
as_of_semantics = retrieval_time_fallback
```

这只是 RESEARCH_ONLY 兜底语义。真正进入 Company Financial / margin / announcement provider adapter 时必须定义更强的 report_period / announcement_at / available_at 规则。

## 7. 下一步

- 为 Company Intelligence 数据类型逐个注册经过验证的 AKShare interface；
- A 股与港股分别建立 capability matrix；
- 对财务报表保存 report_period + announcement_at；
- 事件/公告保存 published_at/available_at；
- 任何希望 Promotion 到 POLICY 的字段必须另走 point-in-time 回放与人工审批。