package com.thirdhand.app

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import com.android.tools.screenshot.PreviewTest

@PreviewTest
@Preview(name = "Strategy console - enabled", showBackground = true, widthDp = 390, heightDp = 844)
@Composable
fun StrategyConsoleEnabledScreenshotTest() {
    val positions = listOf(
        PaperTradingPositionDto(
            symbol = "600900.SH",
            name = "长江电力",
            quantity = 1200.0,
            average_cost = 26.18,
            last_price = 27.68,
            market_value = 33216.0,
            unrealized_pnl = 1800.0,
            unrealized_return_percent = 5.73,
            sellable_quantity = 1200.0,
            locked_quantity = 0.0,
            updated_at = "2026-08-28T13:20:00+08:00",
        ),
        PaperTradingPositionDto(
            symbol = "002594.SZ",
            name = "比亚迪",
            quantity = 300.0,
            average_cost = 110.20,
            last_price = 108.36,
            market_value = 32508.0,
            unrealized_pnl = -552.0,
            unrealized_return_percent = -1.67,
            sellable_quantity = 200.0,
            locked_quantity = 100.0,
            next_eligible_sell_at = "2026-08-29T09:30:00+08:00",
            updated_at = "2026-08-28T13:20:00+08:00",
        ),
    )
    val account = PaperTradingAccountDto(
        available_cash = 54280.0,
        initial_cash = 100000.0,
        market_value = 65724.0,
        total_equity = 120004.0,
        total_pnl = 1248.0,
        total_return_percent = 1.05,
        updated_at = "2026-08-28T13:20:00+08:00",
        enabled = true,
        positions = positions,
    )
    val status = PaperTradingStatusDto(
        enabled = true,
        interval_seconds = 600,
        running = false,
        last_started_at = "2026-08-28T13:10:00+08:00",
        last_finished_at = "2026-08-28T13:11:00+08:00",
        last_status = "completed",
        last_message = "completed",
        last_executed = 1,
        last_skipped = 1,
        last_symbols = listOf("600900.SH", "002594.SZ"),
        seconds_until_next_run = 480,
        last_run_id = "run-20260828-1310",
        state_source = "persisted",
    )
    val logs = listOf(
        PaperTradingLogDto(
            id = "log-1",
            symbol = "600900.SH",
            name = "长江电力",
            side = "BUY",
            quantity = 100.0,
            price = 27.62,
            cash_before = 57042.0,
            cash_after = 54280.0,
            decision_id = "decision-1",
            reason = "formal BUY",
            executed_at = "2026-08-28T13:11:00+08:00",
        ),
        PaperTradingLogDto(
            id = "log-2",
            symbol = "002594.SZ",
            name = "比亚迪",
            side = "SELL",
            quantity = 100.0,
            price = 108.30,
            cash_before = 43450.0,
            cash_after = 54280.0,
            decision_id = "decision-2",
            reason = "formal REDUCE",
            executed_at = "2026-08-28T10:26:00+08:00",
        ),
    )
    val dashboard = PaperTradingDashboardDto(
        account = account,
        logs = logs,
        status = status,
    )
    val presentation = PaperPositionPresentation(
        namesBySymbol = positions.associate { it.symbol to it.name },
    )
    val runs = listOf(
        SimulationRunDto(
            run_id = "run-20260828-1310",
            trigger = "auto",
            started_at = "2026-08-28T13:10:00+08:00",
            finished_at = "2026-08-28T13:11:00+08:00",
            status = "completed",
            symbol_count = 2,
            generated = 2,
            executed = 1,
            skipped = 1,
            message = "completed",
        )
    )

    ThirdHandTheme(ThemeMode.LIGHT) {
        Scaffold(
            topBar = {
                StrategyPageHeader(refreshing = false, onRefresh = {})
            },
        ) { paddingValues ->
            StrategyExecutionContent(
                dashboard = dashboard,
                positionPresentation = presentation,
                runs = runs,
                refreshing = false,
                running = false,
                changingEnabled = false,
                errorMessage = null,
                operationMessage = null,
                onOpenPosition = { _, _ -> },
                onEnabledChange = {},
                onRun = {},
                onOpenRunChain = {},
                onOpenAllLogs = {},
                onOpenDecision = {},
                onOpenLab = {},
                modifier = Modifier.padding(paddingValues),
            )
        }
    }
}
