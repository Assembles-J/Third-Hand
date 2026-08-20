package com.thirdhand.app.lab

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

sealed interface LabUiState {
    data object Loading : LabUiState
    data class Empty(val message: String = "暂无可评估的 SWING_V1 实验。") : LabUiState
    data class Ready(
        val dashboard: LabDashboardData,
        val refreshing: Boolean = false,
        val refreshError: String? = null,
    ) : LabUiState
    data class Error(val message: String, val recoverable: Boolean = true) : LabUiState
}

class LabController(private val repository: LabRepository) {
    private val mutableState = MutableStateFlow<LabUiState>(LabUiState.Loading)
    val state: StateFlow<LabUiState> = mutableState.asStateFlow()

    suspend fun load() {
        mutableState.value = LabUiState.Loading
        mutableState.value = repository.latestFormalSwingV1().toInitialState()
    }

    suspend fun refresh() {
        val previous = mutableState.value
        mutableState.value = if (previous is LabUiState.Ready) {
            previous.copy(refreshing = true, refreshError = null)
        } else {
            LabUiState.Loading
        }

        mutableState.value = when (val result = repository.latestFormalSwingV1()) {
            is LabLoadResult.Success -> LabUiState.Ready(result.dashboard)
            LabLoadResult.Empty -> if (previous is LabUiState.Ready) {
                previous.copy(
                    refreshing = false,
                    refreshError = "最新实验快照暂不可用，继续显示上次成功读取的结果。",
                )
            } else {
                LabUiState.Empty()
            }
            is LabLoadResult.Failure -> if (previous is LabUiState.Ready) {
                previous.copy(refreshing = false, refreshError = result.message)
            } else {
                LabUiState.Error(result.message, result.recoverable)
            }
        }
    }

    private fun LabLoadResult.toInitialState(): LabUiState = when (this) {
        is LabLoadResult.Success -> LabUiState.Ready(dashboard)
        LabLoadResult.Empty -> LabUiState.Empty()
        is LabLoadResult.Failure -> LabUiState.Error(message, recoverable)
    }
}
