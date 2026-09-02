package com.thirdhand.app

import android.os.Bundle
import android.graphics.Paint
import android.util.Log
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
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
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.automirrored.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
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
import androidx.compose.ui.unit.sp
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.marketColors
import com.thirdhand.app.ui.components.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.OffsetDateTime
import java.time.LocalDate
import java.time.Instant
import java.time.temporal.WeekFields
import java.time.temporal.ChronoUnit
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale
import com.thirdhand.app.researchchat.ResearchChatScreen
import com.thirdhand.app.researchchat.ResearchChatController
import com.thirdhand.app.researchchat.ResearchChatLine
import com.thirdhand.app.watchlist.WatchlistScreen

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
private var paperChartMarkers by mutableStateOf<List<PaperTradingLogDto>>(emptyList())

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun ThirdHandApp(resumeSignal: Int) {
    val context = LocalContext.current
    LaunchedEffect(Unit) {
        savedGlossaryTerms = runCatching { ApiClient.service(context).glossaryEntries().map { it.term }.filter { it.isNotBlank() } }.getOrDefault(emptyList())
    }
    var themeMode by remember { mutableStateOf(ThemeStore.load(context)) }
    var tab by remember { mutableIntStateOf(0) } // UIX0 target shell opens on Home.
    var detailStock by remember { mutableStateOf<ResearchTargetDto?>(null) }
    var holdingDetail by remember { mutableStateOf<ResearchTargetDto?>(null) }
    var researchTarget by remember { mutableStateOf<ResearchTargetDto?>(null) }
    var profileOpen by remember { mutableStateOf(false) }
    var startupUpdate by remember { mutableStateOf<AppUpdate?>(null) }
    var dismissedUpdateVersionCode by remember { mutableIntStateOf(-1) }

    LaunchedEffect(resumeSignal) {
        if (resumeSignal <= 0) return@LaunchedEffect
        runCatching { AppUpdateManager.check(context) }
            .onSuccess { update ->
                if (update == null) {
                    startupUpdate = null
                } else {
                    AppUpdateManager.downloadAutomaticallyOnWifi(context, update)
                    if (update.versionCode != dismissedUpdateVersionCode) {
                        startupUpdate = update
                    }
                }
            }
        // Update discovery is best-effort and must never block the normal app path.
    }

    BackHandler(enabled = detailStock != null || holdingDetail != null || researchTarget != null || profileOpen) {
        when {
            researchTarget != null -> researchTarget = null
            holdingDetail != null -> holdingDetail = null
            detailStock != null -> detailStock = null
            profileOpen -> profileOpen = false
        }
    }

    ThirdHandTheme(themeMode) {
        Scaffold(
            bottomBar = {
                if (detailStock == null && researchTarget == null && !profileOpen) {
                    CompactBottomNavigation(
                        selectedTab = tab,
                        items = listOf(
                            CompactNavigationItem("首页", Icons.Filled.Home, 0),
                            CompactNavigationItem("行情", Icons.Filled.AutoGraph, 1),
                            CompactNavigationItem("组合", Icons.Filled.Wallet, 2),
                            CompactNavigationItem("策略", Icons.Filled.AccountBalanceWallet, 3),
                            CompactNavigationItem("自选", Icons.Filled.Bookmark, 4),
                        ),
                        onTabSelected = { destination ->
                    holdingDetail = null
                    tab = destination
                },
                    )
                }
            },
        ) { padding ->
            Box(Modifier.fillMaxSize().padding(padding)) {
                if (profileOpen) {
                    ProfileScreen(
                        themeMode = themeMode,
                        onThemeModeChange = { nextMode ->
                            themeMode = nextMode
                            ThemeStore.save(context, nextMode)
                        },
                    )
                } else if (researchTarget != null) {
                    PositionResearchSubroute(
                        target = researchTarget!!,
                        onClose = { researchTarget = null },
                    )
                } else if (holdingDetail != null) {
                    PositionDetailRoute(
                        target = holdingDetail!!,
                        onBack = { holdingDetail = null },
                    )
                } else if (detailStock != null) {
                    StockDetailDecisionRoute(
                        target = detailStock!!,
                        onBack = { detailStock = null },
                        onResearch = { target ->
                            detailStock = null
                            researchTarget = target
                        },
                    )
                } else {
                    AnimatedContent(
                        targetState = tab,
                        transitionSpec = {
                            fadeIn(tween(200)) togetherWith fadeOut(tween(200))
                        },
                        label = "mainNav"
                    ) { activeTab ->
                        when (activeTab) {
                            0 -> HomeScreen()
                            1 -> MarketScreen(onOpenDetail = { detailStock = it })
                            2 -> CompactHoldingsScreen(onOpenDetail = {
                                holdingDetail = ResearchTargetDto(it.symbol, it.name, "active_holding", it.created_at)
                            })
                            3 -> PaperTradingScreen(onOpenDetail = { detailStock = it })
                            4 -> WatchlistScreen(
                                onOpenDetail = { target ->
                                    if (opensHoldingDetail(target)) holdingDetail = target else detailStock = target
                                },
                                onOpenProfile = { profileOpen = true },
                            )
                            else -> HomeScreen()
                        }
                    }
                }
            }
        }

        startupUpdate?.let { update ->
            AppUpdateDialog(
                update = update,
                onDismiss = {
                    dismissedUpdateVersionCode = update.versionCode
                    startupUpdate = null
                },
            )
        }
    }
}

