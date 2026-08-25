package com.thirdhand.app.watchlist

import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import com.android.tools.screenshot.PreviewTest
import com.thirdhand.app.ThemeMode
import com.thirdhand.app.ThirdHandTheme

private const val WATCHLIST_PREVIEW_WIDTH = 420
private const val WATCHLIST_PREVIEW_HEIGHT = 900

@PreviewTest
@Preview(name = "Watchlist - ready", showBackground = true, widthDp = WATCHLIST_PREVIEW_WIDTH, heightDp = WATCHLIST_PREVIEW_HEIGHT)
@Composable
fun WatchlistReadyScreenshotTest() {
    WatchlistScreenshotFrame(WatchlistUiState.Ready(watchlistScreenshotSnapshot()))
}

@PreviewTest
@Preview(name = "Watchlist - partial stale", showBackground = true, widthDp = WATCHLIST_PREVIEW_WIDTH, heightDp = WATCHLIST_PREVIEW_HEIGHT)
@Composable
fun WatchlistPartialScreenshotTest() {
    WatchlistScreenshotFrame(
        WatchlistUiState.Ready(
            watchlistScreenshotSnapshot(dataState = "partial", warnings = listOf("1 个标的缺少可展示行情")),
            selectedTab = PersonalUniverseTab.POSITIONS,
        ),
    )
}

@PreviewTest
@Preview(name = "Watchlist - empty", showBackground = true, widthDp = WATCHLIST_PREVIEW_WIDTH, heightDp = WATCHLIST_PREVIEW_HEIGHT)
@Composable
fun WatchlistEmptyScreenshotTest() {
    WatchlistScreenshotFrame(
        WatchlistUiState.Ready(
            PersonalUniverseResponseDto(
                generated_at = "2026-08-24T12:00:00+08:00",
                counts = PersonalUniverseCountsDto(),
            ),
        ),
    )
}

@PreviewTest
@Preview(name = "Watchlist - error", showBackground = true, widthDp = WATCHLIST_PREVIEW_WIDTH, heightDp = WATCHLIST_PREVIEW_HEIGHT)
@Composable
fun WatchlistErrorScreenshotTest() {
    WatchlistScreenshotFrame(WatchlistUiState.Error("服务暂不可用"))
}

@Composable
private fun WatchlistScreenshotFrame(state: WatchlistUiState) {
    ThirdHandTheme(ThemeMode.LIGHT) {
        WatchlistScreenContent(
            state = state,
            onRefresh = {},
            onSelectTab = {},
            onAdd = {},
            onOpenDetail = {},
            onEdit = {},
            onDelete = {},
        )
    }
}
