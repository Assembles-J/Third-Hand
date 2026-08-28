package com.thirdhand.app.ui.components

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

/**
 * Compatibility wrappers for existing trading/market screens.
 *
 * UIX1 keeps the public component names stable while moving their presentation
 * onto the shared dense primitives. Feature slices can migrate without a
 * navigation/API rewrite.
 */
@Composable
fun TradingPageHeader(title: String, subtitle: String, action: @Composable (() -> Unit)? = null) {
    DensePageHeader(
        title = title,
        subtitle = subtitle,
        action = action,
    )
}

@Composable
fun TradingSection(title: String, detail: String? = null, modifier: Modifier = Modifier) {
    DenseSectionHeader(
        title = title,
        detail = detail,
        modifier = modifier,
    )
}

@Composable
fun TradingRowDivider(inset: Boolean = true) = DenseRowDivider(inset = inset)
