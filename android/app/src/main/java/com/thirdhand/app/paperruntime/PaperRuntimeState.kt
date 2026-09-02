package com.thirdhand.app.paperruntime

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.UUID

data class PaperRuntimeUiState(
    val runtime: PaperRuntimeStateDto? = null,
    val loading: Boolean = false,
    val restarting: Boolean = false,
    val restartDialogVisible: Boolean = false,
    val initialCashText: String = "100000",
    val errorMessage: String? = null,
    val successMessage: String? = null,
) {
    val parsedInitialCash: Double?
        get() = initialCashText.trim().toDoubleOrNull()?.takeIf { it > 0.0 }

    val canRestart: Boolean
        get() = parsedInitialCash != null && !loading && !restarting
}

class PaperRuntimeController(
    private val gateway: PaperRuntimeGateway,
    private val restartIdProvider: () -> String = { UUID.randomUUID().toString() },
) {
    private val mutableState = MutableStateFlow(PaperRuntimeUiState())
    val state: StateFlow<PaperRuntimeUiState> = mutableState.asStateFlow()
    private var pendingRestartId: String? = null
    private var pendingRestartCash: Double? = null

    suspend fun load() {
        mutableState.value = mutableState.value.copy(
            loading = true,
            errorMessage = null,
        )
        mutableState.value = when (val result = gateway.runtimeState()) {
            is PaperRuntimeLoadResult.Success -> mutableState.value.copy(
                runtime = result.state,
                loading = false,
                errorMessage = null,
            )
            is PaperRuntimeLoadResult.Failure -> mutableState.value.copy(
                loading = false,
                errorMessage = result.message,
            )
        }
    }

    fun openRestartDialog(defaultInitialCash: Double) {
        val value = defaultInitialCash.takeIf { it > 0.0 }
            ?: mutableState.value.runtime?.epoch?.initial_cash?.takeIf { it > 0.0 }
            ?: 100_000.0
        pendingRestartId = null
        pendingRestartCash = null
        mutableState.value = mutableState.value.copy(
            restartDialogVisible = true,
            initialCashText = value.asInputText(),
            errorMessage = null,
            successMessage = null,
        )
    }

    fun closeRestartDialog() {
        if (mutableState.value.restarting) return
        pendingRestartId = null
        pendingRestartCash = null
        mutableState.value = mutableState.value.copy(restartDialogVisible = false)
    }

    fun updateInitialCash(value: String) {
        pendingRestartId = null
        pendingRestartCash = null
        mutableState.value = mutableState.value.copy(
            initialCashText = value.filter { it.isDigit() || it == '.' },
            errorMessage = null,
            successMessage = null,
        )
    }

    suspend fun restart(): Boolean {
        val before = mutableState.value
        val initialCash = before.parsedInitialCash
        if (initialCash == null) {
            mutableState.value = before.copy(
                errorMessage = "请输入大于 0 的模拟初始资金。",
                successMessage = null,
            )
            return false
        }

        mutableState.value = before.copy(
            restarting = true,
            errorMessage = null,
            successMessage = null,
        )
        val requestId = if (pendingRestartId != null && pendingRestartCash == initialCash) {
            requireNotNull(pendingRestartId)
        } else {
            "android-restart-${restartIdProvider()}".also {
                pendingRestartId = it
                pendingRestartCash = initialCash
            }
        }
        val request = PaperSimulationRestartInputDto(
            client_restart_id = requestId,
            initial_cash = initialCash,
        )
        return when (val result = gateway.restart(request)) {
            is PaperRestartResult.Success -> {
                pendingRestartId = null
                pendingRestartCash = null
                val fresh = when (val loaded = gateway.runtimeState()) {
                    is PaperRuntimeLoadResult.Success -> loaded.state
                    is PaperRuntimeLoadResult.Failure -> mutableState.value.runtime
                }
                mutableState.value = mutableState.value.copy(
                    runtime = fresh,
                    restarting = false,
                    restartDialogVisible = false,
                    errorMessage = null,
                    successMessage = "第 ${result.response.epoch.sequence} 轮模拟已开始：空仓，初始资金 ¥${"%.2f".format(initialCash)}。",
                )
                true
            }
            is PaperRestartResult.Failure -> {
                mutableState.value = mutableState.value.copy(
                    restarting = false,
                    errorMessage = result.message,
                    successMessage = null,
                )
                false
            }
        }
    }
}

private fun Double.asInputText(): String =
    if (this % 1.0 == 0.0) toLong().toString() else toString()