internal fun opensHoldingDetail(target: ResearchTargetDto): Boolean =
    target.status == "active_holding"

@Composable
private fun HoldingsScreen(onOpenDetail: (HoldingDto) -> Unit) {
    val context = LocalContext.current
    val api = ApiClient.service(context)
    val scope = rememberCoroutineScope()
    var holdings by remember { mutableStateOf<List<HoldingDto>>(emptyList()) }
    var availableCash by remember { mutableStateOf<AvailableCashDto?>(null) }
    var quotes by remember { mutableStateOf<Map<String, MarketQuoteDto>>(emptyMap()) }
    var loading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    fun refresh() = scope.launch {
        loading = true
        errorMessage = null
        runCatching {
            val h = api.holdings()
            val c = api.availableCash()
            val q = if (h.isNotEmpty()) loadLatestDisplayQuotes(api, h.map { it.symbol }).associateBy { it.symbol } else emptyMap()
            Triple(h, c, q)
        }.onSuccess { (h, c, q) ->
            holdings = h; availableCash = c; quotes = q
        }.onFailure { errorMessage = "暂时无法同步持仓与行情，请稍后重试" }
        loading = false
    }

    LaunchedEffect(Unit) { refresh() }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = AppSpacing.xxLarge)
    ) {
        item {
            TradingPageHeader("我的资产", "实盘持仓登记与价值跟踪") {
                IconButton(onClick = ::refresh) {
                    if (loading) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Default.Refresh, null, tint = MaterialTheme.colorScheme.primary)
                }
            }
        }

        item {
            PortfolioCashCard(
                availableCash = "¥${"%.2f".format(availableCash?.available_cash ?: 0.0)}",
                modifier = Modifier.padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium)
            )
        }

        val valuedHoldings = holdings.map { holding ->
            val price = quotes[holding.symbol]?.price ?: holding.average_cost
            holding to price
        }
        val totalMarketValue = valuedHoldings.sumOf { (h, p) -> h.quantity * p }
        val totalPnl = valuedHoldings.sumOf { (h, p) -> h.quantity * (p - h.average_cost) }

        item {
            HoldingSummaryCard(
                holdingCount = holdings.size,
                pendingCount = 0,
                marketValue = "¥${"%.2f".format(totalMarketValue)}",
                totalPnl = "${if(totalPnl>=0)"+" else ""}${"%.2f".format(totalPnl)}",
                totalPnlIsPositive = totalPnl >= 0,
                onAdd = { /* Add Dialog */ },
                onImport = { /* OCR */ },
                modifier = Modifier.padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.small)
            )
        }

        item {
            TradingSection("持仓列表", "Real-time Portfolio")
        }

        if (errorMessage != null) {
            item { PortfolioStatusMessage(errorMessage!!, isError = true) }
        } else if (holdings.isNotEmpty() && quotes.size < holdings.size) {
            item { PortfolioStatusMessage("部分持仓暂未取得行情，市值与盈亏将以成本价暂估。", isError = false) }
        } else if (holdings.isNotEmpty() && quotes.values.any { it.display_freshness !in setOf("live", "session_close") }) {
            item { PortfolioStatusMessage("行情正在刷新或存在延迟，请以行情状态为准。", isError = false) }
        }

        if (holdings.isEmpty() && !loading) {
            item {
                Box(Modifier.fillMaxWidth().padding(AppSpacing.xxLarge), contentAlignment = Alignment.Center) {
                    Text("暂无持仓记录，点击上方按钮添加", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }

        items(holdings, key = { it.id }) { holding ->
            HoldingCardNew(
                holding = holding,
                quote = quotes[holding.symbol],
                positionWeight = if (totalMarketValue > 0) holding.quantity * (quotes[holding.symbol]?.price ?: holding.average_cost) / totalMarketValue else null,
                onClick = { onOpenDetail(holding) },
            )
        }
    }
}

@Composable
private fun PortfolioStatusMessage(message: String, isError: Boolean) {
    Surface(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.small),
        color = if (isError) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.secondaryContainer,
        shape = MaterialTheme.shapes.medium,
    ) {
        Text(
            message,
            modifier = Modifier.padding(AppSpacing.medium),
            style = MaterialTheme.typography.bodySmall,
            color = if (isError) MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.onSecondaryContainer,
        )
    }
}

