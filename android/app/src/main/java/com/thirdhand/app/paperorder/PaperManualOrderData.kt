package com.thirdhand.app.paperorder

import android.content.Context
import com.google.gson.Gson
import com.thirdhand.app.EndpointStore
import okhttp3.OkHttpClient
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import java.util.concurrent.TimeUnit

data class PaperManualOrderCapabilityDto(
    val symbol: String,
    val market: String? = null,
    val currency: String? = null,
    val paper_account_currency: String = "CNY",
    val executable: Boolean = false,
    val reason_codes: List<String> = emptyList(),
    val lot_size: Int? = null,
    val market_open: Boolean = false,
    val quote_price: Double? = null,
    val quote_observed_at: String? = null,
    val quote_source: String? = null,
    val available_cash: Double = 0.0,
    val held_quantity: Double = 0.0,
    val sellable_quantity: Double = 0.0,
    val locked_quantity: Double = 0.0,
    val next_eligible_sell_at: String? = null,
    val max_buy_quantity: Double = 0.0,
    val max_sell_quantity: Double = 0.0,
)

data class PaperManualOrderInputDto(
    val client_order_id: String,
    val symbol: String,
    val side: String,
    val quantity: Double,
)

data class PaperManualOrderFillDto(
    val id: String,
    val symbol: String,
    val name: String,
    val side: String,
    val quantity: Double,
    val price: Double,
    val fee: Double = 0.0,
    val cash_before: Double,
    val cash_after: Double,
    val decision_id: String? = null,
    val reason: String,
    val execution_quote_at: String? = null,
    val execution_quote_source: String? = null,
    val fill_price_mode: String? = null,
    val executed_at: String,
)

data class PaperManualOrderResponseDto(
    val status: String,
    val idempotent_replay: Boolean = false,
    val fill: PaperManualOrderFillDto,
)

private data class PaperManualOrderErrorDetailDto(
    val reason_code: String? = null,
    val capability: PaperManualOrderCapabilityDto? = null,
)

private data class PaperManualOrderErrorEnvelopeDto(
    val detail: PaperManualOrderErrorDetailDto? = null,
)

interface PaperManualOrderApi {
    @GET("v1/paper-trading/order-capability/{symbol}")
    suspend fun capability(@Path("symbol") symbol: String): PaperManualOrderCapabilityDto

    @POST("v1/paper-trading/orders")
    suspend fun submit(@Body input: PaperManualOrderInputDto): PaperManualOrderResponseDto
}

sealed interface PaperManualOrderLoadResult {
    data class Success(val capability: PaperManualOrderCapabilityDto) : PaperManualOrderLoadResult
    data class Failure(val message: String) : PaperManualOrderLoadResult
}

sealed interface PaperManualOrderSubmitResult {
    data class Success(val response: PaperManualOrderResponseDto) : PaperManualOrderSubmitResult
    data class Failure(
        val message: String,
        val reasonCode: String? = null,
        val capability: PaperManualOrderCapabilityDto? = null,
    ) : PaperManualOrderSubmitResult
}

interface PaperManualOrderGateway {
    suspend fun capability(symbol: String): PaperManualOrderLoadResult
    suspend fun submit(input: PaperManualOrderInputDto): PaperManualOrderSubmitResult
}

