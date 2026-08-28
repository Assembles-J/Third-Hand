package com.thirdhand.app

import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import com.android.tools.screenshot.PreviewTest

@PreviewTest
@Preview(
    name = "Home dashboard - compact ready",
    showBackground = true,
    widthDp = 420,
    heightDp = 900,
)
@Composable
fun HomeDashboardReadyScreenshotTest() {
    val positions = listOf(
        PaperTradingPositionDto(
            symbol = "600025",
            name = "华能水电",
            quantity = 1100.0,
            average_cost = 12.917,
            last_price = 13.260,
            market_value = 14586.0,
            unrealized_pnl = 377.30,
            unrealized_return_percent = 2.66,
            sellable_quantity = 700.0,
            locked_quantity = 400.0,
            next_eligible_sell_at = "2026-08-29T09:30:00+08:00",
            updated_at = "2026-08-28T14:58:00+08:00",
        ),
        PaperTradingPositionDto(
            symbol = "002594",
            name = "比亚迪",
            quantity = 100.0,
            average_cost = 88.558,
            last_price = 87.920,
            market_value = 8792.0,
            unrealized_pnl = -63.80,
            unrealized_return_percent = -0.72,
            sellable_quantity = 100.0,
            locked_quantity = 0.0,
            updated_at = "2026-08-28T14:58:00+08:00",
        ),
    )
    val dashboard = PaperTradingDashboardDto(
        account = PaperTradingAccountDto(
            available_cash = 76321.40,
            initial_cash = 100000.0,
            market_value = 23378.0,
            total_equity = 99699.40,
            total_pnl = 819.64,
            total_return_percent = 0.82,
            updated_at = "2026-08-28T14:58:00+08:00",
            enabled = true,
            positions = positions,
        ),
        status = PaperTradingStatusDto(
            enabled = true,
            interval_seconds = 600,
            running = false,
            last_started_at = "2026-08-28T14:50:00+08:00",
            last_finished_at = "2026-08-28T14:50:18+08:00",
            last_status = "completed",
            last_message = "completed",
            last_executed = 1,
            last_skipped = 2,
            last_symbols = listOf("600025", "002594"),
            seconds_until_next_run = 422,
            state_source = "persisted",
        ),
        logs = listOf(
            PaperTradingLogDto(
                id = "home-log-1",
                symbol = "600025",
                name = "华能水电",
                side = "BUY",
                quantity = 100.0,
                price = 13.260,
                cash_before = 77649.40,
                cash_after = 76321.40,
                decision_id = "decision-1",
                reason = "formal_action",
                executed_at = "2026-08-28T14:50:16+08:00",
            ),
            PaperTradingLogDto(
                id = "home-log-2",
                symbol = "002594",
                name = "比亚迪",
                side = "SELL",
                quantity = 100.0,
                price = 87.920,
                cash_before = 67529.40,
                cash_after = 76321.40,
                decision_id = "decision-2",
                reason = "formal_action",
                executed_at = "2026-08-28T14:31:04+08:00",
            ),
        ),
        snapshots = listOf(
            PaperEquitySnapshotDto(99120.0, 78000.0, 21120.0, 120.0, "2026-08-28T09:35:00+08:00"),
            PaperEquitySnapshotDto(99380.0, 78000.0, 21380.0, 380.0, "2026-08-28T10:15:00+08:00"),
            PaperEquitySnapshotDto(99240.0, 77649.4, 21590.6, 240.0, "2026-08-28T11:05:00+08:00"),
            PaperEquitySnapshotDto(99520.0, 77649.4, 21870.6, 520.0, "2026-08-28T13:20:00+08:00"),
            PaperEquitySnapshotDto(99699.4, 76321.4, 23378.0, 819.64, "2026-08-28T14:58:00+08:00"),
        ),
    )
    val news = listOf(
        NewsItemDto(
            id = "news-1",
            title = "新能源电力板块午后维持活跃",
            explanation = "行业动态与现有关注标的相关。",
            source_name = "市场快讯",
            source_url = "https://example.com/1",
            published_at = "2026-08-28T14:42:00+08:00",
        ),
        NewsItemDto(
            id = "news-2",
            title = "比亚迪披露最新经营进展公告",
            explanation = "公告事实等待正式决策链按既有规则处理。",
            source_name = "交易所公告",
            source_url = "https://example.com/2",
            published_at = "2026-08-28T13:18:00+08:00",
        ),
    )

    ThirdHandTheme(ThemeMode.LIGHT) {
        HomeDashboardContent(
            snapshot = HomeDashboardSnapshot(
                paperDashboard = dashboard,
                news = news,
            ),
            loading = false,
            onRefresh = {},
            onOpenNews = {},
        )
    }
}
