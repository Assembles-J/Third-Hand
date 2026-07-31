package com.thirdhand.app

import android.content.Context
import android.util.Log
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okio.Buffer
import retrofit2.Retrofit
import retrofit2.Response
import retrofit2.HttpException
import java.util.concurrent.TimeUnit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

data class HoldingDto(
    val id: String,
    val symbol: String,
    val name: String,
    val quantity: Double,
    val average_cost: Double,
    val created_at: String,
)

data class HoldingInputDto(
    val symbol: String,
    val name: String,
    val quantity: Double,
    val average_cost: Double,
)

data class HoldingDraftDto(
    val id: String,
    val client_row_id: String,
    val name: String,
    val quantity: Double,
    val average_cost: Double,
    val created_at: String,
    // Gson can deserialize explicit JSON null values despite Kotlin defaults.
    val lookup_status: String? = "pending",
    val lookup_message: String = "等待后台查询证券代码",
    val lookup_updated_at: String? = null,
    val candidates: List<SecurityCandidateDto> = emptyList(),
)

data class HoldingDraftInputDto(
    val client_row_id: String? = null,
    val name: String,
    val quantity: Double,
    val average_cost: Double,
)

data class HoldingDraftBatchInputDto(val items: List<HoldingDraftInputDto>)

data class MarketQuoteDto(
    val symbol: String,
    val name: String,
    val price: Double?,
    val change_percent: Double?,
    val change: Double? = null,
    val open: Double? = null,
    val high: Double? = null,
    val low: Double? = null,
    val previous_close: Double? = null,
    val volume: Double? = null,
    val amount: Double? = null,
    val currency: String,
    val source: String,
    val retrieved_at: String,
    val freshness_note: String,
    val as_of: String? = null,
    val is_realtime: Boolean = false,
    val delay_seconds: Int? = null,
    val license_scope: String = "unknown",
    val refresh_status: String = "fresh",
    val error_code: String? = null,
    val error_message: String? = null,
)
data class MarketQuoteBatchRequestDto(val symbols: List<String>, val refresh: Boolean = false)

data class SecurityCandidateDto(
    val symbol: String,
    val name: String,
    val market: String,
    val currency: String,
    val match_type: String,
)

data class SymbolLookupResultDto(
    val query: String,
    val matches: List<SecurityCandidateDto>,
    val lookup_status: String = "not_found",
    val lookup_message: String = "",
)
data class SymbolResolveRequestDto(val names: List<String>)

data class RiskAssessmentDto(
    val symbol: String,
    val name: String,
    val horizon_trading_days: Int,
    val downside_threshold_percent: Double,
    val historical_downside_probability: Double,
    val annualized_volatility_percent: Double,
    val risk_level: String,
    val confidence: String,
    val sample_count: Int,
    val as_of: String,
    val explanation: String,
    val status: String = "ready",
    val message: String = "",
    val disclaimer: String,
)

data class NewsItemDto(
    val id: String,
    val title: String,
    val explanation: String,
    val source_name: String,
    val source_url: String,
    val published_at: String,
    val ai_analysis: Map<String, Any>? = null,
)