class RetrofitPaperManualOrderRepository(
    private val api: PaperManualOrderApi,
    private val gson: Gson = Gson(),
) : PaperManualOrderGateway {
    override suspend fun capability(symbol: String): PaperManualOrderLoadResult = runCatching {
        api.capability(symbol.trim().uppercase())
    }.fold(
        onSuccess = { PaperManualOrderLoadResult.Success(it) },
        onFailure = {
            PaperManualOrderLoadResult.Failure("无法读取当前模拟下单能力，请稍后重试。")
        },
    )

    override suspend fun submit(input: PaperManualOrderInputDto): PaperManualOrderSubmitResult = try {
        PaperManualOrderSubmitResult.Success(api.submit(input))
    } catch (error: HttpException) {
        val body = error.response()?.errorBody()?.string()
        val parsed = runCatching {
            gson.fromJson(body, PaperManualOrderErrorEnvelopeDto::class.java)
        }.getOrNull()
        val detail = parsed?.detail
        PaperManualOrderSubmitResult.Failure(
            message = manualOrderReasonText(detail?.reason_code, detail?.capability),
            reasonCode = detail?.reason_code,
            capability = detail?.capability,
        )
    } catch (error: Exception) {
        PaperManualOrderSubmitResult.Failure("模拟订单提交失败，请检查网络后重试。")
    }
}

object PaperManualOrderFeature {
    private var configuredBaseUrl: String = ""
    private var configuredRepository: PaperManualOrderGateway? = null

    fun repository(context: Context): PaperManualOrderGateway {
        val baseUrl = EndpointStore.baseUrl(context)
        if (configuredRepository == null || configuredBaseUrl != baseUrl) {
            configuredBaseUrl = baseUrl
            val retrofit = Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(
                    OkHttpClient.Builder()
                        .callTimeout(45, TimeUnit.SECONDS)
                        .build(),
                )
                .addConverterFactory(GsonConverterFactory.create())
                .build()
            configuredRepository = RetrofitPaperManualOrderRepository(
                retrofit.create(PaperManualOrderApi::class.java),
            )
        }
        return requireNotNull(configuredRepository)
    }
}

fun manualOrderReasonText(
    reasonCode: String?,
    capability: PaperManualOrderCapabilityDto? = null,
): String = when (reasonCode) {
    "paper_hk_execution_not_configured" ->
        "港股模拟成交暂未开放：HKD/CNY 资金与费用规则尚未完成。"
    "paper_foreign_market_execution_not_supported" ->
        "当前模拟账套暂不支持该市场成交。"
    "paper_manual_order_market_closed" ->
        "当前市场未开盘，手工模拟订单不会成交。"
    "paper_manual_order_quote_missing" ->
        "缺少可用于成交的最新行情。"
    "paper_manual_order_quote_time_unknown" ->
        "行情时间无法确认，已拒绝模拟成交。"
    "paper_manual_order_quote_outside_session" ->
        "最新行情不属于有效交易时段，已拒绝模拟成交。"
    "paper_manual_order_quote_stale" ->
        "最新行情已经过期，请刷新行情后再提交。"
    "paper_manual_order_insufficient_cash", "insufficient_paper_cash_after_fee" ->
        "模拟账户可用现金不足。"
    "paper_manual_order_no_position" ->
        "当前没有可卖出的模拟持仓。"
    "paper_manual_order_t1_locked", "paper_t1_unsellable_quantity" ->
        "A 股当日买入数量受 T+1 限制，当前不可卖出。"
    "paper_manual_order_exceeds_sellable" ->
        "卖出数量超过服务器确认的当前可卖数量。"
    "paper_manual_order_quantity_violates_lot", "paper_quantity_violates_market_lot" ->
        capability?.lot_size?.let { "下单数量必须按每手 $it 股提交。" }
            ?: "下单数量不符合当前市场每手规则。"
    "paper_instrument_lot_size_required" ->
        "缺少证券每手数量配置，当前不能安全成交。"
    "paper_fee_schedule_unconfigured" ->
        "当前市场模拟费用规则尚未配置。"
    "paper_manual_order_id_conflict" ->
        "订单标识已被另一笔不同订单使用，请重新提交。"
    "paper_manual_order_quantity_invalid" ->
        "请输入有效的正数下单数量。"
    "paper_manual_order_side_invalid" ->
        "仅支持模拟买入或模拟卖出。"
    null -> "模拟订单未成交，请刷新当前可交易状态。"
    else -> "模拟订单未成交：$reasonCode"
}
