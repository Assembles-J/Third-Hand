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
    primary = Color(0xFF164E63), onPrimary = Color.White,
    primaryContainer = Color(0xFFD5F3F5), onPrimaryContainer = Color(0xFF00363E),
    secondary = Color(0xFF475569), onSecondary = Color.White,
    secondaryContainer = Color(0xFFE2E8F0), onSecondaryContainer = Color(0xFF1E293B),
    tertiary = Color(0xFF0F766E), onTertiary = Color.White,
    tertiaryContainer = Color(0xFFCCFBF1), onTertiaryContainer = Color(0xFF134E4A),
    background = Color(0xFFF7F9FC), onBackground = Color(0xFF17212B),
    surface = Color(0xFFFFFFFF), onSurface = Color(0xFF17212B),
    surfaceVariant = Color(0xFFEAF0F5), onSurfaceVariant = Color(0xFF4A5A69),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF8DE2E7), onPrimary = Color(0xFF00363E),
    primaryContainer = Color(0xFF0B5964), onPrimaryContainer = Color(0xFFD5F3F5),
    secondary = Color(0xFFBFC9D6), onSecondary = Color(0xFF293544),
    secondaryContainer = Color(0xFF3A4858), onSecondaryContainer = Color(0xFFE2E8F0),
    tertiary = Color(0xFF81E6D9), onTertiary = Color(0xFF003D39),
    tertiaryContainer = Color(0xFF165E59), onTertiaryContainer = Color(0xFFCCFBF1),
    background = Color(0xFF111A22), onBackground = Color(0xFFE7EEF5),
    surface = Color(0xFF18232D), onSurface = Color(0xFFE7EEF5),
    surfaceVariant = Color(0xFF263542), onSurfaceVariant = Color(0xFFC4D0DC),
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