data class HealthDto(val status: String)
data class AppUpdateDto(
    val version_code: Int,
    val version_name: String,
    val apk_url: String,
    val changelog: String = "",
    val sha256: String,
    val size_bytes: Long,
)
data class AdminOverviewDto(
    val status: String,
    val generated_at: String,
    val uptime_seconds: Int,
    val holdings_count: Int,
    val draft_count: Int,
    val pending_draft_count: Int,
    val cached_quotes_count: Int,
    val market_history_count: Int = 0,
    val latest_market_at: String? = null,
    val cached_content_count: Int,
    val database_bytes: Int,
    val market_refresh_enabled: Boolean = false,
    val market_refresh_interval_seconds: Int = 60,
    val market_worker_running: Boolean = false,
    val market_last_attempt_at: String? = null,
    val market_last_success_at: String? = null,
    val market_last_error: String? = null,
)
data class SystemConfigDto(val update_check_enabled: Boolean = true)
data class AnalysisTraceStepDto(val stage: String, val status: String, val detail: String)
data class TechnicalSnapshotDto(
    val as_of: String,
    val sample_count: Int,
    val close: Double,
    val trend: String,
    val trend_label: String,
    val summary: String,
    val sma20: Double,
    val sma60: Double,
    val sma20_distance_percent: Double,
    val sma60_distance_percent: Double,
    val rsi14: Double,
    val rsi_state: String,
    val macd_histogram: Double,
    val macd_state: String,
    val atr14: Double,
    val atr_percent: Double,
    val drawdown_60d_percent: Double,
)
data class DecisionEventDto(val id: String, val title: String, val impact: String, val summary: String, val source_url: String? = null, val published_at: String? = null)
data class CalibrationHorizonDto(val sample_count: Int = 0, val average_return_percent: Double? = null, val rule_alignment_rate_percent: Double? = null)
data class HistoricalCalibrationDto(val action: String = "", val definition: String = "", val horizons: Map<String, CalibrationHorizonDto> = emptyMap())
data class DecisionSnapshotDto(
    val event_evidence: List<DecisionEventDto> = emptyList(), val missing_evidence: List<String> = emptyList(),
    val evidence_completeness_percent: Int = 0, val candidate_action: String = "", val confidence_definition: String = "", val historical_calibration: HistoricalCalibrationDto? = null,
)
data class PortfolioAnalysisItemDto(val symbol: String, val name: String, val action: String, val reason: String, val evidence: List<String>, val confidence_percent: Int, val rule_snapshot: Map<String, Any>? = null, val technical_snapshot: TechnicalSnapshotDto? = null, val decision_snapshot: DecisionSnapshotDto? = null, val analysis_trace: List<AnalysisTraceStepDto> = emptyList(), val disclaimer: String)
data class PortfolioAnalysisDto(val id: String, val generated_at: String, val items: List<PortfolioAnalysisItemDto>)
data class ImpactGraphNodeDto(
    val id: String, val kind: String, val label: String, val detail: String,
    val symbol: String? = null, val source_url: String? = null, val published_at: String? = null,
)
data class ImpactGraphEdgeDto(
    val source: String, val target: String, val relation: String, val direction: String, val weight: Double,
)
data class ImpactGraphDto(
    val generated_at: String, val focus_symbol: String? = null, val nodes: List<ImpactGraphNodeDto>,
    val edges: List<ImpactGraphEdgeDto>, val disclaimer: String,
)
data class GlossaryCardDto(val term: String, val plain_explanation: String, val watch_for: String)
data class LearningCaseDto(
    val id: String, val symbol: String?, val title: String, val context: String, val lesson: String,
    val outcome: String, val position_band: String, val planned_action: String, val confidence: Double,
    val evidence_links: List<String>, val created_at: String,
)
data class LearningCaseInputDto(
    val symbol: String? = null, val title: String, val context: String, val lesson: String,
    val outcome: String, val position_band: String, val planned_action: String, val confidence: Double,
    val evidence_links: List<String> = emptyList(),
)
data class LearningCaseAnalysisDto(
    val summary: String,
    val recurring_patterns: List<String> = emptyList(),
    val next_review_focus: List<String> = emptyList(),
    val confidence: String,
    val disclaimer: String,
)
data class ResearchRuleDto(
    val id: String, val category: String, val title: String, val trigger_text: String,
    val guidance: String, val confidence_ceiling: Double, val source_url: String, val version: String,
)
data class PersonalRuleDto(
    val id: String, val scope: String, val symbol: String?, val max_position_percent: Double,
    val loss_review_percent: Double, val volatility_review_percent: Double, val enabled: Boolean,
    val version: Int, val updated_at: String,
)
data class PersonalRuleInputDto(
    val scope: String, val symbol: String? = null, val max_position_percent: Double,
    val loss_review_percent: Double, val volatility_review_percent: Double, val enabled: Boolean = true,
)

