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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.clickable
import androidx.compose.foundation.background
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AutoGraph
import androidx.compose.material.icons.filled.CameraAlt
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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { ThirdHandApp() }
    }
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun ThirdHandApp() {
    val context = LocalContext.current
    var themeMode by remember { mutableStateOf(ThemeStore.load(context)) }
    var tab by remember { mutableIntStateOf(0) }
    val labels = listOf("今日", "持仓", "消息", "我的")
    val icons = listOf(Icons.Filled.AutoGraph, Icons.Filled.Wallet, Icons.AutoMirrored.Filled.Article, Icons.Filled.AccountCircle)
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
                    else -> ProfileScreen(
                        themeMode = themeMode,
                        onThemeModeChange = { mode -> ThemeStore.save(context, mode); themeMode = mode },
                    )
                }
            }
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
    fun refresh() = scope.launch {
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
                refreshMessage = if (drafts.isNotEmpty()) "待补全记录没有证券代码，暂时无法拉取行情。" else "还没有正式持仓可供查询。"
                return@launch
            }
            try {
                val symbols = holdings.map { it.symbol }
                quotes = api.quotes(symbols)
                refreshMessage = "已展示最近一次行情，正在后台更新"
                launch {
                    delay(1200)
                    try {
                        quotes = api.quotes(symbols)
                        refreshMessage = "行情已更新"
                    } catch (_: Exception) { }
                }
            } catch (exception: Exception) {
                error = "持仓已加载；行情暂时不可用，请稍后刷新。"
            }
            refreshRiskAssessments()
        } finally {
            refreshing = false
        }
    }
    LaunchedEffect(Unit) { refresh() }
    LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { AppHero("今日行情", "THIRD-HAND · 让资产向阳生长", action = { HeroRefreshAction({ refresh() }, !refreshing) }) }
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
            val holdingName = holdings.firstOrNull { it.symbol == quote.symbol }?.name
            QuoteCard(if (holdingName == null) quote else quote.copy(name = holdingName))
        }
        if (holdings.isNotEmpty()) item { Text("持仓风险观察", modifier = Modifier.padding(start = 20.dp, top = 4.dp, end = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        if (riskLoading) item { StatusCard("正在计算历史风险统计…") }
        riskError?.let { message -> item { StatusCard(message, error = true) } }
        items(risks, key = { it.symbol }) { assessment -> RiskAssessmentCard(assessment) }
    }
}

@Composable
private fun QuoteCard(quote: MarketQuoteDto) = Card(
    modifier = Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
) {
    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
        Text("${quote.name} · ${quote.symbol}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text("${quote.price ?: "--"} ${quote.currency}", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.ExtraBold)
        Text("涨跌幅：${quote.change_percent ?: "--"}%", color = MaterialTheme.colorScheme.tertiary, fontWeight = FontWeight.Bold)
        Text("${quote.source}｜截至：${quote.as_of ?: quote.retrieved_at}", style = MaterialTheme.typography.bodySmall)
        Text(if (quote.is_realtime) "实时行情" else "非实时快照", style = MaterialTheme.typography.bodySmall)
        Text(quote.freshness_note, style = MaterialTheme.typography.bodySmall)
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
private fun HoldingMetric(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.ExtraBold)
    }
}

@Composable
private fun HoldingCard(holding: HoldingDto, onDelete: () -> Unit) = Card(
    modifier = Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
    shape = RoundedCornerShape(20.dp),
    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
) {
    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(holding.name, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold)
                Text(holding.symbol, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Surface(color = MaterialTheme.colorScheme.tertiaryContainer, shape = RoundedCornerShape(10.dp)) {
                Text("已入库", Modifier.padding(horizontal = 10.dp, vertical = 5.dp), color = MaterialTheme.colorScheme.onTertiaryContainer, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
            }
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            HoldingMetric("持有数量", holding.quantity.toString(), Modifier.weight(1f))
            HoldingMetric("平均成本", holding.average_cost.toString(), Modifier.weight(1f))
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("已记录 · ${holding.created_at}", modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            TextButton(onClick = onDelete, colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)) { Text("删除") }
        }
    }
}

@Composable
private fun DraftHoldingCard(draft: HoldingDraftDto, onComplete: () -> Unit, onDelete: () -> Unit) = Card(
    modifier = Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
    shape = RoundedCornerShape(20.dp),
    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
) {
    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(draft.name, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold)
                Text("尚缺证券代码，暂不参与行情计算", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSecondaryContainer)
            }
            Surface(color = MaterialTheme.colorScheme.surface, shape = RoundedCornerShape(10.dp)) {
                Text("待补全", Modifier.padding(horizontal = 10.dp, vertical = 5.dp), color = MaterialTheme.colorScheme.secondary, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
            }
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.onSecondaryContainer.copy(alpha = 0.15f))
        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            HoldingMetric("识别数量", draft.quantity.toString(), Modifier.weight(1f))
            HoldingMetric("识别成本", draft.average_cost.toString(), Modifier.weight(1f))
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            SecondaryAction("补全代码", Icons.Filled.Search, onComplete, Modifier.weight(1f))
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
    var error by remember { mutableStateOf<String?>(null) }
    var showAdd by remember { mutableStateOf(false) }
    var editingDraft by remember { mutableStateOf<HoldingDraftDto?>(null) }
    var preview by remember { mutableStateOf<List<RecognizedHolding>>(emptyList()) }
    var lookupCandidates by remember { mutableStateOf<Map<String, List<SecurityCandidateDto>>>(emptyMap()) }
    var lookupLoading by remember { mutableStateOf(false) }
    var scanError by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { imageUris ->
        if (imageUris.isNotEmpty()) scope.launch {
            try {
                scanError = null
                preview = imageUris.flatMap { ScreenshotOcr.scan(context, it) }.distinctBy { it.name }
                if (preview.isEmpty()) scanError = "未能识别出完整持仓行，请使用清晰、完整的持仓列表截图。"
                else {
                    lookupCandidates = emptyMap()
                    lookupLoading = true
                    try {
                        val watchlistSymbols = imageUris.fold(emptyMap<String, String>()) { all, uri -> all + ScreenshotOcr.scanWatchlistSymbols(context, uri) }
                        val serverMatches = api.symbolLookup(preview.map { it.name }).associate { it.query to it.matches }
                        lookupCandidates = preview.associate { item ->
                            val watchlistCode = watchlistSymbols[item.name]
                            item.name to (watchlistCode?.let { listOf(SecurityCandidateDto(it, item.name, "自选截图", if (it.length == 5) "HKD" else "CNY", "ocr")) } ?: serverMatches[item.name].orEmpty())
                        }
                    } catch (exception: Exception) {
                        scanError = "截图已识别，但证券代码反查暂时不可用；你仍可手动添加。"
                    } finally {
                        lookupLoading = false
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
            error = null
        }
        catch (exception: Exception) { error = "读取持仓失败：${exception.message ?: "请确认后端正在运行"}" }
    }
    LaunchedEffect(Unit) { refresh() }
    LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { AppHero("我的持仓", "资产根系 · 记录每一次成长") }
        item { Text("识别结果可先保存，稍后补充证券代码再确认入库。", modifier = Modifier.padding(horizontal = 20.dp), color = MaterialTheme.colorScheme.onSurfaceVariant) }
        item {
            Card(
                modifier = Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
            ) {
                Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                    Column { Text("已入库", style = MaterialTheme.typography.labelLarge); Text("${holdings.size} 条", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.ExtraBold) }
                    Column { Text("待补全", style = MaterialTheme.typography.labelLarge); Text("${drafts.size} 条", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.ExtraBold) }
                }
            }
        }
        item {
            Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                PrimaryAction("手动添加持仓", Icons.Filled.Add, { showAdd = true }, Modifier.fillMaxWidth())
                SecondaryAction("导入持仓+自选截图", Icons.Filled.CameraAlt, { imagePicker.launch(arrayOf("image/*")) }, Modifier.fillMaxWidth())
            }
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
        if (holdings.isNotEmpty()) item { Text("已入库持仓", modifier = Modifier.padding(start = 20.dp, top = 6.dp, end = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        items(holdings, key = { it.id }) { holding ->
            HoldingCard(holding = holding, onDelete = { scope.launch { api.deleteHolding(holding.id); refresh() } })
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
    if (preview.isNotEmpty()) ScreenshotPreviewDialog(
        items = preview,
        candidatesByName = lookupCandidates,
        lookupLoading = lookupLoading,
        onDismiss = { preview = emptyList(); lookupCandidates = emptyMap(); lookupLoading = false },
        onSaveAll = { matches, unmatched -> scope.launch { try {
            matches.forEach { (recognized, candidate) ->
                api.addHolding(HoldingInputDto(candidate.symbol, candidate.name, recognized.quantity, recognized.averageCost))
            }
            if (unmatched.isNotEmpty()) api.addHoldingDrafts(HoldingDraftBatchInputDto(unmatched.map {
                HoldingDraftInputDto(it.name, it.quantity, it.averageCost)
            }))
            preview = emptyList()
            lookupCandidates = emptyMap()
            refresh()
        } catch (exception: Exception) { scanError = "保存识别结果失败：${exception.message ?: "请稍后重试"}" } } },
    )
}

@Composable
private fun ScreenshotPreviewDialog(
    items: List<RecognizedHolding>,
    candidatesByName: Map<String, List<SecurityCandidateDto>>,
    lookupLoading: Boolean,
    onDismiss: () -> Unit,
    onSaveAll: (List<Pair<RecognizedHolding, SecurityCandidateDto>>, List<RecognizedHolding>) -> Unit,
) {
    val exactMatches = items.mapNotNull { item ->
        candidatesByName[item.name].orEmpty().firstOrNull { it.match_type == "exact" }?.let { item to it }
    }
    val unmatched = items.filter { item -> exactMatches.none { it.first == item } }
    AlertDialog(
    onDismissRequest = onDismiss,
    title = { Text("识别结果", fontWeight = FontWeight.ExtraBold) },
    text = {
        Column(
            modifier = Modifier.heightIn(max = 440.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
        Text("已自动采用精确匹配；其余记录会保存为待补全，稍后可在持仓页补代码。", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text("${exactMatches.size} 条可直接入库 · ${unmatched.size} 条待补全", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
        items.forEach { item ->
            val candidate = exactMatches.firstOrNull { it.first == item }?.second
            Card(colors = CardDefaults.cardColors(containerColor = if (candidate == null) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.tertiaryContainer), shape = RoundedCornerShape(14.dp)) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(item.name, fontWeight = FontWeight.Bold)
                    Text("${item.quantity} 股/份 · 成本 ${item.averageCost}", style = MaterialTheme.typography.bodySmall)
                    Text(
                        when {
                            candidate != null -> "已匹配：${candidate.name}（${candidate.symbol}）"
                            lookupLoading -> "正在查询证券代码…"
                            else -> "未找到精确匹配，将作为待补全保存"
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = if (candidate == null) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.tertiary,
                    )
                }
            }
        }
    } },
    confirmButton = { Button(onClick = { onSaveAll(exactMatches, unmatched) }, shape = RoundedCornerShape(12.dp)) { Text("保存全部") } },
    dismissButton = { TextButton(onClick = onDismiss) { Text("暂不保存") } },
)
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
                        candidates = api.symbolLookup(listOf(name)).firstOrNull()?.matches.orEmpty()
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
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    fun refresh() = scope.launch {
        val symbols = try { api.holdings().map { it.symbol } } catch (exception: Exception) {
            error = "无法读取持仓，请稍后重试。"
            return@launch
        }
        var announcementError: String? = null
        var feedError: String? = null
        try { announcements = api.announcements(symbols) } catch (exception: Exception) { announcementError = "公告暂时不可用" }
        try { feed = api.feed(symbols) } catch (exception: Exception) { feedError = "新闻暂时不可用" }
        error = listOfNotNull(announcementError, feedError).takeIf { it.isNotEmpty() }?.joinToString("；")
    }
    LaunchedEffect(Unit) { refresh() }
    LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { AppHero("关联消息", "消息枝叶 · 捕捉与你有关的变化", action = { HeroRefreshAction(onClick = { refresh() }) }) }
        item { Text("正式公告优先展示；新闻用于补充背景，均请以原文为准。", modifier = Modifier.padding(horizontal = 20.dp), color = MaterialTheme.colorScheme.onSurfaceVariant) }
        error?.let { item { StatusCard(it ?: "消息暂时不可用", error = true) } }
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
        Text("${item.source_name}｜${item.published_at}", style = MaterialTheme.typography.bodySmall)
        TextButton(onClick = { uriHandler.openUri(item.source_url) }, colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.primary)) { Text("查看原文  →", fontWeight = FontWeight.Bold) }
    }
}

@Composable
private fun ProfileScreen(themeMode: ThemeMode, onThemeModeChange: (ThemeMode) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var baseUrl by remember { mutableStateOf(EndpointStore.baseUrl(context)) }
    var connectionStatus by remember { mutableStateOf<String?>(null) }
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
}
