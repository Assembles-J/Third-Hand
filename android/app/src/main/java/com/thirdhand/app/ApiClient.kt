package com.thirdhand.app

import android.content.Context
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
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
    val name: String,
    val quantity: Double,
    val average_cost: Double,
    val created_at: String,
    // Gson can deserialize explicit JSON null values despite Kotlin defaults.
    val lookup_status: String? = "pending",
    val lookup_message: String = "等待后台查询证券代码",
    val lookup_updated_at: String? = null,
)

data class HoldingDraftInputDto(
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
)

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
)

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
data class PortfolioAnalysisItemDto(val symbol: String, val name: String, val action: String, val reason: String, val evidence: List<String>, val disclaimer: String)
data class PortfolioAnalysisDto(val items: List<PortfolioAnalysisItemDto>)

interface ThirdHandApi {
    @GET("health")
    suspend fun health(): HealthDto

    @GET("v1/holdings")
    suspend fun holdings(): List<HoldingDto>

    @POST("v1/holdings")
    suspend fun addHolding(@Body holding: HoldingInputDto): HoldingDto

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

    @GET("v1/market/quotes")
    suspend fun quotes(@Query("symbols") symbols: List<String>): List<MarketQuoteDto>

    @GET("v1/market/symbols")
    suspend fun symbolLookup(@Query("names") names: List<String>): List<SymbolLookupResultDto>

    @GET("v1/risk/assessments")
    suspend fun riskAssessments(): List<RiskAssessmentDto>
    @GET("v1/portfolio/analysis")
    suspend fun portfolioAnalysis(): PortfolioAnalysisDto

    @GET("v1/feed")
    suspend fun feed(@Query("symbols") symbols: List<String>): List<NewsItemDto>

    @GET("v1/announcements")
    suspend fun announcements(@Query("symbols") symbols: List<String>): List<NewsItemDto>
}

object ApiClient {
    private var configuredBaseUrl = ""
    private var configuredService: ThirdHandApi? = null

    fun service(context: Context): ThirdHandApi {
        val baseUrl = EndpointStore.baseUrl(context)
        if (configuredService == null || configuredBaseUrl != baseUrl) {
            configuredBaseUrl = baseUrl
            configuredService = Retrofit.Builder()
            .baseUrl(baseUrl)
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
        .getString(BASE_URL, DEFAULT_URL).orEmpty().ensureTrailingSlash()

    fun saveBaseUrl(context: Context, value: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(BASE_URL, value.trim().ensureTrailingSlash()).apply()
    }

    private fun String.ensureTrailingSlash(): String = if (endsWith('/')) this else "$this/"
}
