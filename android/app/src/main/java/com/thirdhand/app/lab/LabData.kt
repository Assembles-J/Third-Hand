package com.thirdhand.app.lab

import android.content.Context
import com.thirdhand.app.EndpointStore
import kotlinx.coroutines.CancellationException
import okhttp3.OkHttpClient
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query
import java.io.IOException
import java.util.concurrent.TimeUnit

data class LabExperimentItemDto(
    val experiment_id: String,
    val experiment_version: String,
    val experiment_type: String,
    val status: String,
    val strategy_id: String,
    val strategy_version: String,
    val started_at: String,
    val ended_at: String? = null,
    val created_at: String,
    val universe_snapshot_id: String,
    val universe_snapshot_hash: String,
    val universe_policy_version: String,
    val outcome_policy_version: String,
    val benchmark_policy_version: String,
    val sample_quality_policy_version: String,
    val evaluation_policy_version: String,
)

data class LabExperimentListResponseDto(
    val items: List<LabExperimentItemDto> = emptyList(),
    val count: Int = 0,
)

data class LabOutcomeCountsDto(
    val decision_terminal_count: Int = 0,
    val decision_resolved_count: Int = 0,
    val decision_insufficient_count: Int = 0,
    val decision_invalid_count: Int = 0,
    val execution_terminal_count: Int = 0,
    val execution_resolved_count: Int = 0,
    val execution_insufficient_count: Int = 0,
    val execution_invalid_count: Int = 0,
    val episode_terminal_count: Int = 0,
    val episode_resolved_count: Int = 0,
    val episode_insufficient_count: Int = 0,
    val episode_invalid_count: Int = 0,
    val pending_decision_count: Int? = null,
    val pending_count_reason: String? = null,
)

data class LabStrategySummaryDto(
    val available: Boolean = false,
    val evaluation_id: String? = null,
    val computed_at: String? = null,
    val sample_quality: String? = null,
    val resolved_decision_count: Int? = null,
    val completed_trade_count: Int? = null,
    val distinct_symbol_count: Int? = null,
    val reason_codes: List<String> = emptyList(),
)

data class LabBenchmarkSummaryDto(
    val available: Boolean = false,
    val benchmark_evaluation_id: String? = null,
    val benchmark_policy_id: String? = null,
    val benchmark_policy_version: String? = null,
    val benchmark_type: String? = null,
    val computed_at: String? = null,
    val resolved_observation_count: Int? = null,
    val nonresolved_observation_count: Int? = null,
    val reason_codes: List<String> = emptyList(),
)

data class LabSummaryResponseDto(
    val experiment: LabExperimentItemDto,
    val outcome_counts: LabOutcomeCountsDto,
    val strategy: LabStrategySummaryDto,
    val benchmark: LabBenchmarkSummaryDto,
)

data class LabStrategyPerformanceDto(
    val available: Boolean = false,
    val evaluation_id: String? = null,
    val computed_at: String? = null,
    val sample_quality: String? = null,
    val resolved_decision_count: Int? = null,
    val completed_trade_count: Int? = null,
    val distinct_symbol_count: Int? = null,
    val total_return: Double? = null,
    val max_drawdown: Double? = null,
    val turnover: Double? = null,
    val win_rate: Double? = null,
    val average_win: Double? = null,
    val average_loss: Double? = null,
    val payoff_ratio: Double? = null,
    val expectancy: Double? = null,
    val profit_factor: Double? = null,
    val max_consecutive_losses: Int? = null,
    val average_holding_sessions: Double? = null,
    val total_fees: Double? = null,
    val total_slippage: Double? = null,
    val average_episode_net_return: Double? = null,
    val worst_episode_drawdown: Double? = null,
    val reason_codes: List<String> = emptyList(),
)

data class LabBenchmarkPerformanceDto(
    val available: Boolean = false,
    val benchmark_evaluation_id: String? = null,
    val benchmark_policy_id: String? = null,
    val benchmark_policy_version: String? = null,
    val benchmark_type: String? = null,
    val computed_at: String? = null,
    val resolved_observation_count: Int? = null,
    val nonresolved_observation_count: Int? = null,
    val mean_strategy_forward_return: Double? = null,
    val mean_benchmark_forward_return: Double? = null,
    val mean_excess_forward_return: Double? = null,
    val portfolio_benchmark_return: Double? = null,
    val portfolio_excess_return: Double? = null,
    val reason_codes: List<String> = emptyList(),
)

data class LabPerformanceResponseDto(
    val experiment: LabExperimentItemDto,
    val strategy: LabStrategyPerformanceDto,
    val benchmark: LabBenchmarkPerformanceDto,
)

