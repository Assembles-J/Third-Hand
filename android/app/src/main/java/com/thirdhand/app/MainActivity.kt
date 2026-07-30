package com.thirdhand.app

import android.os.Bundle
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.background
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.AdminPanelSettings
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AutoGraph
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Wallet
import androidx.compose.material.icons.automirrored.filled.Article
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.OffsetDateTime
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.delay

class MainActivity : ComponentActivity() {
    private var resumeSignal by mutableIntStateOf(0)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { ThirdHandApp(resumeSignal) }
    }

    override fun onResume() {
        super.onResume()
        resumeSignal += 1
    }
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun ThirdHandApp(resumeSignal: Int) {
    val context = LocalContext.current
    var themeMode by remember { mutableStateOf(ThemeStore.load(context)) }
    var tab by remember { mutableIntStateOf(0) }
    var startupUpdate by remember { mutableStateOf<AppUpdate?>(null) }
    var updateMessage by remember { mutableStateOf<String?>(null) }
    val labels = listOf("今日", "持仓", "消息", "我的", "管理")
    val icons = listOf(Icons.Filled.AutoGraph, Icons.Filled.Wallet, Icons.AutoMirrored.Filled.Article, Icons.Filled.AccountCircle, Icons.Filled.AdminPanelSettings)
    LaunchedEffect(resumeSignal) {
        try {
            startupUpdate = AppUpdateManager.check(context)
            updateMessage = AppUpdateManager.completedUpdateMessage(context)
        } catch (_: Exception) {
            // A failed update check must never block the main application.
        }
    }
    ThirdHandTheme(themeMode) {
        Scaffold(
            bottomBar = {
                NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                    labels.forEachIndexed { index, label ->
                        NavigationBarItem(
                            selected = tab == index,
                            onClick = { tab = index },
                            icon = { Icon(icons[index], contentDescription = label) },
                            label = { Text(label) },
                        )
                    }
                }
            },
        ) { padding ->
            Surface(modifier = Modifier.fillMaxSize().padding(padding), color = MaterialTheme.colorScheme.background) {
                when (tab) {
                    0 -> TodayScreen()
                    1 -> HoldingsScreen()
                    2 -> FeedScreen()
                    3 -> ProfileScreen(
                        themeMode = themeMode,
                        onThemeModeChange = { mode -> ThemeStore.save(context, mode); themeMode = mode },
                    )
                    else -> AdminDashboardScreen()
                }
            }
        }
        startupUpdate?.let { update ->
            AlertDialog(
                onDismissRequest = { startupUpdate = null },
                title = { Text("发现新版本 ${update.versionName}") },
                text = {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(update.changelog.ifBlank { "已准备好新版本，建议更新后继续使用。" })
                        updateMessage?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
                    }
                },
                dismissButton = { TextButton(onClick = { startupUpdate = null }) { Text("稍后") } },
                confirmButton = {
                    TextButton(onClick = {
                        when (AppUpdateManager.downloadAndInstall(context, update)) {
                            UpdateLaunchResult.DOWNLOAD_STARTED -> {
                                updateMessage = "正在下载，完成后会自动打开系统安装器"
                            }
                            UpdateLaunchResult.INSTALLER_OPENED -> {
                                updateMessage = "已重新打开系统安装器"
                            }
                            UpdateLaunchResult.NEED_INSTALL_PERMISSION -> {
                                updateMessage = "请允许此应用安装未知来源应用，返回后再次点击"
                            }
                            UpdateLaunchResult.NEED_STORAGE_PERMISSION -> {
                                updateMessage = "请允许保存安装包，返回后再次点击"
                            }
                            UpdateLaunchResult.SIGNATURE_MISMATCH -> {
                                updateMessage = AppUpdateManager.completedUpdateMessage(context)
                            }
                            UpdateLaunchResult.DOWNLOAD_UNAVAILABLE -> {
                                updateMessage = "安装包不可用，请重新检查更新"
                            }
                        }
                    }) {
                        Text(if (AppUpdateManager.hasCompletedDownload(context)) "继续安装" else "下载并安装")
                    }
                },
            )
        }
    }
}

@Composable
private fun AppHero(title: String, eyebrow: String, action: (@Composable () -> Unit)? = null) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(bottomStart = 28.dp, bottomEnd = 28.dp))
            .background(Brush.linearGradient(listOf(Color(0xFFB8321E), Color(0xFFF06A23), Color(0xFFFFA63D))))
            .padding(start = 20.dp, top = 24.dp, end = 16.dp, bottom = 22.dp),
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text(eyebrow, color = Color(0xFFFFE5C6), style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
            Text(title, color = Color.White, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.ExtraBold)
        }
        if (action != null) Box(Modifier.align(Alignment.CenterEnd)) { action() }
    }
}

@Composable
private fun PrimaryAction(
    label: String,
    icon: ImageVector,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) = Button(
    onClick = onClick,
    enabled = enabled,
    modifier = modifier.height(52.dp),
    shape = RoundedCornerShape(16.dp),
    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary),
    elevation = ButtonDefaults.buttonElevation(defaultElevation = 2.dp, pressedElevation = 0.dp),
) {
    Icon(icon, contentDescription = null)
    Spacer(Modifier.width(8.dp))
    Text(label, fontWeight = FontWeight.Bold)
}

@Composable
private fun SecondaryAction(label: String, icon: ImageVector, onClick: () -> Unit, modifier: Modifier = Modifier) =
    FilledTonalButton(
        onClick = onClick,
        modifier = modifier.height(48.dp),
        shape = RoundedCornerShape(14.dp),
        colors = ButtonDefaults.filledTonalButtonColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
    ) {
        Icon(icon, contentDescription = null)
        Spacer(Modifier.width(6.dp))
        Text(label, fontWeight = FontWeight.SemiBold)
    }

@Composable
private fun HeroRefreshAction(onClick: () -> Unit, enabled: Boolean = true) = IconButton(
    onClick = onClick,
    enabled = enabled,
    modifier = Modifier
        .clip(RoundedCornerShape(14.dp))
        .background(Color(0x33FFFFFF)),
) {
    Icon(Icons.Filled.Refresh, contentDescription = "刷新", tint = Color.White)
}

