# 行情刷新机制与生产排查

## 数据流

行情经过四层：

1. AKShare 公开实时快照：A 股、ETF、港股的首选来源；
2. MarketDataService 内存缓存：普通请求复用短缓存，主动刷新绕过缓存；
3. SQLite `market_quote_cache`：保存最近一次成功结果，外部行情源失败时作为降级数据；
4. Android：打开首页时主动刷新，之后每 60 秒读取服务器最新缓存；手动刷新会要求服务器绕过内存缓存。

后端常驻刷新线程默认每 60 秒读取当前持仓代码并刷新。即使没有手机在线，SQLite 行情缓存也会持续更新。

## 数据源模式

通过 `THIRD_HAND_MARKET_PROVIDER` 控制 A 股来源：

| 值 | 行为 |
| --- | --- |
| `akshare` | 仅使用公开实时快照 |
| `tushare` | 仅使用 Tushare 盘后日线，不是实时行情 |
| `auto` | 优先公开实时快照；公开源失败且配置 Token 时，回退 Tushare 盘后日线 |

生产环境使用 `auto`。港股始终优先公开实时快照，失败时回退最近收盘日线。

## 环境变量

```env
THIRD_HAND_MARKET_PROVIDER=auto
MARKET_REFRESH_ENABLED=true
MARKET_REFRESH_INTERVAL_SECONDS=60
TUSHARE_TOKEN=
```

刷新间隔最小为 30 秒。公开行情源不适合作为交易执行数据，不建议设置得更短。

## 接口

Android 和新客户端使用 POST JSON 批量请求，证券代码不再全部拼进 URL：

```bash
curl -sS -X POST \
  'https://groupim.cn/third-hand/v1/market/quotes/batch' \
  -H 'Content-Type: application/json' \
  -d '{"symbols":["01810","600519","BAD"],"refresh":true}'
```

响应始终按请求顺序返回，一只代码无效或上游失败不会让整批请求返回 503。旧的
`GET /v1/market/quotes?symbols=...` 暂时保留用于兼容。

通过名称反查证券代码：

```bash
curl -sS -X POST \
  'https://groupim.cn/third-hand/v1/market/symbols/resolve' \
  -H 'Content-Type: application/json' \
  -d '{"names":["贵州茅台","小米集团-W"]}'
```

名称反查使用 AKShare 的 `stock_info_a_code_name()` A 股代码表；ETF 和港股代码表
按市场独立查询。某一个市场的数据源异常时，其他市场仍会继续匹配，并通过
`lookup_status`、`lookup_message` 返回本条查询状态。

查看后端定时任务状态：

```bash
curl -sS \
  'https://groupim.cn/third-hand/v1/market/refresh-status'
```

重点字段：

| 字段 | 含义 |
| --- | --- |
| `worker_running` | 后端刷新线程是否存活 |
| `last_attempt_at` | 最近一次尝试时间 |
| `last_success_at` | 最近一次成功时间 |
| `last_error` | 最近错误；成功后清空 |
| `last_trigger` | `scheduler`、`request-forced` 等触发来源 |
| `symbols` | 最近刷新代码 |
| `result_count` | 最近成功返回数量 |

## 返回状态

每条行情的 `refresh_status`：

| 状态 | 含义 |
| --- | --- |
| `fresh` | 本次请求成功访问行情服务并写入缓存 |
| `cached_refreshing` | 先返回 SQLite 缓存，后台正在更新 |
| `stale_fallback` | 上游刷新失败，当前展示上次成功缓存 |
| `failed` | 该代码没有可用缓存且本次获取失败；其他代码不受影响 |

`fresh` 只表示本次上游请求成功，不代表交易所正在开市。还必须检查：

- `source`：实际数据源；
- `as_of`：行情所属日期；
- `retrieved_at`：后端抓取时间；
- `freshness_note`：是否为实时快照或盘后回退。
- `error_code`、`error_message`：该代码本次刷新失败的机器码与说明。

## 日志排查

```bash
cd /opt/third-hand
docker compose logs --tail=300 api | grep -E '行情刷新|公开 A 股|港股实时'
```

刷新失败不再静默吞掉。日志会包含触发方式、证券代码、错误码和上游错误信息。

如果手机仍显示旧数据，按顺序检查：

1. `/v1/market/refresh-status` 的 `worker_running`；
2. `last_success_at` 是否持续变化；
3. 强制刷新返回的 `refresh_status`、`source` 和 `as_of`；
4. 容器日志是否出现上游限流、连接失败或字段变化；
5. 当前是否休市，以及数据源是否回退到了盘后日线。
