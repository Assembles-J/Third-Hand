# Third-Hand Operations Console — Design System

## Product and audience

An internal administration console for the Third-Hand A-share information assistant. It is used by the system owner to see whether the remote backend is healthy, how much capacity is being consumed, where data is flowing, and to make bounded operational changes without exposing sensitive credentials.

Primary jobs: diagnose service health at a glance; find a resource or quota problem before users are affected; review queued jobs and alerts; adjust safe configuration such as refresh cadence, notification thresholds, retention, and feature availability.

## Visual direction

**Name:** Control-room ledger. A dark, high-information operational surface that feels like a precise system instrument rather than a consumer analytics dashboard.

- Canvas: graphite `#111614`; panel `#171E1B`; elevated panel `#1D2622`
- Primary signal: mint `#9EFFBF`; operational teal `#4ED6C2`
- Warning: gold `#F4D35E`; critical: coral `#FF8C69`; quiet text `#9DA9A3`
- Divider: `rgba(202, 220, 208, 0.16)`; all separations use 1px hairlines, with no gradients and no glossy shadows.
- Display/type: Space Grotesk for section headings; General Sans or system sans for body; JetBrains Mono for metrics, timestamps, IDs, controls and technical labels.
- Corners are square or 2px. Use a 12-column desktop grid. Wide panels intentionally share borders, forming a dense command-center ledger.

## Layout and components

- Fixed left rail, 232px wide: product mark, environment selector, structured navigation. The active item carries a 3px mint rule and a compact count/status chip.
- Top bar: breadcrumb, the last data-sync timestamp, a live system-status badge, notification control, and administrator profile.
- Main title row: `系统总览` with subtitle `REMOTE BACKEND / CN-SHANGHAI-01`; right-aligned `刷新数据` and `进入维护模式` actions.
- First row: four equal KPI cells for API availability, active users, task throughput, and daily LLM spend. Each uses a large numeric readout, small delta, and a tiny one-color sparkline.
- Primary body: a large service topology / throughput panel with a 24-hour bar-and-line chart; beside it a compact alert queue ordered by severity.
- Secondary body: resource capacity table (CPU, memory, PostgreSQL, Redis, object storage) with actual vs quota and projection; task queue table with status, latency, retry and owner.
- Bottom strip: data-source health timeline and a configuration panel with real controls: refresh interval segmented control, alert threshold input, retention selector, safe-mode toggle and a `保存更改` button.
- Use Chinese operational copy, specific realistic labels, timestamps and quantities. Never give investment advice or display individual user holdings.

## Interaction and accessibility

- Status always combines icon, text and color. Critical states also have a clear action such as `查看日志` or `暂停任务`.
- All controls are native-looking buttons, inputs, switches and selects with visible labels and keyboard focus states.
- Data-heavy panels collapse in a single column on tablet; on mobile show the health strip and alert queue before charts/tables.
- Motion is limited to a subtle live-status pulse and chart update transition; disable both under reduced motion.

## Signature detail

Use a fine, non-decorative topology trace: short routed lines connect `API`, `Worker`, `PostgreSQL`, `Redis`, and `LLM` markers in the main throughput panel. The trace uses mint for healthy segments and coral for the single delayed segment, so the architecture also communicates current operational state.
