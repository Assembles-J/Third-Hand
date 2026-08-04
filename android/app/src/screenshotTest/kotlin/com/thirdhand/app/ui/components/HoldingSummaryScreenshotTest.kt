package com.thirdhand.app.ui.components

import android.content.res.Configuration
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import com.android.tools.screenshot.PreviewTest
import com.thirdhand.app.ThemeMode
import com.thirdhand.app.ThirdHandTheme
import com.thirdhand.app.ui.theme.AppSpacing
import androidx.compose.foundation.layout.padding

@PreviewTest
@Preview(name = "Holding summary - light", showBackground = true)
@Composable
fun HoldingSummaryLightScreenshotTest() {
    ThirdHandTheme(ThemeMode.LIGHT) {
        HoldingSummaryCard(
            holdingCount = 3,
            pendingCount = 1,
            marketValue = "128,560.00",
            totalPnl = "+6,420.50",
            totalPnlIsPositive = true,
            onAdd = {},
            onImport = {},
            modifier = Modifier.padding(AppSpacing.large),
        )
    }
}

@PreviewTest
@Preview(name = "Holding summary - dark", showBackground = true, uiMode = Configuration.UI_MODE_NIGHT_YES)
@Composable
fun HoldingSummaryDarkScreenshotTest() {
    ThirdHandTheme(ThemeMode.DARK) {
        HoldingSummaryCard(
            holdingCount = 2,
            pendingCount = 0,
            marketValue = "98,100.00",
            totalPnl = "-2,480.00",
            totalPnlIsPositive = false,
            onAdd = {},
            onImport = {},
            modifier = Modifier.padding(AppSpacing.large),
        )
    }
}
