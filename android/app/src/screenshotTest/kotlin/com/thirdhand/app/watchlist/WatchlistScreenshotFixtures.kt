package com.thirdhand.app.watchlist

internal fun watchlistScreenshotSnapshot(
    dataState: String = "ready",
    warnings: List<String> = emptyList(),
) = PersonalUniverseResponseDto(
    generated_at = "2026-08-24T12:00:00+08:00",
    data_state = dataState,
    warnings = warnings,
    counts = PersonalUniverseCountsDto(positions = 2, watchlist = 2, combined = 3),
    items = listOf(
        PersonalUniverseItemDto(
            symbol = "01810", name = "小米集团-W", membership = "POSITION_AND_WATCHLIST", market = "HK",
            watchlist_priority = "CORE", watchlist_note = "财报后继续观察交付与毛利", position_quantity = 200.0,
            sellable_quantity = 200.0, locked_quantity = 0.0, last_price = 28.10, change_percent = 1.20,
            quote_display_state = "live", quote_as_of = "2026-08-24T11:59:00+08:00", formal_action = "HOLD",
        ),
        PersonalUniverseItemDto(
            symbol = "00700", name = "腾讯控股", membership = "WATCHLIST", market = "HK",
            watchlist_priority = "FOCUS", watchlist_note = "等待估值与游戏流水确认", last_price = 620.0,
            change_percent = -0.50, quote_display_state = "session_close", quote_as_of = "2026-08-21T16:08:00+08:00",
        ),
        PersonalUniverseItemDto(
            symbol = "600519", name = "贵州茅台", membership = "POSITION", market = "CN",
            position_quantity = 100.0, sellable_quantity = 0.0, locked_quantity = 100.0,
            last_price = 1450.0, change_percent = 0.10, quote_display_state = "stale", quote_as_of = "2026-08-21T15:00:00+08:00",
        ),
    ),
)
