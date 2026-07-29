# Theme

## Compact token summary

- Framework: Kotlin, Jetpack Compose, Material 3.
- Light canvas/surface: `#FFF8F3`; text: `#261714`; subdued text: `#59413A`.
- Brand orange: `#E45121`; orange container: `#FFD9C9`.
- Positive green: `#2D7A4A`; positive container: `#C7F1D0`.
- Destructive/error is the Material 3 semantic `error` token.
- Spacing uses Compose `dp`, primarily 2, 4, 8, 10, 14, 16, 20.
- Holdings rows are intentionally compact; table dividers use `outlineVariant` with reduced alpha.

## Raw source

Source: `android/app/src/main/java/com/thirdhand/app/Theme.kt`

```kotlin
private val LightColors = lightColorScheme(
    primary = Color(0xFFE45121), onPrimary = Color.White,
    primaryContainer = Color(0xFFFFD9C9), onPrimaryContainer = Color(0xFF4A1100),
    secondary = Color(0xFFB53A22), onSecondary = Color.White,
    tertiary = Color(0xFF2D7A4A), onTertiary = Color.White,
    background = Color(0xFFFFF8F3), onBackground = Color(0xFF261714),
    surface = Color(0xFFFFF8F3), onSurface = Color(0xFF261714),
    surfaceVariant = Color(0xFFF7E6DE), onSurfaceVariant = Color(0xFF59413A),
)
```