interface ThirdHandApi {
    @GET("health")
    suspend fun health(): HealthDto

    @GET("v1/app-update")
    suspend fun appUpdate(): Response<AppUpdateDto>

    @GET("v1/admin/overview")
    suspend fun adminOverview(): AdminOverviewDto

    @GET("v1/admin/config")
    suspend fun adminConfig(): SystemConfigDto

    @PUT("v1/admin/config")
    suspend fun saveAdminConfig(@Body config: SystemConfigDto): SystemConfigDto

    @GET("v1/holdings")
    suspend fun holdings(): List<HoldingDto>

    @POST("v1/holdings")
    suspend fun addHolding(@Body holding: HoldingInputDto): HoldingDto
    @PUT("v1/holdings/{id}")
    suspend fun updateHolding(@Path("id") id: String, @Body holding: HoldingInputDto): HoldingDto

    @DELETE("v1/holdings/{id}")
    suspend fun deleteHolding(@Path("id") id: String)

    @GET("v1/holding-drafts")
    suspend fun holdingDrafts(): List<HoldingDraftDto>

    @POST("v1/holding-drafts")
    suspend fun addHoldingDraft(@Body draft: HoldingDraftInputDto): HoldingDraftDto

    @POST("v1/holding-drafts/batch")
    suspend fun addHoldingDrafts(@Body drafts: HoldingDraftBatchInputDto): List<HoldingDraftDto>

    @POST("v1/holding-drafts/{id}/confirm")
    suspend fun confirmHoldingDraft(@Path("id") id: String, @Body holding: HoldingInputDto): HoldingDto

    @DELETE("v1/holding-drafts/{id}")
    suspend fun deleteHoldingDraft(@Path("id") id: String)

    @POST("v1/market/quotes/batch")
    suspend fun quotes(@Body request: MarketQuoteBatchRequestDto): List<MarketQuoteDto>

    // Compatibility endpoint for servers deployed before batch POST was added.
    @GET("v1/market/quotes")
    suspend fun quotesLegacy(
        @Query("symbols") symbols: List<String>,
        @Query("refresh") refresh: Boolean,
    ): List<MarketQuoteDto>

    @POST("v1/market/symbols/resolve")
    suspend fun symbolLookup(@Body request: SymbolResolveRequestDto): List<SymbolLookupResultDto>

    @GET("v1/risk/assessments")
    suspend fun riskAssessments(): List<RiskAssessmentDto>
    @GET("v1/portfolio/analysis")
    suspend fun portfolioAnalysis(): PortfolioAnalysisDto
    @GET("v1/portfolio/impact-graph")
    suspend fun impactGraph(@Query("symbol") symbol: String? = null): ImpactGraphDto

    @GET("v1/learning-cases")
    suspend fun learningCases(@Query("symbol") symbol: String? = null): List<LearningCaseDto>

    @POST("v1/learning-cases")
    suspend fun createLearningCase(@Body item: LearningCaseInputDto): LearningCaseDto

    @POST("v1/learning-cases/analysis")
    suspend fun learningCaseAnalysis(): LearningCaseAnalysisDto

    @GET("v1/research-rules")
    suspend fun researchRules(): List<ResearchRuleDto>

    @GET("v1/personal-rules")
    suspend fun personalRules(): List<PersonalRuleDto>

    @POST("v1/personal-rules")
    suspend fun savePersonalRule(@Body item: PersonalRuleInputDto): PersonalRuleDto

    @GET("v1/glossary/{term}")
    suspend fun glossary(@Path("term") term: String): GlossaryCardDto

    @GET("v1/feed")
    suspend fun feed(@Query("symbols") symbols: List<String>): List<NewsItemDto>

    @GET("v1/announcements")
    suspend fun announcements(@Query("symbols") symbols: List<String>): List<NewsItemDto>
}

