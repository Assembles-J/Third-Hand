package com.thirdhand.app

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

sealed interface DecisionWorkspaceUiState {
    data object Loading : DecisionWorkspaceUiState

    data class Empty(
        val message: String = "暂无可用的正式决策记录。",
    ) : DecisionWorkspaceUiState

    data class Ready(
        val workspace: DecisionWorkspaceDto,
        val refreshing: Boolean = false,
        val refreshError: String? = null,
    ) : DecisionWorkspaceUiState

    data class Error(
        val message: String,
        val recoverable: Boolean = true,
    ) : DecisionWorkspaceUiState
}

class DecisionWorkspaceController(
    private val repository: DecisionWorkspaceRepository,
) {
    private val mutableState = MutableStateFlow<DecisionWorkspaceUiState>(DecisionWorkspaceUiState.Loading)
    val state: StateFlow<DecisionWorkspaceUiState> = mutableState.asStateFlow()

    suspend fun load(symbol: String) {
        mutableState.value = DecisionWorkspaceUiState.Loading
        mutableState.value = repository.latest(symbol).toInitialState()
    }

    suspend fun refresh(symbol: String) {
        val previous = mutableState.value
        if (previous is DecisionWorkspaceUiState.Ready) {
            mutableState.value = previous.copy(refreshing = true, refreshError = null)
        } else {
            mutableState.value = DecisionWorkspaceUiState.Loading
        }

        mutableState.value = when (val result = repository.latest(symbol)) {
            is DecisionWorkspaceLoadResult.Success -> DecisionWorkspaceUiState.Ready(result.workspace)
            DecisionWorkspaceLoadResult.Empty -> {
                if (previous is DecisionWorkspaceUiState.Ready) {
                    previous.copy(
                        refreshing = false,
                        refreshError = "最新正式决策暂不可用，继续显示上次有效结果。",
                    )
                } else {
                    DecisionWorkspaceUiState.Empty()
                }
            }
            is DecisionWorkspaceLoadResult.Failure -> {
                if (previous is DecisionWorkspaceUiState.Ready) {
                    previous.copy(
                        refreshing = false,
                        refreshError = result.message,
                    )
                } else {
                    DecisionWorkspaceUiState.Error(
                        message = result.message,
                        recoverable = result.recoverable,
                    )
                }
            }
        }
    }

    private fun DecisionWorkspaceLoadResult.toInitialState(): DecisionWorkspaceUiState = when (this) {
        is DecisionWorkspaceLoadResult.Success -> DecisionWorkspaceUiState.Ready(workspace)
        DecisionWorkspaceLoadResult.Empty -> DecisionWorkspaceUiState.Empty()
        is DecisionWorkspaceLoadResult.Failure -> DecisionWorkspaceUiState.Error(
            message = message,
            recoverable = recoverable,
        )
    }
}
