package com.thirdhand.app

import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.android.tools.screenshot.PreviewTest

@PreviewTest
@Preview(
    name = "Paper holdings - fixed security column",
    showBackground = true,
    widthDp = 420,
    heightDp = 360,
)
@Composable
fun PaperPositionsTableScreenshotTest() {
    ThirdHandTheme(ThemeMode.LIGHT) {
        PaperPositionsTable(
            positions = listOf(
                paperPosition("002594", "比亚迪", 100.0, 88.558, 88.660, 8866.0, 10.24, 0.12, 100.0, 0.0),
                paperPosition("601318", "中国平安", 400.0, 53.029, 52.080, 20832.0, -379.73, -1.79, 400.0, 0.0),
                paperPosition("600025", "华能水电", 1100.0, 12.917, 10.900, 11990.0, -2219.0, -15.62, 700.0, 400.0),
                paperPosition("603553", "603553", 600.0, 25.332, 23.510, 14106.0, -1093.49, -7.19, 600.0, 0.0),
            ),
            presentation = PaperPositionPresentation(
                namesBySymbol = mapOf(
                    "002594" to "比亚迪",
                    "601318" to "中国平安",
                    "600025" to "华能水电",
                    "603553" to "名称待同步",
                ),
            ),
            onOpenDetail = { _, _ -> },
            modifier = Modifier.padding(vertical = 8.dp),
        )
    }
}

private fun paperPosition(
    symbol: String,
    name: String,
    quantity: Double,
    averageCost: Double,
    lastPrice: Double,
    marketValue: Double,
    pnl: Double,
    pnlPercent: Double,
    sellable: Double,
    locked: Double,
) = PaperTradingPositionDto(
    symbol = symbol,
    name = name,
    quantity = quantity,
    average_cost = averageCost,
    last_price = lastPrice,
    market_value = marketValue,
    unrealized_pnl = pnl,
    unrealized_return_percent = pnlPercent,
    sellable_quantity = sellable,
    locked_quantity = locked,
    updated_at = "2026-08-19T15:00:00+08:00",
)
