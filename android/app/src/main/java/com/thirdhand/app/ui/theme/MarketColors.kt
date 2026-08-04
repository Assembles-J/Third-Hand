package com.thirdhand.app.ui.theme

import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

data class MarketColors(
    val rise: Color,
    val fall: Color,
    val neutral: Color,
    val warning: Color,
    val information: Color,
    val chartGrid: Color,
)

val LightMarketColors = MarketColors(
    rise = Color(0xFFD32F2F),
    fall = Color(0xFF178A4B),
    neutral = Color(0xFF5F6368),
    warning = Color(0xFF9A6700),
    information = Color(0xFF1B6CA8),
    chartGrid = Color(0x1F000000),
)

val DarkMarketColors = MarketColors(
    rise = Color(0xFFFFB4AB),
    fall = Color(0xFF8CE5A7),
    neutral = Color(0xFFC5C8CC),
    warning = Color(0xFFFFD27D),
    information = Color(0xFF9DCDFF),
    chartGrid = Color(0x33FFFFFF),
)

val LocalMarketColors = staticCompositionLocalOf { LightMarketColors }

val MaterialTheme.marketColors: MarketColors
    @Composable
    get() = LocalMarketColors.current
