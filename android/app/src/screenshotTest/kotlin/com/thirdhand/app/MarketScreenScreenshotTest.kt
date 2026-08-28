package com.thirdhand.app

import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import com.android.tools.screenshot.PreviewTest

@PreviewTest
@Preview(name = "Market dense rows - light", showBackground = true, widthDp = 390)
@Composable
fun MarketDenseRowsScreenshotTest() {
    ThirdHandTheme(ThemeMode.LIGHT) {
        Column {
            MarketQuoteRow(
                quote = MarketQuoteDto(
                    symbol = "600900.SH",
                    name = "长江电力",
                    price = 27.68,
                    change_percent = 1.42,
                    currency = "CNY",
                    source = "cache",
                    retrieved_at = "2026-08-28T13:20:00+08:00",
                    freshness_note = "fresh",
                    as_of = "2026-08-28T13:20:00+08:00",
                ),
                isPaperPosition = true,
                onOpenDetail = {},
            )
            MarketQuoteRow(
                quote = MarketQuoteDto(
                    symbol = "002594.SZ",
                    name = "比亚迪",
                    price = 108.36,
                    change_percent = -0.87,
                    currency = "CNY",
                    source = "cache",
                    retrieved_at = "2026-08-28T13:20:00+08:00",
                    freshness_note = "fresh",
                    as_of = "2026-08-28T13:20:00+08:00",
                ),
                isPaperPosition = false,
                onOpenDetail = {},
            )
            MarketQuoteRow(
                quote = MarketQuoteDto(
                    symbol = "600025.SH",
                    name = "华能水电",
                    price = 10.12,
                    change_percent = 0.0,
                    currency = "CNY",
                    source = "cache",
                    retrieved_at = "2026-08-28T13:20:00+08:00",
                    freshness_note = "fresh",
                    as_of = "2026-08-28T13:20:00+08:00",
                ),
                isPaperPosition = false,
                onOpenDetail = {},
            )
        }
    }
}
