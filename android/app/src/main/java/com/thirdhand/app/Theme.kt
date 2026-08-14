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

private val LightColors = lightColorScheme(
    primary = Color(0xFFF52D3A), onPrimary = Color.White,
    primaryContainer = Color(0xFFFFE0E3), onPrimaryContainer = Color(0xFF5C1017),
    secondary = Color(0xFF6B7280), onSecondary = Color.White,
    secondaryContainer = Color(0xFFF0F1F4), onSecondaryContainer = Color(0xFF262B33),
    tertiary = Color(0xFF16A05D), onTertiary = Color.White,
    tertiaryContainer = Color(0xFFD6F6E4), onTertiaryContainer = Color(0xFF073D20),
    background = Color(0xFFF7F8FA), onBackground = Color(0xFF1F2329),
    surface = Color(0xFFFFFFFF), onSurface = Color(0xFF1F2329),
    surfaceVariant = Color(0xFFF0F1F4), onSurfaceVariant = Color(0xFF667085),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFFFB3B9), onPrimary = Color(0xFF680013),
    primaryContainer = Color(0xFF920020), onPrimaryContainer = Color(0xFFFFDADF),
    secondary = Color(0xFFC9C5C6), onSecondary = Color(0xFF303033),
    secondaryContainer = Color(0xFF47464A), onSecondaryContainer = Color(0xFFE5E1E2),
    tertiary = Color(0xFF7DDBA4), onTertiary = Color(0xFF00391D),
    tertiaryContainer = Color(0xFF00522C), onTertiaryContainer = Color(0xFF98F9BE),
    background = Color(0xFF171113), onBackground = Color(0xFFEDE0E1),
    surface = Color(0xFF211A1C), onSurface = Color(0xFFEDE0E1),
    surfaceVariant = Color(0xFF3A2D30), onSurfaceVariant = Color(0xFFD6C1C4),
)

@Composable
fun ThirdHandTheme(mode: ThemeMode, content: @Composable () -> Unit) {
    val dark = when (mode) {
        ThemeMode.SYSTEM -> isSystemInDarkTheme()
        ThemeMode.LIGHT -> false
        ThemeMode.DARK -> true
    }
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