object ApiClient {
    private const val MARKET_LOG_TAG = "ThirdHandMarket"
    private var configuredBaseUrl = ""
    private var configuredService: ThirdHandApi? = null

    private fun requestBodyForLog(request: okhttp3.Request): String = request.body?.let { body ->
        Buffer().use { buffer ->
            body.writeTo(buffer)
            buffer.readUtf8()
        }
    } ?: "<empty>"

    private val marketDebugInterceptor = Interceptor { chain ->
        val request = chain.request()
        val path = request.url.encodedPath
        val shouldLog = path.contains("/v1/market/") ||
            path.contains("/v1/holdings") ||
            path.contains("/v1/holding-drafts")
        if (!BuildConfig.DEBUG || !shouldLog) {
            return@Interceptor chain.proceed(request)
        }
        val startedAt = System.nanoTime()
        Log.d(MARKET_LOG_TAG, "REQUEST ${request.method} ${request.url} body=${requestBodyForLog(request)}")
        try {
            chain.proceed(request).also { response ->
                val elapsedMs = (System.nanoTime() - startedAt) / 1_000_000
                Log.d(
                    MARKET_LOG_TAG,
                    "RESPONSE ${response.code} ${request.method} ${request.url} elapsed_ms=$elapsedMs body=${response.peekBody(1024L * 1024L).string()}",
                )
            }
        } catch (exception: Exception) {
            val elapsedMs = (System.nanoTime() - startedAt) / 1_000_000
            Log.e(MARKET_LOG_TAG, "FAILURE ${request.method} ${request.url} elapsed_ms=$elapsedMs", exception)
            throw exception
        }
    }

    /**
     * Some production servers may still expose only the original GET endpoint.
     * A 405 is an API-version mismatch, so retrying with GET is safe and avoids
     * presenting it to the user as a market-data failure.
     */
    suspend fun marketQuotes(api: ThirdHandApi, request: MarketQuoteBatchRequestDto): List<MarketQuoteDto> = try {
        api.quotes(request)
    } catch (error: HttpException) {
        if (error.code() != 405) throw error
        Log.w(MARKET_LOG_TAG, "BATCH_POST_405_FALLBACK_TO_GET symbols=${request.symbols} refresh=${request.refresh}")
        api.quotesLegacy(request.symbols, request.refresh)
    }

    fun service(context: Context): ThirdHandApi {
        val baseUrl = EndpointStore.baseUrl(context)
        if (configuredService == null || configuredBaseUrl != baseUrl) {
            configuredBaseUrl = baseUrl
            configuredService = Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(
                OkHttpClient.Builder()
                    .addInterceptor(marketDebugInterceptor)
                    // A forced refresh queries public data sources.  Their full-market
                    // snapshots can legitimately take longer than OkHttp's 10s default.
                    .callTimeout(45, TimeUnit.SECONDS)
                    .build(),
            )
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ThirdHandApi::class.java)
        }
        return requireNotNull(configuredService)
    }
}

object EndpointStore {
    private const val PREFS = "third_hand_settings"
    private const val BASE_URL = "base_url"
    private const val DEFAULT_URL = "http://10.0.2.2:8000/"

    fun baseUrl(context: Context): String = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        .getString(BASE_URL, DEFAULT_URL).orEmpty().normalizeBaseUrl()

    fun saveBaseUrl(context: Context, value: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(BASE_URL, value.normalizeBaseUrl()).apply()
    }

    private fun String.normalizeBaseUrl(): String {
        // Cloudflare redirects the production HTTP endpoint to HTTPS.  OkHttp
        // changes redirected POST requests into GET requests, producing 405 on
        // write endpoints.  Keep plain HTTP unchanged for LAN development URLs.
        val httpsUrl = trim().replaceFirst(
            Regex("^http://groupim\\.cn(?=[:/]|$)", RegexOption.IGNORE_CASE),
            "https://groupim.cn",
        )
        return if (httpsUrl.endsWith('/')) httpsUrl else "$httpsUrl/"
    }
}
