package com.thirdhand.app

import android.content.Context
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import java.util.Locale
import java.util.concurrent.TimeUnit

/** Read-only research context. It never authorizes a formal trade. */
data class CompanyContextDto(
    val symbol: String = "",
    val name: String = "",
    val research_priority: String = "L1",
    val analysis_depth: String = "basic_company",
    val generated_at: String = "",
    val datasets: Map<String, Any?> = emptyMap(),
    val missing_datasets: List<String> = emptyList(),
    val stale_datasets: List<String> = emptyList(),
    val research_ready: Boolean = false,
    val usage_scope: String = "RESEARCH_ONLY",
    val formal_trade_authority: Boolean = false,
)

data class CompanyContextBuildRequestDto(
    val research_priority: String? = null,
    val allow_remote: Boolean = true,
)

private interface CompanyIntelligenceApi {
    @GET("v1/company-intelligence/{symbol}")
    suspend fun latest(@Path("symbol") symbol: String): CompanyContextDto

    @POST("v1/company-intelligence/{symbol}/build")
    suspend fun build(
        @Path("symbol") symbol: String,
        @Body request: CompanyContextBuildRequestDto,
    ): CompanyContextDto
}

private object CompanyIntelligenceClient {
    private var configuredBaseUrl = ""
    private var configuredService: CompanyIntelligenceApi? = null

    fun service(context: Context): CompanyIntelligenceApi {
        val baseUrl = EndpointStore.baseUrl(context)
        if (configuredService == null || configuredBaseUrl != baseUrl) {
            configuredBaseUrl = baseUrl
            configuredService = Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(
                    OkHttpClient.Builder()
                        .callTimeout(45, TimeUnit.SECONDS)
                        .build(),
                )
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(CompanyIntelligenceApi::class.java)
        }
        return requireNotNull(configuredService)
    }
}

