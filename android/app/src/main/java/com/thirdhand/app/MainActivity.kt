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
    var tab by remember { mutableIntStateOf(1) } // Default to Market for better first impression
    var detailStock by remember { mutableStateOf<ResearchTargetDto?>(null) }
    var positionDetailTarget by remember { mutableStateOf<ResearchTargetDto?>(null) }
    var researchTarget by remember { mutableStateOf<ResearchTargetDto?>(null) }
    var profileOpen by remember { mutableStateOf(false) }

    BackHandler(enabled = detailStock != null || positionDetailTarget != null || researchTarget != null || profileOpen) {
        when {
            researchTarget != null -> researchTarget = null
            positionDetailTarget != null -> positionDetailTarget = null
            detailStock != null -> detailStock = null
            profileOpen -> profileOpen = false
        }
    }

    ThirdHandTheme(themeMode) {
        Scaffold(
            bottomBar = {
                if (detailStock == null && positionDetailTarget == null && researchTarget == null && !profileOpen) {
                    NavigationBar(
                        containerColor = MaterialTheme.colorScheme.surface,
                        tonalElevation = 8.dp
                    ) {
                        listOf(
                            Triple("资讯", Icons.AutoMirrored.Filled.Article, 0),
                            Triple("行情", Icons.Filled.AutoGraph, 1),
                            Triple("持仓", Icons.Filled.Wallet, 2),
                            Triple("交易", Icons.Filled.AccountBalanceWallet, 3),
                            Triple("自选", Icons.Filled.Bookmark, 4),
                        ).forEach { (label, icon, targetTab) ->
                            NavigationBarItem(
                                selected = tab == targetTab,
                                onClick = { tab = targetTab },
                                icon = { Icon(icon, contentDescription = label) },
                                label = { Text(label, style = MaterialTheme.typography.labelSmall) },
                                colors = NavigationBarItemDefaults.colors(
                                    selectedIconColor = MaterialTheme.colorScheme.primary,
                                    selectedTextColor = MaterialTheme.colorScheme.primary,
                                    indicatorColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.5f)
                                )
                            )
                        }
                    }
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
                } else if (positionDetailTarget != null) {
                    PositionDetailRoute(
                        target = positionDetailTarget!!,
                        onBack = { positionDetailTarget = null },
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
                            0 -> NewsScreen()
                            1 -> MarketScreen(onOpenDetail = { detailStock = it })
                            2 -> HoldingsScreen(onOpenDetail = {
                                positionDetailTarget = ResearchTargetDto(it.symbol, it.name, "active_holding", it.created_at)
                            })
                            3 -> PaperTradingScreen(onOpenDetail = { detailStock = it })
                            4 -> WatchlistScreen(
                                onOpenDetail = { detailStock = it },
                                onOpenProfile = { profileOpen = true },
                            )
                            else -> MarketScreen(onOpenDetail = { detailStock = it })
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun HoldingsScreen(onOpenDetail: (HoldingDto) -> Unit) {
    val context = LocalContext.current
    val api = ApiClient.service(context)
    val scope = rememberCoroutineScope()
    var holdings by remember { mutableStateOf<List<HoldingDto>>(emptyList()) }
    var availableCash by remember { mutableStateOf<AvailableCashDto?>(null) }
    var quotes by remember { mutableStateOf<Map<String, MarketQuoteDto>>(emptyMap()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }

    fun refresh() = scope.launch {
        loading = true
        error = null
        runCatching {
            val h = api.holdings()
            val c = api.availableCash()
            val q = if (h.isNotEmpty()) ApiClient.latestMarketQuotes(api, h.map { it.symbol }).associateBy { it.symbol } else emptyMap()
            Triple(h, c, q)
        }.onSuccess { (h, c, q) ->
            holdings = h; availableCash = c; quotes = q
        }.onFailure {
            error = it.message ?: "持仓数据加载失败"
        }
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

        val pricedHoldings = holdings.mapNotNull { h -> quotes[h.symbol]?.price?.let { p -> h to p } }
        val totalMarketValue = pricedHoldings.sumOf { (h, p) -> h.quantity * p }
        val totalPnl = pricedHoldings.sumOf { (h, p) -> h.quantity * (p - h.average_cost) }

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

        error?.let { message ->
            item {
                Card(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.small),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
                ) {
                    Row(Modifier.fillMaxWidth().padding(AppSpacing.large), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.ErrorOutline, contentDescription = null, tint = MaterialTheme.colorScheme.onErrorContainer)
                        Spacer(Modifier.width(AppSpacing.medium))
                        Text(message, Modifier.weight(1f), color = MaterialTheme.colorScheme.onErrorContainer, style = MaterialTheme.typography.bodySmall)
                        TextButton(onClick = ::refresh) { Text("重试") }
                    }
                }
            }
        }

        val missingQuoteCount = holdings.count { quotes[it.symbol]?.price == null }
        if (!loading && holdings.isNotEmpty() && missingQuoteCount > 0) {
            item {
                Text(
                    "$missingQuoteCount 只持仓暂缺最新行情，已保留成本与数量事实",
                    modifier = Modifier.padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.small),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.tertiary,
                )
            }
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
                portfolioMarketValue = totalMarketValue,
                onClick = { onOpenDetail(holding) },
            )
        }
    }
}

@Composable
private fun HoldingCardNew(
    holding: HoldingDto,
    quote: MarketQuoteDto?,
    portfolioMarketValue: Double,
    onClick: () -> Unit,
) {
    val colors = MaterialTheme.marketColors
    val currentPrice = quote?.price
    val pnl = currentPrice?.let { (it - holding.average_cost) * holding.quantity }
    val pnlPercent = currentPrice?.takeIf { holding.average_cost != 0.0 }
        ?.let { (it - holding.average_cost) / holding.average_cost * 100 }
    val isPositive = (pnl ?: 0.0) >= 0
    val marketValue = currentPrice?.let { it * holding.quantity }
    val positionWeight = marketValue?.takeIf { portfolioMarketValue > 0 }
        ?.let { it / portfolioMarketValue * 100 }

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
        Column(Modifier.padding(AppSpacing.large), verticalArrangement = Arrangement.spacedBy(AppSpacing.medium)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(holding.name, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
                    Text(holding.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(marketValue?.let { "¥${"%.2f".format(it)}" } ?: "暂缺", style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
                    Text("市值", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Spacer(Modifier.width(AppSpacing.small))
                Icon(Icons.Default.ChevronRight, contentDescription = "查看${holding.name}持仓详情", tint = MaterialTheme.colorScheme.outlineVariant, modifier = Modifier.size(20.dp))
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                HoldingFact("现价", quote?.price?.let { "¥${"%.2f".format(it)}" } ?: "暂缺")
                HoldingFact("数量", portfolioQuantity(holding.quantity))
                HoldingFact("成本", "¥${"%.2f".format(holding.average_cost)}")
                HoldingFact("持仓", "${portfolioHoldingDays(holding.created_at)}天")
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(color = (if (isPositive) colors.rise else colors.fall).copy(alpha = 0.1f), shape = RoundedCornerShape(4.dp)) {
                    Text(
                        if (pnl != null && pnlPercent != null) {
                            "${if(isPositive)"+" else ""}${"%.2f".format(pnl)}  (${if(isPositive)"+" else ""}${"%.2f".format(pnlPercent)}%)"
                        } else {
                            "盈亏暂不可用"
                        },
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = if (isPositive) colors.rise else colors.fall,
                    )
                }
                Spacer(Modifier.weight(1f))
                Text(
                    quote?.let { "${it.display_freshness} · ${it.source}" } ?: "行情不可用",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                positionWeight?.let { Text(" · 仓位 ${"%.1f".format(it)}%", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
        }
    }
}

@Composable
private fun HoldingFact(label: String, value: String) {
    Column {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
    }
}

internal fun portfolioQuantity(value: Double): String =
    if (value % 1.0 == 0.0) "${value.toLong()}股" else "%.2f股".format(Locale.US, value)

internal fun portfolioHoldingDays(value: String): Long {
    val start = runCatching { OffsetDateTime.parse(value).withOffsetSameInstant(ZoneOffset.ofHours(8)).toLocalDate() }
        .getOrElse { runCatching { LocalDate.parse(value.take(10)) }.getOrNull() }
        ?: return 0
    return java.time.temporal.ChronoUnit.DAYS.between(start, LocalDate.now(ZoneOffset.ofHours(8))).coerceAtLeast(0) + 1
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
    }
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
