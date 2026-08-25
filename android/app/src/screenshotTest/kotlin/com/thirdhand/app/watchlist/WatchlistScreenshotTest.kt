package com.thirdhand.app.watchlist

import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import com.android.tools.screenshot.PreviewTest
import com.thirdhand.app.ThemeMode
import com.thirdhand.app.ThirdHandTheme

@PreviewTest
@Preview(
    name = "Watchlist - Light Mode",
    showBackground = true,
    widthDp = 420,
    heightDp = 800,
)
@Composable
fun WatchlistScreenScreenshotTest() {
    val response = PersonalUniverseResponseDto(
        generated_at = "2026-08-14T10:00:00Z",
        items = listOf(
            PersonalUniverseItemDto(
                symbol = "01810",
                name = "小米集团-W",
                membership = "WATCHLIST_POSITION",
                market = "HK",
                watchlist_priority = "CORE",
                watchlist_note = "核心关注，AI Research 重点标的",
                watchlist_enabled = true,
                position_quantity = 1000.0,
                last_price = 18.52,
                change_percent = 2.45,
                quote_display_state = "live"
            ),
            PersonalUniverseItemDto(
                symbol = "600519",
                name = "贵州茅台",
                membership = "WATCHLIST",
                market = "CN",
                watchlist_priority = "FOCUS",
                watchlist_enabled = true,
                last_price = 1750.0,
                change_percent = -0.5,
                quote_display_state = "live"
            ),
            PersonalUniverseItemDto(
                symbol = "00700",
                name = "腾讯控股",
                membership = "POSITION",
                market = "HK",
                position_quantity = 100.0,
                last_price = 380.4,
                change_percent = 1.2,
                quote_display_state = "live"
            )
        ),
        counts = PersonalUniverseCountsDto(positions = 2, watchlist = 2, combined = 3)
    )
    val state = WatchlistUiState.Ready(
        response = response,
        selectedTab = PersonalUniverseTab.WATCHLIST
    )

    ThirdHandTheme(ThemeMode.LIGHT) {
        WatchlistScreenContent(
            state = state,
            onRefresh = {},
            onSelectTab = {},
            onAdd = {},
            onOpenDetail = {},
            onEdit = {},
            onDelete = {}
        )
    }
}

@PreviewTest
@Preview(
    name = "Watchlist Positions Tab - Light Mode",
    showBackground = true,
    widthDp = 420,
    heightDp = 800,
)
@Composable
fun WatchlistPositionsTabScreenshotTest() {
    val response = PersonalUniverseResponseDto(
        generated_at = "2026-08-14T10:00:00Z",
        items = listOf(
            PersonalUniverseItemDto(
                symbol = "01810",
                name = "小米集团-W",
                membership = "WATCHLIST_POSITION",
                market = "HK",
                position_quantity = 1000.0,
                sellable_quantity = 1000.0,
                locked_quantity = 0.0,
                last_price = 18.52,
                change_percent = 2.45,
                quote_display_state = "live"
            ),
            PersonalUniverseItemDto(
                symbol = "00700",
                name = "腾讯控股",
                membership = "POSITION",
                market = "HK",
                position_quantity = 100.0,
                sellable_quantity = 0.0,
                locked_quantity = 100.0,
                last_price = 380.4,
                change_percent = 1.2,
                quote_display_state = "live"
            )
        ),
        counts = PersonalUniverseCountsDto(positions = 2, watchlist = 1, combined = 2)
    )
    val state = WatchlistUiState.Ready(
        response = response,
        selectedTab = PersonalUniverseTab.POSITIONS
    )

    ThirdHandTheme(ThemeMode.LIGHT) {
        WatchlistScreenContent(
            state = state,
            onRefresh = {},
            onSelectTab = {},
            onAdd = {},
            onOpenDetail = {},
            onEdit = {},
            onDelete = {}
        )
    }
}
