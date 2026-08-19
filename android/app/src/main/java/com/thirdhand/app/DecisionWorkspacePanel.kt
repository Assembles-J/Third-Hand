package com.thirdhand.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Path
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale
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
    val paper_risk: DecisionWorkspacePaperRiskDto = DecisionWorkspacePaperRiskDto(),
    val data_quality: DecisionWorkspaceQualityDto = DecisionWorkspaceQualityDto(),
)

private interface DecisionWorkspaceApi {
    @GET("v1/decisions/{symbol}/workspace")
    suspend fun latest(@Path("symbol") symbol: String): DecisionWorkspaceDto
}

private object DecisionWorkspaceClient {
    private var configuredBaseUrl = ""
    private var configuredService: DecisionWorkspaceApi? = null

    fun service(context: android.content.Context): DecisionWorkspaceApi {
        val baseUrl = EndpointStore.baseUrl(context)
        if (configuredService == null || configuredBaseUrl != baseUrl) {
            configuredBaseUrl = baseUrl
            configuredService = Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(OkHttpClient.Builder().callTimeout(45, TimeUnit.SECONDS).build())
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(DecisionWorkspaceApi::class.java)
        }
        return requireNotNull(configuredService)
    }
}

/**
 * Visible projection of persisted formal-decision continuity and paper risk.
 * This component is read-only and never infers a new action from presentation text.
 */