@Composable
private fun StatusCard(message: String, positive: Boolean = false, error: Boolean = false) {
    val colors = when {
        error -> CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)
        positive -> CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer)
        else -> CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)
    }
    Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), colors = colors, shape = RoundedCornerShape(16.dp)) {
        Text(message, Modifier.padding(14.dp), color = if (error) MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.onSurface, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun TodayScreen() {
    val context = LocalContext.current
    val api = ApiClient.service(context)
    var holdings by remember { mutableStateOf<List<HoldingDto>>(emptyList()) }
    var drafts by remember { mutableStateOf<List<HoldingDraftDto>>(emptyList()) }
    var quotes by remember { mutableStateOf<List<MarketQuoteDto>>(emptyList()) }
    var risks by remember { mutableStateOf<List<RiskAssessmentDto>>(emptyList()) }
    var portfolioAnalysis by remember { mutableStateOf<List<PortfolioAnalysisItemDto>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var refreshing by remember { mutableStateOf(false) }
    var refreshMessage by remember { mutableStateOf<String?>(null) }
    var riskLoading by remember { mutableStateOf(false) }
    var riskError by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    fun refreshRiskAssessments() = scope.launch {
        riskLoading = true
        riskError = null
        try {
            risks = api.riskAssessments()
        } catch (exception: Exception) {
            riskError = "风险评估暂时不可用，不影响行情展示。"
        } finally {
            riskLoading = false
        }
    }
    fun refreshPortfolioAnalysis() = scope.launch {
        try { portfolioAnalysis = api.portfolioAnalysis().items } catch (_: Exception) { portfolioAnalysis = emptyList() }
    }
    fun refresh(forceQuotes: Boolean = false) = scope.launch {
        try {
            refreshing = true
            error = null
            refreshMessage = null
            try {
                holdings = api.holdings()
                drafts = api.holdingDrafts()
            } catch (exception: Exception) {
                error = "无法读取持仓：${exception.message ?: "请确认后端正在运行"}"
                return@launch
            }
            if (holdings.isEmpty()) {
                quotes = emptyList()
                risks = emptyList()
                portfolioAnalysis = emptyList()
                refreshMessage = if (drafts.isNotEmpty()) "待补全记录没有证券代码，暂时无法拉取行情。" else "还没有正式持仓可供查询。"
                return@launch
            }
            try {
                val symbols = holdings.map { it.symbol }
                quotes = api.quotes(MarketQuoteBatchRequestDto(symbols, refresh = forceQuotes))
                refreshMessage = when {
                    quotes.any { it.refresh_status == "stale_fallback" } -> "刷新失败，当前显示上次成功获取的行情"
                    forceQuotes -> "行情已主动刷新"
                    else -> "已展示最近一次行情，服务器正在后台更新"
                }
            } catch (exception: Exception) {
                error = "持仓已加载；行情暂时不可用，请稍后刷新。"
            }
            refreshRiskAssessments()
            refreshPortfolioAnalysis()
        } finally {
            refreshing = false
        }
    }
    LaunchedEffect(Unit) { refresh(forceQuotes = true) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(2_000)
            if (drafts.any { it.lookup_status == "pending" || it.lookup_status == "querying" }) refresh()
        }
    }
    LaunchedEffect(holdings.map { it.symbol }) {
        if (holdings.isEmpty()) return@LaunchedEffect
        while (true) {
            delay(60_000)
            try {
                quotes = api.quotes(MarketQuoteBatchRequestDto(holdings.map { it.symbol }))
                refreshMessage = if (quotes.any { it.refresh_status == "stale_fallback" }) {
                    "自动刷新失败，继续显示上次行情"
                } else {
                    "已同步服务器最新行情"
                }
            } catch (_: Exception) {
                refreshMessage = "自动刷新失败，继续显示上次行情"
            }
        }
    }
    LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { AppHero("今日行情", "THIRD-HAND · 让资产向阳生长", action = { HeroRefreshAction({ refresh(forceQuotes = true) }, !refreshing) }) }
        item { Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("把握正在发生的机会", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text("行情来自公开源快照，仅供参考，不构成投资建议。", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        } }
        error?.let { message -> item { StatusCard(message, error = true) } }
        refreshMessage?.let { message -> item { StatusCard(message, positive = true) } }
        if (drafts.isNotEmpty()) item {
            Card(
                modifier = Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
            ) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("有 ${drafts.size} 条待补全持仓", style = MaterialTheme.typography.titleMedium)
                    Text("补充证券代码后，首页会自动显示对应行情。")
                }
            }
        }
        if (holdings.isEmpty() && drafts.isEmpty()) item { StatusCard("先在“持仓”页添加第一只股票，例如小米集团-W（01810）。") }
        if (holdings.isNotEmpty() && quotes.isEmpty()) item { StatusCard("暂未获得任何行情；请检查网络、数据源或证券代码。", error = true) }
        items(quotes) { quote ->
            val holding = holdings.firstOrNull { it.symbol == quote.symbol }
            QuoteCard(if (holding == null) quote else quote.copy(name = holding.name), holding)
        }
        if (holdings.isNotEmpty()) item { Text("持仓风险观察", modifier = Modifier.padding(start = 20.dp, top = 4.dp, end = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        if (riskLoading) item { StatusCard("正在计算历史风险统计…") }
        riskError?.let { message -> item { StatusCard(message, error = true) } }
        items(risks, key = { it.symbol }) { assessment -> RiskAssessmentCard(assessment) }
        if (portfolioAnalysis.isNotEmpty()) item { Text("持仓复核建议", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        items(portfolioAnalysis, key = { it.symbol }) { item -> PortfolioAnalysisCard(item) }
    }
}

private fun beijingTimestamp(value: String?): String {
    if (value.isNullOrBlank()) return "—"
    return runCatching {
        OffsetDateTime.parse(value).withOffsetSameInstant(ZoneOffset.ofHours(8))
            .format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"))
    }.getOrElse {
        runCatching { LocalDate.parse(value).format(DateTimeFormatter.ISO_LOCAL_DATE) }
            .getOrElse { value.replace('T', ' ').substringBefore("+").substringBefore("Z") }
    }
}

private fun marketNumber(value: Double?): String = when {
    value == null -> "--"
    kotlin.math.abs(value) >= 100_000_000 -> String.format("%.2f亿", value / 100_000_000)
    kotlin.math.abs(value) >= 10_000 -> String.format("%.2f万", value / 10_000)
    else -> String.format("%.2f", value)
}

@Composable
private fun QuoteCard(quote: MarketQuoteDto, holding: HoldingDto?) = Card(
    modifier = Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
) {
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {


        val marketTimeText = quote.as_of
            ?.takeIf { it.isNotBlank() }
            ?.let { beijingTimestamp(it) }
            ?: "数据源未提供"


        Text("${quote.name} · ${quote.symbol}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Row(verticalAlignment = Alignment.Bottom) {
            Text(marketNumber(quote.price), modifier = Modifier.weight(1f), style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.ExtraBold)
            Text("${marketNumber(quote.change)}  ${quote.change_percent ?: "--"}%", color = MaterialTheme.colorScheme.tertiary, fontWeight = FontWeight.Bold)
        }
        holding?.let {
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                HoldingMetric("持仓数量", it.quantity.toString(), Modifier.weight(1f))
                HoldingMetric("平均成本", it.average_cost.toString(), Modifier.weight(1f))
            }
            val floating = quote.price?.let { price -> (price - it.average_cost) * it.quantity }
            Text("持仓浮动 ${marketNumber(floating)} ${quote.currency}", color = if ((floating ?: 0.0) >= 0) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.error, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            HoldingMetric("开盘", marketNumber(quote.open), Modifier.weight(1f))
            HoldingMetric("最高", marketNumber(quote.high), Modifier.weight(1f))
            HoldingMetric("最低", marketNumber(quote.low), Modifier.weight(1f))
            HoldingMetric("昨收", marketNumber(quote.previous_close), Modifier.weight(1f))
        }
        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            HoldingMetric("成交量", marketNumber(quote.volume), Modifier.weight(1f))
            HoldingMetric("成交额", marketNumber(quote.amount), Modifier.weight(1f))
        }


        Text(
            "${quote.source}｜行情时间：$marketTimeText",
            style = MaterialTheme.typography.bodySmall,
        )
//         Text(
//             "${quote.source}｜行情日期：${quote.as_of ?: "未知"}｜获取：${beijingTimestamp(quote.retrieved_at)}",
//             style = MaterialTheme.typography.bodySmall,
//         )
        if (quote.freshness_note.isNotBlank()) {
            Text(
                quote.freshness_note,
                style = MaterialTheme.typography.labelSmall,
                color = if (quote.refresh_status == "stale_fallback") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun RiskAssessmentCard(assessment: RiskAssessmentDto) {
    val containerColor = when (assessment.risk_level) {
        "高" -> MaterialTheme.colorScheme.errorContainer
        "中" -> MaterialTheme.colorScheme.secondaryContainer
        else -> MaterialTheme.colorScheme.tertiaryContainer
    }
    Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = containerColor)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("${assessment.name} · 风险${assessment.risk_level}", style = MaterialTheme.typography.titleMedium)
            Text("历史下行概率 ${assessment.historical_downside_probability}% · 年化波动 ${assessment.annualized_volatility_percent}%")
            Text("口径：${assessment.horizon_trading_days} 个交易日累计跌幅 ≥ ${assessment.downside_threshold_percent}%；样本 ${assessment.sample_count} 个，置信度 ${assessment.confidence}。", style = MaterialTheme.typography.bodySmall)
            Text(assessment.explanation, style = MaterialTheme.typography.bodySmall)
            Text(assessment.disclaimer, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun PortfolioAnalysisCard(item: PortfolioAnalysisItemDto) = Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("${item.name} · ${analysisActionLabel(item.action)}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text("证据置信度 ${item.confidence_percent}%", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall)
        Text(item.reason)
        item.technical_snapshot?.let { TechnicalSnapshotSummary(it) }
        item.evidence.forEach { Text("• $it", style = MaterialTheme.typography.bodySmall) }
        Text(item.disclaimer, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun TechnicalSnapshotSummary(snapshot: TechnicalSnapshotDto, detailed: Boolean = false) {
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = .55f))
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("技术指标", modifier = Modifier.weight(1f), style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
            Text("${snapshot.trend_label} · ${snapshot.as_of}", color = technicalTrendColor(snapshot.trend), style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
        }
        Text(snapshot.summary, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TechnicalMetric("MA20", "${marketNumber(snapshot.sma20)}\n${signedPercent(snapshot.sma20_distance_percent)}", Modifier.weight(1f))
            TechnicalMetric("MA60", "${marketNumber(snapshot.sma60)}\n${signedPercent(snapshot.sma60_distance_percent)}", Modifier.weight(1f))
            TechnicalMetric("RSI(14)", "${snapshot.rsi14}\n${snapshot.rsi_state}", Modifier.weight(1f))
        }
        if (detailed) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TechnicalMetric("MACD 柱", "${snapshot.macd_histogram}\n${snapshot.macd_state}", Modifier.weight(1f))
                TechnicalMetric("ATR(14)", "${snapshot.atr14}\n占收盘 ${snapshot.atr_percent}%", Modifier.weight(1f))
                TechnicalMetric("60日回撤", "${snapshot.drawdown_60d_percent}%\n${snapshot.sample_count} 日样本", Modifier.weight(1f))
            }
        }
        Text(
            "均线距离为收盘价相对均线的偏离；指标描述历史价格状态，不代表未来涨跌。",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun TechnicalMetric(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
    }
}

private fun signedPercent(value: Double): String = "${if (value >= 0) "+" else ""}${"%.1f".format(value)}%"

@Composable
private fun technicalTrendColor(trend: String): Color =
    if (trend == "up") MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.error

@Composable
private fun HoldingMetric(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.ExtraBold)
    }
}

@Composable
private fun HoldingCard(holding: HoldingDto, onDelete: () -> Unit) = Card(
    modifier = Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
    shape = RoundedCornerShape(14.dp),
    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
) {
    Column(Modifier.padding(horizontal = 14.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(holding.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.ExtraBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(holding.symbol, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Surface(color = MaterialTheme.colorScheme.tertiaryContainer, shape = RoundedCornerShape(10.dp)) {
                Text("已入库", Modifier.padding(horizontal = 10.dp, vertical = 5.dp), color = MaterialTheme.colorScheme.onTertiaryContainer, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
            }
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            HoldingMetric("持有数量", holding.quantity.toString(), Modifier.weight(1f))
            HoldingMetric("平均成本", holding.average_cost.toString(), Modifier.weight(1f))
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("已记录 · ${beijingTimestamp(holding.created_at)}", modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            TextButton(onClick = onDelete, colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)) { Text("删除") }
        }
    }
}

@Composable
private fun DraftHoldingCard(draft: HoldingDraftDto, onComplete: () -> Unit, onDelete: () -> Unit) = Card(
    modifier = Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
    shape = RoundedCornerShape(14.dp),
    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
    elevation = CardDefaults.cardElevation(defaultElevation = 3.dp),
) {
    val statusText = when (draft.lookup_status.orEmpty()) {
        "pending", "querying" -> "查询中"
        "failed" -> "查询失败"
        "not_found" -> "未找到"
        else -> "待补全"
    }
    Column(Modifier.padding(horizontal = 14.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(1.dp)) {
                Text(draft.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.ExtraBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(draft.lookup_message.orEmpty(), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSecondaryContainer, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            Surface(color = MaterialTheme.colorScheme.surface, shape = RoundedCornerShape(8.dp)) {
                Text(statusText, Modifier.padding(horizontal = 8.dp, vertical = 4.dp), color = MaterialTheme.colorScheme.secondary, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
            }
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.onSecondaryContainer.copy(alpha = 0.15f))
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            HoldingMetric("数量", draft.quantity.toString(), Modifier.weight(1f))
            HoldingMetric("成本", draft.average_cost.toString(), Modifier.weight(1f))
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = onComplete, colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.secondary)) { Icon(Icons.Filled.Search, null); Spacer(Modifier.width(4.dp)); Text("补全代码") }
            Spacer(Modifier.weight(1f))
            TextButton(onClick = onDelete, colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)) { Text("删除") }
        }
    }
}

@Composable
private fun HoldingsScreen() {
    val context = LocalContext.current
    val api = ApiClient.service(context)
    var holdings by remember { mutableStateOf<List<HoldingDto>>(emptyList()) }
    var drafts by remember { mutableStateOf<List<HoldingDraftDto>>(emptyList()) }
    var quotesBySymbol by remember { mutableStateOf<Map<String, MarketQuoteDto>>(emptyMap()) }
    var analysisBySymbol by remember { mutableStateOf<Map<String, PortfolioAnalysisItemDto>>(emptyMap()) }
    var analysisRun by remember { mutableStateOf<PortfolioAnalysisDto?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var quoteError by remember { mutableStateOf<String?>(null) }
    var showAdd by remember { mutableStateOf(false) }
    var editingDraft by remember { mutableStateOf<HoldingDraftDto?>(null) }
    var editingHolding by remember { mutableStateOf<HoldingDto?>(null) }
    var revealedHoldingId by remember { mutableStateOf<String?>(null) }
    var deleteCandidate by remember { mutableStateOf<HoldingDto?>(null) }
    var showMarketStatusDetails by remember { mutableStateOf(false) }
    var showAnalysisDetails by remember { mutableStateOf(false) }
    var scanError by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { imageUris ->
        if (imageUris.isNotEmpty()) scope.launch {
            try {
                scanError = null
                val recognized = imageUris.flatMap { ScreenshotOcr.scan(context, it) }.distinctBy { it.name }
                if (recognized.isEmpty()) scanError = "未能识别出完整持仓行，请使用清晰、完整的持仓列表截图。"
                else {
                    try {
                        api.addHoldingDrafts(HoldingDraftBatchInputDto(recognized.map {
                            HoldingDraftInputDto(it.name, it.quantity, it.averageCost)
                        }))
                        scanError = "已录入 ${recognized.size} 条，后台正在查询证券代码。"
                        drafts = api.holdingDrafts()
                    } catch (exception: Exception) {
                        scanError = "提交识别结果失败：${exception.message ?: "请稍后重试"}"
                    }
                }
            } catch (exception: Exception) {
                scanError = "截图识别失败：${exception.message ?: "请重试"}"
            }
        }
    }
    fun refresh() = scope.launch {
        try {
            holdings = api.holdings()
            drafts = api.holdingDrafts()
            analysisRun = try { api.portfolioAnalysis() } catch (_: Exception) { null }
            analysisBySymbol = analysisRun?.items?.associateBy { it.symbol } ?: emptyMap()
            error = null
            quoteError = null
            quotesBySymbol = if (holdings.isEmpty()) emptyMap() else try {
                api.quotes(MarketQuoteBatchRequestDto(holdings.map { it.symbol }, refresh = true)).associateBy { it.symbol }
            } catch (exception: Exception) {
                quoteError = "现价暂不可用；成本与持仓信息仍可查看。"
                emptyMap()
            }
        }
        catch (exception: Exception) { error = "读取持仓失败：${exception.message ?: "请确认后端正在运行"}" }
    }
    LaunchedEffect(Unit) { refresh() }
    LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item { AppHero("我的持仓", "资产根系 · 记录每一次成长") }
        item {
            Row(Modifier.padding(horizontal = 14.dp).fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                val pricedHoldings = holdings.mapNotNull { holding -> quotesBySymbol[holding.symbol]?.price?.let { price -> holding to price } }
                val totalMarketValue = pricedHoldings.sumOf { (holding, price) -> holding.quantity * price }
                val totalPnl = pricedHoldings.sumOf { (holding, price) -> holding.quantity * (price - holding.average_cost) }
                Column(Modifier.weight(1f)) {
                    Text("${holdings.size} 只持仓 · ${drafts.size} 条待补全", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(
                        if (pricedHoldings.isEmpty()) "等待行情更新" else "市值 ${formatPositionValue(totalMarketValue)} · 浮盈 ${signedPositionValue(totalPnl)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = if (totalPnl >= 0) Color(0xFFD32F2F) else Color(0xFF178A4B),
                    )
                }
                TextButton(onClick = { showAdd = true }) { Icon(Icons.Filled.Add, null); Text("添加") }
                TextButton(onClick = { imagePicker.launch(arrayOf("image/*")) }) { Icon(Icons.Filled.CameraAlt, null); Text("导入") }
            }
        }
        item {
            MarketStatusEntry(
                quotes = quotesBySymbol.values.toList(),
                error = quoteError,
                onClick = { showMarketStatusDetails = true },
            )
        }
        if (analysisBySymbol.isNotEmpty()) item {
            AnalysisEntry(count = analysisBySymbol.size, onClick = { showAnalysisDetails = true })
        }
        error?.let { message -> item { StatusCard(message, error = true) } }
        scanError?.let { message -> item { StatusCard(message, error = true) } }
        if (drafts.isNotEmpty()) item { Text("待补全代码", modifier = Modifier.padding(start = 20.dp, top = 6.dp, end = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        items(drafts, key = { it.id }) { draft ->
            DraftHoldingCard(
                draft = draft,
                onComplete = { editingDraft = draft },
                onDelete = { scope.launch { api.deleteHoldingDraft(draft.id); refresh() } },
            )
        }
        if (holdings.isNotEmpty()) item { HoldingTableHeader() }
        items(holdings, key = { it.id }) { holding ->
            HoldingTableRow(
                holding = holding,
                quote = quotesBySymbol[holding.symbol],
                onEdit = { editingHolding = holding },
                isDeleteRevealed = revealedHoldingId == holding.id,
                onRevealDelete = { revealedHoldingId = holding.id },
                onCloseDelete = { revealedHoldingId = null },
                onDelete = { deleteCandidate = holding },
            )
        }
    }
    if (showAdd) AddHoldingDialog(
        onDismiss = { showAdd = false },
        onSave = { input -> scope.launch { try {
            api.addHolding(input); showAdd = false; refresh()
        } catch (exception: Exception) { error = "保存失败：${exception.message ?: "请稍后重试"}" } } },
    )
    editingDraft?.let { draft -> AddHoldingDialog(
        title = "补全证券代码",
        initial = HoldingInputDto("", draft.name, draft.quantity, draft.average_cost),
        onDismiss = { editingDraft = null },
        onSave = { input -> scope.launch { try {
            api.confirmHoldingDraft(draft.id, input); editingDraft = null; refresh()
        } catch (exception: Exception) { error = "补全代码失败：${exception.message ?: "请稍后重试"}" } } },
    ) }
    editingHolding?.let { holding -> AddHoldingDialog(
        title = "编辑持仓",
        initial = HoldingInputDto(holding.symbol, holding.name, holding.quantity, holding.average_cost),
        onDismiss = { editingHolding = null },
        onSave = { input -> scope.launch { try { api.updateHolding(holding.id, input); editingHolding = null; refresh() } catch (_: Exception) { error = "更新持仓失败，请稍后重试。" } } },
    ) }
    deleteCandidate?.let { holding -> AlertDialog(
        onDismissRequest = { deleteCandidate = null },
        icon = { Icon(Icons.Filled.Delete, null, tint = MaterialTheme.colorScheme.error) },
        title = { Text("删除持仓？") },
        text = { Text("确认删除 ${holding.name}（${holding.symbol}）的持仓记录吗？此操作不可撤销。") },
        confirmButton = {
            Button(
                onClick = { scope.launch { api.deleteHolding(holding.id); deleteCandidate = null; revealedHoldingId = null; refresh() } },
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error),
            ) { Text("删除") }
        },
        dismissButton = { TextButton(onClick = { deleteCandidate = null }) { Text("取消") } },
    ) }
    if (showMarketStatusDetails) AlertDialog(
        onDismissRequest = { showMarketStatusDetails = false },
        title = { Text("行情状态") },
        text = {
            val quote = quotesBySymbol.values.firstOrNull()
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(if (quoteError == null && quote != null) "行情更新正常" else "行情更新异常", fontWeight = FontWeight.Bold)
                quote?.let {
                    Text("来源：${it.source}", style = MaterialTheme.typography.bodySmall)
                    Text("更新时间：${beijingTimestamp(it.retrieved_at)}", style = MaterialTheme.typography.bodySmall)
                    if (it.freshness_note.isNotBlank()) Text("数据说明：${it.freshness_note}", style = MaterialTheme.typography.bodySmall)
                }
                quoteError?.let { Text("摘要：$it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
            }
        },
        confirmButton = { TextButton(onClick = { showMarketStatusDetails = false }) { Text("知道了") } },
    )
    if (showAnalysisDetails) AnalysisDetailDialog(
        analysis = analysisRun,
        fallbackItems = analysisBySymbol.values.toList(),
        onDismiss = { showAnalysisDetails = false },
    )
}

private fun formatPositionValue(value: Double): String = "%.2f".format(value)
private fun signedPositionValue(value: Double): String = if (value >= 0) "+${formatPositionValue(value)}" else formatPositionValue(value)

@Composable
private fun HoldingTableHeader() {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 7.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        PositionHeader("名称 / 市值", Modifier.weight(1.15f), TextAlign.Start)
        PositionHeader("盈亏 / 比例", Modifier.weight(1f), TextAlign.End)
        PositionHeader("持仓 / 可用", Modifier.weight(.78f), TextAlign.End)
        PositionHeader("成本 / 现价", Modifier.weight(1f), TextAlign.End)
    }
    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
}

@Composable
private fun PositionHeader(label: String, modifier: Modifier, alignment: TextAlign) = Text(
    label, modifier = modifier, color = MaterialTheme.colorScheme.onSurfaceVariant,
    style = MaterialTheme.typography.labelSmall, textAlign = alignment,
)

@Composable
private fun HoldingTableRow(
    holding: HoldingDto,
    quote: MarketQuoteDto?,
    onEdit: () -> Unit,
    isDeleteRevealed: Boolean,
    onRevealDelete: () -> Unit,
    onCloseDelete: () -> Unit,
    onDelete: () -> Unit,
) {
    val currentPrice = quote?.price
    val currency = quote?.currency ?: "CNY"
    val marketValue = currentPrice?.let { it * holding.quantity }
    val pnl = currentPrice?.let { (it - holding.average_cost) * holding.quantity }
    val pnlPercent = currentPrice?.let { if (holding.average_cost == 0.0) null else (it - holding.average_cost) / holding.average_cost * 100 }
    val pnlColor = when {
        pnl == null -> MaterialTheme.colorScheme.onSurfaceVariant
        pnl >= 0 -> Color(0xFFD32F2F)
        else -> Color(0xFF178A4B)
    }
    val deleteOffset by animateDpAsState(if (isDeleteRevealed) (-76).dp else 0.dp, label = "holdingDeleteOffset")
    var horizontalDrag by remember(holding.id) { mutableStateOf(0f) }
    Box(Modifier.fillMaxWidth().clipToBounds()) {
        Row(
            Modifier.align(Alignment.CenterEnd).width(76.dp)
                .background(MaterialTheme.colorScheme.error).clickable(onClick = onDelete),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center,
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(Icons.Filled.Delete, "删除 ${holding.name}", tint = MaterialTheme.colorScheme.onError)
                Text("删除", color = MaterialTheme.colorScheme.onError, style = MaterialTheme.typography.labelSmall)
            }
        }
        Row(
            Modifier.fillMaxWidth().offset(x = deleteOffset)
                .background(MaterialTheme.colorScheme.background)
                .pointerInput(holding.id, isDeleteRevealed) {
                    detectHorizontalDragGestures(
                        onDragStart = { horizontalDrag = 0f },
                        onHorizontalDrag = { _, dragAmount -> horizontalDrag += dragAmount },
                        onDragEnd = {
                            if (horizontalDrag < -32f) onRevealDelete()
                            else if (horizontalDrag > 20f) onCloseDelete()
                        },
                    )
                }
                .clickable { if (isDeleteRevealed) onCloseDelete() else onEdit() }
                .padding(horizontal = 8.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1.15f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(holding.name, modifier = Modifier.weight(1f, false), maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodySmall)
                    Text(marketTag(currency), modifier = Modifier.padding(start = 3.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall)
                }
                Text(marketValue?.let { "${formatCurrency(it, currency)} · ${rmbEstimate(it, currency)}" } ?: "市值待更新", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall, maxLines = 1)
            }
            PositionValueCell(
                main = pnl?.let { signedCurrencyValue(it, currency) } ?: "—",
                sub = pnlPercent?.let { percent -> "${if (percent >= 0) "+" else ""}${"%.2f".format(percent)}%" }?.let { percent -> pnl?.let { "$percent · ${rmbEstimate(it, currency)}" } } ?: "待更新",
                color = pnlColor, modifier = Modifier.weight(1f),
            )
            PositionValueCell(
                main = "${holding.quantity.toInt()}", sub = "${holding.quantity.toInt()}",
                color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.weight(.78f),
            )
            PositionValueCell(
                main = formatCurrency(holding.average_cost, currency),
                sub = currentPrice?.let { "现 ${formatCurrency(it, currency)} · ${rmbEstimate(it, currency)}" } ?: "—",
                color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.weight(1f),
            )
            if (!isDeleteRevealed) Icon(Icons.Filled.ChevronRight, "编辑 ${holding.name}", tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.width(12.dp))
        }
    }
    Column(Modifier.fillMaxWidth()) {
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = .65f))
    }
}

@Composable
private fun MarketStatusEntry(quotes: List<MarketQuoteDto>, error: String?, onClick: () -> Unit) {
    val quote = quotes.firstOrNull()
    val status = when {
        error != null -> "更新异常"
        quote == null -> "等待更新"
        else -> "行情正常"
    }
    val color = if (error == null && quote != null) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.error
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 2.dp).clickable(onClick = onClick),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text("行情状态", style = MaterialTheme.typography.labelMedium)
        Spacer(Modifier.width(8.dp))
        Text(status, color = color, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
        Spacer(Modifier.weight(1f))
        Text(quote?.let { "${it.source} · ${beijingTimestamp(it.retrieved_at)}" } ?: "查看详情", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Icon(Icons.Filled.ChevronRight, "查看行情状态", tint = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun AnalysisEntry(count: Int, onClick: () -> Unit) = Row(
    Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 2.dp).clickable(onClick = onClick),
    verticalAlignment = Alignment.CenterVertically,
) {
    Text("组合复核", style = MaterialTheme.typography.labelMedium)
    Spacer(Modifier.width(8.dp))
    Text("$count 条结果", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelSmall)
    Spacer(Modifier.weight(1f))
    Text("查看详情", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall)
    Icon(Icons.Filled.ChevronRight, "查看组合复核", tint = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable
private fun AnalysisDetailDialog(
    analysis: PortfolioAnalysisDto?,
    fallbackItems: List<PortfolioAnalysisItemDto>,
    onDismiss: () -> Unit,
) {
    val items = analysis?.items ?: fallbackItems
    var expandedSymbols by remember { mutableStateOf(items.firstOrNull()?.symbol?.let(::setOf) ?: emptySet()) }
    Dialog(onDismissRequest = onDismiss) {
        Surface(
            modifier = Modifier.fillMaxWidth().heightIn(max = 620.dp),
            shape = RoundedCornerShape(18.dp),
            color = MaterialTheme.colorScheme.surface,
        ) {
            Column(Modifier.padding(vertical = 10.dp)) {
                Row(
                    Modifier.fillMaxWidth().padding(start = 18.dp, end = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text("组合复核详情", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                        Text(
                            analysis?.generated_at?.let { "分析批次 ${analysis.id.take(8)} · ${beijingTimestamp(it)}" } ?: "当前复核结果",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            style = MaterialTheme.typography.labelSmall,
                        )
                    }
                    IconButton(onClick = onDismiss) { Icon(Icons.Filled.Close, "关闭") }
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 18.dp, vertical = 8.dp)) {
                    items(items, key = { it.symbol }) { item ->
                        AnalysisDetailItem(
                            item = item,
                            expanded = item.symbol in expandedSymbols,
                            onToggle = {
                                expandedSymbols = if (item.symbol in expandedSymbols) expandedSymbols - item.symbol else expandedSymbols + item.symbol
                            },
                        )
                    }
                    item {
                        Text(
                            "说明：复核记录展示本次后台所使用的缓存快照、规则和处理状态；它用于核验信息，不构成交易指令或投资建议。",
                            modifier = Modifier.padding(top = 8.dp),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun AnalysisDetailItem(item: PortfolioAnalysisItemDto, expanded: Boolean, onToggle: () -> Unit) {
    Column(Modifier.fillMaxWidth().clickable(onClick = onToggle).padding(vertical = 10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("${item.name} · ${item.symbol}", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium)
                Text(analysisActionLabel(item.action), color = analysisActionColor(item.action), style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
            }
            Text("证据 ${item.confidence_percent}%", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall)
            Icon(if (expanded) Icons.Filled.Close else Icons.Filled.ChevronRight, if (expanded) "收起详情" else "展开详情", tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Text(item.reason, modifier = Modifier.padding(top = 4.dp), style = MaterialTheme.typography.bodySmall, maxLines = if (expanded) Int.MAX_VALUE else 2, overflow = TextOverflow.Ellipsis)
        if (expanded) {
            item.technical_snapshot?.let {
                Text("技术指标快照", modifier = Modifier.padding(top = 10.dp), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
                TechnicalSnapshotSummary(it, detailed = true)
            }
            Text("触发证据", modifier = Modifier.padding(top = 10.dp), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
            if (item.evidence.isEmpty()) Text("本次没有可用的量化证据。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            item.evidence.forEach { Text("• $it", style = MaterialTheme.typography.bodySmall) }
            item.rule_snapshot?.let { rule ->
                Text("命中规则", modifier = Modifier.padding(top = 10.dp), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
                Text(
                    "${if (rule["scope"] == "symbol") "个股规则" else "全局规则"} · v${rule["version"] ?: "—"} · 亏损复核 ${rule["loss_review_percent"] ?: "—"}% · 波动复核 ${rule["volatility_review_percent"] ?: "—"}%",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            Text("后台处理轨迹", modifier = Modifier.padding(top = 10.dp), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
            if (item.analysis_trace.isEmpty()) Text("该分析批次未记录可展示的处理轨迹。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            item.analysis_trace.forEach { step ->
                Row(Modifier.padding(top = 5.dp), verticalAlignment = Alignment.Top) {
                    Text("●", color = analysisTraceColor(step.status), style = MaterialTheme.typography.bodySmall)
                    Column(Modifier.padding(start = 7.dp)) {
                        Text("${step.stage} · ${analysisTraceStatus(step.status)}", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.SemiBold)
                        Text(step.detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            Text(item.disclaimer, modifier = Modifier.padding(top = 8.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        HorizontalDivider(Modifier.padding(top = 10.dp), color = MaterialTheme.colorScheme.outlineVariant)
    }
}

@Composable
private fun analysisActionColor(action: String): Color = when (action) {
    "risk_review" -> MaterialTheme.colorScheme.error
    "wait_for_confirmation" -> MaterialTheme.colorScheme.primary
    else -> MaterialTheme.colorScheme.tertiary
}

private fun analysisTraceStatus(status: String): String = when (status) {
    "ok" -> "已完成"
    "missing" -> "缺少数据"
    "unavailable" -> "暂不可用"
    "default" -> "默认规则"
    else -> "已记录"
}

@Composable
private fun analysisTraceColor(status: String): Color = when (status) {
    "ok" -> MaterialTheme.colorScheme.tertiary
    "missing", "unavailable" -> MaterialTheme.colorScheme.error
    else -> MaterialTheme.colorScheme.primary
}

private fun analysisActionLabel(action: String): String = when (action) {
    "observe" -> "观察"
    "risk_review" -> "风险复核"
    "wait_for_confirmation" -> "等待确认"
    "data_insufficient" -> "数据不足"
    else -> "复核"
}

private fun marketTag(currency: String): String = when (currency) {
    "HKD" -> "港股·HKD"
    "CNY" -> "A股·CNY"
    else -> currency
}

private fun formatCurrency(value: Double, currency: String): String = when (currency) {
    "HKD" -> "HK$${formatPositionValue(value)}"
    "USD" -> "US$${formatPositionValue(value)}"
    else -> "¥${formatPositionValue(value)}"
}

private fun signedCurrencyValue(value: Double, currency: String): String = if (value >= 0) "+${formatCurrency(value, currency)}" else formatCurrency(value, currency)

private fun rmbEstimate(value: Double, currency: String): String = when (currency) {
    "CNY" -> formatCurrency(value, "CNY")
    "HKD" -> "约 ¥${formatPositionValue(value * 0.92)}"
    "USD" -> "约 ¥${formatPositionValue(value * 7.20)}"
    else -> "约 ¥—"
}

@Composable
private fun PositionValueCell(main: String, sub: String, color: Color, modifier: Modifier) = Column(modifier, horizontalAlignment = Alignment.End) {
    Text(main, color = color, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.End, maxLines = 1)
    Text(sub, color = color.copy(alpha = .82f), style = MaterialTheme.typography.labelSmall, textAlign = TextAlign.End, maxLines = 1)
}

@Composable
private fun AddHoldingDialog(
    onDismiss: () -> Unit,
    onSave: (HoldingInputDto) -> Unit,
    title: String = "添加持仓",
    initial: HoldingInputDto? = null,
) {
    val context = LocalContext.current
    val api = ApiClient.service(context)
    val scope = rememberCoroutineScope()
    var symbol by remember { mutableStateOf(initial?.symbol.orEmpty()) }
    var name by remember { mutableStateOf(initial?.name.orEmpty()) }
    var quantity by remember { mutableStateOf(initial?.quantity?.toString().orEmpty()) }
    var cost by remember { mutableStateOf(initial?.average_cost?.toString().orEmpty()) }
    var candidates by remember { mutableStateOf<List<SecurityCandidateDto>>(emptyList()) }
    var lookupMessage by remember { mutableStateOf<String?>(null) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(symbol, { symbol = it }, label = { Text("代码，例如 01810") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(name, { name = it }, label = { Text("名称") }, modifier = Modifier.fillMaxWidth())
            SecondaryAction("按名称查询代码", Icons.Filled.Search, {
                scope.launch {
                    lookupMessage = null
                    candidates = emptyList()
                    try {
                        candidates = api.symbolLookup(SymbolResolveRequestDto(listOf(name))).firstOrNull()?.matches.orEmpty()
                        if (candidates.isEmpty()) lookupMessage = "没有找到候选证券，请检查名称。"
                    } catch (exception: Exception) {
                        lookupMessage = "代码查询失败，请稍后重试。"
                    }
                }
            })
            candidates.forEach { candidate ->
                FilledTonalButton(
                    onClick = { symbol = candidate.symbol; name = candidate.name; candidates = emptyList() },
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                ) { Text("使用 ${candidate.name}（${candidate.symbol} · ${candidate.market}）") }
            }
            lookupMessage?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
            OutlinedTextField(quantity, { quantity = it }, label = { Text("数量") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(cost, { cost = it }, label = { Text("平均成本") }, modifier = Modifier.fillMaxWidth())
        } },
        confirmButton = { Button(onClick = { onSave(HoldingInputDto(symbol, name, quantity.toDoubleOrNull() ?: 0.0, cost.toDoubleOrNull() ?: -1.0)) }, shape = RoundedCornerShape(12.dp)) { Text("保存持仓") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@Composable
private fun FeedScreen() {
    val context = LocalContext.current
    val uriHandler = LocalUriHandler.current
    val api = ApiClient.service(context)
    var feed by remember { mutableStateOf<List<NewsItemDto>>(emptyList()) }
    var announcements by remember { mutableStateOf<List<NewsItemDto>>(emptyList()) }
    var researchRules by remember { mutableStateOf<List<ResearchRuleDto>>(emptyList()) }
    var glossaryCards by remember { mutableStateOf<List<GlossaryCardDto>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var refreshing by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    fun refresh() = scope.launch {
        refreshing = true
        val symbols = try { api.holdings().map { it.symbol } } catch (exception: Exception) {
            error = "无法读取持仓，请稍后重试。"
            refreshing = false
            return@launch
        }
        var announcementError: String? = null
        var feedError: String? = null
        try { announcements = api.announcements(symbols) } catch (exception: Exception) { announcementError = "公告暂时不可用" }
        try { feed = api.feed(symbols) } catch (exception: Exception) { feedError = "新闻暂时不可用" }
        try { researchRules = api.researchRules() } catch (_: Exception) { }
        val loadedGlossary = mutableListOf<GlossaryCardDto>()
        for (term in listOf("回购", "减持", "pe")) {
            try { loadedGlossary += api.glossary(term) } catch (_: Exception) { }
        }
        glossaryCards = loadedGlossary
        error = listOfNotNull(announcementError, feedError).takeIf { it.isNotEmpty() }?.joinToString("；")
        refreshing = false
    }
    LaunchedEffect(Unit) { refresh() }
    LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { AppHero("关联消息", "消息枝叶 · 捕捉与你有关的变化", action = { HeroRefreshAction(onClick = { refresh() }, enabled = !refreshing) }) }
        item { Text("正式公告优先展示；新闻用于补充背景，均请以原文为准。", modifier = Modifier.padding(horizontal = 20.dp), color = MaterialTheme.colorScheme.onSurfaceVariant) }
        error?.let { item { StatusCard(it ?: "消息暂时不可用", error = true) } }
        if (researchRules.isNotEmpty()) item { Text("研究核验框架", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        items(researchRules, key = { it.id }) { rule -> ResearchRuleCard(rule, uriHandler) }
        if (glossaryCards.isNotEmpty()) item { Text("新手词条", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        items(glossaryCards, key = { it.term }) { card -> GlossaryInfoCard(card) }
        if (announcements.isNotEmpty()) item { Text("正式公告", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        items(announcements) { item -> FeedCard(item, uriHandler, "公告") }
        if (feed.isNotEmpty()) item { Text("相关新闻", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        items(feed) { item -> FeedCard(item, uriHandler, "新闻") }
    }
}

@Composable
private fun FeedCard(item: NewsItemDto, uriHandler: androidx.compose.ui.platform.UriHandler, label: String) = Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(label, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelMedium)
        Text(item.title, style = MaterialTheme.typography.titleMedium)
        Text(item.explanation)
        item.ai_analysis?.let { analysis ->
            Text("AI 解读：${analysis["summary"] ?: "已生成，建议结合原文核验。"}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
            Text("影响：${analysis["impact"] ?: "uncertain"}｜置信度：${analysis["confidence"] ?: "low"}", style = MaterialTheme.typography.bodySmall)
            val verifyItems = analysis["verify_items"] as? List<*>
            if (!verifyItems.isNullOrEmpty()) {
                Text("建议核验", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                verifyItems.take(4).forEach { Text("• $it", style = MaterialTheme.typography.bodySmall) }
            }
        }
        Text("${item.source_name}｜${beijingTimestamp(item.published_at)}", style = MaterialTheme.typography.bodySmall)
        TextButton(onClick = { uriHandler.openUri(item.source_url) }, colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.primary)) { Text("查看原文  →", fontWeight = FontWeight.Bold) }
    }
}

@Composable
private fun ResearchRuleCard(rule: ResearchRuleDto, uriHandler: androidx.compose.ui.platform.UriHandler) =
    Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text("${rule.category} · ${rule.title}", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            Text("何时触发：${rule.trigger_text}", style = MaterialTheme.typography.bodySmall)
            Text(rule.guidance, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
            Text("证据完整度上限 ${(rule.confidence_ceiling * 100).toInt()}% · ${rule.version}", style = MaterialTheme.typography.labelSmall)
            if (rule.source_url.startsWith("https://")) {
                TextButton(onClick = { uriHandler.openUri(rule.source_url) }) { Text("查看规则来源") }
            }
        }
    }

@Composable
private fun GlossaryInfoCard(card: GlossaryCardDto) =
    Card(
        Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text(card.term, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            Text(card.plain_explanation, style = MaterialTheme.typography.bodySmall)
            Text("需要留意：${card.watch_for}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSecondaryContainer)
        }
    }

@Composable
private fun ProfileScreen(themeMode: ThemeMode, onThemeModeChange: (ThemeMode) -> Unit) {
    val context = LocalContext.current
    val api = ApiClient.service(context)
    val scope = rememberCoroutineScope()
    var baseUrl by remember { mutableStateOf(EndpointStore.baseUrl(context)) }
    var connectionStatus by remember { mutableStateOf<String?>(null) }
    var availableUpdate by remember { mutableStateOf<AppUpdate?>(null) }
    var updateStatus by remember { mutableStateOf<String?>(null) }
    var checkingUpdate by remember { mutableStateOf(false) }
    var personalRules by remember { mutableStateOf<List<PersonalRuleDto>>(emptyList()) }
    var learningCases by remember { mutableStateOf<List<LearningCaseDto>>(emptyList()) }
    var researchStatus by remember { mutableStateOf<String?>(null) }
    var showRuleDialog by remember { mutableStateOf(false) }
    var showLearningDialog by remember { mutableStateOf(false) }
    fun refreshResearchData() {
        scope.launch {
            try {
                personalRules = api.personalRules()
                learningCases = api.learningCases()
                researchStatus = null
            } catch (_: Exception) {
                researchStatus = "个人研究数据暂时不可用"
            }
        }
    }
    fun checkForUpdate() {
        scope.launch {
            checkingUpdate = true
            updateStatus = AppUpdateManager.completedUpdateMessage(context)
            try {
                availableUpdate = AppUpdateManager.check(context)
                if (availableUpdate == null && updateStatus == null) updateStatus = "已是最新版本"
            } catch (_: Exception) {
                updateStatus = "暂时无法检查更新，请确认服务地址和网络"
            } finally {
                checkingUpdate = false
            }
        }
    }
    LaunchedEffect(Unit) {
        checkForUpdate()
        refreshResearchData()
    }
    availableUpdate?.let { update ->
        AlertDialog(
            onDismissRequest = { availableUpdate = null },
            title = { Text("发现新版本 ${update.versionName}") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(update.changelog.ifBlank { "已准备好新版本，建议更新后继续使用。" })
                    updateStatus?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
                }
            },
            dismissButton = { TextButton(onClick = { availableUpdate = null }) { Text("稍后") } },
            confirmButton = {
                TextButton(onClick = {
                    updateStatus = when (AppUpdateManager.downloadAndInstall(context, update)) {
                        UpdateLaunchResult.DOWNLOAD_STARTED -> "正在下载，完成后会自动打开系统安装器"
                        UpdateLaunchResult.INSTALLER_OPENED -> "已重新打开系统安装器"
                        UpdateLaunchResult.NEED_INSTALL_PERMISSION -> "请允许“安装未知应用”后返回，再次点击"
                        UpdateLaunchResult.NEED_STORAGE_PERMISSION -> "请允许保存安装包后返回，再次点击"
                        UpdateLaunchResult.SIGNATURE_MISMATCH -> AppUpdateManager.completedUpdateMessage(context)
                        UpdateLaunchResult.DOWNLOAD_UNAVAILABLE -> "安装包不可用，请重新检查更新"
                    }
                }) { Text(if (AppUpdateManager.hasCompletedDownload(context)) "继续安装" else "下载并安装") }
            },
        )
    }
    LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { AppHero("我的", "守护资产的每一段生长") }
        item { Text("服务地址（模拟器默认 10.0.2.2；实机填写电脑局域网 IP 或 HTTPS 域名）", modifier = Modifier.padding(horizontal = 20.dp), color = MaterialTheme.colorScheme.onSurfaceVariant) }
        item { OutlinedTextField(baseUrl, { baseUrl = it }, label = { Text("例如 http://192.168.1.10:8000/") }, modifier = Modifier.padding(horizontal = 20.dp).fillMaxWidth()) }
        item { Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            PrimaryAction("保存并测试连接", Icons.Filled.Refresh, {
                EndpointStore.saveBaseUrl(context, baseUrl)
                scope.launch {
                    connectionStatus = try {
                        val status = ApiClient.service(context).health().status
                        if (status == "ok") "连接成功" else "服务返回：$status"
                    } catch (exception: Exception) { "连接失败：${exception.message ?: "请检查网络、地址和后端"}" }
                }
            }, Modifier.fillMaxWidth())
        } }
        connectionStatus?.let { item { StatusCard(it, positive = it == "连接成功", error = it != "连接成功") } }
        item { Text("应用更新", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        item { Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            SecondaryAction(if (checkingUpdate) "正在检查…" else "检查更新", Icons.Filled.Refresh, { checkForUpdate() }, Modifier.fillMaxWidth())
            updateStatus?.let { StatusCard(it, positive = it == "已是最新版本", error = it != "已是最新版本") }
        } }
        item { Text("个人复核规则", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        item {
            Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("规则会参与持仓复核，只控制提醒阈值，不会自动产生交易指令。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                SecondaryAction(
                    if (personalRules.any { it.scope == "global" }) "调整全局规则" else "设置全局规则",
                    Icons.Filled.AutoGraph,
                    { showRuleDialog = true },
                    Modifier.fillMaxWidth(),
                )
            }
        }
        researchStatus?.let { item { StatusCard(it, error = true) } }
        items(personalRules, key = { it.id }) { rule -> PersonalRuleCard(rule) }
        item { Text("复盘记录", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        item {
            Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                SecondaryAction("记录一次复盘", Icons.AutoMirrored.Filled.Article, { showLearningDialog = true }, Modifier.fillMaxWidth())
                if (learningCases.isEmpty()) Text("还没有复盘记录。可把一次判断、核验结果和教训保存下来，供后续 AI 解读参考。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        items(learningCases, key = { it.id }) { item -> LearningCaseCard(item) }
        item { Text("外观", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        items(ThemeMode.entries) { mode ->
            Row(
                modifier = Modifier.padding(horizontal = 20.dp).fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(if (themeMode == mode) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant).clickable { onThemeModeChange(mode) }.padding(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(selected = themeMode == mode, onClick = { onThemeModeChange(mode) })
                Text(mode.label)
            }
        }
        item { Text("当前为本地 MVP。持仓数据存储在后端 SQLite；请在生产部署前补充账号认证与备份。", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
    if (showRuleDialog) {
        PersonalRuleDialog(
            initial = personalRules.firstOrNull { it.scope == "global" },
            onDismiss = { showRuleDialog = false },
            onSave = { input ->
                scope.launch {
                    try {
                        api.savePersonalRule(input)
                        showRuleDialog = false
                        refreshResearchData()
                    } catch (_: Exception) {
                        researchStatus = "保存个人规则失败，请检查输入和服务连接"
                    }
                }
            },
        )
    }
    if (showLearningDialog) {
        LearningCaseDialog(
            onDismiss = { showLearningDialog = false },
            onSave = { input ->
                scope.launch {
                    try {
                        api.createLearningCase(input)
                        showLearningDialog = false
                        refreshResearchData()
                    } catch (_: Exception) {
                        researchStatus = "保存复盘记录失败，请检查输入"
                    }
                }
            },
        )
    }
}

@Composable
private fun PersonalRuleCard(rule: PersonalRuleDto) =
    Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text(
                if (rule.scope == "global") "全局规则 · v${rule.version}" else "${rule.symbol ?: "个股"} · v${rule.version}",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TechnicalMetric("单标的上限", "${rule.max_position_percent}%", Modifier.weight(1f))
                TechnicalMetric("亏损复核", "${rule.loss_review_percent}%", Modifier.weight(1f))
                TechnicalMetric("波动复核", "${rule.volatility_review_percent}%", Modifier.weight(1f))
            }
            Text(
                "${if (rule.enabled) "已启用" else "已停用"} · 更新 ${beijingTimestamp(rule.updated_at)}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }

@Composable
private fun LearningCaseCard(item: LearningCaseDto) =
    Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text(item.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            Text("${item.symbol ?: "组合"} · ${item.position_band} · 置信度 ${(item.confidence * 100).toInt()}%", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
            Text("当时判断：${item.context}", style = MaterialTheme.typography.bodySmall)
            Text("复盘结论：${item.lesson}", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
            Text("结果：${item.outcome}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(beijingTimestamp(item.created_at), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }

@Composable
private fun PersonalRuleDialog(
    initial: PersonalRuleDto?,
    onDismiss: () -> Unit,
    onSave: (PersonalRuleInputDto) -> Unit,
) {
    var maxPosition by remember(initial?.id) { mutableStateOf(initial?.max_position_percent?.toString() ?: "20") }
    var lossReview by remember(initial?.id) { mutableStateOf(initial?.loss_review_percent?.toString() ?: "15") }
    var volatilityReview by remember(initial?.id) { mutableStateOf(initial?.volatility_review_percent?.toString() ?: "50") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("全局复核规则") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(maxPosition, { maxPosition = it }, label = { Text("单一标的仓位上限（%）") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(lossReview, { lossReview = it }, label = { Text("成本下跌复核阈值（%）") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(volatilityReview, { volatilityReview = it }, label = { Text("年化波动复核阈值（%）") }, modifier = Modifier.fillMaxWidth())
            }
        },
        confirmButton = {
            Button(onClick = {
                onSave(PersonalRuleInputDto(
                    scope = "global",
                    max_position_percent = maxPosition.toDoubleOrNull() ?: 20.0,
                    loss_review_percent = lossReview.toDoubleOrNull() ?: 15.0,
                    volatility_review_percent = volatilityReview.toDoubleOrNull() ?: 50.0,
                ))
            }) { Text("保存") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@Composable
private fun LearningCaseDialog(
    onDismiss: () -> Unit,
    onSave: (LearningCaseInputDto) -> Unit,
) {
    var symbol by remember { mutableStateOf("") }
    var title by remember { mutableStateOf("") }
    var context by remember { mutableStateOf("") }
    var lesson by remember { mutableStateOf("") }
    var outcome by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("记录一次复盘") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(symbol, { symbol = it }, label = { Text("证券代码（可不填）") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(title, { title = it }, label = { Text("标题") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(context, { context = it }, label = { Text("当时依据和背景") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
                OutlinedTextField(lesson, { lesson = it }, label = { Text("复盘后得到的教训") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
                OutlinedTextField(outcome, { outcome = it }, label = { Text("后来发生了什么") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
            }
        },
        confirmButton = {
            Button(
                enabled = title.length >= 3 && context.length >= 10 && lesson.length >= 5 && outcome.length >= 2,
                onClick = {
                    onSave(LearningCaseInputDto(
                        symbol = symbol.trim().ifBlank { null },
                        title = title.trim(),
                        context = context.trim(),
                        lesson = lesson.trim(),
                        outcome = outcome.trim(),
                        position_band = "待评估",
                        planned_action = "继续观察并核验原始信息",
                        confidence = 0.5,
                    ))
                },
            ) { Text("保存") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}
