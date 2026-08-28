package com.thirdhand.app.ui.theme

import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * Shared spacing tokens.
 *
 * The legacy scale remains stable so existing screens can migrate incrementally.
 * Dense tokens are the UIX1 contract for scan-heavy financial surfaces and keep
 * interactive rows at or above a 44dp touch target.
 */
object AppSpacing {
    val xxs: Dp = 2.dp
    val xs: Dp = 4.dp
    val small: Dp = 8.dp
    val medium: Dp = 12.dp
    val large: Dp = 16.dp
    val xLarge: Dp = 20.dp
    val xxLarge: Dp = 24.dp

    // UIX1 compact financial layout tokens.
    val contentHorizontal: Dp = 16.dp
    val sectionVertical: Dp = 10.dp
    val rowHorizontal: Dp = 16.dp
    val rowVertical: Dp = 8.dp
    val denseGap: Dp = 6.dp
    val dividerInset: Dp = 16.dp
    val touchTarget: Dp = 44.dp
}