@Composable
fun CompanyIntelligencePanel(
    symbol: String,
    researchPriority: String,
    modifier: Modifier = Modifier,
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val api = remember(context) { CompanyIntelligenceClient.service(context) }
    val scope = rememberCoroutineScope()
    var company by remember(symbol) { mutableStateOf<CompanyContextDto?>(null) }
    var loading by remember(symbol) { mutableStateOf(true) }
    var error by remember(symbol) { mutableStateOf<String?>(null) }

    suspend fun load(forceBuild: Boolean) {
        loading = true
        error = null
        val result = runCatching {
            if (forceBuild) {
                api.build(symbol, CompanyContextBuildRequestDto(researchPriority))
            } else {
                val latest = try {
                    api.latest(symbol)
                } catch (http: HttpException) {
                    if (http.code() != 404) throw http
                    null
                }
                if (latest == null || companyPriorityRank(latest.research_priority) < companyPriorityRank(researchPriority)) {
                    api.build(symbol, CompanyContextBuildRequestDto(researchPriority))
                } else {
                    latest
                }
            }
        }
        result.onSuccess { company = it }
            .onFailure { error = "公司深研暂不可用：${it.message ?: "请稍后刷新"}" }
        loading = false
    }

    LaunchedEffect(symbol, researchPriority) { load(forceBuild = false) }

    Card(
        modifier = modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("公司为什么赚钱", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text(
                        "业务分部 · 收入/毛利 · 盈利与现金流驱动 · 行业位置",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                TextButton(onClick = { scope.launch { load(forceBuild = true) } }, enabled = !loading) {
                    if (loading) CircularProgressIndicator(Modifier.width(16.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Filled.Refresh, contentDescription = "刷新公司深研")
                    Spacer(Modifier.width(4.dp))
                    Text("深研")
                }
            }

            Text(
                "RESEARCH_ONLY · ${company?.research_priority ?: researchPriority} · ${companyDepthLabel(company?.analysis_depth)} · 不直接改变买卖规则",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.SemiBold,
            )

            when {
                loading && company == null -> Text("正在读取本地公司研究；缺失部分才会按数据 TTL 补齐。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                error != null && company == null -> Text(requireNotNull(error), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                company != null -> CompanyIntelligenceBody(requireNotNull(company))
            }
            error?.takeIf { company != null }?.let {
                Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.error)
            }
        }
    }
}

@Composable
private fun CompanyIntelligenceBody(company: CompanyContextDto) {
    val datasets = company.datasets
    val identity = datasets.mapValue("identity_business_model")
    val segments = datasets.mapValue("products_segments")
    val margins = datasets.mapValue("margin_structure")
    val drivers = datasets.mapValue("profit_cashflow_drivers")
    val competition = datasets.mapValue("industry_competition")

    identity?.let { CompanyDatasetSection("商业模式", companyBusinessSummary(it)) }

    val segmentRows = segments.listOfMaps("segments")
    if (segmentRows.isNotEmpty()) {
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("业务分部与收入结构", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
            segmentRows.take(5).forEach { row ->
                val name = row.firstText("主营构成", "分类名称", "产品名称", "项目") ?: "业务分部"
                val revenue = row.firstValue("主营收入", "营业收入", "收入")
                val ratio = row.firstValue("收入比例", "收入占比")
                val margin = row.firstValue("毛利率")
                Text(
                    buildString {
                        append("• ").append(name)
                        ratio?.let { append(" · 收入占比 ").append(formatResearchValue(it, percentHint = true)) }
                        revenue?.let { append(" · 收入 ").append(formatResearchValue(it)) }
                        margin?.let { append(" · 毛利率 ").append(formatResearchValue(it, percentHint = true)) }
                    },
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    } else if (segments != null) {
        CompanyDatasetSection("业务分部与收入结构", "已采集分部数据，但当前源没有可直接展示的分部行。")
    }

    margins?.let {
        val rows = it.listOfMaps("segment_margins").ifEmpty { it.listOfMaps("company_margin_history") }
        if (rows.isNotEmpty()) {
            val latest = rows.first()
            CompanyDatasetSection("毛利与盈利结构", researchRowSummary(latest, listOf("毛利率", "gross_margin_percent", "主营利润", "gross_profit", "净利率", "net_margin_percent")))
        }
    }

    drivers?.let {
        val rows = it.listOfMaps("annual_driver_history").ifEmpty { it.listOfMaps("indicator_history") }
        if (rows.isNotEmpty()) {
            CompanyDatasetSection(
                "盈利与现金流驱动",
                researchRowSummary(
                    rows.first(),
                    listOf(
                        "营业收入同比增长率", "净利润同比增长率", "经营现金流量净额", "净资产收益率",
                        "revenue_yoy_percent", "holder_profit_yoy_percent", "operating_cashflow_to_sales_percent", "roe_percent", "roic_percent",
                    ),
                ),
            )
        }
    }

    competition?.let {
        val peers = it.listOfMaps("growth_peer_comparison").ifEmpty { it.listOfMaps("valuation_peer_comparison") }
        if (peers.isNotEmpty()) CompanyDatasetSection("行业与同业", peers.take(3).joinToString("；") { row -> researchRowSummary(row, row.keys.take(4).map { key -> key.toString() }) })
    }

    if (company.missing_datasets.isNotEmpty()) {
        Text(
            "尚未覆盖：${company.missing_datasets.joinToString("、") { companyDatasetLabel(it) }}。缺什么就明确显示什么，不推测补值。",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
    if (company.stale_datasets.isNotEmpty()) {
        Text(
            "待刷新：${company.stale_datasets.joinToString("、") { companyDatasetLabel(it) }}",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun CompanyDatasetSection(title: String, detail: String) {
    if (detail.isBlank()) return
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(title, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
        Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

private fun Map<String, Any?>.mapValue(key: String): Map<String, Any?>? =
    (this[key] as? Map<*, *>)?.entries?.associate { it.key.toString() to it.value }

private fun Map<String, Any?>?.listOfMaps(key: String): List<Map<String, Any?>> {
    val raw = this?.get(key) as? List<*> ?: return emptyList()
    return raw.mapNotNull { item ->
        (item as? Map<*, *>)?.entries?.associate { it.key.toString() to it.value }
    }
}

private fun Map<String, Any?>.firstText(vararg keys: String): String? = keys.firstNotNullOfOrNull { key ->
    this[key]?.toString()?.takeIf { it.isNotBlank() && it != "null" }
}

private fun Map<String, Any?>.firstValue(vararg keys: String): Any? = keys.firstNotNullOfOrNull { key -> this[key] }

private fun companyBusinessSummary(identity: Map<String, Any?>): String {
    val intro = identity.mapValue("business_introduction")
    val profile = identity.mapValue("profile") ?: identity.mapValue("company_profile")
    val business = intro?.firstText("主营业务", "主营产品", "经营范围", "产品类型", "产品名称")
        ?: profile?.firstText("主营业务", "业务", "公司简介", "主营范围")
    return business ?: researchRowSummary(intro ?: profile.orEmpty(), (intro ?: profile.orEmpty()).keys.take(5).toList())
}

private fun researchRowSummary(row: Map<String, Any?>, preferredKeys: List<String>): String {
    val preferred = preferredKeys.distinct().mapNotNull { key ->
        val value = row[key] ?: return@mapNotNull null
        val text = formatResearchValue(value, percentHint = key.contains("率") || key.contains("percent", ignoreCase = true) || key.contains("ratio", ignoreCase = true))
        if (text.isBlank()) null else "${companyFieldLabel(key)} $text"
    }
    if (preferred.isNotEmpty()) return preferred.take(6).joinToString(" · ")
    return row.entries
        .filter { (_, value) -> value != null && value.toString().isNotBlank() }
        .take(5)
        .joinToString(" · ") { (key, value) -> "${companyFieldLabel(key)} ${formatResearchValue(value)}" }
}

private fun formatResearchValue(value: Any?, percentHint: Boolean = false): String {
    if (value == null) return ""
    val number = (value as? Number)?.toDouble() ?: value.toString().replace(",", "").removeSuffix("%").toDoubleOrNull()
    if (number == null) return value.toString()
    if (percentHint) {
        val normalized = if (kotlin.math.abs(number) <= 1.0 && value.toString().contains(".")) number * 100 else number
        return String.format(Locale.US, "%.2f%%", normalized)
    }
    val abs = kotlin.math.abs(number)
    return when {
        abs >= 100_000_000 -> String.format(Locale.US, "%.2f亿", number / 100_000_000.0)
        abs >= 10_000 -> String.format(Locale.US, "%.2f万", number / 10_000.0)
        else -> String.format(Locale.US, "%.2f", number)
    }
}

private fun companyPriorityRank(value: String): Int = when (value.uppercase()) {
    "L4" -> 4
    "L3" -> 3
    "L2" -> 2
    "L1" -> 1
    else -> 0
}

private fun companyDepthLabel(value: String?): String = when (value) {
    "deep_company" -> "深度公司研究"
    "focused_company" -> "重点公司研究"
    else -> "基础公司研究"
}

private fun companyDatasetLabel(value: String): String = when (value) {
    "identity_business_model" -> "商业模式"
    "products_segments" -> "业务分部/收入结构"
    "financial_summary" -> "财务概要"
    "margin_structure" -> "毛利结构"
    "profit_cashflow_drivers" -> "盈利/现金流驱动"
    "industry_competition" -> "行业竞争"
    "management_capital_allocation" -> "管理层/资本配置"
    "risks_catalysts" -> "风险/催化"
    "valuation_framework" -> "估值框架"
    else -> value
}

private fun companyFieldLabel(value: String): String = when (value) {
    "revenue_yoy_percent" -> "收入同比"
    "holder_profit_yoy_percent" -> "归母利润同比"
    "operating_cashflow_to_sales_percent" -> "经营现金流/收入"
    "roe_percent" -> "ROE"
    "roic_percent" -> "ROIC"
    "gross_margin_percent" -> "毛利率"
    "net_margin_percent" -> "净利率"
    "gross_profit" -> "毛利"
    else -> value
}
