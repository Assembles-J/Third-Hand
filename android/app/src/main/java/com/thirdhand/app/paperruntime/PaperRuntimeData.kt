package com.thirdhand.app.paperruntime

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
import java.util.concurrent.TimeUnit

data class PaperSimulationEpochDto(
    val epoch_id: String,
    val sequence: Int,
    val status: String,
    val started_at: String,
    val ended_at: String? = null,
    val initial_cash: Double = 0.0,
    val end_total_equity: Double? = null,
    val end_cash: Double? = null,
    val end_market_value: Double? = null,
    val restart_request_id: String? = null,
)

data class PaperRuntimeLatestRunDto(
    val run_id: String,
    val trigger: String,
    val started_at: String,
    val finished_at: String? = null,
    val status: String,
    val symbol_count: Int = 0,
    val generated: Int = 0,
    val executed: Int = 0,
    val skipped: Int = 0,
    val message: String = "",
)

data class PaperRuntimeStateDto(
    val epoch: PaperSimulationEpochDto,
    val runtime_status: String,
    val headline: String,
    val mode: String,
    val mode_label: String,
    val auto_execution_enabled: Boolean,
    val running: Boolean,
    val no_trade_reason: String,
    val pending_execution_symbols: List<String> = emptyList(),
    val due_review_symbols: List<String> = emptyList(),
    val pending_execution_count: Int = 0,
    val due_review_count: Int = 0,
    val last_market_refresh_at: String? = null,
    val last_cycle_at: String? = null,
    val last_execution_poll_at: String? = null,
    val last_candidate_scan_at: String? = null,
    val last_research_at: String? = null,
    val last_decision_at: String? = null,
    val seconds_until_review: Int = 0,
    val seconds_until_candidate_scan: Int? = null,
    val seconds_until_company_research: Int? = null,
    val candidate_scan_enabled: Boolean = false,
    val latest_run: PaperRuntimeLatestRunDto? = null,
    val generated_at: String,
)

data class PaperSimulationRestartInputDto(
    val client_restart_id: String,
    val initial_cash: Double,
)

data class PaperSimulationRestartResponseDto(
    val status: String,
    val idempotent_replay: Boolean = false,
    val archived_epoch_id: String? = null,
    val epoch: PaperSimulationEpochDto,
)

private data class PaperRuntimeErrorDetailDto(val reason_code: String? = null)
private data class PaperRuntimeErrorEnvelopeDto(val detail: PaperRuntimeErrorDetailDto? = null)

interface PaperRuntimeApi {
    @GET("v1/paper-trading/runtime-state")
    suspend fun runtimeState(): PaperRuntimeStateDto

    @POST("v1/paper-trading/restart")
    suspend fun restart(@Body input: PaperSimulationRestartInputDto): PaperSimulationRestartResponseDto
}

sealed interface PaperRuntimeLoadResult {
    data class Success(val state: PaperRuntimeStateDto) : PaperRuntimeLoadResult
    data class Failure(val message: String) : PaperRuntimeLoadResult
}

sealed interface PaperRestartResult {
    data class Success(val response: PaperSimulationRestartResponseDto) : PaperRestartResult
    data class Failure(val message: String, val reasonCode: String? = null) : PaperRestartResult
}

interface PaperRuntimeGateway {
    suspend fun runtimeState(): PaperRuntimeLoadResult
    suspend fun restart(input: PaperSimulationRestartInputDto): PaperRestartResult
}

class RetrofitPaperRuntimeRepository(
    private val api: PaperRuntimeApi,
    private val gson: Gson = Gson(),
) : PaperRuntimeGateway {
    override suspend fun runtimeState(): PaperRuntimeLoadResult = runCatching {
        api.runtimeState()
    }.fold(
        onSuccess = { PaperRuntimeLoadResult.Success(it) },
        onFailure = { PaperRuntimeLoadResult.Failure("无法读取模拟系统运行状态，请稍后重试。") },
    )

    override suspend fun restart(input: PaperSimulationRestartInputDto): PaperRestartResult = try {
        PaperRestartResult.Success(api.restart(input))
    } catch (error: HttpException) {
        val parsed = runCatching {
            gson.fromJson(error.response()?.errorBody()?.string(), PaperRuntimeErrorEnvelopeDto::class.java)
        }.getOrNull()
        val reason = parsed?.detail?.reason_code
        PaperRestartResult.Failure(
            message = paperRestartReasonText(reason),
            reasonCode = reason,
        )
    } catch (error: Exception) {
        PaperRestartResult.Failure("重新开始模拟失败，请检查网络后重试。")
    }
}

object PaperRuntimeFeature {
    private var configuredBaseUrl: String = ""
    private var configuredRepository: PaperRuntimeGateway? = null

    fun repository(context: Context): PaperRuntimeGateway {
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
            configuredRepository = RetrofitPaperRuntimeRepository(
                retrofit.create(PaperRuntimeApi::class.java),
            )
        }
        return requireNotNull(configuredRepository)
    }
}

fun paperRestartReasonText(reasonCode: String?): String = when (reasonCode) {
    "paper_restart_initial_cash_must_be_positive" -> "初始资金必须大于 0。"
    "paper_restart_client_id_required" -> "缺少重开请求标识，请重新提交。"
    "paper_restart_runtime_busy" -> "模拟账户正在处理成交或执行轮询，请稍后用同一次请求重试。"
    "paper_restart_request_conflict" -> "同一次重开请求的初始资金发生变化，请刷新后重新发起。"
    "paper_restart_request_already_archived" -> "这次重开请求已经归档，请刷新当前轮次。"
    "paper_simulation_epoch_missing" -> "服务器尚未建立模拟轮次，请更新后端后重试。"
    null -> "重新开始模拟失败，请刷新后重试。"
    else -> "重新开始模拟失败：$reasonCode"
}