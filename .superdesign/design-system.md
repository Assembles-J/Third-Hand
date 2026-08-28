# Third-Hand Mobile Research Design System

## Product context

Third-Hand is a mobile-first A-share research, portfolio review and simulated-account decision/execution assistant. The UI prioritizes authoritative market/position facts and existing research, review or execution state. It must not imply a capability that the repository does not currently implement.

## Approved product shell

The target primary navigation is:

`首页 | 行情 | 组合 | 策略 | 自选`

This supersedes the former `资讯 | 行情 | 持仓 | 交易 | 自选` shell as the visual/product acceptance baseline. Old labels may remain temporarily inside implementation history during migration, but new shell work must converge on the approved target.

Capability mapping:

- `首页`: existing attention/change/portfolio/review/research facts only where APIs already provide them;
- `行情`: current market, search and stock-detail capability;
- `组合`: current Holdings and Position Detail factual capability;
- `策略`: current simulated-account execution, Decision Workspace and available review/research-plan capability;
- `自选`: current Personal Universe / Watchlist capability.

## Visual direction

Use a light-first, brand-red Chinese financial-market language with the scan density of mature securities apps while keeping Third-Hand's own Material 3 identity.

- Canvas and surface: cool white `#F7F8FA` and `#FFFFFF`; secondary emphasis surface `#FFF0F2`.
- Brand / primary shell and action: `#F52D3A`; brand container `#FFE0E3`; dark brand text `#5C1017`.
- Text: `#1F2329`; subdued text: `#667085`.
- Market semantics: A-share rise `#F52D3A`, fall `#16A05D`, flat `#7A8492`; errors remain a separate Material error role.
- Typography: Android system sans. Scan-heavy surfaces use compact roles: page title 18sp, section/list title 14sp, primary body/value 13-14sp, secondary 12sp and auxiliary captions/navigation labels 10-11sp.
- Spacing: dense surfaces prefer 16dp horizontal content inset, 6-8dp visual row rhythm, 8-12dp section rhythm and thin inset dividers while preserving 44dp interaction targets.
- Touch targets: visual density must not reduce interactive targets below 44dp.
- Corners/elevation: use cards only for meaningful grouping; prefer flat rows, thin separators and low/no elevation for lists and financial tables.

Brand red owns shell selection and primary actions. Market rise red remains a data semantic; do not rely on hue alone to distinguish navigation/action state from price movement.

## Global shell rules

- Bottom navigation is compact, low-chrome and anchored by the selected brand-red item and label.
- Unselected destinations use neutral icons/text.
- Top bars stay in the compact 44-52dp class where platform constraints allow.
- Action icons are limited to functions the screen actually implements.
- Comparable financial values align to consistent right-side columns.
- Security identity/name remains left-led; quote/status/value fields remain right-led.
- Prefer one compact section header plus rows/dividers instead of a rounded card around every row.
- Avoid decorative gradients, hero marketing blocks and oversized AI branding.

## Dense financial layout rules

- Align comparable numeric values to the right.
- Keep metadata such as symbol, market, time, freshness and review state visually secondary.
- Use text labels in addition to rise/fall/state colors.
- Avoid oversized dashboard typography on market, portfolio, watchlist and simulated-account screens.
- Do not add decorative charts or metrics when no authoritative DTO supplies them.
- Keep one primary financial number dominant only when the screen genuinely has one; dominance should come from hierarchy, not excessive scale.

## Screen boundaries

### 首页

Home is an attention/change surface, not a place to invent a new AI brief.

Where backed by current APIs it may compose:

- portfolio/account snapshot;
- review or material-attention state;
- important decision/research status;
- currentness/data notices;
- current News/market context;
- quick routes to `组合`, `策略` and `自选`.

Each independently loaded section keeps explicit loading/empty/partial/error behavior. A failed section must not blank the rest of Home.

### 行情

Market keeps existing market/search/detail capability. Use compact session/index summaries, aligned quote/ranking rows and existing breadth/sector facts only when provided. Do not invent unsupported market statistics.

### 组合 / position facts

Portfolio and Holding Detail remain fact-first: price/freshness, quantity, cost, market value, P/L, holding duration, weight, K-line and existing transaction facts. Existing sellable/T+1 facts may be shown where the authoritative position/paper contract supplies them.

AI/research narrative does not move into the basic portfolio table. Decision remains a secondary route from factual detail.

### 策略

Strategy organizes current decision/review and simulated-account capability. It may surface:

- simulated-account equity, cash, market value and cumulative P/L;
- paper positions;
- persisted simulated-account automatic-execution enabled/paused state;
- manual `立即运行决策轮换` action;
- execution-chain history;
- executed records and decision/audit drill-down;
- Decision Workspace;
- server-owned ReviewPlan/research-plan facts where already available;
- existing Strategy Lab/evaluation entry where already implemented.

The simulated-account safety boundary is mandatory. Do not introduce manual BUY/SELL tickets, price/quantity steppers, cancellation, broker switching, real-money transfer, real-broker execution or future N5 isolated AI-agent paper-account behavior before those capabilities are separately implemented and accepted.

Preferred authority-accurate wording includes:

`模拟账套`, `模拟账户自动执行`, `立即运行决策轮换`, `执行链路记录`, `最近成交记录`, `分析记录`, `决策与 AI`.

Avoid `AI 下单`, `确认下单`, `真实交易`, `自动实盘`, `券商下单` while those semantics are unsupported.

### 自选

Watchlist / Personal Universe remains a high-density monitoring and management surface. Keep name/symbol, latest quote/change, freshness and available priority/note/enabled/review state compactly visible. Add/edit/remove flows remain reachable and held-symbol routing remains distinct from watchlist-only routing.

Android does not calculate ReviewPolicy or silently promote Discovery into trading scope.

### Detail and Decision / research

Factual Stock/Position Detail and Decision Workspace share the same compact visual system but remain separate responsibilities.

Factual detail owns quote/freshness, K-line, holding facts when applicable and existing financial/event/currentness facts appropriate to the fact surface.

Decision Workspace owns conclusion/action, supporting evidence, risk, what changed, review/lineage and deeper AI Research entry. Android must not recalculate server-owned decision or review authority.

## Research chat layout

- Conversation content scrolls above a fixed composer; reserve bottom padding so the final assistant card never sits behind the composer or system navigation.
- Assistant analysis uses concise `结论`, `支持`, `风险`, `待确认` labels when those facts are available from the existing research result.
- Chips wrap instead of clipping; the composer remains compact and does not obscure message content.

## Reference-driven acceptance

Screenshot hashes remain regression protection, not the complete visual acceptance standard.

For every rebuilt surface, compare the rendered Android UI against the approved target direction at normal phone scale for:

- exact primary-shell labels and destination hierarchy;
- brand-red shell/action treatment;
- white/cool-light canvas;
- density and whitespace;
- typography scale;
- card restraint and divider use;
- numeric alignment;
- red-up / green-down semantics;
- explicit simulated-account / no-real-broker wording where relevant.

A screenshot may have a newly approved hash and still fail target-reference acceptance if the hierarchy or visual language remains materially off target.

## Accessibility and interaction

- Every icon action has a text label or content description.
- Status always uses text in addition to color.
- Interactive rows have at least a 44dp target; long titles truncate predictably.
- Primary actions must not depend on undiscoverable gestures.
- Destructive actions remain explicit.
- Use native Material controls and restrained motion.
