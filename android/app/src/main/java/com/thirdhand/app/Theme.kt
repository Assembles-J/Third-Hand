package com.thirdhand.app

import android.content.Context
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

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
    primary = Color(0xFFD32F2F), onPrimary = Color.White,
    primaryContainer = Color(0xFFFFDAD6), onPrimaryContainer = Color(0xFF410002),
    secondary = Color(0xFF775651), onSecondary = Color.White,
    surface = Color(0xFFFFFBFF), onSurface = Color(0xFF201A19),
    surfaceVariant = Color(0xFFF5DDDA), onSurfaceVariant = Color(0xFF534341),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFFFB4AB), onPrimary = Color(0xFF690005),
    primaryContainer = Color(0xFF93000A), onPrimaryContainer = Color(0xFFFFDAD6),
    secondary = Color(0xFFE7BDB7), onSecondary = Color(0xFF442924),
    surface = Color(0xFF201A19), onSurface = Color(0xFFEDE0DE),
    surfaceVariant = Color(0xFF534341), onSurfaceVariant = Color(0xFFD8C2BF),
)

@Composable
fun ThirdHandTheme(mode: ThemeMode, content: @Composable () -> Unit) {
    val dark = when (mode) {
        ThemeMode.SYSTEM -> isSystemInDarkTheme()
        ThemeMode.LIGHT -> false
        ThemeMode.DARK -> true
    }
    MaterialTheme(colorScheme = if (dark) DarkColors else LightColors, content = content)
}
