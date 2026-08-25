package com.thirdhand.app

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Business
import androidx.compose.material.icons.filled.QueryStats
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.marketColors
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
            .onFailure { error = "数据同步异常" }
        loading = false
    }

    LaunchedEffect(symbol, researchPriority) { load(forceBuild = false) }

    Card(
        modifier = modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = MaterialTheme.shapes.large,
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(Modifier.padding(AppSpacing.large), verticalArrangement = Arrangement.spacedBy(AppSpacing.medium)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Business, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(20.dp))
                    Spacer(Modifier.width(AppSpacing.small))
                    Text("公司研报概览", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.ExtraBold)
                }
                IconButton(onClick = { scope.launch { load(forceBuild = true) } }, enabled = !loading) {
                    if (loading) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Filled.Refresh, null, tint = MaterialTheme.colorScheme.primary)
                }
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(
                    color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.5f),
                    shape = RoundedCornerShape(4.dp)
                ) {
                    Text(
                        company?.research_priority ?: researchPriority,
                        Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSecondaryContainer
                    )
                }
                Spacer(Modifier.width(AppSpacing.small))
                Text(
                    companyDepthLabel(company?.analysis_depth),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            when {
                loading && company == null -> {
                    Column(Modifier.fillMaxWidth().padding(vertical = AppSpacing.large), horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator(Modifier.size(24.dp))
                        Spacer(Modifier.height(AppSpacing.small))
                        Text("深度同步公司资料...", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                error != null && company == null -> {
                    Surface(
                        color = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.2f),
                        shape = MaterialTheme.shapes.small,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(error!!, Modifier.padding(AppSpacing.medium), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                    }
                }
                company != null -> CompanyIntelligenceBody(requireNotNull(company))
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

    identity?.let {
        CompanyInfoSection("商业模式与核心优势", companyBusinessSummary(it))
    }

    val segmentRows = segments.listOfMaps("segments")
    if (segmentRows.isNotEmpty()) {
        Column(Modifier.padding(top = AppSpacing.small)) {
            Text("主营构成", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.height(AppSpacing.small))
            segmentRows.take(3).forEach { row ->
                val name = row.firstText("主营构成", "分类名称", "产品名称") ?: "其他业务"
                val ratio = row.firstValue("收入比例", "收入占比")
                val margin = row.firstValue("毛利率")

                Row(Modifier.fillMaxWidth().padding(vertical = 2.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("• $name", style = MaterialTheme.typography.bodySmall, maxLines = 1, overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                    Text(
                        "${formatResearchValue(ratio, percentHint = true)} / 毛利 ${formatResearchValue(margin, percentHint = true)}",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }

    margins?.let {
        val rows = it.listOfMaps("segment_margins").ifEmpty { it.listOfMaps("company_margin_history") }
        if (rows.isNotEmpty()) {
            CompanyInfoSection("盈利结构", researchRowSummary(rows.first(), listOf("毛利率", "净利率", "主营利润")))
        }
    }

    drivers?.let {
        val rows = it.listOfMaps("annual_driver_history").ifEmpty { it.listOfMaps("indicator_history") }
        if (rows.isNotEmpty()) {
            CompanyInfoSection("增长驱动", researchRowSummary(rows.first(), listOf("收入同比", "归母利润同比", "ROE", "ROIC")))
        }
    }
}

@Composable
private fun CompanyInfoSection(title: String, content: String) {
    if (content.isBlank()) return
    Column(Modifier.padding(top = AppSpacing.small)) {
        Text(title, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.height(2.dp))
        Text(content, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurface)
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
    return intro?.firstText("主营业务", "经营范围") ?: profile?.firstText("主营业务", "业务") ?: "资料正在整理中"
}

private fun researchRowSummary(row: Map<String, Any?>, preferredKeys: List<String>): String {
    val preferred = preferredKeys.distinct().mapNotNull { key ->
        val value = row[key] ?: return@mapNotNull null
        val text = formatResearchValue(value, percentHint = key.contains("率") || key.contains("同比"))
        if (text.isBlank()) null else "$key $text"
    }
    return if (preferred.isNotEmpty()) preferred.joinToString(" · ") else "数据同步中"
}

private fun formatResearchValue(value: Any?, percentHint: Boolean = false): String {
    if (value == null) return "--"
    val number = (value as? Number)?.toDouble() ?: value.toString().replace(",", "").removeSuffix("%").toDoubleOrNull()
    if (number == null) return value.toString()
    if (percentHint) {
        val normalized = if (kotlin.math.abs(number) <= 1.0 && value.toString().contains(".")) number * 100 else number
        return String.format(Locale.US, "%.1f%%", normalized)
    }
    val abs = kotlin.math.abs(number)
    return when {
        abs >= 100_000_000 -> String.format(Locale.US, "%.1f亿", number / 100_000_000.0)
        abs >= 10_000 -> String.format(Locale.US, "%.1f万", number / 10_000.0)
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
    "deep_company" -> "全量深度研报"
    "focused_company" -> "重点核心分析"
    else -> "基础资料同步"
}
