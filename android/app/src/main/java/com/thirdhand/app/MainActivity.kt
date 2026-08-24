package com.thirdhand.app

import android.os.Bundle
import android.graphics.Paint
import android.util.Log
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.BackHandler
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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.background
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.animation.core.tween
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.AccountBalanceWallet
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.AdminPanelSettings
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AutoGraph
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.CloudDownload
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.SystemUpdateAlt
import androidx.compose.material.icons.filled.Wallet
import androidx.compose.material.icons.automirrored.filled.Article
import androidx.compose.material.icons.automirrored.filled.TrendingDown
import androidx.compose.material.icons.automirrored.filled.TrendingFlat
import androidx.compose.material.icons.automirrored.filled.TrendingUp
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DateRangePicker
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDateRangePickerState
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
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
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.OffsetDateTime
import java.time.LocalDate
import java.time.Instant
import java.time.temporal.WeekFields
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import com.thirdhand.app.researchchat.ResearchChatScreen
import com.thirdhand.app.researchchat.ResearchChatController
import com.thirdhand.app.researchchat.ResearchChatLine
import com.thirdhand.app.watchlist.WatchlistScreen
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

private var savedGlossaryTerms by mutableStateOf<List<String>>(emptyList())
// Kept separate from real execution records; only simulated trades become K-line markers.
private var paperChartMarkers by mutableStateOf<List<PaperTradingLogDto>>(emptyList())
// Deliberately separate from real execution records: KLineChart uses these only
// for purple paper-trade markers.

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun ThirdHandApp(resumeSignal: Int) {
    val context = LocalContext.current
    LaunchedEffect(Unit) {
        savedGlossaryTerms = runCatching { ApiClient.service(context).glossaryEntries().map { it.term }.filter { it.isNotBlank() } }.getOrDefault(emptyList())
    }
    var themeMode by remember { mutableStateOf(ThemeStore.load(context)) }
    var tab by remember { mutableIntStateOf(0) }
    val researchChatController = remember { ResearchChatController() }
    var researchConversation by remember { mutableStateOf<List<ResearchChatLine>>(emptyList()) }
    var researchDraft by remember { mutableStateOf("") }
    var researchEntryTarget by remember { mutableStateOf<ResearchTargetDto?>(null) }
    var detailHolding by remember { mutableStateOf<HoldingDto?>(null) }
    var detailStock by remember { mutableStateOf<ResearchTargetDto?>(null) }
    var startupUpdate by remember { mutableStateOf<AppUpdate?>(null) }
    var updateMessage by remember { mutableStateOf<String?>(null) }
    var startupDownloadProgress by remember { mutableStateOf<UpdateDownloadProgress?>(null) }
    var monitoringStartupDownload by remember { mutableStateOf(false) }
    LaunchedEffect(resumeSignal) {
        try {
            val update = AppUpdateManager.check(context)
            startupDownloadProgress = update?.let { AppUpdateManager.refreshDownloadState(context) }
            val downloaded = update != null && AppUpdateManager.hasCompletedDownload(context, update)
            val active = update != null && AppUpdateManager.hasActiveDownload(context, update)
            val automaticResult = if (update != null && !downloaded && !active) {
                AppUpdateManager.downloadAutomaticallyOnWifi(context, update)
            } else null
            startupUpdate = if (
                downloaded || active || automaticResult == UpdateLaunchResult.DOWNLOAD_STARTED
            ) null else update
            updateMessage = when {
                downloaded -> AppUpdateManager.completedUpdateMessage(context)
                active -> "新版本正在后台下载，可继续使用应用"
                else -> null
            }
            monitoringStartupDownload = active
            if (automaticResult == UpdateLaunchResult.DOWNLOAD_STARTED) {
                startupDownloadProgress = AppUpdateManager.downloadProgress(context)
                monitoringStartupDownload = true
                updateMessage = "已在 Wi‑Fi 下开始后台下载新版本"
            }
        } catch (_: Exception) {
            // A failed update check must never block the main application.
        }
    }
    LaunchedEffect(monitoringStartupDownload) {
        if (!monitoringStartupDownload) return@LaunchedEffect
        while (true) {
            val current = AppUpdateManager.refreshDownloadState(context)
            startupDownloadProgress = current
            if (current == null || !current.state.isActive) {
                monitoringStartupDownload = false
                val ready = AppUpdateManager.hasCompletedDownload(context)
                updateMessage = if (current?.state == UpdateDownloadState.FAILED) {
                    current.message
                } else {
                    if (ready) "更新包已下载并校验完成，请在管理页面点击“安装更新”。" else AppUpdateManager.completedUpdateMessage(context) ?: current?.state?.label
                }
                break
            }
            delay(500)
        }
    }
    val tabOrder = remember { listOf(0, 1, 5, 3, 2) }
    BackHandler(enabled = detailHolding != null || detailStock != null || tab != 0) {
        when {
            detailHolding != null -> detailHolding = null
            detailStock != null -> detailStock = null
            else -> tab = 0
        }
    }
    ThirdHandTheme(themeMode) {
        Scaffold(
            bottomBar = {
                if (detailHolding == null && detailStock == null) {
                    NavigationBar {
                        listOf(
                            Triple("新闻", Icons.AutoMirrored.Filled.Article, 0),
                            Triple("行情", Icons.Filled.AutoGraph, 1),
                            Triple("自选", Icons.Filled.Bookmark, 5),
                            Triple("交易", Icons.Filled.AccountBalanceWallet, 3),
                            Triple("管理", Icons.Filled.AdminPanelSettings, 2),
                        ).forEach { (label, icon, targetTab) ->
                            NavigationBarItem(
                                selected = tab == targetTab,
                                onClick = {
                                    if (targetTab == 4) researchEntryTarget = null
                                    tab = targetTab
                                },
                                icon = { Icon(icon, contentDescription = label) },
                                label = { Text(label) },
                            )
                        }
                    }
                }
            },
        ) { padding ->
            Surface(modifier = Modifier.fillMaxSize().padding(padding), color = MaterialTheme.colorScheme.background) {
                if (detailHolding != null) {
                    HoldingSummaryDetailScreen(
                        target = ResearchTargetDto(detailHolding!!.symbol, detailHolding!!.name, "active_holding", detailHolding!!.created_at),
                        holding = detailHolding!!,
                        onBack = { detailHolding = null },
                        onResearch = { target ->
                            detailHolding = null
                            researchEntryTarget = target
                            researchChatController.beginNewResearch(target.symbol)
                            researchConversation = emptyList()
                            researchDraft = ""
                            tab = 4
                        },
                    )
                } else if (detailStock != null) {
                    HoldingSummaryDetailScreen(detailStock!!, holding = null, onBack = { detailStock = null }, onResearch = { target ->
                        detailStock = null
                        researchEntryTarget = target
                        researchChatController.beginNewResearch(target.symbol)
                        researchConversation = emptyList()
                        researchDraft = ""
                        tab = 4
                    })
                } else androidx.compose.foundation.layout.Box(Modifier.fillMaxSize().pointerInput(tab) {
                    var horizontalDrag = 0f
                    detectHorizontalDragGestures(
                        onDragStart = { horizontalDrag = 0f },
                        onHorizontalDrag = { _, amount -> horizontalDrag += amount },
                        onDragEnd = {
                            val currentIndex = tabOrder.indexOf(tab).coerceAtLeast(0)
                            if (horizontalDrag <= -56f) tab = tabOrder[(currentIndex + 1).coerceAtMost(tabOrder.lastIndex)]
                            if (horizontalDrag >= 56f) tab = tabOrder[(currentIndex - 1).coerceAtLeast(0)]
                        },
                    )
                }) {
                    AnimatedContent(
                        targetState = tab,
                        transitionSpec = {
                            val movingForward = tabOrder.indexOf(targetState) > tabOrder.indexOf(initialState)
                            (slideInHorizontally(animationSpec = tween(260)) { width -> if (movingForward) width else -width } + fadeIn(tween(180))) togetherWith
                                (slideOutHorizontally(animationSpec = tween(220)) { width -> if (movingForward) -width / 3 else width / 3 } + fadeOut(tween(140)))
                        },
                        label = "bottomNavigationPage",
                    ) { activeTab ->
                        when (activeTab) {
                            0 -> NewsScreen()
                            1 -> MarketScreen(onOpenDetail = { detailStock = it })
                            5 -> WatchlistScreen(onOpenDetail = { detailStock = it })
                            2 -> CompactAdminDashboardScreen()
                            3 -> PaperTradingScreen(onOpenDetail = { detailStock = it })
                            else -> NewsScreen()
                        }
                    }
                }
            }
        }
        startupUpdate?.let { update ->
            UpdatePromptDialog(
                update = update,
                progress = startupDownloadProgress,
                status = updateMessage,
                onDismiss = { startupUpdate = null },
                onConfirm = {
                        when (AppUpdateManager.downloadAndInstall(context, update)) {
                            UpdateLaunchResult.DOWNLOAD_STARTED -> {
                                startupDownloadProgress = AppUpdateManager.downloadProgress(context)
                                monitoringStartupDownload = true
                                startupUpdate = null
                                updateMessage = "正在下载，完成后可在管理页面安装"
                            }
                            UpdateLaunchResult.INSTALLER_OPENED -> {
                                updateMessage = "已进入系统安装页：完成安装后，点击“打开”即可直接进入新版"
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
private fun TradePlanScreen() {
    val context = LocalContext.current
    val api = ApiClient.service(context)
    var plans by remember { mutableStateOf<List<TradePlanDto>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var editing by remember { mutableStateOf<TradePlanDto?>(null) }
    var createPlan by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    fun load() = scope.launch {
        loading = true; error = null
        try { plans = api.tradePlans() } catch (_: Exception) { error = "暂时无法读取交易计划，请稍后重试。" } finally { loading = false }
    }
    LaunchedEffect(Unit) { load() }
    LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { AppHero("交易计划", "波段优先 · 条件先于操作", action = { HeroRefreshAction(::load, !loading) }) }
        item {
            Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("先写逻辑、催化剂、加减仓与退出条件；行情和新闻只负责验证条件。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                PrimaryAction("新建计划", Icons.Filled.Add, { createPlan = true }, Modifier.fillMaxWidth())
            }
        }
        if (loading) item { StatusCard("正在读取交易计划…") }
        error?.let { item { StatusCard(it, error = true) } }
        if (!loading && plans.isEmpty()) item { StatusCard("还没有计划。建议先为当前持仓建立波段计划。") }
        items(plans, key = { it.symbol }) { plan ->
            Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth().clickable { editing = plan }) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("${plan.symbol} · ${if (plan.horizon == "swing") "波段" else "短线"}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text(plan.thesis, style = MaterialTheme.typography.bodySmall, maxLines = 3, overflow = TextOverflow.Ellipsis)
                    Text("催化剂：${plan.catalysts.joinToString("、")}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    Text("最大仓位 ${plan.max_position_percent}% · 风险预算 ${plan.risk_budget_percent}% · v${plan.version}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                }
            }
        }
    }
    if (createPlan || editing != null) TradePlanDialog(
        initial = editing,
        onDismiss = { createPlan = false; editing = null },
        onSave = { input -> scope.launch {
            try { api.saveTradePlan(input); createPlan = false; editing = null; load() } catch (_: Exception) { error = "保存交易计划失败，请检查填写内容和后端连接。" }
        } },
    )
}

@Composable
private fun TradePlanDialog(initial: TradePlanDto?, initialSymbol: String = "", onDismiss: () -> Unit, onSave: (TradePlanInputDto) -> Unit) {
    val api = ApiClient.service(LocalContext.current)
    val scope = rememberCoroutineScope()
    var symbol by remember(initial, initialSymbol) { mutableStateOf(initial?.symbol ?: initialSymbol) }
    var horizon by remember(initial) { mutableStateOf(initial?.horizon ?: "swing") }
    var thesis by remember(initial) { mutableStateOf(initial?.thesis ?: "") }
    var expectation by remember(initial) { mutableStateOf(initial?.market_expectation ?: "") }
    var benchmarkSymbol by remember(initial) { mutableStateOf(initial?.benchmark_symbol ?: "") }
    var benchmarkName by remember(initial) { mutableStateOf(initial?.benchmark_name ?: "") }
    var catalysts by remember(initial) { mutableStateOf(initial?.catalysts?.joinToString("；") ?: "") }
    var entry by remember(initial) { mutableStateOf(initial?.entry_condition ?: "") }
    var add by remember(initial) { mutableStateOf(initial?.add_condition ?: "") }
    var reduce by remember(initial) { mutableStateOf(initial?.reduce_condition ?: "") }
    var exit by remember(initial) { mutableStateOf(initial?.exit_condition ?: "") }
    var maxPosition by remember(initial) { mutableStateOf(initial?.max_position_percent?.toString() ?: "15") }
    var riskBudget by remember(initial) { mutableStateOf(initial?.risk_budget_percent?.toString() ?: "3") }
    var validation by remember { mutableStateOf<String?>(null) }
    var draftNotice by remember { mutableStateOf<String?>(null) }
    var drafting by remember { mutableStateOf(false) }
    var showAdvanced by remember(initial) { mutableStateOf(initial?.benchmark_symbol != null || initial?.benchmark_name != null) }
    fun applyDraft() = scope.launch {
        if (symbol.trim().isBlank()) { validation = "请先填写证券代码，系统才能生成草案。"; return@launch }
        drafting = true
        validation = null
        runCatching { api.tradePlanDraft(symbol.trim().uppercase()) }
            .onSuccess { draft ->
                symbol = draft.symbol; horizon = draft.horizon; thesis = draft.thesis; expectation = draft.market_expectation
                catalysts = draft.catalysts.joinToString("；"); entry = draft.entry_condition; add = draft.add_condition
                reduce = draft.reduce_condition; exit = draft.exit_condition; maxPosition = draft.max_position_percent.toString()
                riskBudget = draft.risk_budget_percent.toString(); draftNotice = draft.notice
            }
            .onFailure { validation = "无法生成草案：${it.message ?: "请确认后端已更新后重试。"}" }
        drafting = false
    }
    Dialog(onDismissRequest = onDismiss) {
        Surface(Modifier.fillMaxWidth().heightIn(max = 700.dp), shape = RoundedCornerShape(18.dp)) {
            Column(Modifier.padding(18.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(if (initial == null) "新建交易计划" else "编辑交易计划", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text("先用系统草案降低录入负担，再确认真正属于你的交易逻辑。计划不是自动交易授权。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                PlanField("证券代码", symbol, help = "用于关联持仓、行情、风险数据与后续复核。") { symbol = it }
                if (initial == null) FilledTonalButton(onClick = ::applyDraft, enabled = !drafting, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Filled.AutoGraph, null); Spacer(Modifier.width(6.dp)); Text(if (drafting) "正在生成研究草案…" else "根据持仓与风险生成草案")
                }
                draftNotice?.let { Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary) }
                Row(verticalAlignment = Alignment.CenterVertically) { RadioButton(horizon == "swing", { horizon = "swing" }); Text("波段（默认）"); Spacer(Modifier.width(12.dp)); RadioButton(horizon == "short", { horizon = "short" }); Text("短线") }
                PlanField("交易逻辑", thesis, 3, "你为什么持有它；用于判断原始依据是否仍成立。") { thesis = it }
                PlanField("市场原有预期", expectation, 2, "市场普遍已经预期什么；用来识别预期差和风险。") { expectation = it }
                PlanField("催化剂（用；分隔）", catalysts, 2, "未来可能验证或推翻逻辑的事件，例如财报、行业数据、公告。") { catalysts = it }
                PlanField("入场条件", entry, 2, "什么情况下才允许新建仓，避免只因价格波动而追入。") { entry = it }
                PlanField("加仓条件", add, 2, "什么证据增强时才加仓；系统会同时检查仓位上限与风险。") { add = it }
                PlanField("减仓条件", reduce, 2, "什么风险或仓位信号出现时应复核减仓。") { reduce = it }
                PlanField("退出 / 失效条件", exit, 2, "什么事实证明原交易逻辑不再成立，是最重要的风险边界。") { exit = it }
                PlanField("最大仓位 %", maxPosition, help = "单一标的最多占总资产的比例；用于限制集中风险。") { maxPosition = it }
                PlanField("单笔风险预算 %", riskBudget, help = "一次交易最多允许承担的总资产损失比例；用于计算建议数量。") { riskBudget = it }
                TextButton(onClick = { showAdvanced = !showAdvanced }) { Text(if (showAdvanced) "收起高级比较项" else "显示高级比较项（可选）") }
                if (showAdvanced) {
                    PlanField("比较基准代码（如 sh000300）", benchmarkSymbol, help = "可选。用于判断该标的相对市场是强还是弱。") { benchmarkSymbol = it }
                    PlanField("比较基准名称（如 沪深300）", benchmarkName, help = "可选，仅用于界面显示。") { benchmarkName = it }
                }
                validation?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedButton(onClick = onDismiss, modifier = Modifier.weight(1f)) { Text("取消") }
                    Button(onClick = {
                        val max = maxPosition.toDoubleOrNull(); val risk = riskBudget.toDoubleOrNull()
                        val catalystItems = catalysts.split('；', ';').map(String::trim).filter(String::isNotBlank)
                        if (listOf(symbol, thesis, expectation, entry, add, reduce, exit).any { it.trim().length < 5 } || catalystItems.isEmpty() || max == null || risk == null) validation = "请补全所有条件，并填写有效的仓位和风险预算。"
                        else onSave(TradePlanInputDto(symbol.trim().uppercase(), horizon, thesis.trim(), expectation.trim(), benchmarkSymbol.trim().ifBlank { null }, benchmarkName.trim().ifBlank { null }, catalystItems, entry.trim(), add.trim(), reduce.trim(), exit.trim(), max, risk))
                    }, modifier = Modifier.weight(1f)) { Text("保存") }
                }
            }
        }
    }
}

@Composable
private fun PlanField(label: String, value: String, lines: Int = 1, help: String = "", onChange: (String) -> Unit) {
    OutlinedTextField(value = value, onValueChange = onChange, label = { Text(label) }, supportingText = if (help.isBlank()) null else ({ Text(help) }), modifier = Modifier.fillMaxWidth(), minLines = lines, maxLines = lines + 2)
}

@Composable
private fun ImpactGraphScreen() {
    val context = LocalContext.current
    val api = ApiClient.service(context)
    val uriHandler = LocalUriHandler.current
    var graph by remember { mutableStateOf<ImpactGraphDto?>(null) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    fun load() = scope.launch {
        loading = true
        error = null
        try {
            graph = api.impactGraph()
        } catch (_: Exception) {
            error = "暂时无法读取影响关系，请确认后端已升级并稍后重试。"
        } finally {
            loading = false
        }
    }
    LaunchedEffect(Unit) { load() }
    LazyColumn(
        contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item { AppHero("持仓影响图", "证据关系 · 不是交易指令", action = { HeroRefreshAction(::load, !loading) }) }
        item {
            Text(
                "从持仓出发查看现价、历史风险与来源事件。箭头表示关联，不表示已证明的因果。",
                modifier = Modifier.padding(horizontal = 20.dp),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (loading) item { StatusCard("正在整理持仓影响关系…") }
        error?.let { message -> item { StatusCard(message, error = true) } }
        graph?.let { payload ->
            if (payload.nodes.isEmpty()) item { StatusCard("还没有可展示的已确认持仓。先添加持仓并刷新行情或信息流。") }
            val edgesByTarget = payload.edges.groupBy { it.target }
            items(payload.nodes.filter { it.kind == "holding" }, key = { it.id }) { holding ->
                Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text(holding.label, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text(holding.detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        val linkedIds = edgesByTarget[holding.id].orEmpty().map { it.source }.toSet()
                        payload.nodes.filter { it.id in linkedIds }.forEach { node ->
                            val edge = payload.edges.firstOrNull { it.source == node.id && it.target == holding.id }
                            HorizontalDivider()
                            Text("${impactKindLabel(node.kind)}  →  ${edge?.relation ?: "关联"}", style = MaterialTheme.typography.labelMedium, color = impactColor(edge?.direction))
                            Text(node.label, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
                            Text(node.detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            node.source_url?.let { url ->
                                TextButton(onClick = { uriHandler.openUri(url) }) { Text("查看来源") }
                            }
                        }
                    }
                }
            }
            item { Text(payload.disclaimer, modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
    }
}

private fun impactKindLabel(kind: String): String = when (kind) {
    "market" -> "行情快照"
    "risk" -> "历史风险"
    "event" -> "新闻 / 公告"
    else -> "关联信息"
}

@Composable
private fun impactColor(direction: String?): Color = when (direction) {
    "positive" -> MaterialTheme.colorScheme.tertiary
    "negative" -> MaterialTheme.colorScheme.error
    else -> MaterialTheme.colorScheme.primary
}

@Composable
private fun TodayScreen(onOpenTradePlan: () -> Unit, onOpenRules: () -> Unit, onOpenPortfolio: () -> Unit) {
    val context = LocalContext.current
    val uriHandler = LocalUriHandler.current
    val api = remember { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var news by remember { mutableStateOf<List<NewsItemDto>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    fun load() = scope.launch {
        loading = true
        error = null
        runCatching {
            val symbols = api.researchTargets().map { it.symbol }.distinct()
            (api.announcements(symbols) + api.feed(symbols))
                .distinctBy { it.id }
                .sortedByDescending { it.published_at }
        }.onSuccess { news = it }
            .onFailure { error = "无法读取新闻：${it.message ?: "请确认后端正在运行"}" }
        loading = false
    }
    LaunchedEffect(Unit) { load() }
    LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Row(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("今日资讯", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                    Text("优先展示持仓与自选股的公告、新闻和已保存的 AI 解读。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                IconButton(onClick = ::load, enabled = !loading) { Icon(Icons.Filled.Refresh, "刷新今日资讯") }
            }
        }
        if (loading) item {
            Row(Modifier.padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                CircularProgressIndicator(Modifier.width(18.dp), strokeWidth = 2.dp)
                Text("正在读取公告与新闻…", style = MaterialTheme.typography.bodySmall)
            }
        }
        error?.let { message -> item {
            Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("今日资讯不可用", fontWeight = FontWeight.Bold)
                    Text(message, style = MaterialTheme.typography.bodySmall)
                    TextButton(onClick = ::load) { Text("重试") }
                }
            }
        } }
        if (!loading && error == null && news.isEmpty()) item { StatusCard("暂无相关新闻。添加持仓或自选后，刷新即可检索公告与新闻。") }
        items(news, key = { item -> "today-news-${item.id}" }) { item ->
            FeedCard(item, uriHandler, if (item.source_name.contains("公告") || item.source_name.contains("交易所")) "公告" else "新闻")
        }
    }
}

@Composable
private fun LegacyTodayScreen(onOpenTradePlan: () -> Unit, onOpenRules: () -> Unit, onOpenPortfolio: () -> Unit) {
    val context = LocalContext.current
    val api = ApiClient.service(context)
    var holdings by remember { mutableStateOf<List<HoldingDto>>(emptyList()) }
    var portfolioAnalysis by remember { mutableStateOf<List<PortfolioAnalysisItemDto>>(emptyList()) }
    var decisionReport by remember { mutableStateOf<DecisionReportDto?>(null) }
    var showDecisionHistory by remember { mutableStateOf(false) }
    var selectedSymbol by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var statusMessage by remember { mutableStateOf<String?>(null) }
    var analyzing by remember { mutableStateOf(false) }
    var showSymbolPicker by remember { mutableStateOf(false) }
    var instrumentSetupSymbol by remember { mutableStateOf<String?>(null) }
    var opportunityScan by remember { mutableStateOf<OpportunityScanDto?>(null) }
    var scanningOpportunities by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    fun load() = scope.launch {
        try {
            error = null
            holdings = api.holdings()
            portfolioAnalysis = api.portfolioAnalysis().items
            if (selectedSymbol == null) selectedSymbol = holdings.firstOrNull()?.symbol
            selectedSymbol?.let { symbol -> decisionReport = runCatching { api.latestDecision(symbol) }.getOrNull() }
        } catch (exception: Exception) {
            error = "无法读取决策数据：${exception.message ?: "请确认后端正在运行"}"
        }
    }
    fun analyzeSelected() = scope.launch {
        val holding = holdings.firstOrNull { it.symbol == selectedSymbol } ?: return@launch
        analyzing = true
        error = null
        statusMessage = "正在刷新行情并生成 ${holding.name} 的决策报告…"
        try {
            ApiClient.marketQuotes(api, MarketQuoteBatchRequestDto(listOf(holding.symbol), refresh = true))
            val job = api.generateDecision(DecisionGenerateRequestDto(listOf(holding.symbol))).jobs.firstOrNull()
                ?: error("服务端未返回决策任务")
            repeat(24) {
                val current = api.decisionJob(job.job_id)
                when (current.status) {
                    "succeeded" -> {
                        decisionReport = api.latestDecision(holding.symbol)
                        portfolioAnalysis = api.portfolioAnalysis().items
                        statusMessage = "决策报告已生成：包含证据、规则候选与仓位测算；不会自动交易。"
                        return@launch
                    }
                    "failed" -> error(current.error_message ?: "决策任务失败")
                }
                delay(750)
            }
            error("决策任务仍在后台处理，请稍后刷新此页查看结果")
        } catch (exception: Exception) {
            error = "未能生成决策报告：${exception.message ?: "请稍后重试"}"
        } finally {
            analyzing = false
        }
    }
    fun scanOpportunities() = scope.launch {
        scanningOpportunities = true
        try {
            opportunityScan = api.refreshOpportunityScan()
        } catch (_: Exception) {
            error = "机会扫描暂时不可用；请确认后端正在运行并且已缓存行情和至少 60 天日线。"
        } finally {
            scanningOpportunities = false
        }
    }
    fun loadCachedOpportunityScan() = scope.launch {
        try {
            opportunityScan = api.opportunityScan()
        } catch (_: Exception) {
            // The decision workspace remains usable when this independent
            // section has no cached scan or the provider is temporarily down.
        }
    }
    LaunchedEffect(Unit) {
        load()
        loadCachedOpportunityScan()
    }
    val selectedHolding = holdings.firstOrNull { it.symbol == selectedSymbol }
    val selectedAnalysis = portfolioAnalysis.firstOrNull { it.symbol == selectedSymbol }
    val rankedAnalysis = portfolioAnalysis.sortedWith(
        compareBy<PortfolioAnalysisItemDto> { todayAnalysisPriority(it.action) }
            .thenByDescending { it.confidence_percent },
    )
    LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { AppHero("今日决策", "规则负责约束，AI 负责复核解释") }
        item {
            Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Text("AI 决策工作台", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text("行情不在这里重复展示；请选择持仓，沿着证据、规则和结论查看本次分析。", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
            }
        }
        item {
            OpportunityScanCard(
                scan = opportunityScan,
                loading = scanningOpportunities,
                onRefresh = ::scanOpportunities,
                onOpenTradePlan = onOpenTradePlan,
            )
        }
        error?.let { item { StatusCard(it, error = true) } }
        statusMessage?.let { item { StatusCard(it, positive = true) } }
        if (holdings.isEmpty()) item { StatusCard("先在“持仓”页添加第一只持仓，才能建立决策分析。") }
        if (rankedAnalysis.isNotEmpty()) {
            item { Text("今日分析", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
            items(rankedAnalysis, key = { "today-analysis-${it.symbol}" }) { item ->
                Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth().clickable {
                    selectedSymbol = item.symbol
                    decisionReport = null
                    scope.launch { decisionReport = runCatching { api.latestDecision(item.symbol) }.getOrNull() }
                }) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("${item.name} · ${item.symbol}", modifier = Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
                            Text(analysisActionLabel(item.action), color = analysisActionColor(item.action), style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                        }
                        Text(item.reason, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("证据置信度 ${item.confidence_percent}% · 点击查看本次保存的依据和数据范围", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
        selectedHolding?.let { holding -> item {
            OutlinedButton(
                onClick = { showSymbolPicker = true },
                modifier = Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
                shape = RoundedCornerShape(14.dp),
            ) {
                Column(Modifier.weight(1f), horizontalAlignment = Alignment.Start) {
                    Text("分析标的", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("${holding.name} · ${holding.symbol}", fontWeight = FontWeight.SemiBold)
                }
                Text("切换")
            }
        } }
        selectedHolding?.let { holding -> item {
            Card(
                Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
            ) { Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("决策操作", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onPrimaryContainer)
                PrimaryAction("根据当前行情主动分析 ${holding.name}", Icons.Filled.AutoGraph, ::analyzeSelected, Modifier.fillMaxWidth(), enabled = !analyzing)
                Text("会把行情、你的持仓和计划放在一起核对，告诉你哪些信息支持或反对当前判断；AI 只负责解释，不会替你下单。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            } }
        } }
        decisionReport?.let { report -> item {
            DecisionWorkbenchRoute(
                report,
                onViewHistory = { showDecisionHistory = true },
                onOpenRules = onOpenRules,
                onResolveBlocker = { code ->
                    when (blockerTarget(code)) {
                        "plan" -> onOpenTradePlan()
                        "instrument" -> instrumentSetupSymbol = report.symbol
                        else -> onOpenPortfolio()
                    }
                },
            )
        } }
        if (decisionReport == null) selectedAnalysis?.let { item { BaselineReviewRoute(it) } }
        if (selectedHolding != null && decisionReport == null) item { StatusCard("尚未生成新版决策报告。点击主动分析后将在这里展示可追溯的证据与仓位结果。") }
    }
    instrumentSetupSymbol?.let { symbol -> InstrumentMetadataDialog(symbol, onDismiss = { instrumentSetupSymbol = null }) }
    if (showSymbolPicker) AlertDialog(
        onDismissRequest = { showSymbolPicker = false },
        title = { Text("切换分析标的") },
        text = { LazyColumn(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            items(holdings, key = { it.symbol }) { holding ->
                val selected = holding.symbol == selectedSymbol
                TextButton(onClick = {
                    selectedSymbol = holding.symbol
                    decisionReport = null
                    statusMessage = null
                    showSymbolPicker = false
                    scope.launch { decisionReport = runCatching { api.latestDecision(holding.symbol) }.getOrNull() }
                }, modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.fillMaxWidth()) {
                        Text("${holding.name} · ${holding.symbol}", fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal)
                        Text(if (selected) "当前分析对象" else "切换到此标的", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        } },
        confirmButton = { TextButton(onClick = { showSymbolPicker = false }) { Text("关闭") } },
    )
    if (showDecisionHistory && selectedSymbol != null) DecisionHistoryDialog(selectedSymbol!!, onDismiss = { showDecisionHistory = false })
}

@Composable
private fun OpportunityScanCard(
    scan: OpportunityScanDto?,
    loading: Boolean,
    onRefresh: () -> Unit,
    onOpenTradePlan: () -> Unit,
) {
    Card(
        modifier = Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("市场机会扫描", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text("没有持仓也可以先观察；系统不会把“可能上涨”包装成“明天必涨”。", style = MaterialTheme.typography.bodySmall)
                }
                IconButton(onClick = onRefresh, enabled = !loading) {
                    Icon(Icons.Filled.Refresh, contentDescription = "刷新机会扫描")
                }
            }
            when {
                loading -> Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    LinearProgressIndicator(modifier = Modifier.width(56.dp))
                    Text("正在从已缓存的行情中筛选可观察标的…", style = MaterialTheme.typography.bodySmall)
                }
                scan == null -> Text("暂时没有机会扫描结果。", style = MaterialTheme.typography.bodySmall)
                else -> {
                    Text(scan.coverage_note, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSecondaryContainer)
                    if (scan.hot_sectors.isNotEmpty()) {
                        Text("当前热门板块：${scan.hot_sectors.joinToString(" · ")}", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
                    }
                    if (scan.items.isEmpty()) {
                        Text("热门板块候选正在补齐日线，完成后会自动进入分析；无需录入股票代码。", style = MaterialTheme.typography.bodySmall)
                    } else scan.items.forEach { item ->
                        HorizontalDivider(color = MaterialTheme.colorScheme.onSecondaryContainer.copy(alpha = 0.18f))
                        Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                            Text("${item.name}（${item.symbol}） · ${if (item.action == "trim") "优先复核持仓" else "值得观察"}", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                            CandidateSourceBadges(item.sources)
                            item.sector?.let { Text("所属板块：$it", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSecondaryContainer) }
                            Text(item.summary, style = MaterialTheme.typography.bodySmall)
                            item.reasons.take(2).forEach { reason -> Text("• $reason", style = MaterialTheme.typography.bodySmall) }
                            Text("综合评分 ${item.score}/100 · 证据置信度 ${item.confidence}/100 · 偏强可能性 ${item.upside_likelihood}/100（非承诺）", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
                            Text("风险：${item.risk_level}。置信度衡量证据完整度，不等于涨跌概率。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSecondaryContainer)
                            Text("考虑前提：${item.buy_condition}", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
                            Text("不做/离场：${item.avoid_condition}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                            Text("数据截至 ${item.data_as_of ?: "未知"} · 观察强度 ${item.score}/100（不是上涨概率）", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSecondaryContainer)
                        }
                    }
                    TextButton(onClick = onOpenTradePlan) { Text("建立交易计划后，再查看可执行数量") }
                }
            }
        }
    }
}

@Composable
private fun CandidateSourceBadges(sources: List<String>) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        if ("holding" in sources) {
            Icon(Icons.Filled.Wallet, contentDescription = "持仓候选", modifier = Modifier.width(16.dp), tint = MaterialTheme.colorScheme.primary)
            Text("持仓", style = MaterialTheme.typography.labelSmall)
        }
        if ("watchlist" in sources) {
            Icon(Icons.Filled.Bookmark, contentDescription = "自选候选", modifier = Modifier.width(16.dp), tint = MaterialTheme.colorScheme.secondary)
            Text("自选", style = MaterialTheme.typography.labelSmall)
        }
        if ("market" in sources) {
            Icon(Icons.Filled.AutoGraph, contentDescription = "市场推荐候选", modifier = Modifier.width(16.dp), tint = MaterialTheme.colorScheme.tertiary)
            Text("市场推荐", style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
private fun BaselineReviewRoute(item: PortfolioAnalysisItemDto) {
    val steps = item.analysis_trace.ifEmpty {
        listOf(AnalysisTraceStepDto("决策结论", "unavailable", "尚未取得本次分析的可视化轨迹。"))
    }
    Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), shape = RoundedCornerShape(18.dp)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("基础风险复核", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text("${analysisActionLabel(item.action)} · 数据完整度 ${item.confidence_percent}%", color = analysisActionColor(item.action), style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
            ExplainableText(item.reason, style = MaterialTheme.typography.bodyMedium)
            steps.forEachIndexed { index, step ->
                Row(verticalAlignment = Alignment.Top) {
                    Text("${index + 1}", modifier = Modifier.clip(RoundedCornerShape(99.dp)).background(analysisTraceColor(step.status)).padding(horizontal = 8.dp, vertical = 3.dp), color = MaterialTheme.colorScheme.onPrimary, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
                    Column(Modifier.padding(start = 10.dp).weight(1f)) {
                        Text("${step.stage} · ${analysisTraceStatus(step.status)}", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
                        Text(step.detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                if (index != steps.lastIndex) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            }
            Text("这是旧版基础复核，仅作数据检查；请以上方新版决策报告作为本次主动分析结果。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun InstrumentMetadataDialog(symbol: String, onDismiss: () -> Unit) {
    val context = LocalContext.current
    val api = ApiClient.service(context)
    val scope = rememberCoroutineScope()
    var lotSize by remember(symbol) { mutableStateOf("100") }
    var saving by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(symbol) {
        runCatching { api.instrumentMetadata(symbol) }.getOrNull()?.let { metadata ->
            lotSize = metadata.lot_size?.toString() ?: "100"
        }
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("补充交易单位") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("系统需要最小交易单位，才能把风险预算换算为可交易数量。A 股通常为 100 股；请以该证券的交易规则为准。", style = MaterialTheme.typography.bodySmall)
                OutlinedTextField(lotSize, { lotSize = it }, label = { Text("最小交易单位（股）") }, modifier = Modifier.fillMaxWidth())
                error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
            }
        },
        confirmButton = {
            Button(enabled = !saving, onClick = {
                val value = lotSize.toIntOrNull()
                if (value == null || value <= 0) {
                    error = "请输入大于 0 的整数。"
                    return@Button
                }
                scope.launch {
                    saving = true
                    try {
                        api.saveInstrumentMetadata(symbol, InstrumentMetadataInputDto("CN", "CNY", value, "0.01", "user_confirmed", LocalDate.now().toString()))
                        onDismiss()
                    } catch (_: Exception) {
                        error = "保存失败，请检查网络后重试。"
                    } finally {
                        saving = false
                    }
                }
            }) { Text(if (saving) "保存中…" else "保存") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@Composable
private fun DecisionWorkbenchRoute(
    report: DecisionReportDto,
    onViewHistory: (() -> Unit)? = null,
    onOpenRules: (() -> Unit)? = null,
    onResolveBlocker: ((String) -> Unit)? = null,
) {
    var showAnalysisDetail by remember(report.decision_id) { mutableStateOf(false) }
    Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("待执行", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        val operationItems = report.operation_items.orEmpty()
        if (operationItems.isEmpty()) {
            StatusCard("本次结果没有可执行项目；请先完成待补全项后重新生成。")
        }
        operationItems.forEach { item ->
            val blocked = item.status == "needs_input"
            Card(
                Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = if (blocked) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.primaryContainer),
            ) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(item.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text(item.trigger, style = MaterialTheme.typography.bodyMedium)
                    if (!blocked) {
                        item.reference_price?.let { Text("执行参考价 ${marketNumber(it)}", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold) }
                        item.suggested_quantity?.let { Text("建议本次数量 ${formatPositionValue(it)} 股", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold) }
                        item.target_quantity?.let { Text("建议目标持仓 ${formatPositionValue(it)} 股", style = MaterialTheme.typography.bodySmall) }
                        item.invalidation_price?.let { Text("失效价 ${marketNumber(it)}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
                    } else item.blockers.orEmpty().forEach { code ->
                        val guidance = blockerGuidance(code)
                        Text(guidance.title, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
                        Text(guidance.nextStep, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        if (onResolveBlocker != null) TextButton(onClick = { onResolveBlocker(code) }) { Text(blockerActionLabel(code)) }
                    }
                }
            }
        }
        Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(14.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
            Row(Modifier.padding(horizontal = 14.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("本次工作台已保存", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodySmall)
                    Text("研究细则、证据与推理请在“研究”中查看。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                onViewHistory?.let { TextButton(onClick = it) { Text("历史") } }
                TextButton(onClick = { showAnalysisDetail = !showAnalysisDetail }) { Text(if (showAnalysisDetail) "收起详情" else "分析详情") }
            }
        }
        if (showAnalysisDetail) DecisionReportRoute(
            report = report,
            onOpenRules = onOpenRules,
            onResolveBlocker = onResolveBlocker,
        )
        Text("仅供研究和交易复核，不会自动执行真实交易。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun DecisionReportRoute(
    report: DecisionReportDto,
    onViewHistory: (() -> Unit)? = null,
    onOpenRules: (() -> Unit)? = null,
    onResolveBlocker: ((String) -> Unit)? = null,
) {
    // Gson assigns an explicit JSON null directly to Kotlin properties despite their
    // non-null declarations. Keep this report view resilient while older or partial
    // server responses are still present in the cache.
    val evidence = report.evidence.orEmpty()
    val actionCandidates = report.action_candidates.orEmpty()
    Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), shape = RoundedCornerShape(18.dp)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("本次决策报告", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text(
                "${decisionActionLabel(report.action)} · ${decisionStatusLabel(report.status)}",
                color = decisionActionColor(report.action), style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold,
            )
            Text(report.summary, style = MaterialTheme.typography.bodyMedium)
            Text("生成于 ${beijingTimestamp(report.generated_at)} · 策略 ${report.policy_version}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            report.market_change_percent?.let { change -> MarketMovementBadge(change, report.market_price, report.market_as_of) }

            actionCandidates.forEachIndexed { index, candidate ->
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                if (candidate.blocked_reasons.orEmpty().isNotEmpty()) {
                    Text(if (index == 0) "解除阻断" else "备选动作：${decisionActionLabel(candidate.action)}", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                    Text("本次未生成操作结论。请先完成以下项目，再重新分析。", style = MaterialTheme.typography.bodySmall)
                    candidate.blocked_reasons.orEmpty().forEach { code ->
                        val guidance = blockerGuidance(code)
                        Text(guidance.title, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
                        Text(guidance.nextStep, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        if (onResolveBlocker != null && code in setOf("trade_plan.enabled", "trade_plan.invalidation_price", "instrument.lot_size")) {
                            TextButton(onClick = { onResolveBlocker(code) }) { Text(blockerActionLabel(code)) }
                        }
                    }
                } else {
                    Text(if (index == 0) "首选规则候选" else "备选动作", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                    Text("${decisionActionLabel(candidate.action)} · 优先级 ${candidate.priority} · 规则评分 ${(candidate.policy_score * 100).toInt()}%", style = MaterialTheme.typography.bodySmall)
                    candidate.supporting_evidence_ids.orEmpty().mapNotNull { id -> evidence.firstOrNull { it.evidence_id == id }?.title }.takeIf { it.isNotEmpty() }?.let { Text("支持：${it.joinToString("、")}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    candidate.opposing_evidence_ids.orEmpty().mapNotNull { id -> evidence.firstOrNull { it.evidence_id == id }?.title }.takeIf { it.isNotEmpty() }?.let { Text("反对：${it.joinToString("、")}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                }
            }

            report.sizing?.let { sizing ->
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Text("仓位约束", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                val target = sizing.target_quantity ?: sizing.suggested_quantity
                Text(
                    if (target == null) "${sizingStatusLabel(sizing.status)}：当前 ${formatPositionValue(sizing.current_quantity)} 股，暂不提供数量建议。"
                    else "${sizingStatusLabel(sizing.status)}：当前 ${formatPositionValue(sizing.current_quantity)} 股，建议目标 ${formatPositionValue(target)} 股。",
                    style = MaterialTheme.typography.bodySmall,
                )
                sizing.current_position_percent?.let { Text("当前仓位 ${formatPositionValue(it)}%${sizing.target_position_percent?.let { targetPercent -> " · 目标 ${formatPositionValue(targetPercent)}%" } ?: ""}", style = MaterialTheme.typography.bodySmall) }
                listOfNotNull(
                    sizing.quantity_by_risk?.let { "风险上限 ${formatPositionValue(it)} 股" },
                    sizing.quantity_by_cash?.let { "资金上限 ${formatPositionValue(it)} 股" },
                    sizing.quantity_by_position_cap?.let { "仓位上限 ${formatPositionValue(it)} 股" },
                ).takeIf { it.isNotEmpty() }?.let { Text(it.joinToString(" · "), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                sizing.blocked_reasons.orEmpty().map(::blockerGuidance).forEach { guidance -> Text("需处理：${guidance.title}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
            }

            report.sizing?.blocked_reasons
                ?.filter { it in setOf("trade_plan.enabled", "trade_plan.invalidation_price", "instrument.lot_size") }
                ?.forEach { code ->
                    TextButton(onClick = { onResolveBlocker?.invoke(code) }) { Text(blockerActionLabel(code)) }
                }

            report.ai_assessment?.let { ai ->
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("AI 帮你读这份分析", modifier = Modifier.weight(1f), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                    AiSentimentBadge(ai.preferred_action, ai.thesis_status)
                }
                Text("原来的判断：${thesisStatusLabel(ai.thesis_status)} · 把握程度：${uncertaintyLabel(ai.uncertainty)}", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
                Text(ai.summary, style = MaterialTheme.typography.bodySmall)
                ai.reasoning_steps.orEmpty().forEach { step -> Text("${aiReasoningStageLabel(step.stage)}：${step.summary}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                ai.missing_evidence.orEmpty().forEach { missing -> Text("还需要确认：$missing", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                ai.rule_suggestions.orEmpty().forEach { suggestion ->
                    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
                        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text("AI 规则优化建议 · ${if (suggestion.scope == "symbol") suggestion.symbol ?: "个股" else "全局"}", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodySmall)
                            listOfNotNull(
                                suggestion.max_position_percent?.let { "单标的上限 ${formatPositionValue(it)}%" },
                                suggestion.loss_review_percent?.let { "亏损复核 ${formatPositionValue(it)}%" },
                                suggestion.volatility_review_percent?.let { "波动复核 ${formatPositionValue(it)}%" },
                            ).takeIf { it.isNotEmpty() }?.let { Text(it.joinToString(" · "), style = MaterialTheme.typography.labelSmall) }
                            Text(suggestion.rationale, style = MaterialTheme.typography.bodySmall)
                            Text("风险提示：${suggestion.risk_note}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text("这是待确认建议，请在规则页编辑后保存。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                            onOpenRules?.let { TextButton(onClick = it) { Text("查看并调整规则") } }
                        }
                    }
                }
            }
            if (report.ai_assessment == null) {
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Text("这次还没有 AI 解读", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                Text(decisionAiUnavailableMessage(report.ai_status, report.ai_error_code), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }

            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Text("关键证据", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            if (evidence.isEmpty()) Text("本次没有可展示的结构化证据。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            evidence.sortedByDescending { it.strength }.take(5).forEach { evidence ->
                Text("${evidenceDirectionLabel(evidence.direction)} ${evidence.title}", color = evidenceDirectionColor(evidence.direction), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
                Text(evidence.description, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            onViewHistory?.let { TextButton(onClick = it, modifier = Modifier.align(Alignment.End)) { Text("查看历史报告与回放") } }
            Text("报告仅用于研究与复核，不构成交易指令，也不会自动执行。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun AiSentimentBadge(action: String, thesisStatus: String) {
    val bullish = action in setOf("OPEN", "ADD") || thesisStatus == "strengthened"
    val bearish = action in setOf("REDUCE", "EXIT") || thesisStatus in setOf("weakened", "invalidated")
    val icon = when {
        bullish -> Icons.AutoMirrored.Filled.TrendingUp
        bearish -> Icons.AutoMirrored.Filled.TrendingDown
        else -> Icons.AutoMirrored.Filled.TrendingFlat
    }
    val label = when {
        bullish -> "AI 倾向：积极看涨"
        bearish -> "AI 倾向：谨慎看跌"
        else -> "AI 倾向：中性观察"
    }
    val color = when {
        bullish -> MaterialTheme.colorScheme.tertiary
        bearish -> MaterialTheme.colorScheme.error
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Row(
        modifier = Modifier.clip(RoundedCornerShape(10.dp)).background(color.copy(alpha = 0.12f)).padding(horizontal = 8.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, contentDescription = label, tint = color, modifier = Modifier.height(16.dp))
        Text(label, modifier = Modifier.padding(start = 4.dp), color = color, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun MarketMovementBadge(changePercent: Double, price: Double?, asOf: String?) {
    val rising = changePercent > 0
    val falling = changePercent < 0
    val icon = when {
        rising -> Icons.AutoMirrored.Filled.TrendingUp
        falling -> Icons.AutoMirrored.Filled.TrendingDown
        else -> Icons.AutoMirrored.Filled.TrendingFlat
    }
    val label = when {
        rising -> "上涨"
        falling -> "下跌"
        else -> "平稳"
    }
    val color = when {
        rising -> MaterialTheme.colorScheme.tertiary
        falling -> MaterialTheme.colorScheme.error
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Row(
        modifier = Modifier.clip(RoundedCornerShape(10.dp)).background(color.copy(alpha = 0.12f)).padding(horizontal = 10.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, contentDescription = "行情$label", tint = color, modifier = Modifier.height(18.dp))
        Text(
            "相对昨收$label ${if (changePercent > 0) "+" else ""}${formatPositionValue(changePercent)}%" +
                (price?.let { " · 现价 ${marketNumber(it)}" } ?: "") +
                (asOf?.take(10)?.let { " · $it" } ?: ""),
            modifier = Modifier.padding(start = 6.dp), color = color, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold,
        )
    }
}

private fun decisionAiUnavailableMessage(status: String?, errorCode: String?): String {
    val reason = when (errorCode) {
        "not_configured" -> "容器内没有读到 DEEPSEEK_API_KEY"
        "feature_disabled" -> "DECISION_AI_ENABLED 未开启"
        "http_error" -> "DeepSeek API 返回了 HTTP 错误（请查看后端日志中的状态码）"
        "transport_error" -> "服务器无法连接 DeepSeek API 或请求超时"
        "local_rate_limited" -> "本地 DeepSeek 并发已满"
        "circuit_open" -> "DeepSeek 连续失败后熔断器已开启"
        "invalid_response" -> "DeepSeek 返回结构无法解析"
        "empty_content" -> "DeepSeek 返回了空内容"
        "output_truncated" -> "DeepSeek 输出被截断"
        "invalid_ai_output" -> "AI 的回答格式或引用的数据对不上。本次已保留行情和规则核对结果；请稍后重新分析，AI 会按本次数据重新整理。"
        else -> when (status) {
            "disabled" -> "决策 AI 功能未开启"
            "skipped" -> "决策 AI 未满足调用条件"
            "failed" -> "决策 AI 调用失败，请查看后端 Decision AI 日志"
            else -> "后端未返回 AI 运行状态；请在升级服务后重新生成报告"
        }
    }
    return "当前结论仍可参考已核对的数据和规则。$reason"
}

@Composable
private fun DecisionHistoryDialog(symbol: String, onDismiss: () -> Unit) {
    val api = ApiClient.service(LocalContext.current)
    var reports by remember(symbol) { mutableStateOf<List<DecisionReportDto>>(emptyList()) }
    var loading by remember(symbol) { mutableStateOf(true) }
    var error by remember(symbol) { mutableStateOf<String?>(null) }
    var selectedId by remember(symbol) { mutableStateOf<String?>(null) }
    LaunchedEffect(symbol) {
        runCatching { api.decisionHistory(symbol) }
            .onSuccess { reports = it; selectedId = null }
            .onFailure { error = "无法读取历史报告：${it.message ?: "请稍后重试"}" }
        loading = false
    }
    Dialog(onDismissRequest = onDismiss) {
        Surface(Modifier.fillMaxWidth().heightIn(max = 760.dp), shape = RoundedCornerShape(18.dp)) {
            Column(Modifier.padding(18.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) { Text("决策历史 · ${reports.firstOrNull()?.name?.takeIf { it.isNotBlank() } ?: symbol}", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold); Text("每次报告保留独立输入快照，不会覆盖旧记录。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    IconButton(onClick = onDismiss) { Icon(Icons.Filled.Close, "关闭") }
                }
                if (loading) Text("正在读取历史报告…", Modifier.padding(vertical = 20.dp))
                error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(vertical = 20.dp)) }
                if (!loading && error == null) LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(reports, key = { it.decision_id }) { report ->
                        val selected = report.decision_id == selectedId
                        OutlinedButton(onClick = { selectedId = if (selected) null else report.decision_id }, modifier = Modifier.fillMaxWidth(), colors = ButtonDefaults.outlinedButtonColors(containerColor = if (selected) MaterialTheme.colorScheme.primaryContainer else Color.Transparent)) {
                            Column(Modifier.fillMaxWidth()) { Text("${decisionActionLabel(report.action)} · ${decisionStatusLabel(report.status)}", fontWeight = FontWeight.SemiBold); Text("${beijingTimestamp(report.generated_at)} · ${if (selected) "收起详情" else "查看摘要与证据"}", style = MaterialTheme.typography.labelSmall) }
                        }
                        if (selected) DecisionReportRoute(report)
                    }
                    if (reports.isEmpty()) item { Text("尚无历史报告。请先在“今日”发起主动分析。", style = MaterialTheme.typography.bodySmall) }
                }
            }
        }
    }
}

private fun decisionActionLabel(action: String): String = when (action) {
    "OPEN" -> "建立仓位候选"; "ADD" -> "加仓候选"; "HOLD" -> "持有"; "WATCH" -> "观察"; "REDUCE" -> "减仓复核"; "EXIT" -> "退出复核"; "BLOCKED" -> "暂不生成结论"; else -> action
}

@Composable
private fun decisionActionColor(action: String): Color = when (action) {
    "REDUCE", "EXIT", "BLOCKED" -> MaterialTheme.colorScheme.error
    "ADD", "OPEN" -> MaterialTheme.colorScheme.tertiary
    else -> MaterialTheme.colorScheme.primary
}

private fun decisionStatusLabel(status: String): String = when (status) { "READY" -> "数据可用"; "DEGRADED" -> "数据需留意"; "BLOCKED" -> "数据阻断"; else -> status }
private fun sizingStatusLabel(status: String): String = when (status) { "ready" -> "测算完成"; "blocked" -> "测算受阻"; "not_applicable" -> "当前不适用"; else -> status }
private fun thesisStatusLabel(status: String): String = when (status) { "strengthened" -> "强化"; "unchanged" -> "维持"; "weakened" -> "削弱"; "invalidated" -> "失效"; else -> "待判断" }
private fun uncertaintyLabel(level: String): String = when (level) { "low" -> "低"; "medium" -> "中"; "high" -> "高"; else -> level }
private fun aiReasoningStageLabel(stage: String): String = when (stage) { "evidence" -> "证据权衡"; "conflict" -> "冲突识别"; "uncertainty" -> "不确定性"; else -> stage }
private fun evidenceDirectionLabel(direction: String): String = when (direction) { "positive" -> "支持"; "negative" -> "反对"; "uncertain" -> "不确定"; else -> "中性" }
@Composable
private fun evidenceDirectionColor(direction: String): Color = when (direction) { "negative" -> MaterialTheme.colorScheme.error; "positive" -> MaterialTheme.colorScheme.tertiary; else -> MaterialTheme.colorScheme.onSurfaceVariant }
private data class BlockerGuidance(val title: String, val nextStep: String)
private fun normalizedBlockerCode(code: String) = code.substringBefore(" unavailable").trim().lowercase()
private fun blockerTarget(code: String): String = when (normalizedBlockerCode(code)) {
    "instrument.lot_size" -> "instrument"
    "trade_plan.enabled", "trade_plan.invalidation_price", "trade_plan.auto_draft" -> "plan"
    else -> "portfolio"
}
private fun blockerActionLabel(code: String): String = when (blockerTarget(code)) {
    "instrument" -> "填写交易单位"
    "plan" -> "填写交易计划"
    else -> "前往持仓处理"
}
private fun blockerGuidance(code: String): BlockerGuidance = when (normalizedBlockerCode(code)) {
    "trade_plan.enabled" -> BlockerGuidance("缺少已启用的交易计划", "前往“管理”→“交易计划”，为该标的新增或启用计划，并填写入场、加仓、减仓、退出条件、仓位上限和风险预算；保存后回到此页重新分析。")
    "trade_plan.auto_draft" -> BlockerGuidance("交易计划尚未准备好", "前往“管理”→“交易计划”，补充入场、加仓、减仓和退出条件后保存。")
    "trade_plan.invalidation_price" -> BlockerGuidance("缺少失效价", "前往“管理”→“交易计划”，填写本次判断失效时的价格，再重新生成工作台。")
    "quote.price" -> BlockerGuidance("缺少可用行情价格", "前往“持仓”刷新行情；若仍失败，请核对证券代码、网络连接和行情服务状态。")
    "daily_bars.minimum_60" -> BlockerGuidance("需要补齐近期日线数据", "前往“持仓”刷新行情与日线数据；数据补齐后，重新生成工作台。")
    "risk" -> BlockerGuidance("风险数据暂不可用", "前往“持仓”刷新行情和日线；系统会据此重新计算风险数据。")
    "events" -> BlockerGuidance("事件信息暂不可用", "前往“持仓”刷新行情；稍后重新分析即可补充最新事件信息。")
    "account.total_assets" -> BlockerGuidance("无法计算组合总资产", "请确认所有持仓均有可用行情，并在“持仓”页录入可用资金；随后重新刷新行情。")
    else -> BlockerGuidance("需要更新分析所需数据", "前往“持仓”刷新行情并核对持仓资料；完成后重新生成工作台。")
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

private fun hasClockTime(value: String?): Boolean =
    !value.isNullOrBlank() && Regex("\\d{1,2}:\\d{2}(?::\\d{2})?").containsMatchIn(value)

private fun quoteTimeLabel(quote: MarketQuoteDto): String {
    val asOf = quote.as_of?.takeIf { it.isNotBlank() }
    return when {
        hasClockTime(asOf) -> "\u884c\u60c5\u65f6\u523b ${beijingTimestamp(asOf)}"
        asOf != null -> "\u884c\u60c5\u4ea4\u6613\u65e5 ${asOf.take(10)} \u00b7 \u7cfb\u7edf\u6293\u53d6 ${beijingTimestamp(quote.retrieved_at)}"
        else -> "\u6570\u636e\u6e90\u672a\u7ed9\u51fa\u884c\u60c5\u65f6\u523b \u00b7 \u7cfb\u7edf\u6293\u53d6 ${beijingTimestamp(quote.retrieved_at)}"
    }
}

private fun currentBeijingDate(): String = LocalDate.now(ZoneOffset.ofHours(8)).toString()

private fun todaySnapshotBar(bars: List<DailyPriceDto>, quote: MarketQuoteDto?): List<DailyPriceDto> {
    val price = quote?.price ?: return bars
    val quoteDay = quote.as_of?.let(::marketDate)?.toString() ?: return bars
    if (quoteDay != currentBeijingDate()) return bars
    val opening = quote.open ?: quote.previous_close ?: price
    val snapshot = DailyPriceDto(
        trading_date = quoteDay, open = opening, close = price,
        high = quote.high ?: maxOf(opening, price), low = quote.low ?: minOf(opening, price),
        volume = quote.volume, amount = quote.amount, turnover_rate = quote.turnover_rate,
        adjustment = "intraday_snapshot", source = quote.source,
    )
    return when {
        bars.lastOrNull()?.trading_date == quoteDay -> bars.dropLast(1) + snapshot
        bars.lastOrNull()?.trading_date.orEmpty() < quoteDay -> bars + snapshot
        else -> bars
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


        val marketTimeText = quoteTimeLabel(quote)


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
            HoldingMetric("换手率", quote.turnover_rate?.let { "%.2f%%".format(it) } ?: "--", Modifier.weight(1f))
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
            if (assessment.status == "data_insufficient") {
                Text(assessment.message, style = MaterialTheme.typography.bodySmall)
            } else {
                Text("历史下行概率 ${assessment.historical_downside_probability}% · 年化波动 ${assessment.annualized_volatility_percent}%")
                Text("口径：${assessment.horizon_trading_days} 个交易日累计跌幅 ≥ ${assessment.downside_threshold_percent}%；样本 ${assessment.sample_count} 个，置信度 ${assessment.confidence}。", style = MaterialTheme.typography.bodySmall)
                Text(assessment.explanation, style = MaterialTheme.typography.bodySmall)
            }
            Text(assessment.disclaimer, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun PortfolioAnalysisCard(item: PortfolioAnalysisItemDto) = Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("${item.name} · ${analysisActionLabel(item.action)}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text("证据置信度 ${item.confidence_percent}%", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall)
        ExplainableText(item.reason)
        item.technical_snapshot?.let { TechnicalSnapshotSummary(it) }
        item.evidence.forEach { ExplainableText("• $it", style = MaterialTheme.typography.bodySmall) }
        Text(item.disclaimer, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun TechnicalSnapshotSummary(snapshot: TechnicalSnapshotDto, detailed: Boolean = false) {
    var lookupTerm by remember { mutableStateOf<String?>(null) }
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
        ExplainableText(snapshot.summary, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TechnicalMetric("MA20", "${marketNumber(snapshot.sma20)}\n${signedPercent(snapshot.sma20_distance_percent)}", Modifier.weight(1f)) { lookupTerm = "MA20" }
            TechnicalMetric("MA60", "${marketNumber(snapshot.sma60)}\n${signedPercent(snapshot.sma60_distance_percent)}", Modifier.weight(1f)) { lookupTerm = "MA60" }
            TechnicalMetric("RSI(14)", "${snapshot.rsi14}\n${snapshot.rsi_state}", Modifier.weight(1f)) { lookupTerm = "RSI" }
        }
        if (detailed) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TechnicalMetric("MACD 柱", "${snapshot.macd_histogram}\n${snapshot.macd_state}", Modifier.weight(1f)) { lookupTerm = "MACD" }
                TechnicalMetric("ATR(14)", "${snapshot.atr14}\n占收盘 ${snapshot.atr_percent}%", Modifier.weight(1f)) { lookupTerm = "ATR" }
                TechnicalMetric("60日回撤", "${snapshot.drawdown_60d_percent}%\n${snapshot.sample_count} 日样本", Modifier.weight(1f)) { lookupTerm = "回撤" }
            }
        }
        Text(
            "均线距离为收盘价相对均线的偏离；指标描述历史价格状态，不代表未来涨跌。",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
    lookupTerm?.let { term -> GlossaryLookupDialog(term = term, onDismiss = { lookupTerm = null }) }
}

@Composable
private fun UpdateDownloadProgressCard(progress: UpdateDownloadProgress, modifier: Modifier = Modifier) {
    val progressText = progress.fraction?.let { " ${(it * 100).toInt()}%" }.orEmpty()
    val sizeText = if (progress.totalBytes > 0) {
        " · ${formatDownloadSize(progress.downloadedBytes)} / ${formatDownloadSize(progress.totalBytes)}"
    } else if (progress.downloadedBytes > 0) {
        " · 已下载 ${formatDownloadSize(progress.downloadedBytes)}"
    } else {
        ""
    }
    Card(modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("${progress.message}$progressText$sizeText", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
            if (progress.fraction != null) {
                LinearProgressIndicator(progress = { progress.fraction }, modifier = Modifier.fillMaxWidth())
            } else if (progress.state.isActive) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }
        }
    }
}

@Composable
private fun UpdatePromptDialog(
    update: AppUpdate,
    progress: UpdateDownloadProgress?,
    status: String?,
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
) {
    Dialog(onDismissRequest = onDismiss) {
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(24.dp),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 6.dp,
        ) {
            Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Surface(
                        shape = RoundedCornerShape(14.dp),
                        color = MaterialTheme.colorScheme.primaryContainer,
                    ) {
                        Icon(
                            Icons.Filled.SystemUpdateAlt,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onPrimaryContainer,
                            modifier = Modifier.padding(12.dp),
                        )
                    }
                    Column(Modifier.padding(start = 14.dp).weight(1f)) {
                        Text("新版本可用", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                        Text("Third-Hand ${update.versionName}", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                        Text("${formatDownloadSize(update.sizeBytes)} · 构建 ${update.versionCode}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("本次更新", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                    Text(update.changelog.ifBlank { "优化使用体验与稳定性。" }, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                progress?.let { UpdateDownloadProgressCard(it) }
                status?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = if (isUpdateStatusError(it)) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Button(
                    onClick = onConfirm,
                    enabled = progress?.state?.isActive != true,
                    modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
                ) {
                    Icon(Icons.Filled.CloudDownload, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(if (AppUpdateManager.hasCompletedDownload(LocalContext.current, update)) "安装更新" else "后台下载")
                }
                TextButton(onClick = onDismiss, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("稍后提醒") }
                Text("下载期间可继续使用；安装时由 Android 系统再次确认。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
            }
        }
    }
}

@Composable
private fun UpdateCenterCard(
    update: AppUpdate?,
    progress: UpdateDownloadProgress?,
    status: String?,
    checking: Boolean,
    automaticDownload: Boolean,
    onAutomaticDownloadChange: (Boolean) -> Unit,
    onCheck: () -> Unit,
    onInstall: () -> Unit,
) {
    val context = LocalContext.current
    val ready = update?.let { AppUpdateManager.hasCompletedDownload(context, it) } == true
    val headline = when {
        ready -> "更新已准备好"
        progress?.state?.isActive == true -> progress.message
        update != null -> "发现 ${update.versionName}"
        status == "已是最新版本" -> "已是最新版本"
        else -> "保持应用最新"
    }
    Card(
        modifier = Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Surface(shape = RoundedCornerShape(12.dp), color = MaterialTheme.colorScheme.primaryContainer) {
                    Icon(
                        if (ready) Icons.Filled.CheckCircle else Icons.Filled.SystemUpdateAlt,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.onPrimaryContainer,
                        modifier = Modifier.padding(10.dp),
                    )
                }
                Column(Modifier.padding(start = 12.dp).weight(1f)) {
                    Text("应用更新", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(headline, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                }
                Surface(shape = RoundedCornerShape(50), color = MaterialTheme.colorScheme.surface) {
                    Text("v${BuildConfig.VERSION_NAME}", modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp), style = MaterialTheme.typography.labelMedium)
                }
            }
            progress?.let { UpdateDownloadProgressCard(it) }
            if (ready) {
                Button(onClick = onInstall, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                    Icon(Icons.Filled.SystemUpdateAlt, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("前往系统安装 ${update?.versionName.orEmpty()}")
                }
                Text(
                    "在系统安装完成页点击“打开”，即可直接启动新版应用。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                )
            } else {
                OutlinedButton(onClick = onCheck, enabled = !checking, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                    Icon(Icons.Filled.Refresh, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(if (checking) "正在检查…" else "检查更新")
                }
            }
            status?.takeUnless { progress != null || ready }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = if (isUpdateStatusError(it)) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Wi‑Fi 下自动下载", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                    Text("默认开启，下载完成后由你确认安装", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Switch(checked = automaticDownload, onCheckedChange = onAutomaticDownloadChange)
            }
        }
    }
}

private fun formatDownloadSize(bytes: Long): String = when {
    bytes >= 1024 * 1024 -> "%.1f MB".format(bytes / 1024.0 / 1024.0)
    bytes >= 1024 -> "%.0f KB".format(bytes / 1024.0)
    else -> "$bytes B"
}

private fun isUpdateStatusError(status: String): Boolean =
    status.contains("失败") || status.contains("不可用") || status.contains("无法")

private fun installResultMessage(result: UpdateLaunchResult, context: android.content.Context): String = when (result) {
    UpdateLaunchResult.INSTALLER_OPENED -> "已进入系统安装页；安装完成后点击“打开”即可直接进入新版"
    UpdateLaunchResult.NEED_INSTALL_PERMISSION -> "请允许“安装未知应用”后返回，再次点击安装"
    UpdateLaunchResult.SIGNATURE_MISMATCH -> AppUpdateManager.completedUpdateMessage(context) ?: "安装包签名不一致"
    UpdateLaunchResult.DOWNLOAD_UNAVAILABLE -> "安装包不可用，请重新检查更新"
    else -> "新版本已下载，点击安装"
}

@Composable
private fun TechnicalMetric(label: String, value: String, modifier: Modifier = Modifier, onLookup: (() -> Unit)? = null) {
    var lookupTerm by remember(label) { mutableStateOf<String?>(null) }
    val indexedTerm = explainableTerms.firstOrNull { label.contains(it, ignoreCase = true) }
    Column(modifier, verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(
            label,
            modifier = if (onLookup != null || indexedTerm != null) Modifier.clickable(onClick = { onLookup?.invoke() ?: run { lookupTerm = indexedTerm } }) else Modifier,
            style = MaterialTheme.typography.labelSmall,
            color = if (onLookup != null || indexedTerm != null) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
            textDecoration = if (onLookup != null || indexedTerm != null) TextDecoration.Underline else TextDecoration.None,
        )
        Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
    }
    lookupTerm?.let { term -> GlossaryLookupDialog(term = term, onDismiss = { lookupTerm = null }) }
}

private fun signedPercent(value: Double): String = "${if (value >= 0) "+" else ""}${"%.1f".format(value)}%"

private val starterGlossaryTerms = listOf(
    "空头排列", "多头排列", "量价背离", "市盈率", "波动率",
    "历史下行概率", "年化波动", "中期复核", "波动复核", "亏损复核", "技术面中期偏强", "研究候选方案",
    "MA20", "MA60", "RSI", "MACD", "ATR", "回撤", "减持", "回购", "PE",
    "中期偏弱", "现价相对成本", "亏损复核阈值", "波动复核阈值", "证据完整度", "数据不足", "风险复核", "等待确认",
    "RSI偏热", "RSI偏冷", "MACD动能", "ATR/收盘价", "60日回撤",
).sortedByDescending { it.length }

private val explainableTerms: List<String>
    get() = (starterGlossaryTerms + savedGlossaryTerms).distinct().sortedByDescending { it.length }

private fun glossaryTermAt(text: String, offset: Int): String? = explainableTerms.firstOrNull { term ->
    var start = text.indexOf(term, ignoreCase = true)
    while (start >= 0) {
        if (offset in start until (start + term.length)) return@firstOrNull true
        start = text.indexOf(term, start + term.length, ignoreCase = true)
    }
    false
}

private fun phraseAt(text: String, offset: Int): String? {
    if (text.isEmpty() || offset !in text.indices) return null
    val separators = "，。；：、,.!?！？()（）[]【】\n"
    var start = offset
    var end = offset + 1
    while (start > 0 && text[start - 1] !in separators && end - start < 24) start--
    while (end < text.length && text[end] !in separators && end - start < 24) end++
    return text.substring(start, end).trim().takeIf { it.length in 2..24 }
}

/** Long-press an indexed financial term to open its explanation without leaving the current page. */
@Composable
private fun ExplainableText(
    text: String,
    modifier: Modifier = Modifier,
    style: TextStyle = MaterialTheme.typography.bodyMedium,
    color: Color = MaterialTheme.colorScheme.onSurface,
    fontWeight: FontWeight? = null,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
) {
    var layoutResult by remember(text) { mutableStateOf<androidx.compose.ui.text.TextLayoutResult?>(null) }
    var lookupTerm by remember { mutableStateOf<String?>(null) }
    val annotated = remember(text) {
        buildAnnotatedString {
            append(text)
            explainableTerms.forEach { term ->
                var start = text.indexOf(term, ignoreCase = true)
                while (start >= 0) {
                    addStyle(SpanStyle(textDecoration = TextDecoration.Underline), start, start + term.length)
                    start = text.indexOf(term, start + term.length, ignoreCase = true)
                }
            }
        }
    }
    Text(
        text = annotated,
        modifier = modifier.pointerInput(text) {
            detectTapGestures(onTap = { position ->
                layoutResult?.getOffsetForPosition(position)?.let { offset -> (glossaryTermAt(text, offset) ?: phraseAt(text, offset))?.let { lookupTerm = it } }
            }, onLongPress = { position ->
                layoutResult?.getOffsetForPosition(position)?.let { offset ->
                    (glossaryTermAt(text, offset) ?: phraseAt(text, offset))?.let { lookupTerm = it }
                }
            })
        },
        style = style,
        color = color,
        fontWeight = fontWeight,
        maxLines = maxLines,
        overflow = overflow,
        onTextLayout = { layoutResult = it },
    )
    lookupTerm?.let { term -> GlossaryLookupDialog(term = term, onDismiss = { lookupTerm = null }) }
}

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
    shape = MaterialTheme.shapes.medium,
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
    modifier = Modifier.padding(horizontal = 14.dp).fillMaxWidth(),
    shape = MaterialTheme.shapes.medium,
    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
    elevation = CardDefaults.cardElevation(defaultElevation = com.thirdhand.app.ui.theme.AppElevation.raised),
) {
    val statusText = when (draft.lookup_status.orEmpty()) {
        "pending", "querying" -> "查询中"
        "matched" -> "待确认"
        "failed" -> "查询失败"
        "not_found" -> "未找到"
        else -> "待补全"
    }
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
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
            TextButton(onClick = onComplete, colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.secondary)) {
                Icon(Icons.Filled.Search, null)
                Spacer(Modifier.width(4.dp))
                Text(if (draft.lookup_status == "matched") "核对并确认" else "补全代码")
            }
            Spacer(Modifier.weight(1f))
            TextButton(onClick = onDelete, colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)) { Text("删除") }
        }
    }
}

@Composable
private fun SaleHistoryScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val api = remember { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var sales by remember { mutableStateOf<List<SaleRecordDto>>(emptyList()) }
    var query by remember { mutableStateOf("") }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    fun load() = scope.launch {
        loading = true; error = null
        runCatching { api.sales(query.trim().ifBlank { null }) }
            .onSuccess { sales = it }
            .onFailure { error = "无法读取出售历史，请检查服务连接。" }
        loading = false
    }
    LaunchedEffect(Unit) { load() }
    LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { AppHero("出售历史", "按股票代码查询每笔已完成的出售", action = { HeroRefreshAction(::load, !loading) }) }
        item { Row(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null); Text("返回管理") }
        } }
        item { Row(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(query, { query = it.uppercase() }, label = { Text("股票代码（可选）") }, singleLine = true, modifier = Modifier.weight(1f))
            Button(onClick = ::load, enabled = !loading) { Text("查询") }
        } }
        error?.let { item { StatusCard(it, error = true) } }
        if (loading) item { StatusCard("正在读取出售记录…") }
        if (!loading && sales.isEmpty()) item { StatusCard(if (query.isBlank()) "还没有出售记录。" else "未找到该股票的出售记录。") }
        items(sales, key = { it.id }) { sale ->
            Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) { Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("${sale.name} · ${sale.symbol}", fontWeight = FontWeight.SemiBold)
                    Text(signedPositionValue(sale.realized_pnl), color = if (sale.realized_pnl >= 0) Color(0xFFD32F2F) else Color(0xFF178A4B), fontWeight = FontWeight.Bold)
                }
                Text("${beijingTimestamp(sale.sold_at)} · ${sale.quantity} 股 × ${formatPositionValue(sale.sale_price)}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (sale.reason.isNotBlank()) Text(sale.reason, style = MaterialTheme.typography.bodySmall)
            } }
        }
    }
}

@Composable
private fun LegacyStockDetailScreen(target: ResearchTargetDto, onBack: () -> Unit, onResearch: (ResearchTargetDto) -> Unit) {
    val context = LocalContext.current
    val api = remember { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    val uriHandler = LocalUriHandler.current
    var quote by remember(target.symbol) { mutableStateOf<MarketQuoteDto?>(null) }
    var history by remember(target.symbol) { mutableStateOf<List<DailyPriceDto>>(emptyList()) }
    var sales by remember(target.symbol) { mutableStateOf<List<SaleRecordDto>>(emptyList()) }
    var content by remember(target.symbol) { mutableStateOf<List<NewsItemDto>>(emptyList()) }
    var contentDialogOpen by remember(target.symbol) { mutableStateOf(false) }
    var risk by remember(target.symbol) { mutableStateOf<RiskAssessmentDto?>(null) }
    var settingsDialogOpen by remember(target.symbol) { mutableStateOf(false) }
    var riskDialogOpen by remember(target.symbol) { mutableStateOf(false) }
    var error by remember(target.symbol) { mutableStateOf<String?>(null) }
    var clearHistoryRequested by remember(target.symbol) { mutableStateOf(false) }
    fun load() = scope.launch {
        error = null
        runCatching { ApiClient.latestMarketQuotes(api, listOf(target.symbol)) }
            .onSuccess { quote = it.firstOrNull() }
            .onFailure { error = "无法读取股票详情，请检查服务连接。" }
        history = runCatching { api.marketHistory(target.symbol, 30) }.getOrDefault(emptyList())
        sales = runCatching { api.sales(target.symbol) }.getOrDefault(emptyList())
        risk = runCatching { api.riskAssessments().firstOrNull { it.symbol == target.symbol } }.getOrNull()
        content = (runCatching { api.announcements(listOf(target.symbol)) }.getOrDefault(emptyList()) + runCatching { api.feed(listOf(target.symbol)) }.getOrDefault(emptyList())).distinctBy { it.id }.sortedByDescending { it.published_at }
    }
    LaunchedEffect(target.symbol) { load() }
    LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { AppHero(target.name, "${target.symbol} · ${watchlistStatusLabel(target.status)}", action = { HeroRefreshAction(::load, false) }) }
        item { Row(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null); Text("返回自选") }
            Spacer(Modifier.weight(1f))
            Button(onClick = { onResearch(target) }) { Icon(Icons.Filled.AutoGraph, null); Spacer(Modifier.width(6.dp)); Text("AI 分析") }
        } }
        item { Row(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilledTonalButton(onClick = { riskDialogOpen = true }, modifier = Modifier.weight(1f)) { Text("风险分析") }
            FilledTonalButton(onClick = { settingsDialogOpen = true }, modifier = Modifier.weight(1f)) { Text("配置与计划") }
        } }
        error?.let { item { StatusCard(it, error = true) } }
        item { Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) { Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("最新行情", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text(quote?.price?.let { formatPositionValue(it) } ?: "暂未获取", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Text(quote?.let { "${it.source} · ${it.freshness_note}" } ?: "行情正在准备中", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        } } }
        item { Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) { Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("日线 K 线", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                TextButton(onClick = { clearHistoryRequested = true }, enabled = history.isNotEmpty()) { Text("清理缓存") }
            }
            if (history.size < 2) Text("日线数据正在准备中；清理后会由后台重新拉取。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            else KLineChart(history.takeLast(60))
        } } }
        if (content.isNotEmpty()) item { Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth().clickable { contentDialogOpen = true }, colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) { Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text("新闻与公告 · ${content.size} 条", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            Text(content.first().explanation.ifBlank { content.first().title }, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall)
            content.first().ai_analysis?.get("summary")?.let { Text("AI：$it", maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary) }
            Text("点击查看新闻列表与原文", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
        } } }
        item { Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) { Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("出售历史", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            if (sales.isEmpty()) Text("暂无出售记录。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            else sales.take(5).forEach { sale -> Text("${beijingTimestamp(sale.sold_at)} · ${sale.quantity} 股 · ${signedPositionValue(sale.realized_pnl)}", style = MaterialTheme.typography.bodySmall) }
        } } }
    }
    if (clearHistoryRequested) AlertDialog(
        onDismissRequest = { clearHistoryRequested = false },
        title = { Text("清理 ${target.name} 的日线缓存？") },
        text = { Text("仅删除本地缓存的日线数据，不会删除持仓、自选或成交记录。下次刷新会重新从行情源获取。") },
        confirmButton = { Button(onClick = { scope.launch {
            runCatching { api.deleteMarketHistory(target.symbol) }
                .onSuccess { history = emptyList(); clearHistoryRequested = false; load() }
                .onFailure { error = "清理日线缓存失败，请稍后重试。" }
        } }) { Text("确认清理") } },
        dismissButton = { TextButton(onClick = { clearHistoryRequested = false }) { Text("取消") } },
    )
    if (contentDialogOpen) AlertDialog(
        onDismissRequest = { contentDialogOpen = false },
        title = { Text("新闻与公告") },
        text = { Text(content.take(8).joinToString("\n\n") { "${it.title}\n${it.explanation}" }) },
        confirmButton = { TextButton(onClick = { contentDialogOpen = false }) { Text("关闭") } },
        dismissButton = { TextButton(onClick = { content.firstOrNull()?.let { uriHandler.openUri(it.source_url) } }) { Text("查看首条原文") } },
    )
    if (riskDialogOpen) AlertDialog(onDismissRequest = { riskDialogOpen = false }, title = { Text("风险分析") }, text = { Text(risk?.let { if (it.status == "data_insufficient") it.message else "风险等级：${it.risk_level}\n下行概率：${it.historical_downside_probability}%\n年化波动：${it.annualized_volatility_percent}%\n${it.explanation}" } ?: "暂未生成风险评估。") }, confirmButton = { TextButton(onClick = { riskDialogOpen = false }) { Text("关闭") } })
    if (settingsDialogOpen) AlertDialog(onDismissRequest = { settingsDialogOpen = false }, title = { Text("配置与计划") }, text = { Text("交易计划、持仓编辑与出售操作集中在持仓详情中管理；AI 分析请使用上方统一研究会话入口。") }, confirmButton = { TextButton(onClick = { settingsDialogOpen = false }) { Text("关闭") } })
}

/**
 * Kept as the navigation entry point while the decision workspace lives in its
 * own feature file.  The legacy implementation above remains available as a
 * reference during this incremental refactor.
 */
@Composable
private fun StockDetailScreen(target: ResearchTargetDto, onBack: () -> Unit, onResearch: (ResearchTargetDto) -> Unit) {
    StockDetailDecisionRoute(target = target, onBack = onBack, onResearch = onResearch)
}

/** Common entry point for a stock opened from either self-select or holdings. */
@Composable
private fun HoldingSummaryDetailScreen(
    target: ResearchTargetDto,
    holding: HoldingDto?,
    onBack: () -> Unit,
    onResearch: (ResearchTargetDto) -> Unit,
) {
    // The selected holding only changes the identity summary; market and AI
    // capability is intentionally shared with self-selected securities.
    StockDetailScreen(target, onBack, onResearch)
}

@Composable
private fun WatchlistScreen(onOpenDetail: (ResearchTargetDto) -> Unit, onResearch: (ResearchTargetDto) -> Unit) {
    val context = LocalContext.current
    val api = remember { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var targets by remember { mutableStateOf<List<ResearchTargetDto>>(emptyList()) }
    var selectedTarget by remember { mutableStateOf<ResearchTargetDto?>(null) }
    var sales by remember { mutableStateOf<List<SaleRecordDto>>(emptyList()) }
    var showAdd by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    fun refresh() = scope.launch {
        try {
            targets = api.researchTargets()
            error = null
        } catch (_: Exception) {
            error = "读取自选股失败，请确认服务正在运行。"
        }
    }
    fun openDetail(target: ResearchTargetDto) {
        selectedTarget = target
        scope.launch {
            sales = try { api.sales(target.symbol) } catch (_: Exception) { emptyList() }
        }
    }

    LaunchedEffect(Unit) { refresh() }
    LazyColumn(
        contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item { AppHero("自选股", "持仓自动同步；持续关注的标的和已清仓股票都在这里") }
        item {
            Row(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("${targets.size} 只关注标的", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text("可直接发起 AI 分析；AI 会结合持仓成本、入手时间和卖出记录。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                TextButton(onClick = { showAdd = true }) { Icon(Icons.Filled.Add, null); Text("添加") }
            }
        }
        if (targets.isEmpty()) item {
            StatusCard("还没有自选股。添加关注股票或录入持仓后，会自动显示在这里。")
        }
        items(targets, key = { "watchlist-target-${it.symbol}" }) { target ->
            WatchlistTableRow(target, onOpenDetail = { onOpenDetail(target) }, onResearch = { onResearch(target) })
        }
        error?.let { item { StatusCard(it, error = true) } }
    }
    if (showAdd) WatchlistDialog(
        onDismiss = { showAdd = false },
        onSave = { item -> scope.launch {
            try { api.saveWatchlistItem(item); showAdd = false; refresh() }
            catch (_: Exception) { error = "保存自选股失败，请稍后重试。" }
        } },
    )
    selectedTarget?.let { target -> AlertDialog(
        onDismissRequest = { selectedTarget = null },
        title = { Text("${target.name} · ${target.symbol}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("当前状态：${watchlistStatusLabel(target.status)}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                Text("历史成交", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                if (sales.isEmpty()) Text("暂无卖出或清仓记录。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                sales.take(5).forEach { sale ->
                    Text("${beijingTimestamp(sale.sold_at)} · 卖出 ${sale.quantity} · 已实现 ${signedPositionValue(sale.realized_pnl)}", style = MaterialTheme.typography.bodySmall)
                }
            }
        },
        confirmButton = { Button(onClick = { selectedTarget = null; onResearch(target) }) { Text("AI 分析") } },
        dismissButton = { TextButton(onClick = { selectedTarget = null }) { Text("关闭") } },
    ) }
}

@Composable
private fun WatchlistTableRow(
    target: ResearchTargetDto,
    onOpenDetail: () -> Unit,
    onResearch: () -> Unit,
) {
    Row(
        Modifier.fillMaxWidth()
            .clickable(onClick = onOpenDetail)
            .padding(horizontal = 20.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            if (target.status == "active_holding") Icons.Filled.Wallet else Icons.Filled.Bookmark,
            contentDescription = watchlistStatusLabel(target.status),
            tint = MaterialTheme.colorScheme.primary,
        )
        Column(Modifier.padding(start = 12.dp).weight(1f)) {
            Text(target.name, maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyLarge)
            Text("${target.symbol} · ${watchlistStatusLabel(target.status)}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        TextButton(onClick = onResearch) { Text("AI 分析") }
        Icon(Icons.Filled.ChevronRight, contentDescription = "打开 ${target.name}", tint = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    HorizontalDivider(Modifier.padding(start = 20.dp), color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = .65f))
}

private fun watchlistStatusLabel(status: String) = when (status) {
    "active_holding" -> "持仓中"
    "closed_position" -> "已清仓，持续跟踪"
    else -> "关注中"
}

@Composable
private fun HoldingsScreen(onOpenDetail: (HoldingDto) -> Unit) {
    val context = LocalContext.current
    val api = ApiClient.service(context)
    var holdings by remember { mutableStateOf<List<HoldingDto>>(emptyList()) }
    var watchlist by remember { mutableStateOf<List<WatchlistItemDto>>(emptyList()) }
    var sales by remember { mutableStateOf<List<SaleRecordDto>>(emptyList()) }
    var drafts by remember { mutableStateOf<List<HoldingDraftDto>>(emptyList()) }
    var quotesBySymbol by remember { mutableStateOf<Map<String, MarketQuoteDto>>(emptyMap()) }
    var analysisBySymbol by remember { mutableStateOf<Map<String, PortfolioAnalysisItemDto>>(emptyMap()) }
    var analysisRun by remember { mutableStateOf<PortfolioAnalysisDto?>(null) }
    var availableCash by remember { mutableStateOf<AvailableCashDto?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var quoteError by remember { mutableStateOf<String?>(null) }
    var showAdd by remember { mutableStateOf(false) }
    var showWatchlistAdd by remember { mutableStateOf(false) }
    var showCashEditor by remember { mutableStateOf(false) }
    var editingDraft by remember { mutableStateOf<HoldingDraftDto?>(null) }
    var editingHolding by remember { mutableStateOf<HoldingDto?>(null) }
    var revealedHoldingId by remember { mutableStateOf<String?>(null) }
    var deleteCandidate by remember { mutableStateOf<HoldingDto?>(null) }
    var showMarketStatusDetails by remember { mutableStateOf(false) }
    var showAnalysisDetails by remember { mutableStateOf(false) }
    var scanError by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { imageUri ->
        if (imageUri != null) scope.launch {
            try {
                scanError = null
                val recognized = ScreenshotOcr.scan(context, imageUri)
                if (recognized.isEmpty()) scanError = "未能识别出完整持仓行，请使用清晰、完整的持仓列表截图。"
                else {
                    try {
                        api.addHoldingDrafts(HoldingDraftBatchInputDto(recognized.map {
                            HoldingDraftInputDto(it.clientRowId, it.name, it.quantity, it.averageCost)
                        }))
                        scanError = "已识别 ${recognized.size} 行，请逐行核对代码、数量和成本后确认。"
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
            watchlist = api.watchlist()
            availableCash = api.availableCash()
            sales = api.sales()
            drafts = api.holdingDrafts()
            analysisRun = try { api.portfolioAnalysis() } catch (_: Exception) { null }
            analysisBySymbol = analysisRun?.items?.associateBy { it.symbol } ?: emptyMap()
            error = null
            quoteError = null
            quotesBySymbol = if (holdings.isEmpty()) emptyMap() else try {
                val requestedSymbols = holdings.map { it.symbol }
                Log.d("ThirdHandMarket", "HOLDINGS_REQUEST symbols=$requestedSymbols refresh=true")
                // Start an immediate server-side refresh and wait only until its
                // cache write is observable; never wait for the next scheduler tick.
                val fetchedQuotes = ApiClient.latestMarketQuotes(api, requestedSymbols)
                val failures = fetchedQuotes.filter { it.price == null || !it.error_code.isNullOrBlank() }
                if (failures.isNotEmpty()) {
                    quoteError = failures.joinToString("；") { quote ->
                        "${quote.symbol}: ${quote.error_code ?: "missing_price"} ${quote.error_message ?: quote.freshness_note}"
                    }
                    Log.e("ThirdHandMarket", "HOLDINGS_RESPONSE_FAILURE $quoteError")
                } else {
                    Log.d("ThirdHandMarket", "HOLDINGS_RESPONSE_OK quotes=$fetchedQuotes")
                }
                fetchedQuotes.associateBy { it.symbol }
            } catch (exception: Exception) {
                quoteError = "请求异常 ${exception::class.simpleName}: ${exception.message ?: "无额外错误信息"}"
                Log.e("ThirdHandMarket", "HOLDINGS_REQUEST_FAILURE", exception)
                emptyMap()
            }
        }
        catch (exception: Exception) { error = "读取持仓失败：${exception.message ?: "请确认后端正在运行"}" }
    }
    LaunchedEffect(Unit) { refresh() }
    LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            com.thirdhand.app.ui.components.PortfolioCashCard(
                availableCash = formatPositionValue(availableCash?.available_cash ?: 0.0),
                onEdit = null,
                modifier = Modifier.padding(horizontal = 14.dp),
            )
        }
        item { AppHero("我的持仓", "资产根系 · 记录每一次成长") }
        item {
            val pricedHoldings = holdings.mapNotNull { holding -> quotesBySymbol[holding.symbol]?.price?.let { price -> holding to price } }
            val totalMarketValue = pricedHoldings.sumOf { (holding, price) -> holding.quantity * price }
            val totalPnl = pricedHoldings.sumOf { (holding, price) -> holding.quantity * (price - holding.average_cost) }
            com.thirdhand.app.ui.components.HoldingSummaryCard(
                holdingCount = holdings.size,
                pendingCount = drafts.size,
                marketValue = totalMarketValue.takeIf { pricedHoldings.isNotEmpty() }?.let(::formatPositionValue),
                totalPnl = totalPnl.takeIf { pricedHoldings.isNotEmpty() }?.let(::signedPositionValue),
                totalPnlIsPositive = totalPnl >= 0,
                onAdd = { showAdd = true },
                onImport = { imagePicker.launch(arrayOf("image/*")) },
                modifier = Modifier.padding(horizontal = 14.dp),
            )
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
        if (sales.isNotEmpty()) item {
            val realized = sales.sumOf { it.realized_pnl }
            Text(
                "已实现盈亏 ${signedPositionValue(realized)} · ${sales.size} 笔出售记录",
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 4.dp),
                color = if (realized >= 0) Color(0xFFD32F2F) else Color(0xFF178A4B),
                style = MaterialTheme.typography.bodySmall,
            )
        }
        item {
            Row(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("自选股", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text(if (watchlist.isEmpty()) "添加关注标的，持续用于研究与复盘" else "${watchlist.size} 只关注标的", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                TextButton(onClick = { showWatchlistAdd = true }) { Icon(Icons.Filled.Add, null); Text("添加") }
            }
        }
        items(watchlist, key = { "watch-${it.symbol}" }) { item ->
            Card(
                modifier = Modifier.padding(horizontal = 14.dp).fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
                elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
            ) {
                Row(Modifier.padding(horizontal = 16.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(item.name, fontWeight = FontWeight.SemiBold)
                        com.thirdhand.app.ui.components.MarketTag(
                            "观察中",
                            modifier = Modifier.padding(top = 4.dp),
                        )
                        Text("${item.symbol} · 研究与复盘持续跟踪", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    IconButton(onClick = { scope.launch { api.deleteWatchlistItem(item.symbol); refresh() } }) {
                        Icon(Icons.Filled.Close, contentDescription = "取消关注 ${item.name}")
                    }
                }
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
        if (holdings.isNotEmpty()) item { HoldingTableHeader() }
        items(holdings, key = { it.id }) { holding ->
            HoldingTableRow(
                holding = holding,
                quote = quotesBySymbol[holding.symbol],
                onEdit = { onOpenDetail(holding) },
                isDeleteRevealed = revealedHoldingId == holding.id,
                onRevealDelete = { revealedHoldingId = holding.id },
                onCloseDelete = { revealedHoldingId = null },
                onDelete = { deleteCandidate = holding },
            )
        }
    }
    if (showCashEditor) AvailableCashDialog(
        initial = availableCash?.available_cash ?: 0.0,
        onDismiss = { showCashEditor = false },
        onSave = { value -> scope.launch {
            try { availableCash = api.saveAvailableCash(AvailableCashInputDto(value)); showCashEditor = false }
            catch (_: Exception) { error = "可用资金保存失败，请稍后重试。" }
        } },
    )
    if (showAdd) AddHoldingDialog(
        onDismiss = { showAdd = false },
        onSave = { input -> scope.launch { try {
            api.addHolding(input); showAdd = false; refresh()
        } catch (exception: Exception) { error = "保存失败：${exception.message ?: "请稍后重试"}" } } },
    )
    if (showWatchlistAdd) WatchlistDialog(
        onDismiss = { showWatchlistAdd = false },
        onSave = { item -> scope.launch {
            try { api.saveWatchlistItem(item); showWatchlistAdd = false; refresh() }
            catch (exception: Exception) { error = "保存自选股失败：${exception.message ?: "请稍后重试"}" }
        } },
    )
    editingDraft?.let { draft -> AddHoldingDialog(
        title = "补全证券代码",
        initial = draft.candidates.firstOrNull()?.let {
            HoldingInputDto(it.symbol, it.name, draft.quantity, draft.average_cost)
        } ?: HoldingInputDto("", draft.name, draft.quantity, draft.average_cost),
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
                    if (!it.error_code.isNullOrBlank()) Text("错误代码：${it.error_code}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                    if (!it.error_message.isNullOrBlank()) Text("错误详情：${it.error_message}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
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
@OptIn(ExperimentalMaterial3Api::class)
@Deprecated(message ="使用 TradingPeriodKLinePanel")

private fun HoldingDetailScreen(holding: HoldingDto, onBack: () -> Unit) {
    val api = ApiClient.service(LocalContext.current)
    val scope = rememberCoroutineScope()
    var bars by remember(holding.id) { mutableStateOf<List<DailyPriceDto>>(emptyList()) }
    var intradayBars by remember(holding.id) { mutableStateOf<List<DailyPriceDto>>(emptyList()) }
    var intradayLoadError by remember(holding.id) { mutableStateOf<String?>(null) }
    var dailyHistoryLoadError by remember(holding.id) { mutableStateOf<String?>(null) }
    var refreshingDailyHistory by remember(holding.id) { mutableStateOf(false) }
    var sales by remember(holding.id) { mutableStateOf<List<SaleRecordDto>>(emptyList()) }
    var risk by remember(holding.id) { mutableStateOf<RiskAssessmentDto?>(null) }
    var quote by remember(holding.id) { mutableStateOf<MarketQuoteDto?>(null) }
    var analysis by remember(holding.id) { mutableStateOf<PortfolioAnalysisItemDto?>(null) }
    var decisionReport by remember(holding.id) { mutableStateOf<DecisionReportDto?>(null) }
    var tradePlan by remember(holding.id) { mutableStateOf<TradePlanDto?>(null) }
    var planEditorOpen by remember(holding.id) { mutableStateOf(false) }
    var recommendation by remember(holding.id) { mutableStateOf<ResearchRecommendationDto?>(null) }
    var evaluations by remember(holding.id) { mutableStateOf<List<RecommendationEvaluationDto>>(emptyList()) }
    var period by remember { mutableStateOf("日线") }
    var monthRangeStart by remember(holding.id) { mutableStateOf(LocalDate.now(ZoneOffset.ofHours(8)).minusMonths(6)) }
    var monthRangeEnd by remember(holding.id) { mutableStateOf(LocalDate.now(ZoneOffset.ofHours(8))) }
    var monthRangePickerOpen by remember(holding.id) { mutableStateOf(false) }
    var sellOpen by remember { mutableStateOf(false) }
    var editOpen by remember { mutableStateOf(false) }
    var editError by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(holding.id) {
        val dailyHistoryResult = runCatching { api.marketHistory(holding.symbol) }
        bars = dailyHistoryResult.getOrDefault(emptyList())
        dailyHistoryLoadError = dailyHistoryResult.exceptionOrNull()?.let { error ->
            "日线请求失败：${error.message ?: error.javaClass.simpleName}"
        }
        val intradayResult = runCatching { api.marketIntraday(holding.symbol) }
        intradayBars = intradayResult.getOrDefault(emptyList()).map { bar ->
            DailyPriceDto(trading_date = bar.bar_time, open = bar.open, close = bar.close, high = bar.high, low = bar.low, volume = bar.volume, amount = bar.amount, adjustment = "1m")
        }
        intradayLoadError = intradayResult.exceptionOrNull()?.let { error ->
            "小时 K 线数据请求失败：${error.message ?: error.javaClass.simpleName}"
        }
        sales = runCatching { api.sales(holding.symbol) }.getOrDefault(emptyList())
        risk = runCatching { api.riskAssessments().firstOrNull { it.symbol == holding.symbol } }.getOrNull()
        quote = runCatching { ApiClient.latestMarketQuotes(api, listOf(holding.symbol)).firstOrNull() }.getOrNull()
        analysis = runCatching { api.portfolioAnalysis().items.firstOrNull { it.symbol == holding.symbol } }.getOrNull()
        tradePlan = runCatching { api.tradePlans().firstOrNull { it.symbol == holding.symbol } }.getOrNull()
        decisionReport = runCatching { api.latestDecision(holding.symbol) }.getOrNull()
        recommendation = runCatching { api.recommendations(holding.symbol).firstOrNull() }.getOrNull()
        recommendation?.let { item ->
            evaluations = runCatching { api.recommendationEvaluations(item.id) }.getOrDefault(emptyList())
        }
    }
    fun refreshDailyHistory(startDate: LocalDate? = null, endDate: LocalDate? = null) = scope.launch {
        refreshingDailyHistory = true
        dailyHistoryLoadError = null
        runCatching { api.refreshMarketHistory(holding.symbol, MarketHistoryRefreshInputDto(startDate?.toString(), endDate?.toString())) }
            .onSuccess { refreshed ->
                bars = refreshed
                if (refreshed.size < 2) {
                    dailyHistoryLoadError = "服务端没有返回足够的日线；请查看服务端 provider=akshare 和 provider=tushare 日志。"
                }
            }
            .onFailure { error ->
                dailyHistoryLoadError = "日线刷新失败：${error.message ?: error.javaClass.simpleName}"
            }
        refreshingDailyHistory = false
    }
    val chartBars = when (period) {
        "今日" -> intradayBars
        "日线" -> todaySnapshotBar(bars, quote)
        "月线" -> aggregateBars(bars.filter { bar ->
            marketDate(bar.trading_date)?.let { !it.isBefore(monthRangeStart) && !it.isAfter(monthRangeEnd) } == true
        }, period)
        else -> aggregateBars(bars, period)
    }
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, "返回持仓") }
            Column(Modifier.weight(1f)) { Text(holding.name, fontWeight = FontWeight.Bold); Text(holding.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            TextButton(onClick = { editOpen = true }) { Text("编辑") }
            TextButton(onClick = { sellOpen = true }) { Text("出售", color = MaterialTheme.colorScheme.error) }
        }
        LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item { Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("持有 ${holding.quantity} · 成本 ${holding.average_cost} · 现价 ${quote?.price ?: "--"}", style = MaterialTheme.typography.bodySmall)
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("行情 K 线", modifier = Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
                TextButton(onClick = ::refreshDailyHistory, enabled = !refreshingDailyHistory) {
                    Text(if (refreshingDailyHistory) "正在加载日线" else "重新加载日线")
                }
            }
//            Text(
//                "日线是每个已结束交易日的一根 K 线；“今日”才是分钟 K 线。量为该周期累计成交量，额为累计成交金额；换手率反映当日流通筹码的交易比例。",
//                style = MaterialTheme.typography.labelSmall,
//                color = MaterialTheme.colorScheme.onSurfaceVariant,
//            )
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) { listOf("今日", "日线", "周线", "月线").forEach { label -> TextButton(onClick = { period = label }) { Text(label, color = if (period == label) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant) } } }
            if (period == "月线") {
                FilledTonalButton(onClick = { monthRangePickerOpen = true }) {
                    Text("${monthRangeStart} 至 ${monthRangeEnd}")
                }
            }
            if (chartBars.size >= 2) KLineChart(
                chartBars,
                quote.takeIf { period == "日线" || period == "今日" },
                useTimeAxis = period == "今日",
            ) else Text(
                when {
                    period == "今日" -> intradayLoadError ?: "暂无分钟行情缓存；请稍后刷新。"
                    else -> dailyHistoryLoadError ?: "暂无可展示的日线；可点击“重新加载日线”立即重试。"
                },
                style = MaterialTheme.typography.bodySmall,
                color = if (
                    (intradayLoadError != null && period == "今日") ||
                    (dailyHistoryLoadError != null && period != "今日")
                ) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
            )
            } }
            decisionReport?.let { report -> item { DecisionReportRoute(report) } }
            if (decisionReport == null) analysis?.let { review -> item { Column(Modifier.padding(horizontal = 20.dp)) {
                Text("持仓分析 · ${analysisActionLabel(review.action)}", fontWeight = FontWeight.SemiBold)
                Text(review.reason, style = MaterialTheme.typography.bodySmall)
                review.technical_snapshot?.let { snapshot -> Text(snapshot.summary, style = MaterialTheme.typography.bodySmall) }
            } } }
            recommendation?.let { item -> item { Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("历史交易记录（兼容）", fontWeight = FontWeight.SemiBold)
                TextButton(onClick = { planEditorOpen = true }) { Text(if (tradePlan == null) "录入交易计划与条件" else "修改入场、加仓、减仓、退出条件") }
                if (item.status != "ready") {
                    Text("暂不能生成：${item.blocked_reasons.joinToString("、")}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else {
                    val action = if (item.action == "trim") "历史减仓候选" else "历史加仓候选"
                    val zone = item.price_zone
                    Text("$action：候选区间 ${marketNumber(zone?.get("low"))} – ${marketNumber(zone?.get("high"))}；失效价 ${marketNumber(item.invalidation_price)}", style = MaterialTheme.typography.bodySmall)
                    Text(if (item.suggested_quantity != null) "建议数量 ${item.suggested_quantity.toInt()}（${item.quantity_status ?: "规则计算"}）" else "暂不建议计算买入数量：${item.quantity_status ?: "缺少账户可用资金"}", style = MaterialTheme.typography.bodySmall)
                    if (evaluations.isEmpty()) Text("交易记录尚未形成足够的后续交易日。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    evaluations.forEach { evaluation ->
                        Text("${evaluation.horizon}日交易：${signedPositionValue(evaluation.net_pnl)}，${"%.2f".format(evaluation.return_percent)}%｜最大有利 ${"%.2f".format(evaluation.mfe_percent)}%｜最大不利 ${"%.2f".format(evaluation.mae_percent)}%", style = MaterialTheme.typography.labelSmall)
                    }
                    Text("仅作研究与复盘，不会自动执行真实交易。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            } } }
            risk?.let { assessment -> item { Column(Modifier.padding(horizontal = 20.dp)) {
                Text("风险分析", fontWeight = FontWeight.SemiBold)
                Text(if (assessment.status == "data_insufficient") assessment.message else "下行概率 ${assessment.historical_downside_probability}% · 年化波动 ${assessment.annualized_volatility_percent}% · ${assessment.risk_level}", style = MaterialTheme.typography.bodySmall)
            } } }
            item { Column(Modifier.padding(horizontal = 20.dp)) {
                Text("卖出记录", fontWeight = FontWeight.SemiBold)
                if (sales.isEmpty()) Text("暂无出售记录。", style = MaterialTheme.typography.bodySmall)
                sales.take(20).forEach { sale -> Text("${sale.sold_at.take(10)} · ${sale.quantity} 股 @ ${sale.sale_price} · 已实现 ${signedPositionValue(sale.realized_pnl)}${if (sale.reason.isBlank()) "" else " · ${sale.reason}"}", style = MaterialTheme.typography.bodySmall) }
            } }
        }
    }
    if (sellOpen) SellHoldingDialog(holding, quote?.price, onDismiss = { sellOpen = false }, onConfirm = { sale ->
        // The record is persisted first; returning to holdings reveals the updated remainder.
        scope.launch { runCatching { api.sellHolding(holding.id, sale) }; sellOpen = false; onBack() }
    })
    editError?.let { message -> AlertDialog(
        onDismissRequest = { editError = null },
        title = { Text("更新持仓失败") }, text = { Text(message) },
        confirmButton = { TextButton(onClick = { editError = null }) { Text("知道了") } },
    ) }
    if (editOpen) AddHoldingDialog(
        title = "编辑持仓",
        initial = HoldingInputDto(holding.symbol, holding.name, holding.quantity, holding.average_cost),
        onDismiss = { editOpen = false },
        onSave = { input -> scope.launch {
            runCatching { api.updateHolding(holding.id, input) }
                .onSuccess { editOpen = false; onBack() }
                .onFailure { editError = it.message ?: "请稍后重试。" }
        } },
    )
    if (planEditorOpen) TradePlanDialog(
        initial = tradePlan,
        initialSymbol = holding.symbol,
        onDismiss = { planEditorOpen = false },
        onSave = { input -> scope.launch {
            runCatching { api.saveTradePlan(input) }.onSuccess { saved ->
                tradePlan = saved
                planEditorOpen = false
                decisionReport = null
                recommendation = runCatching { api.recommendations(holding.symbol).firstOrNull() }.getOrNull()
            }
        } },
    )
    if (monthRangePickerOpen) MonthRangePickerDialog(
        initialStart = monthRangeStart,
        initialEnd = monthRangeEnd,
        onDismiss = { monthRangePickerOpen = false },
        onConfirm = { start, end ->
            monthRangeStart = start
            monthRangeEnd = end
            monthRangePickerOpen = false
            refreshDailyHistory(start, end)
        },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MonthRangePickerDialog(
    initialStart: LocalDate,
    initialEnd: LocalDate,
    onDismiss: () -> Unit,
    onConfirm: (LocalDate, LocalDate) -> Unit,
) {
    val state = rememberDateRangePickerState(
        initialSelectedStartDateMillis = initialStart.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli(),
        initialSelectedEndDateMillis = initialEnd.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli(),
    )
    DatePickerDialog(
        onDismissRequest = onDismiss,
        confirmButton = {
            TextButton(
                enabled = state.selectedStartDateMillis != null && state.selectedEndDateMillis != null,
                onClick = {
                    onConfirm(
                        Instant.ofEpochMilli(state.selectedStartDateMillis!!).atZone(ZoneOffset.UTC).toLocalDate(),
                        Instant.ofEpochMilli(state.selectedEndDateMillis!!).atZone(ZoneOffset.UTC).toLocalDate(),
                    )
                },
            ) { Text("应用范围") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    ) { DateRangePicker(state = state, title = { Text("选择月K日期范围") }) }
}

private fun marketDate(value: String): LocalDate? = runCatching {
    val trimmed = value.trim()
    if (Regex("\\d{8}").matches(trimmed)) LocalDate.parse(trimmed, DateTimeFormatter.BASIC_ISO_DATE)
    else LocalDate.parse(trimmed.take(10))
}.getOrNull()

private fun aggregateBars(bars: List<DailyPriceDto>, period: String): List<DailyPriceDto> {
    if (period == "日线") return bars.takeLast(120)
    return bars.mapNotNull { bar -> marketDate(bar.trading_date)?.let { it to bar } }.groupBy { (date, _) ->
        if (period == "周线") "${date.year}-${date.get(WeekFields.ISO.weekOfWeekBasedYear())}" else "${date.year}-${date.monthValue}"
    }.values.map { group ->
        val rows = group.map { it.second }
        DailyPriceDto(trading_date = rows.last().trading_date, open = rows.first().open, close = rows.last().close, high = rows.maxOfOrNull { it.high ?: it.close }, low = rows.minOfOrNull { it.low ?: it.close }, volume = rows.sumOf { it.volume ?: 0.0 }, amount = rows.sumOf { it.amount ?: 0.0 }, adjustment = rows.last().adjustment ?: "qfq", source = rows.last().source)
    }.takeLast(120)
}

private fun intradayTimeLabel(timestamp: String): String =
    Regex("\\d{2}:\\d{2}").find(timestamp)?.value ?: timestamp.takeLast(5)

/** Selects enough evenly spaced labels for a compact mobile axis without crowding it. */
private fun intradayAxisIndices(size: Int): List<Int> {
    val labelCount = minOf(size, 5)
    if (labelCount <= 1) return listOf(0)
    val denominator = labelCount - 1
    return (0 until labelCount).map { slot ->
        (slot * (size - 1) + denominator / 2) / denominator
    }.distinct()
}

/**
 * Shared original chart module: intraday, daily, weekly and monthly candles.
 * It owns the same loading, retry and month-range behaviours previously used
 * by the holding detail screen, so every stock detail renders one chart flow.
 */
@Composable
fun TradingPeriodKLinePanel(symbol: String, quote: MarketQuoteDto?) {
    val api = ApiClient.service(LocalContext.current)
    val scope = rememberCoroutineScope()
    var bars by remember(symbol) { mutableStateOf<List<DailyPriceDto>>(emptyList()) }
    var intradayBars by remember(symbol) { mutableStateOf<List<DailyPriceDto>>(emptyList()) }
    var intradayLoadError by remember(symbol) { mutableStateOf<String?>(null) }
    var dailyHistoryLoadError by remember(symbol) { mutableStateOf<String?>(null) }
    var refreshingDailyHistory by remember(symbol) { mutableStateOf(false) }
    var period by remember(symbol) { mutableStateOf("日线") }
    var monthRangeStart by remember(symbol) { mutableStateOf(LocalDate.now(ZoneOffset.ofHours(8)).minusMonths(6)) }
    var monthRangeEnd by remember(symbol) { mutableStateOf(LocalDate.now(ZoneOffset.ofHours(8))) }
    var monthRangePickerOpen by remember(symbol) { mutableStateOf(false) }
    var paperTradeMarkers by remember(symbol) { mutableStateOf<List<PaperTradingLogDto>>(emptyList()) }

    fun loadBars() = scope.launch {
        val dailyHistoryResult = runCatching { api.marketHistory(symbol) }
        bars = dailyHistoryResult.getOrDefault(emptyList())
        dailyHistoryLoadError = dailyHistoryResult.exceptionOrNull()?.let { error ->
            "日线请求失败：${error.message ?: error.javaClass.simpleName}"
        }
        val intradayResult = runCatching { api.marketIntraday(symbol) }
        intradayBars = intradayResult.getOrDefault(emptyList()).map { bar ->
            DailyPriceDto(
                trading_date = bar.bar_time, open = bar.open, close = bar.close, high = bar.high, low = bar.low,
                volume = bar.volume, amount = bar.amount, adjustment = "1m",
            )
        }
        intradayLoadError = intradayResult.exceptionOrNull()?.let { error ->
            "分时 K 线数据请求失败：${error.message ?: error.javaClass.simpleName}"
        }
    }
    fun refreshDailyHistory(startDate: LocalDate? = null, endDate: LocalDate? = null) = scope.launch {
        refreshingDailyHistory = true
        dailyHistoryLoadError = null
        runCatching { api.refreshMarketHistory(symbol, MarketHistoryRefreshInputDto(startDate?.toString(), endDate?.toString())) }
            .onSuccess { refreshed ->
                bars = refreshed
                if (refreshed.size < 2) dailyHistoryLoadError = "服务端没有返回足够的日线数据。"
            }
            .onFailure { error -> dailyHistoryLoadError = "日线刷新失败：${error.message ?: error.javaClass.simpleName}" }
        refreshingDailyHistory = false
    }
    LaunchedEffect(symbol) { loadBars() }
    LaunchedEffect(symbol) {
        paperTradeMarkers = runCatching { api.paperTradingLogs(symbol) }
            .getOrDefault(emptyList())
            .filter { it.status == "executed" && it.side in setOf("BUY", "SELL") }
        paperChartMarkers = paperTradeMarkers
    }
    val chartBars = when (period) {
        "今日" -> intradayBars
        "日线" -> todaySnapshotBar(bars, quote)
        "月线" -> aggregateBars(bars.filter { bar ->
            marketDate(bar.trading_date)?.let { !it.isBefore(monthRangeStart) && !it.isAfter(monthRangeEnd) } == true
        }, period)
        else -> aggregateBars(bars, period)
    }
    Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("行情 K 线", modifier = Modifier.weight(1f), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                TextButton(onClick = ::refreshDailyHistory, enabled = !refreshingDailyHistory) {
                    Text(if (refreshingDailyHistory) "正在加载日线" else "重新加载日线")
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                listOf("今日", "日线", "周线", "月线").forEach { label ->
                    TextButton(onClick = { period = label }) {
                        Text(label, color = if (period == label) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            if (period == "月线") {
                FilledTonalButton(onClick = { monthRangePickerOpen = true }) { Text("${monthRangeStart} 至 ${monthRangeEnd}") }
            }
            if (chartBars.size >= 2) {
                KLineChart(chartBars, quote.takeIf { period == "日线" || period == "今日" }, useTimeAxis = period == "今日", paperMarkers = paperTradeMarkers)
            } else {
                Text(
                    when {
                        period == "今日" -> intradayLoadError ?: "暂无分时行情缓存；请稍后刷新。"
                        else -> dailyHistoryLoadError ?: "暂无可展示的日线；可点击“重新加载日线”立即重试。"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = if ((intradayLoadError != null && period == "今日") || (dailyHistoryLoadError != null && period != "今日")) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
    }
    if (false && paperTradeMarkers.isNotEmpty()) {
        Text("交易 B/S 标记（紫色，与真实操作区分）", style = MaterialTheme.typography.labelSmall, color = Color(0xFF7E57C2))
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            paperTradeMarkers.take(4).forEach { marker ->
                Text("${if (marker.side == "BUY") "B" else "S"} ${marker.executed_at.take(10)} ¥${marketNumber(marker.price)}", style = MaterialTheme.typography.labelSmall, color = Color(0xFF7E57C2))
            }
        }
    }
    if (monthRangePickerOpen) MonthRangePickerDialog(
        initialStart = monthRangeStart,
        initialEnd = monthRangeEnd,
        onDismiss = { monthRangePickerOpen = false },
        onConfirm = { start, end ->
            monthRangeStart = start
            monthRangeEnd = end
            monthRangePickerOpen = false
            refreshDailyHistory(start, end)
        },
    )
}

@Composable
fun KLineChart(
    bars: List<DailyPriceDto>,
    quote: MarketQuoteDto? = null,
    useTimeAxis: Boolean = false,
    paperMarkers: List<PaperTradingLogDto> = emptyList(),
) = Column {
    // Daily/weekly/monthly views stay compact, but a "today" chart must retain
    // the complete trading session.  Truncating every view to 60 candles made
    // a 11:30 morning close appear to begin at 10:31.
    val visible = if (useTimeAxis) bars else bars.takeLast(60)
    var selectedIndex by remember(visible.lastOrNull()?.trading_date) { mutableIntStateOf(visible.lastIndex) }
    val selected = visible[selectedIndex.coerceIn(0, visible.lastIndex)]
    val values = visible.flatMap { listOfNotNull(it.high, it.low, it.close, it.open) }
    val minimum = values.minOrNull() ?: return@Column
    val maximum = values.maxOrNull() ?: return@Column
    val crosshairColor = MaterialTheme.colorScheme.primary
    val previousClose = visible.getOrNull((selectedIndex - 1).coerceAtLeast(0))?.close ?: selected.close
    val change = if (previousClose == 0.0) 0.0 else (selected.close / previousClose - 1) * 100
    val isTodaySnapshot = selectedIndex == visible.lastIndex &&
        selected.adjustment == "intraday_snapshot" && quote?.as_of?.take(10) == currentBeijingDate()
    Column(Modifier.fillMaxWidth().padding(top = 6.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        if (isTodaySnapshot) {
            Text(
                "\u5f53\u65e5\u8fdb\u884c\u4e2d K \u7ebf \u00b7 ${selected.trading_date} \u00b7 ${quoteTimeLabel(quote!!)}",
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
            )
        }
        if (!isTodaySnapshot) Text(if (selectedIndex == visible.lastIndex) "最新交易日 K 线 · ${selected.trading_date}" else "十字线定位 · ${selected.trading_date}", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
        val changeColor = if (change >= 0) Color(0xFFD32F2F) else Color(0xFF178A4B)
        Text(
            "开 ${marketNumber(selected.open)}   高 ${marketNumber(selected.high)}   低 ${marketNumber(selected.low)}",
            style = MaterialTheme.typography.labelSmall,
            color = changeColor,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            "收 ${marketNumber(selected.close)}   涨跌 ${"%.2f".format(change)}%   量 ${marketNumber(selected.volume)}",
            style = MaterialTheme.typography.labelSmall,
            color = changeColor,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            "额 ${marketNumber(selected.amount)}   换手 ${selected.turnover_rate?.let { "%.2f%%".format(it) } ?: "--"}   振幅 ${selected.amplitude_percent?.let { "%.2f%%".format(it) } ?: "--"}",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
    Row(Modifier.fillMaxWidth().padding(top = 6.dp)) {
        Column(Modifier.width(48.dp).height(230.dp), verticalArrangement = Arrangement.SpaceBetween) {
            Text("%.2f".format(maximum), style = MaterialTheme.typography.labelSmall); Text("%.2f".format((maximum + minimum) / 2), style = MaterialTheme.typography.labelSmall); Text("%.2f".format(minimum), style = MaterialTheme.typography.labelSmall); Text("量", style = MaterialTheme.typography.labelSmall)
        }
        Canvas(Modifier.weight(1f).height(230.dp).pointerInput(visible) {
            fun xFor(index: Int): Float = (index + .5f) / visible.size * size.width
            fun selectAt(x: Float) {
                selectedIndex = visible.indices.minByOrNull { index -> kotlin.math.abs(xFor(index) - x) } ?: visible.lastIndex
            }
            detectDragGestures(onDragStart = { selectAt(it.x) }, onDrag = { changeEvent, _ -> selectAt(changeEvent.position.x) })
        }) {
            val priceHeight = size.height * .74f
            val volumeTop = priceHeight + 8f
            val span = (maximum - minimum).takeIf { it > 0 } ?: 1.0
            val step = size.width / visible.size
            val candleWidth = (step * .55f).coerceAtLeast(2f)
            val maxVolume = visible.maxOfOrNull { it.volume ?: 0.0 }?.takeIf { it > 0 } ?: 1.0
            fun y(value: Double) = priceHeight - ((value - minimum) / span * priceHeight).toFloat()
            visible.forEachIndexed { index, bar ->
                val x = step * index + step / 2
                val open = bar.open ?: bar.close
                val color = if (bar.close >= open) Color(0xFFD32F2F) else Color(0xFF178A4B)
                drawLine(color, Offset(x, y(bar.high ?: bar.close)), Offset(x, y(bar.low ?: bar.close)), strokeWidth = 1.4f)
                drawLine(color, Offset(x, y(open)), Offset(x, y(bar.close)), strokeWidth = candleWidth)
                val volumeHeight = ((bar.volume ?: 0.0) / maxVolume * (size.height - volumeTop)).toFloat()
                drawLine(color.copy(alpha = .7f), Offset(x, size.height), Offset(x, size.height - volumeHeight), strokeWidth = candleWidth)
            }
            (if (paperMarkers.isEmpty()) paperChartMarkers else paperMarkers).forEach { marker ->
                val markerTime = marker.executed_at.replace('T', ' ').substringBefore("+").take(16)
                val markerIndex = if (useTimeAxis) {
                    visible.indexOfLast { it.trading_date.replace('T', ' ').take(16) <= markerTime }
                } else {
                    visible.indexOfLast { it.trading_date.take(10) == marker.executed_at.take(10) }
                }
                if (markerIndex >= 0) {
                    val markerPrice = marker.price.coerceIn(minimum, maximum)
                    val markerColor = if (marker.side == "BUY") Color(0xFF7E57C2) else Color(0xFFAB47BC)
                    val markerX = step * markerIndex + step / 2
                    drawCircle(markerColor, radius = 13f, center = Offset(markerX, y(markerPrice)))
                    drawContext.canvas.nativeCanvas.drawText(
                        if (marker.side == "BUY") "B" else "S",
                        markerX - 6f,
                        y(markerPrice) + 6f,
                        Paint().apply { color = android.graphics.Color.WHITE; textSize = 16f; isFakeBoldText = true },
                    )
                }
            }
            val crossX = step * selectedIndex + step / 2
            drawLine(crosshairColor.copy(alpha = .75f), Offset(crossX, 0f), Offset(crossX, size.height), strokeWidth = 1.5f)
            drawLine(crosshairColor.copy(alpha = .45f), Offset(0f, y(selected.close)), Offset(size.width, y(selected.close)), strokeWidth = 1f)
        }
    }
    Row(Modifier.fillMaxWidth().padding(start = 48.dp), horizontalArrangement = Arrangement.SpaceBetween) {
        if (useTimeAxis) {
            intradayAxisIndices(visible.size).forEach { index ->
                Text(intradayTimeLabel(visible[index].trading_date), style = MaterialTheme.typography.labelSmall)
            }
        } else {
            Text(visible.first().trading_date, style = MaterialTheme.typography.labelSmall)
            Text(visible[visible.size / 2].trading_date, style = MaterialTheme.typography.labelSmall)
            Text(visible.last().trading_date, style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
private fun HoldingTableHeader() {
    Row(
        Modifier.fillMaxWidth()
            .padding(horizontal = 14.dp, vertical = 4.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surfaceContainerHigh)
            .padding(horizontal = 10.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        PositionHeader("名称 / 市值", Modifier.weight(1.15f), TextAlign.Start)
        PositionHeader("盈亏 / 比例", Modifier.weight(1f), TextAlign.End)
        PositionHeader("持仓 / 可用", Modifier.weight(.78f), TextAlign.End)
        PositionHeader("成本 / 现价", Modifier.weight(1f), TextAlign.End)
    }
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
        pnl >= 0 -> com.thirdhand.app.ui.theme.LocalMarketColors.current.rise
        else -> com.thirdhand.app.ui.theme.LocalMarketColors.current.fall
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
                    marketTag(currency)?.let { tag ->
                        com.thirdhand.app.ui.components.MarketTag(tag, modifier = Modifier.padding(start = 4.dp))
                    }
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
private fun AvailableCashDialog(initial: Double, onDismiss: () -> Unit, onSave: (Double) -> Unit) {
    var value by remember(initial) { mutableStateOf(if (initial == 0.0) "" else initial.toString()) }
    var error by remember { mutableStateOf<String?>(null) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("可用资金") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("用于计算候选加仓的上限，不会连接券商，也不会自动下单。", style = MaterialTheme.typography.bodySmall)
                OutlinedTextField(value = value, onValueChange = { value = it; error = null }, label = { Text("金额") }, singleLine = true)
                error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
            }
        },
        confirmButton = { Button(onClick = {
            val cash = value.toDoubleOrNull()
            if (cash == null || cash < 0) error = "请输入大于或等于 0 的金额" else onSave(cash)
        }) { Text("保存") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@Composable
private fun SellHoldingDialog(
    holding: HoldingDto,
    suggestedPrice: Double?,
    onDismiss: () -> Unit,
    onConfirm: (SaleInputDto) -> Unit,
) {
    var quantity by remember(holding.id) { mutableStateOf(holding.quantity.toString()) }
    var price by remember(holding.id) { mutableStateOf(suggestedPrice?.toString().orEmpty()) }
    var reason by remember(holding.id) { mutableStateOf("") }
    val parsedQuantity = quantity.toDoubleOrNull()
    val parsedPrice = price.toDoubleOrNull()
    val valid = parsedQuantity != null && parsedQuantity > 0 && parsedQuantity <= holding.quantity && parsedPrice != null && parsedPrice > 0
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("出售 ${holding.name}") },
        text = { Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("可售数量：${holding.quantity}；成本：${holding.average_cost}", style = MaterialTheme.typography.bodySmall)
            OutlinedTextField(quantity, { quantity = it }, label = { Text("出售数量") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(price, { price = it }, label = { Text("成交价") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(reason, { reason = it }, label = { Text("出售依据／复盘备注（可选）") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
            if (valid) {
                val pnl = parsedQuantity!! * (parsedPrice!! - holding.average_cost)
                Text("预计已实现盈亏：${signedPositionValue(pnl)}", color = if (pnl >= 0) Color(0xFFD32F2F) else Color(0xFF178A4B), style = MaterialTheme.typography.bodySmall)
            }
        } },
        confirmButton = { Button(onClick = { onConfirm(SaleInputDto(parsedQuantity!!, parsedPrice!!, reason.trim())) }, enabled = valid) { Text("确认出售") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
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
    val uriHandler = LocalUriHandler.current
    Column(Modifier.fillMaxWidth().clickable(onClick = onToggle).padding(vertical = 10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("${item.name} · ${item.symbol}", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium)
                Text(analysisActionLabel(item.action), color = analysisActionColor(item.action), style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
            }
            Text("证据 ${item.confidence_percent}%", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall)
            Icon(if (expanded) Icons.Filled.Close else Icons.Filled.ChevronRight, if (expanded) "收起详情" else "展开详情", tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        ExplainableText(item.reason, modifier = Modifier.padding(top = 4.dp), style = MaterialTheme.typography.bodySmall, maxLines = if (expanded) Int.MAX_VALUE else 2, overflow = TextOverflow.Ellipsis)
        if (expanded) {
            item.decision_snapshot?.let { snapshot ->
                Text("决策快照", modifier = Modifier.padding(top = 10.dp), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
                Text("证据完整度 ${snapshot.evidence_completeness_percent}%", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
                Text(snapshot.candidate_action, style = MaterialTheme.typography.bodySmall)
                snapshot.market_regime?.let { regime ->
                    Text("市场环境：${marketRegimeLabel(regime.regime)}", modifier = Modifier.padding(top = 6.dp), style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                    Text(regime.indexes.joinToString(" · ") { "${it.name} ${it.five_day_return_percent}%" }.ifBlank { regime.note }, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                snapshot.relative_strength?.let { strength ->
                    Text("相对强弱：${strength.label ?: "待配置"}", modifier = Modifier.padding(top = 6.dp), style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                    Text(strength.horizons.orEmpty().entries.joinToString(" · ") { "${it.key}日差 ${it.value.relative_return_percent}%" }.ifBlank { strength.note }, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                snapshot.historical_calibration?.let { calibration ->
                    Text("历史校准", modifier = Modifier.padding(top = 6.dp), style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                    calibration.horizons.orEmpty().forEach { (days, result) ->
                        val summary = if (result.sample_count == 0) {
                            "样本尚未成熟"
                        } else {
                            "样本 ${result.sample_count} · 平均 ${result.average_return_percent}% · 规则一致 ${result.rule_alignment_rate_percent}%"
                        }
                        Text("${days} 日：$summary", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Text(calibration.definition, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                if (snapshot.missing_evidence.isNotEmpty()) {
                    Text("仍缺少：${snapshot.missing_evidence.joinToString("、")}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                snapshot.event_evidence.forEach { event ->
                    Text("${event.impact} · ${event.title}", modifier = Modifier.padding(top = 5.dp), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
                    Text(event.summary, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    event.source_url?.let { url -> TextButton(onClick = { uriHandler.openUri(url) }) { Text("核验来源") } }
                }
                Text(snapshot.confidence_definition, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            item.technical_snapshot?.let {
                Text("技术指标快照", modifier = Modifier.padding(top = 10.dp), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
                TechnicalSnapshotSummary(it, detailed = true)
            }
            Text("触发证据", modifier = Modifier.padding(top = 10.dp), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
            if (item.evidence.isEmpty()) Text("本次没有可用的量化证据。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            item.evidence.forEach { ExplainableText("• $it", style = MaterialTheme.typography.bodySmall) }
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

private fun marketRegimeLabel(regime: String): String = when (regime) {
    "supportive" -> "顺风"
    "defensive" -> "防守"
    "mixed" -> "分化"
    else -> "数据待补"
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

private fun todayAnalysisPriority(action: String): Int = when (action.lowercase()) {
    "risk_review", "reduce", "exit", "sell", "stop" -> 0
    "add", "buy", "open" -> 1
    "wait_for_confirmation", "hold" -> 2
    "observe", "watch", "data_insufficient" -> 9
    else -> 5
}

private fun marketTag(currency: String): String? = when (currency) {
    "CNY" -> null
    "HKD" -> "港股"
    "USD" -> "美股"
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
fun AddHoldingDialog(
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
    val reverseLookupQuery = when {
        symbol.isBlank() && name.trim().length >= 2 -> name.trim()
        name.isBlank() && symbol.trim().length >= 5 -> symbol.trim()
        else -> ""
    }
    LaunchedEffect(reverseLookupQuery) {
        if (reverseLookupQuery.isBlank()) return@LaunchedEffect
        delay(350)
        lookupMessage = null
        candidates = emptyList()
        runCatching { api.symbolLookup(SymbolResolveRequestDto(listOf(reverseLookupQuery))).firstOrNull() }
            .onSuccess { result ->
                val matches = result?.matches.orEmpty()
                if (matches.size == 1) {
                    symbol = matches.first().symbol
                    name = matches.first().name
                } else {
                    candidates = matches
                    if (matches.isEmpty()) lookupMessage = "未找到匹配的股票代码或名称，请核对输入。"
                }
            }
            .onFailure { lookupMessage = "股票查询暂时不可用，可继续填写其他信息后再试。" }
    }
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
private fun WatchlistDialog(onDismiss: () -> Unit, onSave: (WatchlistInputDto) -> Unit) {
    val context = LocalContext.current
    val api = remember { ApiClient.service(context) }
    var symbol by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }
    var lookupStatus by remember { mutableStateOf<String?>(null) }
    val reverseLookupQuery = when {
        symbol.isBlank() && name.trim().length >= 2 -> name.trim()
        name.isBlank() && symbol.trim().length >= 5 -> symbol.trim()
        else -> ""
    }
    LaunchedEffect(reverseLookupQuery) {
        if (reverseLookupQuery.isBlank()) return@LaunchedEffect
        delay(350)
        lookupStatus = "正在查询股票信息…"
        runCatching { api.symbolLookup(SymbolResolveRequestDto(listOf(reverseLookupQuery))).firstOrNull()?.matches.orEmpty() }
            .onSuccess { matches ->
                when {
                    matches.size == 1 -> { symbol = matches.first().symbol; name = matches.first().name; lookupStatus = null }
                    matches.isEmpty() -> lookupStatus = "未找到匹配的股票代码或名称，请核对输入。"
                    else -> lookupStatus = "找到多个匹配项，请补充更完整的名称或代码。"
                }
            }
            .onFailure { lookupStatus = "股票查询暂时不可用，可继续填写后保存。" }
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("添加自选股") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                lookupStatus?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                Text("自选股不计入持仓，会保留在研究与复盘中。", style = MaterialTheme.typography.bodySmall)
                OutlinedTextField(symbol, { symbol = it.uppercase() }, label = { Text("股票代码") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(name, { name = it }, label = { Text("股票名称（可不填，后台自动补齐）") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            }
        },
        confirmButton = {
            Button(onClick = { onSave(WatchlistInputDto(symbol.trim(), name.trim())) }, enabled = symbol.isNotBlank()) { Text("保存关注") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@Composable
private fun GlossaryLookupDialog(term: String, onDismiss: () -> Unit) {
    val context = LocalContext.current
    val api = remember { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var card by remember(term) { mutableStateOf<GlossaryCardDto?>(null) }
    var explanation by remember(term) { mutableStateOf("") }
    var watchFor by remember(term) { mutableStateOf("") }
    var loading by remember(term) { mutableStateOf(true) }
    var saving by remember { mutableStateOf(false) }
    var error by remember(term) { mutableStateOf<String?>(null) }

    LaunchedEffect(term) {
        loading = true
        error = null
        try {
            card = api.lookupGlossary(GlossaryLookupInputDto(term))
        } catch (_: Exception) {
            error = "词条查询暂时不可用，请检查网络后重试。"
        } finally {
            loading = false
        }
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("术语解释") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(term, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                when {
                    loading -> Text("正在查询词条…", style = MaterialTheme.typography.bodySmall)
                    card != null && card!!.found -> {
                        Text(card!!.plain_explanation)
                        Text("需要留意：${card!!.watch_for}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(if (card!!.source == "user") "来自你的词库" else "内置基础词库", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                    }
                    else -> {
                        Text(card?.plain_explanation ?: "暂未收录这个词。")
                        OutlinedTextField(explanation, { explanation = it }, label = { Text("用自己的话解释") }, minLines = 2, modifier = Modifier.fillMaxWidth())
                        OutlinedTextField(watchFor, { watchFor = it }, label = { Text("需要留意（可选）") }, minLines = 2, modifier = Modifier.fillMaxWidth())
                        Text("保存后会写入个人词库，下次检索直接复用。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
            }
        },
        confirmButton = {
            if (card?.found == false) {
                Button(
                    onClick = {
                        saving = true
                        scope.launch {
                            try {
                            card = api.saveGlossary(GlossaryEntryInputDto(term, explanation.trim(), watchFor.trim()))
                            savedGlossaryTerms = (savedGlossaryTerms + term).distinct()
                            } catch (_: Exception) {
                                error = "保存失败，请稍后重试。"
                            } finally {
                                saving = false
                            }
                        }
                    },
                    enabled = explanation.trim().length >= 2 && !saving,
                ) { Text(if (saving) "保存中…" else "保存到词库") }
            } else TextButton(onClick = onDismiss) { Text("知道了") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
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
    var aiJobs by remember { mutableStateOf<Map<String, AiJobDto>>(emptyMap()) }
    var glossaryCards by remember { mutableStateOf<List<GlossaryCardDto>>(emptyList()) }
    var glossarySearch by remember { mutableStateOf("") }
    var glossaryTerm by remember { mutableStateOf<String?>(null) }
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
        aiJobs = runCatching { api.aiJobs().associateBy { it.target_id } }.getOrDefault(emptyMap())
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
        item {
            Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("查术语", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                    Text("看到不理解的技术词，输入或从页面中复制后查询；查询记录和你补充的解释会保存。", style = MaterialTheme.typography.bodySmall)
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(glossarySearch, { glossarySearch = it }, label = { Text("例如：量价背离") }, singleLine = true, modifier = Modifier.weight(1f))
                        IconButton(onClick = { glossaryTerm = glossarySearch.trim() }, enabled = glossarySearch.isNotBlank()) {
                            Icon(Icons.Filled.Search, contentDescription = "查询术语")
                        }
                    }
                }
            }
        }
        error?.let { item { StatusCard(it ?: "消息暂时不可用", error = true) } }
        if (researchRules.isNotEmpty()) item { Text("研究核验框架", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        items(researchRules, key = { it.id }) { rule -> ResearchRuleCard(rule, uriHandler) }
        if (glossaryCards.isNotEmpty()) item { Text("新手词条", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        items(glossaryCards, key = { it.term }) { card -> GlossaryInfoCard(card) }
        if (announcements.isNotEmpty()) item { Text("正式公告", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        items(announcements) { item -> FeedCard(item, uriHandler, "公告", aiJobs[item.id], onRetryAi = { job -> scope.launch { runCatching { api.retryAiJob(job.id) }; refresh() } }) }
        if (feed.isNotEmpty()) item { Text("相关新闻", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        items(feed) { item -> FeedCard(item, uriHandler, "新闻", aiJobs[item.id], onRetryAi = { job -> scope.launch { runCatching { api.retryAiJob(job.id) }; refresh() } }) }
    }
    glossaryTerm?.let { term -> GlossaryLookupDialog(term = term, onDismiss = { glossaryTerm = null }) }
}

@Composable
private fun FeedCard(item: NewsItemDto, uriHandler: androidx.compose.ui.platform.UriHandler, label: String, aiJob: AiJobDto? = null, onRetryAi: (AiJobDto) -> Unit = {}) = Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(label, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelMedium)
        ExplainableText(item.title, style = MaterialTheme.typography.titleMedium)
        ExplainableText(item.explanation)
        if (item.ai_analysis == null && aiJob != null) {
            val status = when (aiJob.status) { "pending" -> "AI 解读排队中"; "running" -> "AI 解读生成中"; "failed" -> "AI 解读失败"; else -> "AI 解读状态：${aiJob.status}" }
            Text("$status（${aiJob.attempts}/${aiJob.max_attempts}）", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (aiJob.status == "failed" && aiJob.attempts < aiJob.max_attempts) TextButton(onClick = { onRetryAi(aiJob) }) { Text("重试 AI 解读") }
        }
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
fun ProfileScreen() {
    val context = LocalContext.current
    val api = ApiClient.service(context)
    val scope = rememberCoroutineScope()
    var personalRules by remember { mutableStateOf<List<PersonalRuleDto>>(emptyList()) }
    var learningCases by remember { mutableStateOf<List<LearningCaseDto>>(emptyList()) }
    var learningAnalysis by remember { mutableStateOf<LearningCaseAnalysisDto?>(null) }
    var analyzingLearning by remember { mutableStateOf(false) }
    var dailyReviews by remember { mutableStateOf<List<DailyReviewDto>>(emptyList()) }
    var generatingDailyReview by remember { mutableStateOf(false) }
    var recordingReviewItem by remember { mutableStateOf<Pair<DailyReviewDto, DailyReviewItemDto>?>(null) }
    var researchStatus by remember { mutableStateOf<String?>(null) }
    var showRuleDialog by remember { mutableStateOf(false) }
    var ruleScope by remember { mutableStateOf("global") }
    var showLearningDialog by remember { mutableStateOf(false) }
    var editingLearningCase by remember { mutableStateOf<LearningCaseDto?>(null) }
    var deletingLearningCase by remember { mutableStateOf<LearningCaseDto?>(null) }
    fun refreshResearchData() {
        scope.launch {
            try {
                personalRules = api.personalRules().sortedByDescending { it.scope == "symbol" }
                learningCases = api.learningCases()
                dailyReviews = api.dailyReviews()
                researchStatus = null
            } catch (_: Exception) {
                researchStatus = "个人研究数据暂时不可用"
            }
        }
    }
    fun analyzeLearningCases() {
        scope.launch {
            analyzingLearning = true
            researchStatus = null
            try {
                learningAnalysis = api.learningCaseAnalysis()
            } catch (exception: Exception) {
                researchStatus = "AI 复盘分析暂时不可用：${exception.message ?: "请稍后重试"}"
            } finally {
                analyzingLearning = false
            }
        }
    }
    LaunchedEffect(Unit) { refreshResearchData() }
    fun generateDailyReview() {
        scope.launch {
            generatingDailyReview = true
            researchStatus = null
            try {
                api.generateDailyReview()
                dailyReviews = api.dailyReviews()
            } catch (exception: Exception) {
                researchStatus = "盘后计划生成失败：${exception.message ?: "请先补齐行情、日线和交易计划"}"
            } finally {
                generatingDailyReview = false
            }
        }
    }
    fun evaluateDailyReview(review: DailyReviewDto) {
        scope.launch {
            try {
                api.evaluateDailyReview(review.id)
                dailyReviews = api.dailyReviews()
            } catch (exception: Exception) {
                researchStatus = "暂不能生成结果复盘：${exception.message ?: "等待下一交易日收盘数据"}"
            }
        }
    }
    LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { AppHero("资产与复盘", "把每次判断沉淀为下一次的依据") }
        item {
            AiLearningAnalysisCard(
                analysis = learningAnalysis,
                caseCount = learningCases.size,
                loading = analyzingLearning,
                onAnalyze = { analyzeLearningCases() },
            )
        }
        item {
            DailyReviewCard(
                review = dailyReviews.firstOrNull(),
                generating = generatingDailyReview,
                onGenerate = ::generateDailyReview,
                onEvaluate = ::evaluateDailyReview,
                onRecordExecution = { review, item -> recordingReviewItem = review to item },
            )
        }
        item { Text("风险约束与优先级", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        item {
            Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("用于持仓核验、决策上下文、交易计划候选和今日复盘；不会自动下单。优先级：个股规则 > 全局规则 > 系统默认值。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                SecondaryAction(
                    if (personalRules.any { it.scope == "global" }) "调整全局规则" else "设置全局规则",
                    Icons.Filled.AutoGraph,
                    { ruleScope = "global"; showRuleDialog = true },
                    Modifier.fillMaxWidth(),
                )
                SecondaryAction("新增个股规则", Icons.Filled.Add, { ruleScope = "symbol"; showRuleDialog = true }, Modifier.fillMaxWidth())
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
        items(learningCases, key = { it.id }) { item ->
            LearningCaseCard(
                item = item,
                onEdit = { editingLearningCase = item },
                onDelete = { deletingLearningCase = item },
            )
        }
        item { Text("当前为本地 MVP。持仓数据存储在后端 SQLite；请在生产部署前补充账号认证与备份。", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
    if (showRuleDialog) {
        PersonalRuleDialog(
            initial = personalRules.firstOrNull { it.scope == ruleScope && (ruleScope == "global" || it.symbol.isNullOrBlank()) },
            scope = ruleScope,
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
            initial = null,
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
    editingLearningCase?.let { initial ->
        LearningCaseDialog(
            initial = initial,
            onDismiss = { editingLearningCase = null },
            onSave = { input ->
                scope.launch {
                    try {
                        api.updateLearningCase(initial.id, input)
                        editingLearningCase = null
                        refreshResearchData()
                    } catch (_: Exception) {
                        researchStatus = "修改复盘记录失败，请检查输入和服务连接"
                    }
                }
            },
        )
    }
    deletingLearningCase?.let { item ->
        AlertDialog(
            onDismissRequest = { deletingLearningCase = null },
            title = { Text("删除复盘记录？") },
            text = { Text("将删除“${item.title}”。此操作无法撤销。") },
            confirmButton = {
                Button(onClick = {
                    scope.launch {
                        try {
                            api.deleteLearningCase(item.id)
                            deletingLearningCase = null
                            refreshResearchData()
                        } catch (_: Exception) {
                            researchStatus = "删除复盘记录失败，请稍后重试"
                        }
                    }
                }) { Text("删除") }
            },
            dismissButton = { TextButton(onClick = { deletingLearningCase = null }) { Text("取消") } },
        )
    }
    recordingReviewItem?.let { (review, item) ->
        DailyReviewExecutionDialog(
            item = item,
            onDismiss = { recordingReviewItem = null },
            onSave = { input ->
                scope.launch {
                    try {
                        api.recordDailyReviewExecution(review.id, item.symbol, input)
                        recordingReviewItem = null
                        dailyReviews = api.dailyReviews()
                    } catch (_: Exception) {
                        researchStatus = "执行记录保存失败，请检查成交数量和价格。"
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
private fun LearningCaseCard(
    item: LearningCaseDto,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
) =
    Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(item.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                Row {
                    IconButton(onClick = onEdit) { Icon(Icons.Filled.Edit, contentDescription = "编辑复盘记录") }
                    IconButton(onClick = onDelete) { Icon(Icons.Filled.Delete, contentDescription = "删除复盘记录") }
                }
            }
            Text("${item.symbol ?: "组合"} · ${item.position_band} · 置信度 ${(item.confidence * 100).toInt()}%", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
            Text("当时判断：${item.context}", style = MaterialTheme.typography.bodySmall)
            Text("复盘结论：${item.lesson}", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
            Text("结果：${item.outcome}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(beijingTimestamp(item.created_at), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }

@Composable
private fun DailyReviewCard(
    review: DailyReviewDto?,
    generating: Boolean,
    onGenerate: () -> Unit,
    onEvaluate: (DailyReviewDto) -> Unit,
    onRecordExecution: (DailyReviewDto, DailyReviewItemDto) -> Unit,
) = Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("盘后计划与自动复盘", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text("收盘后生成研究快照；录入实际成交后，下一交易日收盘可自动对比计划与实际结果。不会自动下单。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
        ) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text("自动覆盖范围", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
                Text("默认纳入已录入持仓和自选股；仅保存的交易计划不会自动加入。", style = MaterialTheme.typography.bodySmall)
                val considered = (review?.market_snapshot?.get("symbols_considered") as? List<*>)?.size ?: 0
                Text(
                    if (review == null) "生成后会在这里显示本次纳入的持仓数量。" else "本次已纳入 $considered 个持仓标的",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
        }
        if (review == null) {
            Text("尚未生成盘后计划。即使数据未齐也可生成待补齐清单。", style = MaterialTheme.typography.bodySmall)
        } else {
            val blockedItems = (review.market_snapshot["blocked_items"] as? Number)?.toInt() ?: 0
            val displayedBand = if (review.suggested_position_band == "Data incomplete: no portfolio band") "数据待补齐：暂不设置仓位区间" else review.suggested_position_band
            Text("${review.review_date} · $displayedBand", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
            Text(
                if (blockedItems == 0) "数据状态：本次标的已生成研究快照"
                else "数据状态：$blockedItems 个标的资料不完整，已保留为“等待补齐数据”",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            review.items.forEach { item ->
                Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(
                        "${item.name.ifBlank { item.symbol }} · ${item.symbol} · ${when (item.action) { "add" -> "关注加仓"; "trim" -> "关注减仓"; else -> "等待补齐数据" }}",
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(if (item.action == "watch") item.rationale else "参考价 ${item.reference_price} · 建议数量 ${item.suggested_quantity ?: "待确认"} · ${dailyReviewExecutionLabel(item.execution_status)}", style = MaterialTheme.typography.bodySmall)
                    if (item.execution_status == "pending" && item.action != "watch") {
                        TextButton(onClick = { onRecordExecution(review, item) }) { Text("录入实际执行") }
                    }
                }
            }
            if (review.status == "evaluated") {
                Text("理论盈亏 ${review.theoretical_pnl ?: 0.0} · 实际盈亏 ${review.actual_pnl ?: 0.0}", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
                review.highlights.take(2).forEach { Text("亮点：$it", style = MaterialTheme.typography.bodySmall) }
                review.mistakes.take(2).forEach { Text("复核：$it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
            } else {
                TextButton(onClick = { onEvaluate(review) }) { Text("生成次日收盘复盘") }
            }
        }
        TextButton(onClick = onGenerate, enabled = !generating) { Text(if (generating) "正在生成…" else "生成今日盘后计划") }
    }
}

private fun dailyReviewExecutionLabel(status: String): String = when (status) {
    "executed" -> "已记录执行"
    "partial" -> "已记录部分执行"
    "skipped" -> "已跳过"
    else -> "待录入实际执行"
}

@Composable
private fun DailyReviewExecutionDialog(
    item: DailyReviewItemDto,
    onDismiss: () -> Unit,
    onSave: (DailyReviewExecutionInputDto) -> Unit,
) {
    var quantity by remember(item.symbol) { mutableStateOf(item.suggested_quantity?.toString() ?: "") }
    var price by remember(item.symbol) { mutableStateOf(item.reference_price.toString()) }
    var note by remember(item.symbol) { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("记录 ${item.name.ifBlank { item.symbol }}（${item.symbol}）的实际执行") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("请填写实际成交数据，用于和计划快照分开评价。", style = MaterialTheme.typography.bodySmall)
                OutlinedTextField(quantity, { quantity = it }, label = { Text("实际成交数量") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(price, { price = it }, label = { Text("实际成交价格") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(note, { note = it }, label = { Text("执行备注（可选）") }, modifier = Modifier.fillMaxWidth())
            }
        },
        confirmButton = {
            Button(onClick = {
                onSave(DailyReviewExecutionInputDto("executed", quantity.toDoubleOrNull() ?: 0.0, price.toDoubleOrNull(), note))
            }) { Text("保存执行记录") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@Composable
private fun PersonalRuleDialog(
    initial: PersonalRuleDto?,
    scope: String,
    onDismiss: () -> Unit,
    onSave: (PersonalRuleInputDto) -> Unit,
) {
    var symbol by remember(scope, initial?.id) { mutableStateOf(initial?.symbol.orEmpty()) }
    var maxPosition by remember(initial?.id) { mutableStateOf(initial?.max_position_percent?.toString() ?: "20") }
    var lossReview by remember(initial?.id) { mutableStateOf(initial?.loss_review_percent?.toString() ?: "15") }
    var volatilityReview by remember(initial?.id) { mutableStateOf(initial?.volatility_review_percent?.toString() ?: "50") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (scope == "symbol") "个股复核规则" else "全局复核规则") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (scope == "symbol") {
                    OutlinedTextField(symbol, { symbol = it.uppercase() }, label = { Text("证券代码") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                }
                Text(if (scope == "symbol") "仅对该标的生效，并优先于全局规则。" else "适用于全部持仓；若设置个股规则，个股规则优先。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                OutlinedTextField(maxPosition, { maxPosition = it }, label = { Text("单一标的仓位上限（%）") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(lossReview, { lossReview = it }, label = { Text("成本下跌复核阈值（%）") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(volatilityReview, { volatilityReview = it }, label = { Text("年化波动复核阈值（%）") }, modifier = Modifier.fillMaxWidth())
            }
        },
        confirmButton = {
            Button(enabled = scope != "symbol" || symbol.isNotBlank(), onClick = {
                onSave(PersonalRuleInputDto(
                    scope = scope,
                    symbol = symbol.trim().ifBlank { null },
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
    initial: LearningCaseDto?,
    onDismiss: () -> Unit,
    onSave: (LearningCaseInputDto) -> Unit,
) {
    var symbol by remember(initial?.id) { mutableStateOf(initial?.symbol ?: "") }
    var title by remember(initial?.id) { mutableStateOf(initial?.title ?: "") }
    var context by remember(initial?.id) { mutableStateOf(initial?.context ?: "") }
    var lesson by remember(initial?.id) { mutableStateOf(initial?.lesson ?: "") }
    var outcome by remember(initial?.id) { mutableStateOf(initial?.outcome ?: "") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (initial == null) "记录一次复盘" else "编辑复盘记录") },
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
                        position_band = initial?.position_band ?: "待评估",
                        planned_action = initial?.planned_action ?: "继续观察并核验原始信息",
                        confidence = initial?.confidence ?: 0.5,
                        evidence_links = initial?.evidence_links ?: emptyList(),
                    ))
                },
            ) { Text("保存") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}