@Composable
private fun HoldingCardNew(
    holding: HoldingDto,
    quote: MarketQuoteDto?,
    positionWeight: Double?,
    onClick: () -> Unit,
) {
    val colors = MaterialTheme.marketColors
    val currentPrice = quote?.price ?: holding.average_cost
    val pnl = (currentPrice - holding.average_cost) * holding.quantity
    val pnlPercent = if(holding.average_cost != 0.0) (currentPrice - holding.average_cost) / holding.average_cost * 100 else 0.0
    val isPositive = pnl >= 0
    val priceState = when (quote?.display_freshness) {
        "live" -> "实时"
        "session_close" -> "收盘"
        "refreshing" -> "刷新中"
        "stale" -> "延迟"
        else -> "暂估"
    }
    val holdingDays = portfolioHoldingDays(holding.created_at)

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.small)
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = MaterialTheme.shapes.medium,
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        border = BorderStroke(0.5.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
    ) {
        Column(Modifier.padding(AppSpacing.large), verticalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(holding.name, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
                    Text("${holding.symbol} · 持有 $holdingDays 天", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text("${quote?.currency.currencySymbol()}${"%.2f".format(currentPrice)}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text(priceState, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Spacer(Modifier.width(AppSpacing.small))
                Icon(Icons.Default.ChevronRight, contentDescription = "查看 ${holding.name} 持仓详情", tint = MaterialTheme.colorScheme.outlineVariant, modifier = Modifier.size(20.dp))
            }
            TradingRowDivider()
            Row(Modifier.fillMaxWidth()) {
                HoldingFact("数量", holding.quantity.portfolioQuantity(), Modifier.weight(1f))
                HoldingFact("成本", "${quote?.currency.currencySymbol()}${"%.2f".format(holding.average_cost)}", Modifier.weight(1f))
                HoldingFact("仓位", positionWeight?.let { "%.1f%%".format(it * 100) } ?: "--", Modifier.weight(1f))
            }
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("市值 ${quote?.currency.currencySymbol()}${"%.2f".format(currentPrice * holding.quantity)}", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
                Spacer(Modifier.weight(1f))
                Text("盈亏 ${if (isPositive) "+" else ""}${quote?.currency.currencySymbol()}${"%.2f".format(pnl)} (${if (isPositive) "+" else ""}${"%.2f".format(pnlPercent)}%)", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = if (isPositive) colors.rise else colors.fall)
            }
        }
    }
}

@Composable
private fun HoldingFact(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
    }
}

private fun String?.currencySymbol(): String = when (this?.uppercase(Locale.ROOT)) {
    "HKD" -> "HK$"
    "USD" -> "\$"
    "CNY", "RMB", null, "" -> "¥"
    else -> "$this "
}

private fun Double.portfolioQuantity(): String =
    if (this % 1.0 == 0.0) "${toLong()} 股" else "%.2f 股".format(this)

