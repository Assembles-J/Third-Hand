# Third-Hand Mobile Research Design System

## Product context

Third-Hand is a mobile-first A-share research and review assistant. The research screen helps an investor return to saved conversations, understand evidence, and record follow-up questions without suggesting automatic trading.

## Visual direction

Use a red-first financial-market Material 3 product language.

- Canvas and surface: cool white `#F7F8FA` and `#FFFFFF`; secondary surface `#FFF0F2`.
- Brand: market red `#F52D3A`; brand container `#FFE0E3`; dark brand text `#5C1017`.
- Text: `#1F2329`; subdued text: `#667085`.
- Market semantics: A-share rise `#F52D3A`, fall `#16A05D`, flat `#7A8492`; errors remain a separate Material error role.
- Typography: Android system sans / Material 3 typography; medium and semibold only for hierarchy.
- Spacing: use 4, 8, 10, 14, 16, 20 dp. Corners are 12-18 dp, with restrained elevation.

## Research chat layout

- Mobile market screen: a red top market-scope header with search, followed by a white segmented switch for \`大盘 / 板块 / 个股\`. Preserve the app's existing four-item Material NavigationBar: \`新闻 / 行情 / 交易 / 管理\`, with \`交易\` using the wallet icon.
- Conversation: content scrolls above a fixed composer; reserve bottom padding so the final assistant card never sits behind the composer or system navigation.
- Assistant analysis: replace dense prose with a clear summary card followed by short evidence/action chips. Show `结论`, `支持`, `风险`, `待确认` as separate labeled rows. Chips must wrap instead of clipping.
- Composer: a single compact text field, send button, and visible background-analysis state. Do not obscure message content.

## Accessibility and interaction

- Every icon action has a text label or content description.
- Status always uses text in addition to color.
- Session rows have at least a 44 dp touch target; long titles truncate to two lines.
- Use native Material controls and no gradients or decorative motion.
