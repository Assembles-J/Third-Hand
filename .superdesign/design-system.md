# Third-Hand Mobile Research Design System

## Product context

Third-Hand is a mobile-first A-share research and review assistant. The research screen helps an investor return to saved conversations, understand evidence, and record follow-up questions without suggesting automatic trading.

## Visual direction

Use the existing light orange Material 3 product language.

- Canvas and surface: warm ivory `#FFF8F3`; secondary surface `#F7E6DE`.
- Brand: orange `#E45121`; brand container `#FFD9C9`; dark brand text `#4A1100`.
- Text: `#261714`; subdued text: `#59413A`.
- Positive: `#2D7A4A`; errors use the semantic Material error color.
- Typography: Android system sans / Material 3 typography; medium and semibold only for hierarchy.
- Spacing: use 4, 8, 10, 14, 16, 20 dp. Corners are 12-18 dp, with restrained elevation.

## Research chat layout

- Mobile screen: a compact header with a session switcher and a new-chat button. A modal navigation drawer shows saved sessions with symbol, short title, latest time, and the active-session marker.
- Conversation: content scrolls above a fixed composer; reserve bottom padding so the final assistant card never sits behind the composer or system navigation.
- Assistant analysis: replace dense prose with a clear summary card followed by short evidence/action chips. Show `结论`, `支持`, `风险`, `待确认` as separate labeled rows. Chips must wrap instead of clipping.
- Composer: a single compact text field, send button, and visible background-analysis state. Do not obscure message content.

## Accessibility and interaction

- Every icon action has a text label or content description.
- Status always uses text in addition to color.
- Session rows have at least a 44 dp touch target; long titles truncate to two lines.
- Use native Material controls and no gradients or decorative motion.