private fun portfolioHoldingDays(value: String): Long {
    val start = runCatching { OffsetDateTime.parse(value).withOffsetSameInstant(ZoneOffset.ofHours(8)).toLocalDate() }
        .getOrElse { runCatching { LocalDate.parse(value.take(10)) }.getOrNull() }
        ?: return 0
    return ChronoUnit.DAYS.between(start, LocalDate.now(ZoneOffset.ofHours(8))).coerceAtLeast(0) + 1
}

// Additional helper functions for consistency...
private fun Double.money(): String = "%.2f".format(Locale.US, this)

private enum class ProfileDialog { THEME, ROADMAP }

@Composable
fun ProfileScreen(
    themeMode: ThemeMode,
    onThemeModeChange: (ThemeMode) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }
    var dialog by remember { mutableStateOf<ProfileDialog?>(null) }
    var manualUpdate by remember { mutableStateOf<AppUpdate?>(null) }
    var updateChecking by remember { mutableStateOf(false) }
    var automaticDownload by remember { mutableStateOf(AppUpdateManager.automaticDownloadEnabled(context)) }

    Scaffold(snackbarHost = { SnackbarHost(snackbarHostState) }) { paddingValues ->
        Column(
            Modifier.fillMaxSize().padding(paddingValues).verticalScroll(rememberScrollState()),
        ) {
        TradingPageHeader("个人中心", "配置规则与复盘档案")

        Surface(
            modifier = Modifier.fillMaxWidth().padding(AppSpacing.xxLarge),
            color = MaterialTheme.colorScheme.surface,
            shape = MaterialTheme.shapes.large,
            border = BorderStroke(0.5.dp, MaterialTheme.colorScheme.outlineVariant)
        ) {
            Column(Modifier.padding(AppSpacing.xxLarge)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Surface(Modifier.size(64.dp), shape = CircleShape, color = MaterialTheme.colorScheme.primaryContainer) {
                        Box(contentAlignment = Alignment.Center) {
                            Icon(Icons.Default.Person, null, modifier = Modifier.size(32.dp), tint = MaterialTheme.colorScheme.primary)
                        }
                    }
                    Spacer(Modifier.width(AppSpacing.large))
                    Column {
                        Text("系统交易员", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold)
                        Text("ID: 8829341 · 标准版", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }

        TradingSection("全局管理")
        ProfileMenuItem("交易计划库", Icons.Default.Description) { dialog = ProfileDialog.ROADMAP }
        ProfileMenuItem("风险复核规则", Icons.Default.Gavel) { dialog = ProfileDialog.ROADMAP }
        ProfileMenuItem("复盘案例集", Icons.Default.History) { dialog = ProfileDialog.ROADMAP }

        TradingSection("应用设置")
        ProfileMenuItem("外观与主题", Icons.Default.Palette) { dialog = ProfileDialog.THEME }
        ProfileMenuItem("数据源同步", Icons.Default.CloudSync) {
            scope.launch {
                val message = runCatching { ApiClient.service(context).health() }
                    .fold(
                        onSuccess = { "数据服务连接正常" },
                        onFailure = { "暂时无法连接数据服务" },
                    )
                snackbarHostState.showSnackbar(message)
            }
        }
        ProfileMenuItem(if (updateChecking) "正在检查更新…" else "检查更新", Icons.Default.Refresh) {
            if (!updateChecking) {
                scope.launch {
                    updateChecking = true
                    runCatching { AppUpdateManager.check(context) }
                        .onSuccess { update ->
                            manualUpdate = update
                            if (update == null) {
                                snackbarHostState.showSnackbar(
                                    if (BuildConfig.DEBUG) "调试版不接收生产更新" else "当前已是最新版本"
                                )
                            } else {
                                AppUpdateManager.downloadAutomaticallyOnWifi(context, update)
                            }
                        }
                        .onFailure {
                            snackbarHostState.showSnackbar("检查更新失败，请稍后重试")
                        }
                    updateChecking = false
                }
            }
        }
        ProfileSwitchItem(
            title = "Wi‑Fi 自动下载更新",
            subtitle = "发现新版本后仅在 Wi‑Fi 下自动开始后台下载",
            icon = Icons.Default.CloudSync,
            checked = automaticDownload,
            onCheckedChange = { enabled ->
                automaticDownload = enabled
                AppUpdateManager.setAutomaticDownloadEnabled(context, enabled)
            },
        )

        Spacer(Modifier.height(AppSpacing.xxLarge))
    }

    when (dialog) {
        ProfileDialog.THEME -> AlertDialog(
            onDismissRequest = { dialog = null },
            title = { Text("外观与主题") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
                    ThemeMode.entries.forEach { mode ->
                        Row(
                            modifier = Modifier.fillMaxWidth().clickable { onThemeModeChange(mode); dialog = null }.padding(vertical = AppSpacing.small),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            RadioButton(selected = themeMode == mode, onClick = { onThemeModeChange(mode); dialog = null })
                            Text(mode.label, Modifier.padding(start = AppSpacing.small), style = MaterialTheme.typography.bodyLarge)
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { dialog = null }) { Text("关闭") } },
        )
        ProfileDialog.ROADMAP -> AlertDialog(
            onDismissRequest = { dialog = null },
            title = { Text("移动端入口待开发") },
            text = { Text("该能力已有服务端数据接口，但独立的移动端编辑与验收页面尚未实现。当前不会模拟成功或修改数据。") },
            confirmButton = { TextButton(onClick = { dialog = null }) { Text("知道了") } },
        )
        null -> Unit
    }

    manualUpdate?.let { update ->
        AppUpdateDialog(update = update, onDismiss = { manualUpdate = null })
    }
    }
}

@Composable
private fun AppUpdateDialog(
    update: AppUpdate,
    onDismiss: () -> Unit,
) {
    val context = LocalContext.current
    var actionMessage by remember(update.versionCode) { mutableStateOf<String?>(null) }
    val completed = AppUpdateManager.hasCompletedDownload(context, update)
    val active = AppUpdateManager.hasActiveDownload(context, update)

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("发现新版本 ${update.versionName}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
                Text(update.changelog.ifBlank { "新版本已经可用。" })
                when {
                    completed -> Text(
                        AppUpdateManager.completedUpdateMessage(context) ?: "安装包已下载完成，可开始安装。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    active -> Text(
                        "安装包正在后台下载，下载完成后可在个人中心安装。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
                actionMessage?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                }
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("稍后") } },
        confirmButton = {
            TextButton(
                enabled = !active || completed,
                onClick = {
                    when (AppUpdateManager.downloadAndInstall(context, update)) {
                        UpdateLaunchResult.DOWNLOAD_STARTED -> onDismiss()
                        UpdateLaunchResult.INSTALLER_OPENED -> onDismiss()
                        UpdateLaunchResult.NEED_INSTALL_PERMISSION -> actionMessage = "请允许 Third-Hand 安装未知来源应用，返回后再次点击安装更新。"
                        UpdateLaunchResult.NEED_STORAGE_PERMISSION -> actionMessage = "请允许存储访问后重新下载。"
                        UpdateLaunchResult.SIGNATURE_MISMATCH -> actionMessage = "安装包签名与当前应用不一致，已阻止覆盖安装。"
                        UpdateLaunchResult.DOWNLOAD_UNAVAILABLE -> actionMessage = "暂时无法下载或打开安装包，请稍后重试。"
                    }
                },
            ) {
                Text(if (completed) "安装更新" else if (active) "后台下载中" else "下载更新")
            }
        },
    )
}

@Composable
private fun ProfileMenuItem(title: String, icon: ImageVector, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.large),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(icon, null, modifier = Modifier.size(20.dp), tint = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.width(AppSpacing.large))
        Text(title, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium, modifier = Modifier.weight(1f))
        Icon(Icons.Default.ChevronRight, null, tint = MaterialTheme.colorScheme.outlineVariant, modifier = Modifier.size(16.dp))
    }
    HorizontalDivider(modifier = Modifier.padding(horizontal = AppSpacing.xxLarge), thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
}

@Composable
private fun ProfileSwitchItem(
    title: String,
    subtitle: String,
    icon: ImageVector,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, null, modifier = Modifier.size(20.dp), tint = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.width(AppSpacing.large))
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
            Text(subtitle, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
    HorizontalDivider(modifier = Modifier.padding(horizontal = AppSpacing.xxLarge), thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
}
