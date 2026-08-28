package com.thirdhand.app

import android.content.Context
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.graphics.Color
import com.thirdhand.app.ui.theme.DarkMarketColors
import com.thirdhand.app.ui.theme.LightMarketColors
import com.thirdhand.app.ui.theme.LocalMarketColors
import com.thirdhand.app.ui.theme.ThirdHandShapes
import com.thirdhand.app.ui.theme.ThirdHandSystemBars
import com.thirdhand.app.ui.theme.ThirdHandTypography

enum class ThemeMode(val label: String) {
    SYSTEM("跟随系统"), LIGHT("浅色"), DARK("深色"),
}

object ThemeStore {
    private const val PREFS = "third_hand_settings"
    private const val THEME_MODE = "theme_mode"

    fun load(context: Context): ThemeMode = runCatching {
        ThemeMode.valueOf(context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(THEME_MODE, ThemeMode.SYSTEM.name).orEmpty())
    }.getOrDefault(ThemeMode.SYSTEM)

    fun save(context: Context, mode: ThemeMode) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(THEME_MODE, mode.name).apply()
    }
}

// UIX0 target palette: light-first, brand-red Chinese securities styling.
// Market rise/fall semantics remain owned by MarketColors rather than these
// generic Material roles.
private val LightColors = lightColorScheme(
    primary = Color(0xFFF52D3A),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFFFE0E3),
    onPrimaryContainer = Color(0xFF5C1017),
    secondary = Color(0xFFB4232F),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFFFE8EA),
    onSecondaryContainer = Color(0xFF5C1017),
    tertiary = Color(0xFF16A05D),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFDDF5E8),
    onTertiaryContainer = Color(0xFF0B4D30),
    error = Color(0xFFBA1A1A),
    onError = Color.White,
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002),
    background = Color(0xFFF7F8FA),
    onBackground = Color(0xFF1F2329),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF1F2329),
    surfaceVariant = Color(0xFFF1F3F5),
    onSurfaceVariant = Color(0xFF667085),
    outline = Color(0xFFD0D5DD),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFFF6B75),
    onPrimary = Color(0xFF5C0009),
    primaryContainer = Color(0xFF7A1520),
    onPrimaryContainer = Color(0xFFFFE0E3),
    secondary = Color(0xFFFFB3B8),
    onSecondary = Color(0xFF650D16),
    secondaryContainer = Color(0xFF5C2026),
    onSecondaryContainer = Color(0xFFFFDADD),
    tertiary = Color(0xFF58D18E),
    onTertiary = Color(0xFF00391F),
    tertiaryContainer = Color(0xFF145C37),
    onTertiaryContainer = Color(0xFFDDF5E8),
    error = Color(0xFFFFB4AB),
    onError = Color(0xFF690005),
    errorContainer = Color(0xFF93000A),
    onErrorContainer = Color(0xFFFFDAD6),
    background = Color(0xFF111315),
    onBackground = Color(0xFFE8EAED),
    surface = Color(0xFF191C1F),
    onSurface = Color(0xFFE8EAED),
    surfaceVariant = Color(0xFF252A2F),
    onSurfaceVariant = Color(0xFFB6BCC5),
    outline = Color(0xFF747B84),
)

@Composable
fun ThirdHandTheme(mode: ThemeMode, content: @Composable () -> Unit) {
    val dark = when (mode) {
        ThemeMode.SYSTEM -> isSystemInDarkTheme()
        ThemeMode.LIGHT -> false
        ThemeMode.DARK -> true
    }
    ThirdHandSystemBars(dark)
    MaterialTheme(
        colorScheme = if (dark) DarkColors else LightColors,
        typography = ThirdHandTypography,
        shapes = ThirdHandShapes,
    ) {
        CompositionLocalProvider(LocalMarketColors provides if (dark) DarkMarketColors else LightMarketColors) {
            content()
        }
    }
}
