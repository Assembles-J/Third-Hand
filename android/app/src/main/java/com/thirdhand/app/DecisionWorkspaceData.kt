package com.thirdhand.app

import android.content.Context
import kotlinx.coroutines.CancellationException
import okhttp3.OkHttpClient
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Path
import java.io.IOException
import java.util.concurrent.TimeUnit

data class DecisionWorkspaceWhatChangedDto(
    val prior_decision_id: String? = null,
    val prior_action: String? = null,
    val current_action: String? = null,
    val input_changed: Boolean = false,
    val material_change: Boolean = false,
    val material_change_reason: String = "unavailable",
    val material_change_components: List<String> = emptyList(),
    val position_age: Int? = null,
    val cooldown_until: String? = null,
    val review_after: String? = null,
    val invalidation_conditions: List<String> = emptyList(),
    val continuity_policy_version: String? = null,
)

data class DecisionWorkspaceFinancialCurrentnessDto(
    val scope: String = "FROZEN_DECISION",
    val policy_version: String? = null,
    val latest_observed_period: String? = null,
    val expected_report_at: String? = null,
    val latest_period_status: String? = null,
    val current_confirmation: String? = null,
    val reason_codes: List<String> = emptyList(),
)

data class DecisionWorkspaceEventEvidenceDto(
    val evidence_id: String? = null,
    val metric: String? = null,
    val scheduled_at: String? = null,
    val source_name: String? = null,
    val source_reference: String? = null,
    val freshness_status: String? = null,
    val polarity: String? = null,
    val confidence: Double? = null,
)

data class DecisionWorkspaceCorporateEventDto(
    val event_id: String? = null,
    val title: String? = null,
    val event_type: String? = null,
    val scheduled_at: String? = null,
    val period: String? = null,
    val lifecycle_status: String? = null,
    val verification_level: String? = null,
    val source: String? = null,
    val source_rank: Int? = null,
    val source_reference: String? = null,
    val conflict_status: String? = null,
    val conflict_dates: List<String> = emptyList(),
    val policy_eligible: Boolean = false,
    val announced_at: String? = null,
    val verified_at: String? = null,
)

data class DecisionWorkspaceCorporateEventsDto(
    val scope: String = "CURRENT_PERSISTED",
    val status: String = "unavailable",
    val retrieved_at: String? = null,
    val official_source_status: String? = null,
    val unavailable_dates: List<String> = emptyList(),
    val active_events: List<DecisionWorkspaceCorporateEventDto> = emptyList(),
    val recent_history: List<DecisionWorkspaceCorporateEventDto> = emptyList(),
    val decision_evidence: List<DecisionWorkspaceEventEvidenceDto> = emptyList(),
)

data class DecisionWorkspaceDeferralDto(
    val decision_id: String? = null,
    val action: String? = null,
    val reason_code: String? = null,
    val next_eligible_at: String? = null,
    val state: String? = null,
)

data class DecisionWorkspacePaperRiskDto(
    val position_present: Boolean = false,
    val quantity: Double? = null,
    val sellable_quantity: Double? = null,
    val locked_quantity: Double? = null,
    val next_eligible_sell_at: String? = null,
    val active_deferrals: List<DecisionWorkspaceDeferralDto> = emptyList(),
)

data class DecisionWorkspaceQualityDto(
    val status: String? = null,
    val score_percent: Int? = null,
    val missing_fields: List<String> = emptyList(),
    val stale_fields: List<String> = emptyList(),
    val warnings: List<String> = emptyList(),
)

data class DecisionWorkspaceDto(
    val symbol: String,
    val name: String = "",
    val decision_id: String = "",
    val generated_at: String? = null,
    val formal_action: String? = null,
    val summary: String = "",
    val strategy: StrategyProfileDto? = null,
    val timeframe_authority: TimeframeAuthorityDto? = null,
    val what_changed: DecisionWorkspaceWhatChangedDto = DecisionWorkspaceWhatChangedDto(),
    val financial_currentness: DecisionWorkspaceFinancialCurrentnessDto? = null,
    val corporate_events: DecisionWorkspaceCorporateEventsDto = DecisionWorkspaceCorporateEventsDto(),
    val paper_risk: DecisionWorkspacePaperRiskDto = DecisionWorkspacePaperRiskDto(),
    val data_quality: DecisionWorkspaceQualityDto = DecisionWorkspaceQualityDto(),
)

sealed interface DecisionWorkspaceLoadResult {
    data class Success(val workspace: DecisionWorkspaceDto) : DecisionWorkspaceLoadResult
    data object Empty : DecisionWorkspaceLoadResult
    data class Failure(
        val message: String,
        val recoverable: Boolean = true,
    ) : DecisionWorkspaceLoadResult
}

interface DecisionWorkspaceRepository {
    suspend fun latest(symbol: String): DecisionWorkspaceLoadResult
}

private interface DecisionWorkspaceApi {
    @GET("v1/decisions/{symbol}/workspace")
    suspend fun latest(@Path("symbol") symbol: String): DecisionWorkspaceDto
}

class NetworkDecisionWorkspaceRepository(
    context: Context,
    private val httpClient: OkHttpClient = OkHttpClient.Builder()
        .callTimeout(45, TimeUnit.SECONDS)
        .build(),
) : DecisionWorkspaceRepository {
    private val appContext = context.applicationContext
    private var configuredBaseUrl = ""
    private var configuredService: DecisionWorkspaceApi? = null

    override suspend fun latest(symbol: String): DecisionWorkspaceLoadResult {
        val normalized = symbol.trim()
        if (normalized.isBlank()) {
            return DecisionWorkspaceLoadResult.Failure("股票代码不可为空", recoverable = false)
        }

        return try {
            DecisionWorkspaceLoadResult.Success(service().latest(normalized))
        } catch (error: CancellationException) {
            throw error
        } catch (error: HttpException) {
            if (error.code() == 404) {
                DecisionWorkspaceLoadResult.Empty
            } else {
                DecisionWorkspaceLoadResult.Failure("决策工作区读取失败（HTTP ${error.code()}）")
            }
        } catch (error: IOException) {
            DecisionWorkspaceLoadResult.Failure(error.message ?: "网络连接失败")
        } catch (error: Exception) {
            DecisionWorkspaceLoadResult.Failure(error.message ?: "决策工作区暂不可用")
        }
    }

    private fun service(): DecisionWorkspaceApi {
        val baseUrl = EndpointStore.baseUrl(appContext)
        if (configuredService == null || configuredBaseUrl != baseUrl) {
            configuredBaseUrl = baseUrl
            configuredService = Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(httpClient)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(DecisionWorkspaceApi::class.java)
        }
        return requireNotNull(configuredService)
    }
}
