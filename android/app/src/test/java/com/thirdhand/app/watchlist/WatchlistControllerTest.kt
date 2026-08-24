package com.thirdhand.app.watchlist

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WatchlistControllerTest {
    @Test
    fun sibling_tabs_filter_without_losing_overlap() = runBlocking {
        val repository = FakeWatchlistRepository(successSnapshot())
        val controller = WatchlistController(repository)
        controller.load()
        val ready = controller.state.value as WatchlistUiState.Ready
        assertEquals(listOf("01810", "00700"), ready.visibleItems().map { it.symbol })

        controller.selectTab(PersonalUniverseTab.POSITIONS)
        val positions = controller.state.value as WatchlistUiState.Ready
        assertEquals(listOf("01810", "600519"), positions.visibleItems().map { it.symbol })
    }

    @Test
    fun refresh_failure_keeps_last_successful_snapshot() = runBlocking {
        val repository = FakeWatchlistRepository(successSnapshot())
        val controller = WatchlistController(repository)
        controller.load()
        repository.next = WatchlistLoadResult.Failure("network down")

        controller.refresh()

        val state = controller.state.value as WatchlistUiState.Ready
        assertEquals(3, state.response.items.size)
        assertEquals("network down", state.transientError)
        assertFalse(state.refreshing)
    }

    @Test
    fun position_only_row_cannot_be_removed_as_watchlist() = runBlocking {
        val repository = FakeWatchlistRepository(successSnapshot())
        val controller = WatchlistController(repository)
        controller.load()

        controller.remove("600519")

        assertEquals(0, repository.removeCalls)
        assertTrue((controller.state.value as WatchlistUiState.Ready).response.items.any { it.symbol == "600519" })
    }

    @Test
    fun watchlist_mutation_reloads_authoritative_personal_universe() = runBlocking {
        val repository = FakeWatchlistRepository(successSnapshot())
        val controller = WatchlistController(repository)
        controller.load()
        repository.next = WatchlistLoadResult.Success(
            successSnapshot().copy(items = successSnapshot().items.filterNot { it.symbol == "00700" }),
        )

        controller.remove("00700")

        val state = controller.state.value as WatchlistUiState.Ready
        assertEquals(1, repository.removeCalls)
        assertFalse(state.response.items.any { it.symbol == "00700" })
        assertTrue(state.message.orEmpty().contains("移出自选"))
    }
}

private class FakeWatchlistRepository(initial: PersonalUniverseResponseDto) : WatchlistRepository {
    var next: WatchlistLoadResult = WatchlistLoadResult.Success(initial)
    var removeCalls = 0
    override suspend fun load(): WatchlistLoadResult = next
    override suspend fun add(symbol: String, name: String): WatchlistLoadResult = next
    override suspend fun update(symbol: String, priority: String, note: String): WatchlistLoadResult = next
    override suspend fun remove(symbol: String): WatchlistLoadResult {
        removeCalls += 1
        return next
    }
}

private fun successSnapshot() = PersonalUniverseResponseDto(
    generated_at = "2026-08-24T12:00:00+08:00",
    counts = PersonalUniverseCountsDto(positions = 2, watchlist = 2, combined = 3),
    items = listOf(
        PersonalUniverseItemDto(
            symbol = "01810", name = "小米集团-W", membership = "POSITION_AND_WATCHLIST", market = "HK",
            watchlist_priority = "CORE", position_quantity = 200.0, sellable_quantity = 200.0,
            last_price = 28.10, change_percent = 1.20, quote_display_state = "live",
        ),
        PersonalUniverseItemDto(
            symbol = "00700", name = "腾讯控股", membership = "WATCHLIST", market = "HK",
            watchlist_priority = "FOCUS", last_price = 620.0, change_percent = -0.50, quote_display_state = "session_close",
        ),
        PersonalUniverseItemDto(
            symbol = "600519", name = "贵州茅台", membership = "POSITION", market = "CN",
            position_quantity = 100.0, sellable_quantity = 100.0, last_price = 1450.0, change_percent = 0.10,
        ),
    ),
)