data class LabDecisionBreakdownItemDto(
    val action: String? = null,
    val market_regime: String? = null,
    val horizon_sessions: Int,
    val sample_count: Int = 0,
    val favorable_count: Int = 0,
    val unfavorable_count: Int = 0,
    val mixed_count: Int = 0,
    val neutral_count: Int = 0,
    val not_applicable_count: Int = 0,
    val mean_forward_return: Double? = null,
    val mean_mfe: Double? = null,
    val mean_mae: Double? = null,
)

data class LabExecutionBreakdownItemDto(
    val disposition: String,
    val count: Int = 0,
    val resolved_count: Int = 0,
    val nonresolved_count: Int = 0,
)

data class LabBenchmarkHorizonItemDto(
    val market: String,
    val horizon_sessions: Int,
    val resolved_count: Int = 0,
    val nonresolved_count: Int = 0,
    val mean_strategy_forward_return: Double? = null,
    val mean_benchmark_forward_return: Double? = null,
    val mean_excess_forward_return: Double? = null,
)

data class LabBreakdownResponseDto(
    val experiment: LabExperimentItemDto,
    val action_breakdown: List<LabDecisionBreakdownItemDto> = emptyList(),
    val regime_breakdown: List<LabDecisionBreakdownItemDto> = emptyList(),
    val horizon_breakdown: List<LabDecisionBreakdownItemDto> = emptyList(),
    val execution_attribution: List<LabExecutionBreakdownItemDto> = emptyList(),
    val benchmark_horizon_breakdown: List<LabBenchmarkHorizonItemDto> = emptyList(),
    val reason_codes: List<String> = emptyList(),
)

data class LabDashboardData(
    val experiment: LabExperimentItemDto,
    val summary: LabSummaryResponseDto,
    val performance: LabPerformanceResponseDto,
    val breakdown: LabBreakdownResponseDto,
)

sealed interface LabLoadResult {
    data class Success(val dashboard: LabDashboardData) : LabLoadResult
    data object Empty : LabLoadResult
    data class Failure(val message: String, val recoverable: Boolean = true) : LabLoadResult
}

interface LabRepository {
    suspend fun latestFormalSwingV1(): LabLoadResult
}

private interface LabApi {
    @GET("v1/lab/experiments")
    suspend fun experiments(@Query("limit") limit: Int = 100): LabExperimentListResponseDto

    @GET("v1/lab/experiments/{experimentId}/summary")
    suspend fun summary(
        @Path("experimentId") experimentId: String,
        @Query("version") version: String,
    ): LabSummaryResponseDto

    @GET("v1/lab/experiments/{experimentId}/performance")
    suspend fun performance(
        @Path("experimentId") experimentId: String,
        @Query("version") version: String,
    ): LabPerformanceResponseDto

    @GET("v1/lab/experiments/{experimentId}/breakdown")
    suspend fun breakdown(
        @Path("experimentId") experimentId: String,
        @Query("version") version: String,
    ): LabBreakdownResponseDto
}

class NetworkLabRepository(
    context: Context,
    private val httpClient: OkHttpClient = OkHttpClient.Builder()
        .callTimeout(45, TimeUnit.SECONDS)
        .build(),
) : LabRepository {
    private val appContext = context.applicationContext
    private var configuredBaseUrl = ""
    private var configuredService: LabApi? = null

    override suspend fun latestFormalSwingV1(): LabLoadResult = try {
        val experiments = service().experiments(limit = 100).items
        val selected = experiments.firstOrNull {
            it.strategy_id.equals("SWING_V1", ignoreCase = true) &&
                it.experiment_type.equals("FORMAL_OBSERVATION", ignoreCase = true)
        } ?: experiments.firstOrNull {
            it.strategy_id.equals("SWING_V1", ignoreCase = true)
        } ?: return LabLoadResult.Empty

        val version = selected.experiment_version
        val summary = service().summary(selected.experiment_id, version)
        val performance = service().performance(selected.experiment_id, version)
        val breakdown = service().breakdown(selected.experiment_id, version)
        LabLoadResult.Success(
            LabDashboardData(
                experiment = selected,
                summary = summary,
                performance = performance,
                breakdown = breakdown,
            ),
        )
    } catch (error: CancellationException) {
        throw error
    } catch (error: HttpException) {
        LabLoadResult.Failure("策略实验室读取失败（HTTP ${error.code()}）")
    } catch (error: IOException) {
        LabLoadResult.Failure(error.message ?: "策略实验室网络连接失败")
    } catch (error: Exception) {
        LabLoadResult.Failure(error.message ?: "策略实验室暂不可用")
    }

    private fun service(): LabApi {
        val baseUrl = EndpointStore.baseUrl(appContext)
        if (configuredService == null || configuredBaseUrl != baseUrl) {
            configuredBaseUrl = baseUrl
            configuredService = Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(httpClient)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(LabApi::class.java)
        }
        return requireNotNull(configuredService)
    }
}
