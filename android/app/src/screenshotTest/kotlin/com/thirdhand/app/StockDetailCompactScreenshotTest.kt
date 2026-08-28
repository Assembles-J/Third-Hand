package com.thirdhand.app

import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import com.android.tools.screenshot.PreviewTest

@PreviewTest
@Preview(
    name = "Stock facts - compact",
    showBackground = true,
    widthDp = 420,
    heightDp = 280,
)
@Composable
fun StockFactsCompactScreenshotTest() {
    ThirdHandTheme(ThemeMode.LIGHT) {
        Column {
            StockFactsHeader(
                quote = MarketQuoteDto(
                    symbol = "002594.SZ",
                    name = "比亚迪",
                    price = 108.36,
                    change_percent = 1.28,
                    change = 1.37,
                    open = 107.10,
                    high = 109.25,
                    low = 106.88,
                    previous_close = 106.99,
                    volume = 22_360_000.0,
                    amount = 2_418_000_000.0,
                    currency = "CNY",
                    source = "cache",
                    retrieved_at = "2026-08-28T13:20:00+08:00",
                    freshness_note = "fresh",
                    as_of = "2026-08-28T13:20:00+08:00",
                    is_realtime = true,
                    display_freshness = "live",
                ),
                membershipLabel = "组合持仓",
                averageCost = 104.82,
                returnPercent = 3.38,
            )
            StockMarketFacts(
                MarketQuoteDto(
                    symbol = "002594.SZ",
                    name = "比亚迪",
                    price = 108.36,
                    change_percent = 1.28,
                    change = 1.37,
                    open = 107.10,
                    high = 109.25,
                    low = 106.88,
                    previous_close = 106.99,
                    volume = 22_360_000.0,
                    amount = 2_418_000_000.0,
                    currency = "CNY",
                    source = "cache",
                    retrieved_at = "2026-08-28T13:20:00+08:00",
                    freshness_note = "fresh",
                    as_of = "2026-08-28T13:20:00+08:00",
                    is_realtime = true,
                    display_freshness = "live",
                )
            )
        }
    }
}
