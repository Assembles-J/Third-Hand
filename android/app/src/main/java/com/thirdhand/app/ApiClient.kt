package com.thirdhand.app

import android.content.Context
import android.util.Log
import kotlinx.coroutines.delay
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

data class MarketHistoryRefreshInputDto(
    val start_date: String? = null,
    val end_date: String? = null,
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
    val turnover_rate: Double? = null,
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

data class SaleInputDto(val quantity: Double, val sale_price: Double, val reason: String = "")
data class SaleRecordDto(
    val id: String, val holding_id: String, val symbol: String, val name: String, val quantity: Double,
    val sale_price: Double, val average_cost: Double, val proceeds: Double, val cost_basis: Double,
    val realized_pnl: Double, val realized_pnl_percent: Double, val remaining_quantity: Double,
    val reason: String = "", val sold_at: String,
)
data class ResearchTargetDto(
    val symbol: String,
    val name: String,
    val status: String,
    val last_activity_at: String,
)
data class WatchlistInputDto(val symbol: String, val name: String)
data class WatchlistItemDto(
    val symbol: String,
    val name: String,
    val created_at: String,
    val updated_at: String,
)
data class DailyPriceDto(
    val trading_date: String, val open: Double? = null, val close: Double, val high: Double? = null,
    val low: Double? = null, val volume: Double? = null, val amount: Double? = null,
    val amplitude_percent: Double? = null, val change_percent: Double? = null,
    val change_amount: Double? = null, val turnover_rate: Double? = null,
    val adjustment: String? = "qfq", val source: String = "",
)
data class IntradayPriceDto(val bar_time: String, val open: Double, val close: Double, val high: Double, val low: Double, val volume: Double? = null, val amount: Double? = null, val average_price: Double? = null, val source: String, val updated_at: String)
data class InstrumentMetadataDto(val symbol: String, val market: String, val currency: String, val lot_size: Int? = null, val price_tick: String? = null, val source: String, val as_of: String, val updated_at: String)
data class InstrumentMetadataInputDto(val market: String, val currency: String, val lot_size: Int? = null, val price_tick: String? = null, val source: String, val as_of: String)
data class RecommendationRequestDto(val symbols: List<String>)
data class AvailableCashDto(val available_cash: Double, val updated_at: String = "")
data class AvailableCashInputDto(val available_cash: Double)
data class ResearchRecommendationDto(val id: String, val symbol: String, val status: String, val action: String? = null, val price_zone: Map<String, Double>? = null, val invalidation_price: Double? = null, val suggested_quantity: Double? = null, val quantity_status: String? = null, val blocked_reasons: List<String> = emptyList())
data class RecommendationEvaluationDto(val horizon: Int, val evaluation_date: String, val net_pnl: Double, val return_percent: Double, val mfe_percent: Double, val mae_percent: Double)
data class DailyReviewGenerateRequestDto(val symbols: List<String>? = null)
data class DailyReviewExecutionInputDto(val execution_status: String, val executed_quantity: Double, val executed_price: Double? = null, val note: String = "")
data class DailyReviewItemDto(
    val symbol: String, val name: String = "", val action: String, val suggested_quantity: Double? = null,
    val price_zone: Map<String, Double>? = null, val invalidation_price: Double? = null, val rationale: String,
    val reference_price: Double, val execution_status: String = "pending", val executed_quantity: Double? = null,
    val executed_price: Double? = null, val execution_note: String = "", val theoretical_pnl: Double? = null, val actual_pnl: Double? = null,
)
data class DailyReviewDto(
    val id: String, val review_date: String, val generated_at: String, val suggested_position_band: String,
    val market_snapshot: Map<String, Any> = emptyMap(), val items: List<DailyReviewItemDto>, val status: String,
    val evaluated_at: String? = null, val theoretical_pnl: Double? = null, val actual_pnl: Double? = null,
    val highlights: List<String> = emptyList(), val mistakes: List<String> = emptyList(),
)
data class AiJobDto(val id: String, val target_id: String, val status: String, val attempts: Int, val max_attempts: Int, val error_message: String? = null, val updated_at: String)

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
// Gson may deserialize an explicit JSON null despite the Kotlin default value.
data class HistoricalCalibrationDto(val action: String = "", val definition: String = "", val horizons: Map<String, CalibrationHorizonDto>? = emptyMap())
data class MarketIndexRegimeDto(val symbol: String, val name: String, val five_day_return_percent: Double, val trend: String, val above_sma20: Boolean)
data class MarketRegimeDto(val status: String = "unavailable", val regime: String = "unknown", val indexes: List<MarketIndexRegimeDto> = emptyList(), val source: String = "", val note: String = "")
data class RelativeHorizonDto(val stock_return_percent: Double, val benchmark_return_percent: Double, val relative_return_percent: Double)
data class RelativeStrengthDto(val status: String = "not_configured", val benchmark_symbol: String? = null, val benchmark_name: String? = null, val horizons: Map<String, RelativeHorizonDto>? = emptyMap(), val label: String? = null, val note: String = "")
data class DecisionSnapshotDto(
    val event_evidence: List<DecisionEventDto> = emptyList(), val missing_evidence: List<String> = emptyList(),
    val evidence_completeness_percent: Int = 0, val candidate_action: String = "", val confidence_definition: String = "", val historical_calibration: HistoricalCalibrationDto? = null, val market_regime: MarketRegimeDto? = null, val relative_strength: RelativeStrengthDto? = null,
)
data class DecisionDataQualityDto(
    val status: String,
    val score_percent: Int,
    val missing_fields: List<String> = emptyList(),
    val stale_fields: List<String> = emptyList(),
    val warnings: List<String> = emptyList(),
)
data class DecisionContextDto(
    val context_id: String,
    val symbol: String,
    val name: String,
    val generated_at: String,
    val data_quality: DecisionDataQualityDto,
)
data class DecisionGenerateRequestDto(val symbols: List<String>, val force: Boolean = true)
data class DecisionJobStartDto(val symbol: String, val job_id: String, val status: String)
data class DecisionGenerateResponseDto(val jobs: List<DecisionJobStartDto>)
data class DecisionJobDto(val job_id: String, val symbol: String, val status: String, val error_message: String? = null)
data class DecisionEvidenceDto(
    val evidence_id: String, val category: String, val direction: String, val strength: Double,
    val title: String, val description: String, val value: Any? = null, val threshold: Any? = null,
    val source: String, val fresh: Boolean, val rule_id: String? = null,
)
data class DecisionActionCandidateDto(
    val action: String, val priority: Int, val policy_score: Double,
    val supporting_evidence_ids: List<String> = emptyList(), val opposing_evidence_ids: List<String> = emptyList(),
    val triggered_rule_ids: List<String> = emptyList(), val blocked_reasons: List<String> = emptyList(),
)
data class DecisionReasoningStepDto(val stage: String, val summary: String, val evidence_ids: List<String> = emptyList())
data class RuleImprovementSuggestionDto(
    val scope: String, val symbol: String? = null, val max_position_percent: Double? = null,
    val loss_review_percent: Double? = null, val volatility_review_percent: Double? = null,
    val rationale: String, val risk_note: String,
)
data class DecisionAiAssessmentDto(
    val thesis_status: String, val preferred_action: String, val supporting_evidence_ids: List<String> = emptyList(),
    val opposing_evidence_ids: List<String> = emptyList(), val missing_evidence: List<String> = emptyList(),
    val reasoning_steps: List<DecisionReasoningStepDto> = emptyList(), val rule_suggestions: List<RuleImprovementSuggestionDto> = emptyList(), val uncertainty: String, val summary: String,
)
data class PositionSizingResultDto(
    val status: String, val current_quantity: Double, val suggested_quantity: Double? = null, val target_quantity: Double? = null,
    val current_position_percent: Double? = null, val target_position_percent: Double? = null,
    val quantity_by_risk: Double? = null, val quantity_by_cash: Double? = null, val quantity_by_position_cap: Double? = null,
    val quantity_by_liquidity: Double? = null, val lot_size: Int? = null, val entry_price: Double? = null,
    val invalidation_price: Double? = null, val risk_per_share: Double? = null, val risk_capital: Double? = null,
    val blocked_reasons: List<String> = emptyList(), val sizing_version: String,
)
data class OperationItemDto(
    val kind: String, val title: String, val trigger: String, val reference_price: Double? = null,
    val invalidation_price: Double? = null, val suggested_quantity: Double? = null, val target_quantity: Double? = null,
    val status: String, val blockers: List<String>? = emptyList(),
)
data class DecisionReportDto(
    val decision_id: String, val context_id: String, val symbol: String, val generated_at: String, val status: String,
    val action: String, val summary: String, val evidence: List<DecisionEvidenceDto> = emptyList(),
    val action_candidates: List<DecisionActionCandidateDto> = emptyList(), val operation_items: List<OperationItemDto>? = emptyList(), val ai_assessment: DecisionAiAssessmentDto? = null,
    val ai_status: String? = null, val ai_error_code: String? = null, val model: String? = null,
    val market_price: Double? = null, val market_change_percent: Double? = null, val market_as_of: String? = null,
    val sizing: PositionSizingResultDto? = null, val policy_version: String, val prompt_version: String? = null,
    val input_hash: String, val automatic_execution: Boolean = false,
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
data class GlossaryCardDto(
    val term: String,
    val plain_explanation: String,
    val watch_for: String,
    val found: Boolean = true,
    val source: String = "built_in",
)
data class GlossaryLookupInputDto(val term: String, val context: String = "")
data class GlossaryEntryInputDto(val term: String, val plain_explanation: String, val watch_for: String = "")
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
data class TradePlanDto(
    val id: String, val symbol: String, val horizon: String, val thesis: String, val market_expectation: String, val benchmark_symbol: String? = null, val benchmark_name: String? = null,
    val catalysts: List<String>, val entry_condition: String, val add_condition: String, val reduce_condition: String,
    val exit_condition: String, val max_position_percent: Double, val risk_budget_percent: Double,
    val enabled: Boolean, val version: Int, val updated_at: String,
)
data class TradePlanDraftDto(
    val symbol: String, val horizon: String, val thesis: String, val market_expectation: String,
    val catalysts: List<String>, val entry_condition: String, val add_condition: String,
    val reduce_condition: String, val exit_condition: String, val max_position_percent: Double,
    val risk_budget_percent: Double, val notice: String,
)
data class TradePlanInputDto(
    val symbol: String, val horizon: String, val thesis: String, val market_expectation: String, val benchmark_symbol: String? = null, val benchmark_name: String? = null,
    val catalysts: List<String>, val entry_condition: String, val add_condition: String, val reduce_condition: String,
    val exit_condition: String, val max_position_percent: Double, val risk_budget_percent: Double, val enabled: Boolean = true,
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

    @POST("v1/holdings/{id}/sales")
    suspend fun sellHolding(@Path("id") id: String, @Body sale: SaleInputDto): SaleRecordDto

    @GET("v1/sales")
    suspend fun sales(@Query("symbol") symbol: String? = null): List<SaleRecordDto>

    @GET("v1/research/targets")
    suspend fun researchTargets(): List<ResearchTargetDto>

    @GET("v1/watchlist")
    suspend fun watchlist(): List<WatchlistItemDto>

    @POST("v1/watchlist")
    suspend fun saveWatchlistItem(@Body item: WatchlistInputDto): WatchlistItemDto

    @DELETE("v1/watchlist/{symbol}")
    suspend fun deleteWatchlistItem(@Path("symbol") symbol: String)

    @GET("v1/market/history/{symbol}")
    suspend fun marketHistory(@Path("symbol") symbol: String, @Query("limit") limit: Int = 120, @Query("start_date") startDate: String? = null, @Query("end_date") endDate: String? = null): List<DailyPriceDto>
    @POST("v1/market/history/{symbol}/refresh")
    suspend fun refreshMarketHistory(@Path("symbol") symbol: String, @Body input: MarketHistoryRefreshInputDto = MarketHistoryRefreshInputDto()): List<DailyPriceDto>
    @DELETE("v1/market/history/{symbol}")
    suspend fun deleteMarketHistory(@Path("symbol") symbol: String)
    @GET("v1/market/intraday/{symbol}")
    suspend fun marketIntraday(@Path("symbol") symbol: String, @Query("limit") limit: Int = 500): List<IntradayPriceDto>
    @GET("v1/instruments/{symbol}/metadata")
    suspend fun instrumentMetadata(@Path("symbol") symbol: String): InstrumentMetadataDto
    @PUT("v1/instruments/{symbol}/metadata")
    suspend fun saveInstrumentMetadata(@Path("symbol") symbol: String, @Body input: InstrumentMetadataInputDto): InstrumentMetadataDto
    @GET("v1/account/cash")
    suspend fun availableCash(): AvailableCashDto
    @PUT("v1/account/cash")
    suspend fun saveAvailableCash(@Body input: AvailableCashInputDto): AvailableCashDto
    @POST("v1/research-recommendations/generate")
    suspend fun generateRecommendations(@Body request: RecommendationRequestDto): List<ResearchRecommendationDto>
    @GET("v1/research-recommendations")
    suspend fun recommendations(@Query("symbol") symbol: String? = null): List<ResearchRecommendationDto>
    @GET("v1/research-recommendations/{id}/evaluations")
    suspend fun recommendationEvaluations(@Path("id") id: String): List<RecommendationEvaluationDto>
    @POST("v1/daily-reviews/generate")
    suspend fun generateDailyReview(@Body request: DailyReviewGenerateRequestDto = DailyReviewGenerateRequestDto()): DailyReviewDto
    @GET("v1/daily-reviews")
    suspend fun dailyReviews(@Query("limit") limit: Int = 30): List<DailyReviewDto>
    @PUT("v1/daily-reviews/{reviewId}/items/{symbol}/execution")
    suspend fun recordDailyReviewExecution(@Path("reviewId") reviewId: String, @Path("symbol") symbol: String, @Body input: DailyReviewExecutionInputDto): DailyReviewDto
    @POST("v1/daily-reviews/{reviewId}/evaluate")
    suspend fun evaluateDailyReview(@Path("reviewId") reviewId: String): DailyReviewDto
    @GET("v1/ai-jobs")
    suspend fun aiJobs(@Query("target_id") targetId: String? = null): List<AiJobDto>
    @POST("v1/ai-jobs/{id}/retry")
    suspend fun retryAiJob(@Path("id") id: String): AiJobDto

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
    @GET("v1/decisions/context/{symbol}")
    suspend fun decisionContext(@Path("symbol") symbol: String): DecisionContextDto
    @POST("v1/decisions/generate")
    suspend fun generateDecision(@Body request: DecisionGenerateRequestDto): DecisionGenerateResponseDto
    @GET("v1/decisions/jobs/{jobId}")
    suspend fun decisionJob(@Path("jobId") jobId: String): DecisionJobDto
    @GET("v1/decisions/latest")
    suspend fun latestDecision(@Query("symbol") symbol: String): DecisionReportDto
    @GET("v1/decisions")
    suspend fun decisionHistory(@Query("symbol") symbol: String, @Query("limit") limit: Int = 20): List<DecisionReportDto>
    @GET("v1/portfolio/impact-graph")
    suspend fun impactGraph(@Query("symbol") symbol: String? = null): ImpactGraphDto

    @GET("v1/learning-cases")
    suspend fun learningCases(@Query("symbol") symbol: String? = null): List<LearningCaseDto>

    @POST("v1/learning-cases")
    suspend fun createLearningCase(@Body item: LearningCaseInputDto): LearningCaseDto

    @PUT("v1/learning-cases/{id}")
    suspend fun updateLearningCase(@Path("id") id: String, @Body item: LearningCaseInputDto): LearningCaseDto

    @DELETE("v1/learning-cases/{id}")
    suspend fun deleteLearningCase(@Path("id") id: String)

    @POST("v1/learning-cases/analysis")
    suspend fun learningCaseAnalysis(): LearningCaseAnalysisDto

    @GET("v1/research-rules")
    suspend fun researchRules(): List<ResearchRuleDto>

    @GET("v1/personal-rules")
    suspend fun personalRules(): List<PersonalRuleDto>

    @POST("v1/personal-rules")
    suspend fun savePersonalRule(@Body item: PersonalRuleInputDto): PersonalRuleDto

    @GET("v1/trade-plans")
    suspend fun tradePlans(): List<TradePlanDto>
    @GET("v1/trade-plans/draft/{symbol}")
    suspend fun tradePlanDraft(@Path("symbol") symbol: String): TradePlanDraftDto
    @POST("v1/trade-plans")
    suspend fun saveTradePlan(@Body item: TradePlanInputDto): TradePlanDto

    @GET("v1/glossary/{term}")
    suspend fun glossary(@Path("term") term: String): GlossaryCardDto

    @GET("v1/glossary")
    suspend fun glossaryEntries(): List<GlossaryCardDto>

    @POST("v1/glossary/lookup")
    suspend fun lookupGlossary(@Body request: GlossaryLookupInputDto): GlossaryCardDto

    @POST("v1/glossary")
    suspend fun saveGlossary(@Body request: GlossaryEntryInputDto): GlossaryCardDto

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

    /**
     * Ask the server to fetch a new upstream snapshot, then read its cache until
     * that task has actually written a newer result.  This is condition-based:
     * it does not wait for the scheduler's next interval before showing data.
     */
    suspend fun latestMarketQuotes(api: ThirdHandApi, symbols: List<String>): List<MarketQuoteDto> {
        val requested = symbols.distinct().filter { it.isNotBlank() }
        if (requested.isEmpty()) return emptyList()

        val initial = marketQuotes(api, MarketQuoteBatchRequestDto(requested, refresh = true))
        val initialBySymbol = initial.associateBy { it.symbol }
        var latest = initial

        repeat(60) {
            delay(500)
            latest = marketQuotes(api, MarketQuoteBatchRequestDto(requested))
            val latestBySymbol = latest.associateBy { it.symbol }
            val allUpdated = requested.all { symbol ->
                val current = latestBySymbol[symbol]
                val previous = initialBySymbol[symbol]
                current?.price != null && (previous?.price == null || current.retrieved_at != previous.retrieved_at)
            }
            if (allUpdated) return latest
        }
        return latest
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
    private const val DEFAULT_URL = "https://groupim.cn/third-hand/"
//    private const val DEFAULT_URL = "http://10.0.2.2:8000/"

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