@Composable
fun DecisionWorkspaceSummaryPanel(
    symbol: String,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val api = remember(context) { DecisionWorkspaceClient.service(context) }
    val scope = rememberCoroutineScope()
    var workspace by remember(symbol) { mutableStateOf<DecisionWorkspaceDto?>(null) }
    var loading by remember(symbol) { mutableStateOf(true) }
    var error by remember(symbol) { mutableStateOf<String?>(null) }

    suspend fun load() {
        loading = true
        runCatching { api.latest(symbol) }
            .onSuccess { workspace = it; error = null }
            .onFailure { error = it.message ?: "决策工作区暂不可用" }
        loading = false
    }

    LaunchedEffect(symbol) { load() }

    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("正式决策 · 发生了什么变化", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                    Text("只读 DecisionMemory / Paper Ledger", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                TextButton(onClick = { scope.launch { load() } }, enabled = !loading) {
                    if (loading) CircularProgressIndicator(Modifier.width(15.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Filled.Refresh, contentDescription = "刷新决策变化")
                    Spacer(Modifier.width(4.dp))
                    Text("刷新")
                }
            }

            when {
                loading && workspace == null -> Text("正在读取最新正式决策与连续性记录…", style = MaterialTheme.typography.bodySmall)
                workspace == null && error != null -> Text("工作区暂不可用：$error", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                workspace != null -> DecisionWorkspaceSummaryBody(requireNotNull(workspace))
            }
            error?.takeIf { workspace != null }?.let {
                Text("刷新失败，继续显示上次可用结果：$it", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.error)
            }
        }
    }
}

@Composable
private fun DecisionWorkspaceSummaryBody(workspace: DecisionWorkspaceDto) {
    val change = workspace.what_changed
    val risk = workspace.paper_risk
    val quality = workspace.data_quality

    Text(
        "${workspaceActionLabel(workspace.formal_action)} · ${workspace.summary.ifBlank { "暂无摘要" }}",
        style = MaterialTheme.typography.bodyMedium,
        fontWeight = FontWeight.SemiBold,
    )

    if (change.material_change) {
        val before = workspaceActionLabel(change.prior_action)
        val after = workspaceActionLabel(change.current_action)
        Text(
            "有实质变化：$before → $after",
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.primary,
        )
        if (change.material_change_components.isNotEmpty()) {
            Text(
                "变化来源：${change.material_change_components.joinToString("、") { workspaceChangeComponentLabel(it) }}",
                style = MaterialTheme.typography.labelSmall,
            )
        }
    } else {
        Text(
            "没有足够重要的新变化；DecisionContinuity 继续维持 ${workspaceActionLabel(change.current_action)}。",
            style = MaterialTheme.typography.bodySmall,
        )
    }

    Text(
        "连续性原因：${workspaceContinuityReason(change.material_change_reason)}${change.position_age?.let { " · 持仓 $it 天" }.orEmpty()}",
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    change.review_after?.let {
        Text("下次计划复核：${workspaceTimestamp(it)}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    change.cooldown_until?.let {
        Text("冷却期至：${workspaceTimestamp(it)}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }

    if (risk.position_present) {
        val locked = risk.locked_quantity ?: 0.0
        Text(
            "仓位 ${risk.quantity.workspaceQuantity()} 股 · 可卖 ${risk.sellable_quantity.workspaceQuantity()} · T+1锁定 ${risk.locked_quantity.workspaceQuantity()}",
            style = MaterialTheme.typography.bodySmall,
            fontWeight = if (locked > 0.0) FontWeight.SemiBold else FontWeight.Normal,
        )
        if (locked > 0.0) {
            Text(
                risk.next_eligible_sell_at?.let { "下次可卖/复核：${workspaceTimestamp(it)}" }
                    ?: "存在锁定仓位，但服务没有提供下次可卖时间。",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
    risk.active_deferrals.forEach { deferral ->
        Text(
            "等待执行：${workspaceActionLabel(deferral.action)} · ${workspaceDeferralReason(deferral.reason_code)}${deferral.next_eligible_at?.let { " · ${workspaceTimestamp(it)}" }.orEmpty()}",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.primary,
            fontWeight = FontWeight.SemiBold,
        )
    }

    if (quality.status != null && quality.status != "ready") {
        Text(
            "数据状态 ${quality.status}${quality.score_percent?.let { " · $it%" }.orEmpty()}${quality.missing_fields.takeIf { it.isNotEmpty() }?.let { " · 缺少 ${it.joinToString()}" }.orEmpty()}${quality.stale_fields.takeIf { it.isNotEmpty() }?.let { " · 过期 ${it.joinToString()}" }.orEmpty()}",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.error,
        )
    }
}

private fun workspaceActionLabel(value: String?): String = when (value?.uppercase(Locale.ROOT)) {
    "BUY", "OPEN" -> "买入候选"
    "WAIT", "WATCH" -> "观察"
    "HOLD" -> "持有"
    "ADD" -> "加仓"
    "REDUCE" -> "减仓"
    "EXIT", "SELL" -> "退出"
    "BLOCKED" -> "阻断"
    null, "" -> "未知"
    else -> value
}

private fun workspaceChangeComponentLabel(value: String): String = when (value) {
    "action_gates" -> "硬门禁"
    "position_state" -> "持仓状态"
    "price_state" -> "失效价状态"
    "technical_state" -> "日线技术状态"
    "risk_level" -> "风险等级"
    "market_regime" -> "市场环境"
    "event_state" -> "公司事件"
    "research_veto_state" -> "研究反证"
    "timeframe_policy_state" -> "多周期状态"
    "position_quantity" -> "持仓数量"
    "plan_contract_hash" -> "交易计划"
    else -> value
}

private fun workspaceContinuityReason(value: String): String = when (value) {
    "initial_decision" -> "首次正式决策"
    "hard_gate_changed" -> "硬门禁发生变化"
    "position_state_changed" -> "持仓状态发生变化"
    "material_fingerprint_changed" -> "策略相关状态发生变化"
    "continuity_preserved_prior_action" -> "新输入不足以推翻上一正式动作"
    "no_material_change" -> "没有策略级实质变化"
    "legacy_prior_input_changed" -> "旧版历史记录没有完整指纹，本次按输入变化迁移"
    else -> value.ifBlank { "不可用" }
}

private fun workspaceDeferralReason(value: String?): String = when {
    value.isNullOrBlank() -> "等待重新评估"
    value.contains("paper_t1_unsellable_quantity") -> "A 股 T+1 锁定"
    value.contains("execution_quote") -> "等待合格成交报价"
    value.contains("cooldown") -> "冷却期未结束"
    else -> value
}

private fun workspaceTimestamp(value: String): String = runCatching {
    OffsetDateTime.parse(value)
        .withOffsetSameInstant(ZoneOffset.ofHours(8))
        .format(DateTimeFormatter.ofPattern("MM-dd HH:mm"))
}.getOrElse { value.replace('T', ' ').substringBefore("+").substringBefore("Z") }

private fun Double?.workspaceQuantity(): String = when {
    this == null -> "未提供"
    this % 1.0 == 0.0 -> toLong().toString()
    else -> "%.2f".format(Locale.US, this)
}
