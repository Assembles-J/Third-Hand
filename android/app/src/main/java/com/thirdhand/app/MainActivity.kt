package com.thirdhand.app

import android.os.Bundle
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
import androidx.compose.material.icons.filled.ArrowBack
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
import java.time.temporal.WeekFields
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

private var savedGlossaryTerms by mutableStateOf<List<String>>(emptyList())

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun ThirdHandApp(resumeSignal: Int) {
    val context = LocalContext.current
    LaunchedEffect(Unit) {
        savedGlossaryTerms = runCatching { ApiClient.service(context).glossaryEntries().map { it.term }.filter { it.isNotBlank() } }.getOrDefault(emptyList())
    }
    var themeMode by remember { mutableStateOf(ThemeStore.load(context)) }
    var tab by remember { mutableIntStateOf(0) }
    var detailHolding by remember { mutableStateOf<HoldingDto?>(null) }
    var startupUpdate by remember { mutableStateOf<AppUpdate?>(null) }
    var updateMessage by remember { mutableStateOf<String?>(null) }
    var startupDownloadProgress by remember { mutableStateOf<UpdateDownloadProgress?>(null) }
    var monitoringStartupDownload by remember { mutableStateOf(false) }
    LaunchedEffect(resumeSignal) {
        try {
            updateMessage = AppUpdateManager.completedUpdateMessage(context)
            startupDownloadProgress = AppUpdateManager.downloadProgress(context)
            monitoringStartupDownload = startupDownloadProgress?.state?.isActive == true
            val update = AppUpdateManager.check(context)
            val automaticResult = if (update != null && !AppUpdateManager.hasCompletedDownload(context)) {
                AppUpdateManager.downloadAutomaticallyOnWifi(context, update)
            } else null
            startupUpdate = if (
                automaticResult == UpdateLaunchResult.DOWNLOAD_STARTED || AppUpdateManager.hasCompletedDownload(context)
            ) null else update
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
            val current = AppUpdateManager.downloadProgress(context)
            startupDownloadProgress = current
            if (current == null || !current.state.isActive) {
                monitoringStartupDownload = false
                updateMessage = if (current?.state == UpdateDownloadState.FAILED) {
                    current.state.label
                } else {
                    AppUpdateManager.completedUpdateMessage(context) ?: current?.state?.label
                }
                break
            }
            delay(500)
        }
    }
    BackHandler(enabled = detailHolding != null || tab == 3) {
        if (detailHolding != null) detailHolding = null else tab = 1
    }
    ThirdHandTheme(themeMode) {
        Scaffold(
            bottomBar = {
                if (detailHolding == null) {
                    NavigationBar {
                        listOf(
                            Triple("今日", Icons.Filled.AutoGraph, 0),
                            Triple("持仓", Icons.Filled.Wallet, 1),
                            Triple("管理", Icons.Filled.AdminPanelSettings, 2),
                        ).forEach { (label, icon, targetTab) ->
                            NavigationBarItem(
                                selected = tab == targetTab || (targetTab == 2 && tab == 3),
                                onClick = { tab = targetTab },
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
                    HoldingDetailScreen(detailHolding!!, onBack = { detailHolding = null })
                } else androidx.compose.foundation.layout.Box(Modifier.fillMaxSize().pointerInput(tab) {
                    var horizontalDrag = 0f
                    detectHorizontalDragGestures(
                        onDragStart = { horizontalDrag = 0f },
                        onHorizontalDrag = { _, amount -> horizontalDrag += amount },
                        onDragEnd = {
                            if (horizontalDrag <= -56f) tab = (tab + 1).coerceAtMost(2)
                            if (horizontalDrag >= 56f) tab = (tab - 1).coerceAtLeast(0)
                        },
                    )
                }) {
                    AnimatedContent(
                        targetState = tab,
                        transitionSpec = {
                            val movingForward = targetState > initialState
                            (slideInHorizontally(animationSpec = tween(260)) { width -> if (movingForward) width else -width } + fadeIn(tween(180))) togetherWith
                                (slideOutHorizontally(animationSpec = tween(220)) { width -> if (movingForward) -width / 3 else width / 3 } + fadeOut(tween(140)))
                        },
                        label = "bottomNavigationPage",
                    ) { activeTab ->
                        when (activeTab) {
                            0 -> TodayScreen()
                            1 -> HoldingsScreen(onOpenDetail = { detailHolding = it })
                            2 -> UnifiedCenterScreen(ThemeMode.DARK, onThemeModeChange = { themeMode -> })
                            3 -> TradePlanScreen()
                            else -> TodayScreen()
                        }
                    }
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
                        startupDownloadProgress?.let { UpdateDownloadProgressCard(it) }
                        updateMessage?.let {
                            Text(it, color = if (isUpdateStatusError(it)) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                },
                dismissButton = { TextButton(onClick = { startupUpdate = null }) { Text("稍后") } },
                confirmButton = {
                    TextButton(onClick = {
                        when (AppUpdateManager.downloadAndInstall(context, update)) {
                            UpdateLaunchResult.DOWNLOAD_STARTED -> {
                                startupDownloadProgress = AppUpdateManager.downloadProgress(context)
                                monitoringStartupDownload = true
                                updateMessage = "正在下载，完成后可在管理页面安装"
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
                    }, enabled = startupDownloadProgress?.state?.isActive != true) {
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
    Dialog(onDismissRequest = onDismiss) {
        Surface(Modifier.fillMaxWidth().heightIn(max = 700.dp), shape = RoundedCornerShape(18.dp)) {
            Column(Modifier.padding(18.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(if (initial == null) "新建交易计划" else "编辑交易计划", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text("计划是条件核验模板，不是自动交易授权。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                PlanField("证券代码", symbol) { symbol = it }
                Row(verticalAlignment = Alignment.CenterVertically) { RadioButton(horizon == "swing", { horizon = "swing" }); Text("波段（默认）"); Spacer(Modifier.width(12.dp)); RadioButton(horizon == "short", { horizon = "short" }); Text("短线") }
                PlanField("交易逻辑", thesis, 3) { thesis = it }
                PlanField("市场原有预期", expectation, 2) { expectation = it }
                PlanField("比较基准代码（如 sh000300）", benchmarkSymbol) { benchmarkSymbol = it }
                PlanField("比较基准名称（如 沪深300）", benchmarkName) { benchmarkName = it }
                PlanField("催化剂（用；分隔）", catalysts, 2) { catalysts = it }
                PlanField("入场条件", entry, 2) { entry = it }
                PlanField("加仓条件", add, 2) { add = it }
                PlanField("减仓条件", reduce, 2) { reduce = it }
                PlanField("退出 / 失效条件", exit, 2) { exit = it }
                PlanField("最大仓位 %", maxPosition) { maxPosition = it }
                PlanField("单笔风险预算 %", riskBudget) { riskBudget = it }
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
private fun PlanField(label: String, value: String, lines: Int = 1, onChange: (String) -> Unit) {
    OutlinedTextField(value = value, onValueChange = onChange, label = { Text(label) }, modifier = Modifier.fillMaxWidth(), minLines = lines, maxLines = lines + 2)
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
                quotes = ApiClient.marketQuotes(api, MarketQuoteBatchRequestDto(symbols, refresh = forceQuotes))
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
    // On entry prefer the server cache and let its background worker refresh.
    // The hero refresh button remains the explicit forced-refresh path.
    LaunchedEffect(Unit) { refresh() }
    LaunchedEffect(Unit) {
        while (true) {
            delay(2_000)
            if (drafts.any { it.lookup_status == "pending" || it.lookup_status == "querying" }) {
                try {
                    // Draft resolution is independent of quotes, risk, and portfolio analysis.
                    drafts = api.holdingDrafts()
                } catch (_: Exception) { }
            }
        }
    }
    LaunchedEffect(holdings.map { it.symbol }) {
        if (holdings.isEmpty()) return@LaunchedEffect
        while (true) {
            delay(60_000)
            try {
                quotes = ApiClient.marketQuotes(api, MarketQuoteBatchRequestDto(holdings.map { it.symbol }))
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
        val readyRisks = risks.filter { it.status != "data_insufficient" }
        val deferredRisks = risks.filter { it.status == "data_insufficient" }
        if (readyRisks.isNotEmpty()) item { Text("持仓风险观察", modifier = Modifier.padding(start = 20.dp, top = 4.dp, end = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        if (riskLoading) item { StatusCard("正在计算历史风险统计…") }
        riskError?.let { message -> item { StatusCard(message, error = true) } }
        items(readyRisks, key = { it.symbol }) { assessment -> RiskAssessmentCard(assessment) }
        if (portfolioAnalysis.isNotEmpty()) item { Text("持仓复核建议", modifier = Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        items(portfolioAnalysis, key = { it.symbol }) { item -> PortfolioAnalysisCard(item) }
        if (deferredRisks.isNotEmpty()) item { Text("后台数据准备", modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelMedium) }
        items(deferredRisks, key = { "deferred-${it.symbol}" }) { assessment -> RiskAssessmentCard(assessment) }
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
        volume = quote.volume, amount = quote.amount, adjustment = "intraday_snapshot",
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
            Text("${progress.state.label}$progressText$sizeText", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
            if (progress.fraction != null) {
                LinearProgressIndicator(progress = { progress.fraction }, modifier = Modifier.fillMaxWidth())
            } else if (progress.state.isActive) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
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
        "matched" -> "待确认"
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
private fun HoldingsScreen(onOpenDetail: (HoldingDto) -> Unit) {
    val context = LocalContext.current
    val api = ApiClient.service(context)
    var holdings by remember { mutableStateOf<List<HoldingDto>>(emptyList()) }
    var sales by remember { mutableStateOf<List<SaleRecordDto>>(emptyList()) }
    var drafts by remember { mutableStateOf<List<HoldingDraftDto>>(emptyList()) }
    var quotesBySymbol by remember { mutableStateOf<Map<String, MarketQuoteDto>>(emptyMap()) }
    var analysisBySymbol by remember { mutableStateOf<Map<String, PortfolioAnalysisItemDto>>(emptyMap()) }
    var analysisRun by remember { mutableStateOf<PortfolioAnalysisDto?>(null) }
    var availableCash by remember { mutableStateOf<AvailableCashDto?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var quoteError by remember { mutableStateOf<String?>(null) }
    var showAdd by remember { mutableStateOf(false) }
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
                // Do not block the holdings page on a full public-market snapshot.
                // Cached results return immediately and the server refreshes them in the background.
                val fetchedQuotes = ApiClient.marketQuotes(api, MarketQuoteBatchRequestDto(requestedSymbols))
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
        item { Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
            Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("可用资金", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(formatPositionValue(availableCash?.available_cash ?: 0.0), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                }
                TextButton(onClick = { showCashEditor = true }) { Text("录入/修改") }
            }
        } }
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
        if (sales.isNotEmpty()) item {
            val realized = sales.sumOf { it.realized_pnl }
            Text(
                "已实现盈亏 ${signedPositionValue(realized)} · ${sales.size} 笔出售记录",
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 4.dp),
                color = if (realized >= 0) Color(0xFFD32F2F) else Color(0xFF178A4B),
                style = MaterialTheme.typography.bodySmall,
            )
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
private fun HoldingDetailScreen(holding: HoldingDto, onBack: () -> Unit) {
    val api = ApiClient.service(LocalContext.current)
    val scope = rememberCoroutineScope()
    var bars by remember(holding.id) { mutableStateOf<List<DailyPriceDto>>(emptyList()) }
    var intradayBars by remember(holding.id) { mutableStateOf<List<DailyPriceDto>>(emptyList()) }
    var sales by remember(holding.id) { mutableStateOf<List<SaleRecordDto>>(emptyList()) }
    var risk by remember(holding.id) { mutableStateOf<RiskAssessmentDto?>(null) }
    var quote by remember(holding.id) { mutableStateOf<MarketQuoteDto?>(null) }
    var analysis by remember(holding.id) { mutableStateOf<PortfolioAnalysisItemDto?>(null) }
    var tradePlan by remember(holding.id) { mutableStateOf<TradePlanDto?>(null) }
    var planEditorOpen by remember(holding.id) { mutableStateOf(false) }
    var recommendation by remember(holding.id) { mutableStateOf<ResearchRecommendationDto?>(null) }
    var evaluations by remember(holding.id) { mutableStateOf<List<RecommendationEvaluationDto>>(emptyList()) }
    var period by remember { mutableStateOf("日线") }
    var sellOpen by remember { mutableStateOf(false) }
    LaunchedEffect(holding.id) {
        bars = runCatching { api.marketHistory(holding.symbol) }.getOrDefault(emptyList())
        intradayBars = runCatching { api.marketIntraday(holding.symbol).map { bar -> DailyPriceDto(trading_date = bar.bar_time, open = bar.open, close = bar.close, high = bar.high, low = bar.low, volume = bar.volume, amount = bar.amount, adjustment = "1m") } }.getOrDefault(emptyList())
        sales = runCatching { api.sales(holding.symbol) }.getOrDefault(emptyList())
        risk = runCatching { api.riskAssessments().firstOrNull { it.symbol == holding.symbol } }.getOrNull()
        quote = runCatching { ApiClient.marketQuotes(api, MarketQuoteBatchRequestDto(listOf(holding.symbol))).firstOrNull() }.getOrNull()
        analysis = runCatching { api.portfolioAnalysis().items.firstOrNull { it.symbol == holding.symbol } }.getOrNull()
        tradePlan = runCatching { api.tradePlans().firstOrNull { it.symbol == holding.symbol } }.getOrNull()
        recommendation = runCatching { api.generateRecommendations(RecommendationRequestDto(listOf(holding.symbol))).firstOrNull() }.getOrNull()
        recommendation?.let { item ->
            evaluations = runCatching { api.recommendationEvaluations(item.id) }.getOrDefault(emptyList())
        }
    }
    val chartBars = when (period) {
        "今日" -> intradayBars
        "日线" -> todaySnapshotBar(bars, quote)
        else -> aggregateBars(bars, period)
    }
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, "返回持仓") }
            Column(Modifier.weight(1f)) { Text(holding.name, fontWeight = FontWeight.Bold); Text(holding.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            TextButton(onClick = { sellOpen = true }) { Text("出售", color = MaterialTheme.colorScheme.error) }
        }
        LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item { Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("持有 ${holding.quantity} · 成本 ${holding.average_cost} · 现价 ${quote?.price ?: "--"}", style = MaterialTheme.typography.bodySmall)
            Text("行情 K 线", fontWeight = FontWeight.SemiBold)
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) { listOf("今日", "日线", "周线", "月线").forEach { label -> TextButton(onClick = { period = label }) { Text(label, color = if (period == label) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant) } } }
            if (chartBars.size >= 2) KLineChart(chartBars, quote.takeIf { period == "日线" || period == "今日" }) else Text(if (period == "今日") "今日分钟线正在后台同步；仅显示已缓存数据。" else "日线正在后台准备。", style = MaterialTheme.typography.bodySmall)
            } }
            analysis?.let { review -> item { Column(Modifier.padding(horizontal = 20.dp)) {
                Text("持仓分析 · ${analysisActionLabel(review.action)}", fontWeight = FontWeight.SemiBold)
                Text(review.reason, style = MaterialTheme.typography.bodySmall)
                review.technical_snapshot?.let { snapshot -> Text(snapshot.summary, style = MaterialTheme.typography.bodySmall) }
            } } }
            recommendation?.let { item -> item { Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("研究候选方案", fontWeight = FontWeight.SemiBold)
                TextButton(onClick = { planEditorOpen = true }) { Text(if (tradePlan == null) "录入交易计划与条件" else "修改入场、加仓、减仓、退出条件") }
                if (item.status != "ready") {
                    Text("暂不能生成：${item.blocked_reasons.joinToString("、")}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else {
                    val action = if (item.action == "trim") "建议减仓" else "候选加仓"
                    val zone = item.price_zone
                    Text("$action：候选区间 ${marketNumber(zone?.get("low"))} – ${marketNumber(zone?.get("high"))}；失效价 ${marketNumber(item.invalidation_price)}", style = MaterialTheme.typography.bodySmall)
                    Text(if (item.suggested_quantity != null) "建议数量 ${item.suggested_quantity.toInt()}（${item.quantity_status ?: "规则计算"}）" else "暂不建议计算买入数量：${item.quantity_status ?: "缺少账户可用资金"}", style = MaterialTheme.typography.bodySmall)
                    if (evaluations.isEmpty()) Text("模拟成交尚未形成足够的后续交易日。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    evaluations.forEach { evaluation ->
                        Text("${evaluation.horizon}日模拟：${signedPositionValue(evaluation.net_pnl)}，${"%.2f".format(evaluation.return_percent)}%｜最大有利 ${"%.2f".format(evaluation.mfe_percent)}%｜最大不利 ${"%.2f".format(evaluation.mae_percent)}%", style = MaterialTheme.typography.labelSmall)
                    }
                    Text("仅作研究与模拟复盘，不会自动执行交易。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
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
    if (planEditorOpen) TradePlanDialog(
        initial = tradePlan,
        initialSymbol = holding.symbol,
        onDismiss = { planEditorOpen = false },
        onSave = { input -> scope.launch {
            runCatching { api.saveTradePlan(input) }.onSuccess { saved ->
                tradePlan = saved
                planEditorOpen = false
                recommendation = runCatching { api.generateRecommendations(RecommendationRequestDto(listOf(holding.symbol))).firstOrNull() }.getOrNull()
            }
        } },
    )
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
        DailyPriceDto(trading_date = rows.last().trading_date, open = rows.first().open, close = rows.last().close, high = rows.maxOfOrNull { it.high ?: it.close }, low = rows.minOfOrNull { it.low ?: it.close }, volume = rows.sumOf { it.volume ?: 0.0 }, amount = rows.sumOf { it.amount ?: 0.0 }, adjustment = rows.last().adjustment ?: "qfq")
    }.takeLast(120)
}

@Composable
private fun KLineChart(bars: List<DailyPriceDto>, quote: MarketQuoteDto? = null) = Column {
    val visible = bars.takeLast(60)
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
        Text("开 ${marketNumber(selected.open)}  高 ${marketNumber(selected.high)}  低 ${marketNumber(selected.low)}  收 ${marketNumber(selected.close)}  涨跌 ${"%.2f".format(change)}%  量 ${marketNumber(selected.volume)}", style = MaterialTheme.typography.labelSmall, color = if (change >= 0) Color(0xFFD32F2F) else Color(0xFF178A4B))
    }
    Row(Modifier.fillMaxWidth().padding(top = 6.dp)) {
        Column(Modifier.width(48.dp).height(230.dp), verticalArrangement = Arrangement.SpaceBetween) {
            Text("%.2f".format(maximum), style = MaterialTheme.typography.labelSmall); Text("%.2f".format((maximum + minimum) / 2), style = MaterialTheme.typography.labelSmall); Text("%.2f".format(minimum), style = MaterialTheme.typography.labelSmall); Text("量", style = MaterialTheme.typography.labelSmall)
        }
        Canvas(Modifier.weight(1f).height(230.dp).pointerInput(visible) {
            fun selectAt(x: Float) { selectedIndex = (x / size.width * visible.size).toInt().coerceIn(0, visible.lastIndex) }
            detectDragGestures(onDragStart = { selectAt(it.x) }, onDrag = { changeEvent, _ -> selectAt(changeEvent.position.x) })
        }) {
            val priceHeight = size.height * .74f
            val volumeTop = priceHeight + 8f
            val span = (maximum - minimum).takeIf { it > 0 } ?: 1.0
            val step = size.width / visible.size
            val maxVolume = visible.maxOfOrNull { it.volume ?: 0.0 }?.takeIf { it > 0 } ?: 1.0
            fun y(value: Double) = priceHeight - ((value - minimum) / span * priceHeight).toFloat()
            visible.forEachIndexed { index, bar ->
                val x = step * index + step / 2; val open = bar.open ?: bar.close
                val color = if (bar.close >= open) Color(0xFFD32F2F) else Color(0xFF178A4B)
                drawLine(color, Offset(x, y(bar.high ?: bar.close)), Offset(x, y(bar.low ?: bar.close)), strokeWidth = 1.4f)
                drawLine(color, Offset(x, y(open)), Offset(x, y(bar.close)), strokeWidth = (step * .55f).coerceAtLeast(2f))
                val volumeHeight = ((bar.volume ?: 0.0) / maxVolume * (size.height - volumeTop)).toFloat()
                drawLine(color.copy(alpha = .7f), Offset(x, size.height), Offset(x, size.height - volumeHeight), strokeWidth = (step * .55f).coerceAtLeast(2f))
            }
            val crossX = step * selectedIndex + step / 2
            drawLine(crosshairColor.copy(alpha = .75f), Offset(crossX, 0f), Offset(crossX, size.height), strokeWidth = 1.5f)
            drawLine(crosshairColor.copy(alpha = .45f), Offset(0f, y(selected.close)), Offset(size.width, y(selected.close)), strokeWidth = 1f)
        }
    }
    Row(Modifier.fillMaxWidth().padding(start = 48.dp), horizontalArrangement = Arrangement.SpaceBetween) { Text(visible.first().trading_date, style = MaterialTheme.typography.labelSmall); Text(visible[visible.size / 2].trading_date, style = MaterialTheme.typography.labelSmall); Text(visible.last().trading_date, style = MaterialTheme.typography.labelSmall) }
}

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
                    marketTag(currency)?.let { tag ->
                        Text(tag, modifier = Modifier.padding(start = 3.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall)
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
                    Text(strength.horizons.entries.joinToString(" · ") { "${it.key}日差 ${it.value.relative_return_percent}%" }.ifBlank { strength.note }, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                snapshot.historical_calibration?.let { calibration ->
                    Text("历史校准", modifier = Modifier.padding(top = 6.dp), style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                    calibration.horizons.forEach { (days, result) ->
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
fun ProfileScreen(themeMode: ThemeMode, onThemeModeChange: (ThemeMode) -> Unit) {
    val context = LocalContext.current
    val api = ApiClient.service(context)
    val scope = rememberCoroutineScope()
    var baseUrl by remember { mutableStateOf(EndpointStore.baseUrl(context)) }
    var connectionStatus by remember { mutableStateOf<String?>(null) }
    var availableUpdate by remember { mutableStateOf<AppUpdate?>(null) }
    var updateStatus by remember { mutableStateOf<String?>(null) }
    var checkingUpdate by remember { mutableStateOf(false) }
    var automaticDownload by remember { mutableStateOf(AppUpdateManager.automaticDownloadEnabled(context)) }
    var downloadProgress by remember { mutableStateOf<UpdateDownloadProgress?>(null) }
    var monitoringDownload by remember { mutableStateOf(false) }
    var personalRules by remember { mutableStateOf<List<PersonalRuleDto>>(emptyList()) }
    var learningCases by remember { mutableStateOf<List<LearningCaseDto>>(emptyList()) }
    var learningAnalysis by remember { mutableStateOf<LearningCaseAnalysisDto?>(null) }
    var analyzingLearning by remember { mutableStateOf(false) }
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
            downloadProgress = AppUpdateManager.downloadProgress(context)
            monitoringDownload = downloadProgress?.state?.isActive == true
            try {
                val update = AppUpdateManager.check(context)
                if (AppUpdateManager.hasCompletedDownload(context)) {
                    availableUpdate = null
                    updateStatus = AppUpdateManager.completedUpdateMessage(context)
                } else {
                    val automaticResult = update?.let { AppUpdateManager.downloadAutomaticallyOnWifi(context, it) }
                    availableUpdate = if (automaticResult == UpdateLaunchResult.DOWNLOAD_STARTED) null else update
                    if (automaticResult == UpdateLaunchResult.DOWNLOAD_STARTED) {
                        downloadProgress = AppUpdateManager.downloadProgress(context)
                        monitoringDownload = true
                        updateStatus = "已在 Wi‑Fi 下开始后台下载新版本"
                    } else if (update == null && updateStatus == null) {
                        updateStatus = "已是最新版本"
                    }
                }
            } catch (_: Exception) {
                updateStatus = "暂时无法检查更新，请确认服务地址和网络"
            } finally {
                checkingUpdate = false
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
    LaunchedEffect(Unit) {
        checkForUpdate()
        refreshResearchData()
    }
    LaunchedEffect(monitoringDownload) {
        if (!monitoringDownload) return@LaunchedEffect
        while (true) {
            val current = AppUpdateManager.downloadProgress(context)
            downloadProgress = current
            if (current == null || !current.state.isActive) {
                monitoringDownload = false
                updateStatus = if (current?.state == UpdateDownloadState.FAILED) {
                    current.state.label
                } else {
                    AppUpdateManager.completedUpdateMessage(context) ?: current?.state?.label
                }
                break
            }
            delay(500)
        }
    }
    availableUpdate?.let { update ->
        AlertDialog(
            onDismissRequest = { availableUpdate = null },
            title = { Text("发现新版本 ${update.versionName}") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(update.changelog.ifBlank { "已准备好新版本，建议更新后继续使用。" })
                    downloadProgress?.let { UpdateDownloadProgressCard(it) }
                    updateStatus?.let {
                        Text(it, color = if (isUpdateStatusError(it)) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
                    }
                }
            },
            dismissButton = { TextButton(onClick = { availableUpdate = null }) { Text("稍后") } },
            confirmButton = {
                TextButton(onClick = {
                    updateStatus = when (AppUpdateManager.downloadAndInstall(context, update)) {
                        UpdateLaunchResult.DOWNLOAD_STARTED -> {
                            downloadProgress = AppUpdateManager.downloadProgress(context)
                            monitoringDownload = true
                            "正在下载，完成后可在管理页面安装"
                        }
                        UpdateLaunchResult.INSTALLER_OPENED -> "已重新打开系统安装器"
                        UpdateLaunchResult.NEED_INSTALL_PERMISSION -> "请允许“安装未知应用”后返回，再次点击"
                        UpdateLaunchResult.NEED_STORAGE_PERMISSION -> "请允许保存安装包后返回，再次点击"
                        UpdateLaunchResult.SIGNATURE_MISMATCH -> AppUpdateManager.completedUpdateMessage(context)
                        UpdateLaunchResult.DOWNLOAD_UNAVAILABLE -> "安装包不可用，请重新检查更新"
                    }
                }, enabled = downloadProgress?.state?.isActive != true) { Text(if (AppUpdateManager.hasCompletedDownload(context)) "继续安装" else "下载并安装") }
            },
        )
    }
    LazyColumn(contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { AppHero("资产与复盘", "把每次判断沉淀为下一次的依据") }
        item {
            AiLearningAnalysisCard(
                analysis = learningAnalysis,
                hasCases = learningCases.isNotEmpty(),
                loading = analyzingLearning,
                onAnalyze = { analyzeLearningCases() },
            )
        }
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
            Text("当前版本 v${BuildConfig.VERSION_NAME}（构建 ${BuildConfig.VERSION_CODE}）", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                Column(Modifier.weight(1f)) {
                    Text("Wi‑Fi 下自动下载更新", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                    Text("默认开启；仅下载，安装仍需你确认。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Switch(
                    checked = automaticDownload,
                    onCheckedChange = { enabled ->
                        automaticDownload = enabled
                        AppUpdateManager.setAutomaticDownloadEnabled(context, enabled)
                    },
                )
            }
            SecondaryAction(if (checkingUpdate) "正在检查…" else "检查更新", Icons.Filled.Refresh, { checkForUpdate() }, Modifier.fillMaxWidth())
            downloadProgress?.let { UpdateDownloadProgressCard(it) }
            if (AppUpdateManager.hasCompletedDownload(context)) {
                PrimaryAction("新版本已下载，点击安装", Icons.Filled.Refresh, {
                    updateStatus = when (AppUpdateManager.installDownloadedUpdate(context)) {
                        UpdateLaunchResult.INSTALLER_OPENED -> "已打开系统安装器，请确认安装"
                        UpdateLaunchResult.NEED_INSTALL_PERMISSION -> "请允许“安装未知应用”后返回，再次点击安装"
                        UpdateLaunchResult.SIGNATURE_MISMATCH -> AppUpdateManager.completedUpdateMessage(context)
                        UpdateLaunchResult.DOWNLOAD_UNAVAILABLE -> "安装包不可用，请重新检查更新"
                        else -> "安装包已下载，请点击安装"
                    }
                }, Modifier.fillMaxWidth())
            }
            updateStatus?.let { StatusCard(it, positive = it == "已是最新版本", error = isUpdateStatusError(it)) }
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
