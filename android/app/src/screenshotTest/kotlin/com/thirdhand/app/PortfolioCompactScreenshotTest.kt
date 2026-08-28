package com.thirdhand.app

import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import com.android.tools.screenshot.PreviewTest

@PreviewTest
@Preview(name = "Portfolio compact - ready", showBackground = true, widthDp = 390)
@Composable
fun PortfolioCompactReadyScreenshotTest() {
    val holdings = listOf(
        HoldingDto(
            id = "h1",
            symbol = "600900.SH",
            name = "长江电力",
            quantity = 1200.0,
            average_cost = 26.18,
            created_at = "2026-08-01T09:30:00+08:00",
        ),
        HoldingDto(
            id = "h2",
            symbol = "002594.SZ",
            name = "比亚迪",
            quantity = 300.0,
            average_cost = 110.20,
            created_at = "2026-08-18T10:00:00+08:00",
        ),
    )
    val quotes = mapOf(
        "600900.SH" to MarketQuoteDto(
            symbol = "600900.SH",
            name = "长江电力",
            price = 27.68,
            change_percent = 1.42,
            currency = "CNY",
            source = "cache",
            retrieved_at = "2026-08-28T13:20:00+08:00",
            freshness_note = "fresh",
            display_freshness = "live",
        ),
        "002594.SZ" to MarketQuoteDto(
            symbol = "002594.SZ",
            name = "比亚迪",
            price = 108.36,
            change_percent = -0.87,
            currency = "CNY",
            source = "cache",
            retrieved_at = "2026-08-28T13:20:00+08:00",
            freshness_note = "fresh",
            display_freshness = "session_close",
        ),
    )

    ThirdHandTheme(ThemeMode.LIGHT) {
        CompactPortfolioContent(
            holdings = holdings,
            availableCash = 54280.0,
            quotes = quotes,
            totalMarketValue = 1200 * 27.68 + 300 * 108.36,
            totalPnl = 1200 * (27.68 - 26.18) + 300 * (108.36 - 110.20),
            loading = false,
            errorMessage = null,
            onRefresh = {},
            onOpenDetail = {},
        )
    }
}
