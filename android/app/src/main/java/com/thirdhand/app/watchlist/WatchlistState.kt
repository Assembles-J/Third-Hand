package com.thirdhand.app.watchlist

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

enum class PersonalUniverseTab { WATCHLIST, POSITIONS }

sealed interface WatchlistUiState {
    data object Loading : WatchlistUiState
    data class Ready(
        val response: PersonalUniverseResponseDto,
        val selectedTab: PersonalUniverseTab = PersonalUniverseTab.WATCHLIST,
        val refreshing: Boolean = false,
        val mutating: Boolean = false,
        val message: String? = null,
        val transientError: String? = null,
    ) : WatchlistUiState
    data class Error(val message: String, val recoverable: Boolean = true) : WatchlistUiState
}

fun WatchlistUiState.Ready.visibleItems(): List<PersonalUniverseItemDto> = when (selectedTab) {
    PersonalUniverseTab.WATCHLIST -> response.items.filter { it.isWatchlist }
    PersonalUniverseTab.POSITIONS -> response.items.filter { it.isPosition }
}

class WatchlistController(private val repository: WatchlistRepository) {
    private val mutableState = MutableStateFlow<WatchlistUiState>(WatchlistUiState.Loading)
    val state: StateFlow<WatchlistUiState> = mutableState.asStateFlow()

    suspend fun load() {
        mutableState.value = WatchlistUiState.Loading
        mutableState.value = repository.load().toInitialState()
    }

    fun selectTab(tab: PersonalUniverseTab) {
        val current = mutableState.value as? WatchlistUiState.Ready ?: return
        mutableState.value = current.copy(selectedTab = tab, message = null, transientError = null)
    }

    suspend fun refresh() {
        val previous = mutableState.value
        mutableState.value = if (previous is WatchlistUiState.Ready) {
            previous.copy(refreshing = true, message = null, transientError = null)
        } else {
            WatchlistUiState.Loading
        }
        mutableState.value = when (val result = repository.load()) {
            is WatchlistLoadResult.Success -> WatchlistUiState.Ready(
                response = result.response,
                selectedTab = (previous as? WatchlistUiState.Ready)?.selectedTab ?: PersonalUniverseTab.WATCHLIST,
            )
            is WatchlistLoadResult.Failure -> if (previous is WatchlistUiState.Ready) {
                previous.copy(refreshing = false, transientError = result.message)
            } else {
                WatchlistUiState.Error(result.message, result.recoverable)
            }
        }
    }

    suspend fun add(symbol: String, name: String) = mutate(
        action = { repository.add(symbol, name) },
        successMessage = "已加入自选：$symbol",
    )

    suspend fun update(symbol: String, enabled: Boolean, priority: String, note: String) {
        val current = mutableState.value as? WatchlistUiState.Ready ?: return
        val item = current.response.items.firstOrNull { it.symbol == symbol } ?: return
        if (!item.isWatchlist) return
        mutate(
            action = { repository.update(symbol, enabled, priority, note) },
            successMessage = "已更新 ${item.name.ifBlank { symbol }}",
        )
    }

    suspend fun remove(symbol: String) {
        val current = mutableState.value as? WatchlistUiState.Ready ?: return
        val item = current.response.items.firstOrNull { it.symbol == symbol } ?: return
        if (!item.isWatchlist) return
        mutate(
            action = { repository.remove(symbol) },
            successMessage = "已移出自选：${item.name.ifBlank { symbol }}",
        )
    }

    private suspend fun mutate(
        action: suspend () -> WatchlistLoadResult,
        successMessage: String,
    ) {
        val previous = mutableState.value as? WatchlistUiState.Ready ?: return
        mutableState.value = previous.copy(mutating = true, message = null, transientError = null)
        mutableState.value = when (val result = action()) {
            is WatchlistLoadResult.Success -> WatchlistUiState.Ready(
                response = result.response,
                selectedTab = previous.selectedTab,
                message = successMessage,
            )
            is WatchlistLoadResult.Failure -> previous.copy(
                mutating = false,
                transientError = result.message,
            )
        }
    }

    private fun WatchlistLoadResult.toInitialState(): WatchlistUiState = when (this) {
        is WatchlistLoadResult.Success -> WatchlistUiState.Ready(response)
        is WatchlistLoadResult.Failure -> WatchlistUiState.Error(message, recoverable)
    }
}
