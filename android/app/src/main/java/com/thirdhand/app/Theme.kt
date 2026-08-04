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
    primary = Color(0xFFE45121), onPrimary = Color.White,
    primaryContainer = Color(0xFFFFD9C9), onPrimaryContainer = Color(0xFF4A1100),
    secondary = Color(0xFFB53A22), onSecondary = Color.White,
    secondaryContainer = Color(0xFFFFDDD1), onSecondaryContainer = Color(0xFF421000),
    tertiary = Color(0xFF2D7A4A), onTertiary = Color.White,
    tertiaryContainer = Color(0xFFC7F1D0), onTertiaryContainer = Color(0xFF003917),
    background = Color(0xFFFFF8F3), onBackground = Color(0xFF261714),
    surface = Color(0xFFFFF8F3), onSurface = Color(0xFF261714),
    surfaceVariant = Color(0xFFF7E6DE), onSurfaceVariant = Color(0xFF59413A),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFFFB59D), onPrimary = Color(0xFF621A04),
    primaryContainer = Color(0xFF8A2E14), onPrimaryContainer = Color(0xFFFFD9C9),
    secondary = Color(0xFFFFB5A0), onSecondary = Color(0xFF641B09),
    secondaryContainer = Color(0xFF85301C), onSecondaryContainer = Color(0xFFFFD9D0),
    tertiary = Color(0xFFA8DCB1), onTertiary = Color(0xFF003919),
    tertiaryContainer = Color(0xFF155D32), onTertiaryContainer = Color(0xFFC7F1D0),
    background = Color(0xFF211713), onBackground = Color(0xFFF6EDE8),
    surface = Color(0xFF211713), onSurface = Color(0xFFF6EDE8),
    surfaceVariant = Color(0xFF51413B), onSurfaceVariant = Color(0xFFDBC9C2),
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
