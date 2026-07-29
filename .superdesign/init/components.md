# Shared UI components

This Android application uses Jetpack Compose Material 3 rather than a web component library.

## PositionValueCell

- Source: `android/app/src/main/java/com/thirdhand/app/MainActivity.kt`
- Purpose: compact, right-aligned two-line numeric cell used by the holdings grid.

```kotlin
@Composable
private fun PositionValueCell(main: String, sub: String, color: Color, modifier: Modifier) = Column(
    modifier, horizontalAlignment = Alignment.End,
) {
    Text(main, color = color, fontWeight = FontWeight.SemiBold,
        style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.End, maxLines = 1)
    Text(sub, color = color.copy(alpha = .82f), style = MaterialTheme.typography.labelSmall,
        textAlign = TextAlign.End, maxLines = 1)
}
```

## Status entries

`MarketStatusEntry` and `AnalysisEntry` are compact navigable rows in `MainActivity.kt`. They use the Material 3 color scheme, a trailing ChevronRight icon, and no card surface.
