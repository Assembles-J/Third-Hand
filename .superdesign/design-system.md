# Third-Hand Mobile Research Design System

## Product context

Third-Hand is a mobile-first A-share research, portfolio review and simulated-account execution assistant. The UI must prioritize authoritative market/position facts and existing research or execution state. It must not imply a capability that the repository does not currently implement.

## Visual direction

Use a light-first, red-first Chinese financial-market language with the scan density of mature securities apps, while keeping Third-Hand's own Material 3 identity.

- Canvas and surface: cool white `#F7F8FA` and `#FFFFFF`; secondary surface `#FFF0F2`.
- Brand: market red `#F52D3A`; brand container `#FFE0E3`; dark brand text `#5C1017`.
- Text: `#1F2329`; subdued text: `#667085`.
- Market semantics: A-share rise `#F52D3A`, fall `#16A05D`, flat `#7A8492`; errors remain a separate Material error role.
- Typography: Android system sans. Scan-heavy surfaces use compact roles: page title 18sp, section/list title 14sp, primary body/value 13-14sp, secondary 12sp and auxiliary captions/navigation labels 10sp.
- Spacing: existing scale remains compatible; dense surfaces prefer 16dp horizontal content inset, 8dp row vertical padding, 10dp section rhythm and thin inset dividers.
- Touch targets: visual density must not reduce interactive targets below 44dp.
- Corners/elevation: use cards only for meaningful grouping; prefer flat rows, thin separators and low/no elevation for lists and financial tables.

## Current mobile information architecture

UIX1 does not change the current primary navigation:

`资讯 | 行情 | 持仓 | 交易 | 自选`

The bottom bar should use small labels/icons, restrained selection treatment and no decorative elevation. Navigation semantics and routes stay unchanged while individual screens migrate incrementally.

## Dense financial layout rules

- Align comparable numeric values to the right.
- Keep security identity/name on the left and quote/status values on the right.
- Use text labels in addition to rise/fall/state colors.
- Prefer one compact section header plus rows/dividers instead of a rounded card around every row.
- Keep metadata such as symbol, market, time, freshness and review state visually secondary.
- Avoid oversized marketing/dashboard typography on market, portfolio, watchlist and simulated-account screens.
- Do not add decorative charts or metrics when no authoritative DTO currently supplies them.

## Screen boundaries

### Holdings / position facts

Portfolio and Holding Detail remain fact-first: price/freshness, quantity, cost, market value, P/L, holding duration, weight, K-line and existing transaction facts. AI/research narrative does not move into the basic holdings table.

### Decision / research

Decision Workspace remains separate from basic holding facts. Existing conclusion/action, supporting evidence, risk, what-changed and review/lineage facts may use compact labeled rows. Android must not recalculate server-owned decision or review authority.

### Trading

The current `交易` entry is the existing simulated-account / Paper Trading execution console. It is **not** a real broker order ticket.

Preserve the current capabilities only:

- simulated-account equity, cash, market value and cumulative P/L;
- paper positions;
- persisted simulated-account automatic-execution enabled/paused state;
- manual `立即运行决策轮换` action;
- execution-chain history;
- executed records and their decision/audit drill-down.

Do not introduce manual BUY/SELL tickets, price/quantity steppers, cancellation, broker switching, real-money transfer or real-broker execution unless a later accepted product slice explicitly implements those capabilities.

## Research chat layout

- Conversation content scrolls above a fixed composer; reserve bottom padding so the final assistant card never sits behind the composer or system navigation.
- Assistant analysis uses concise `结论`, `支持`, `风险`, `待确认` labels when those facts are available from the existing research result.
- Chips wrap instead of clipping; the composer remains compact and does not obscure message content.

## Accessibility and interaction

- Every icon action has a text label or content description.
- Status always uses text in addition to color.
- Interactive rows have at least a 44dp touch target; long titles truncate predictably.
- Use native Material controls and no gradients or decorative motion.
