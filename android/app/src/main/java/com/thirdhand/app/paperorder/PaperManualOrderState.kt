package com.thirdhand.app.paperorder

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.UUID

enum class PaperManualOrderSide(val wireValue: String) {
    BUY("BUY"),
    SELL("SELL"),
}

data class PaperManualOrderUiState(
    val symbol: String = "",
    val side: PaperManualOrderSide = PaperManualOrderSide.BUY,
    val quantityText: String = "",
    val capability: PaperManualOrderCapabilityDto? = null,
    val loadingCapability: Boolean = false,
    val submitting: Boolean = false,
    val errorMessage: String? = null,
    val successMessage: String? = null,
) {
    val parsedQuantity: Double?
        get() = quantityText.trim().toDoubleOrNull()?.takeIf { it > 0.0 }

    val serverMaximum: Double
        get() = when (side) {
            PaperManualOrderSide.BUY -> capability?.max_buy_quantity ?: 0.0
            PaperManualOrderSide.SELL -> capability?.max_sell_quantity ?: 0.0
        }

    val canSubmit: Boolean
        get() = capability?.executable == true &&
            parsedQuantity != null &&
            !loadingCapability &&
            !submitting
}

class PaperManualOrderController(
    private val gateway: PaperManualOrderGateway,
    private val orderIdProvider: () -> String = { UUID.randomUUID().toString() },
) {
    private val mutableState = MutableStateFlow(PaperManualOrderUiState())
    val state: StateFlow<PaperManualOrderUiState> = mutableState.asStateFlow()

    fun updateSymbol(value: String) {
        mutableState.value = mutableState.value.copy(
            symbol = value.uppercase(),
            capability = null,
            errorMessage = null,
            successMessage = null,
        )
    }

    fun updateSide(value: PaperManualOrderSide) {
        mutableState.value = mutableState.value.copy(
            side = value,
            errorMessage = null,
            successMessage = null,
        )
    }

    fun updateQuantity(value: String) {
        mutableState.value = mutableState.value.copy(
            quantityText = value.filter { it.isDigit() || it == '.' },
            errorMessage = null,
            successMessage = null,
        )
    }

    fun useServerMaximum() {
        val maximum = mutableState.value.serverMaximum
        if (maximum <= 0) return
        mutableState.value = mutableState.value.copy(
            quantityText = if (maximum % 1.0 == 0.0) maximum.toLong().toString() else maximum.toString(),
            errorMessage = null,
            successMessage = null,
        )
    }

    suspend fun loadCapability() {
        val symbol = mutableState.value.symbol.trim().uppercase()
        if (symbol.isBlank()) {
            mutableState.value = mutableState.value.copy(
                capability = null,
                errorMessage = "请输入证券代码后再检查可交易状态。",
                successMessage = null,
            )
            return
        }
        mutableState.value = mutableState.value.copy(
            symbol = symbol,
            loadingCapability = true,
            errorMessage = null,
            successMessage = null,
        )
        mutableState.value = when (val result = gateway.capability(symbol)) {
            is PaperManualOrderLoadResult.Success -> mutableState.value.copy(
                capability = result.capability,
                loadingCapability = false,
                errorMessage = result.capability.reason_codes.firstOrNull()?.let {
                    manualOrderReasonText(it, result.capability)
                },
            )
            is PaperManualOrderLoadResult.Failure -> mutableState.value.copy(
                capability = null,
                loadingCapability = false,
                errorMessage = result.message,
            )
        }
    }

    suspend fun submit(): Boolean {
        val before = mutableState.value
        val capability = before.capability
        val quantity = before.parsedQuantity
        if (capability?.executable != true) {
            mutableState.value = before.copy(
                errorMessage = capability?.reason_codes?.firstOrNull()?.let {
                    manualOrderReasonText(it, capability)
                } ?: "请先检查服务器当前可交易状态。",
                successMessage = null,
            )
            return false
        }
        if (quantity == null) {
            mutableState.value = before.copy(
                errorMessage = "请输入有效的正数下单数量。",
                successMessage = null,
            )
            return false
        }

        mutableState.value = before.copy(
            submitting = true,
            errorMessage = null,
            successMessage = null,
        )
        val input = PaperManualOrderInputDto(
            client_order_id = "android-${orderIdProvider()}",
            symbol = before.symbol.trim().uppercase(),
            side = before.side.wireValue,
            quantity = quantity,
        )
        return when (val result = gateway.submit(input)) {
            is PaperManualOrderSubmitResult.Success -> {
                val freshCapability = when (val refreshed = gateway.capability(input.symbol)) {
                    is PaperManualOrderLoadResult.Success -> refreshed.capability
                    is PaperManualOrderLoadResult.Failure -> capability
                }
                val fill = result.response.fill
                mutableState.value = mutableState.value.copy(
                    capability = freshCapability,
                    submitting = false,
                    errorMessage = null,
                    successMessage = buildString {
                        append(if (fill.side == "BUY") "模拟买入" else "模拟卖出")
                        append("已成交：")
                        append(if (fill.quantity % 1.0 == 0.0) fill.quantity.toLong() else fill.quantity)
                        append(" 股 @ ")
                        append("%.2f".format(fill.price))
                    },
                )
                true
            }
            is PaperManualOrderSubmitResult.Failure -> {
                val freshCapability = result.capability ?: when (val refreshed = gateway.capability(input.symbol)) {
                    is PaperManualOrderLoadResult.Success -> refreshed.capability
                    is PaperManualOrderLoadResult.Failure -> capability
                }
                mutableState.value = mutableState.value.copy(
                    capability = freshCapability,
                    submitting = false,
                    errorMessage = result.message,
                    successMessage = null,
                )
                false
            }
        }
    }
}
