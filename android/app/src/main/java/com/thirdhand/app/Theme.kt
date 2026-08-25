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

// 现代化的金融类 App 配色方案：更专业的深蓝色/红绿对比
private val LightColors = lightColorScheme(
    primary = Color(0xFF0052D9), // 品牌蓝
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD6E4FF),
    onPrimaryContainer = Color(0xFF001D46),
    secondary = Color(0xFF535F70),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFD7E3F7),
    onSecondaryContainer = Color(0xFF101C2B),
    tertiary = Color(0xFF2D6A4F), // 辅助绿
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFB7E4C7),
    onTertiaryContainer = Color(0xFF082015),
    error = Color(0xFFBA1A1A),
    onError = Color.White,
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002),
    background = Color(0xFFF8FAFC), // 极简灰白背景
    onBackground = Color(0xFF191C1E),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF191C1E),
    surfaceVariant = Color(0xFFE0E2EC),
    onSurfaceVariant = Color(0xFF44474E),
    outline = Color(0xFF74777F)
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFADC6FF),
    onPrimary = Color(0xFF002E69),
    primaryContainer = Color(0xFF0044A6),
    onPrimaryContainer = Color(0xFFD6E4FF),
    secondary = Color(0xFFBBC7DB),
    onSecondary = Color(0xFF253140),
    secondaryContainer = Color(0xFF3B4758),
    onSecondaryContainer = Color(0xFFD7E3F7),
    tertiary = Color(0xFF9BD3B3),
    onTertiary = Color(0xFF003923),
    tertiaryContainer = Color(0xFF145138),
    onTertiaryContainer = Color(0xFFB7E4C7),
    error = Color(0xFFFFB4AB),
    onError = Color(0xFF690005),
    errorContainer = Color(0xFF93000A),
    onErrorContainer = Color(0xFFFFDAD6),
    background = Color(0xFF0F172A), // 深海蓝背景
    onBackground = Color(0xFFE2E2E6),
    surface = Color(0xFF1E293B), // 卡片颜色稍浅
    onSurface = Color(0xFFE2E2E6),
    surfaceVariant = Color(0xFF44474E),
    onSurfaceVariant = Color(0xFFC4C6D0),
    outline = Color(0xFF8E9099)
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
