package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.components.TradingSection
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.LocalMarketColors
import com.thirdhand.app.ui.theme.marketColors
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MarketScreen(onOpenDetail: (ResearchTargetDto) -> Unit) {
    val context = LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var quotes by remember { mutableStateOf<List<MarketQuoteDto>>(emptyList()) }
    var pulse by remember { mutableStateOf<MarketIntelligenceDto?>(null) }
    var paperSymbols by remember { mutableStateOf<Set<String>>(emptySet()) }
    var selectedTab by remember { mutableIntStateOf(0) }
    var stockRanking by remember { mutableStateOf("全部") }
    var selectedSector by remember { mutableStateOf<MarketSectorDto?>(null) }
    var sectorDetail by remember { mutableStateOf<MarketSectorDetailDto?>(null) }
    var sectorLoading by remember { mutableStateOf(false) }
    var searchOpen by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }

    fun refresh() = scope.launch {
        loading = true
        runCatching {
            val positions = api.paperTradingAccount().positions.map { it.symbol }.toSet()
            val sorted = api.cachedMarketQuotes().sortedWith(compareByDescending<MarketQuoteDto> { it.symbol in positions }.thenBy { it.name.ifBlank { it.symbol } })
            Triple(positions, sorted, api.marketIntelligence(refresh = true))
        }.onSuccess { (positions, cachedQuotes, intelligence) ->
            paperSymbols = positions
            quotes = cachedQuotes
            pulse = intelligence
            error = null
            scope.launch {
                repeat(8) {
                    if (it > 0) delay(650)
                    val refreshed = runCatching { api.marketIntelligence() }.getOrNull() ?: return@repeat
                    pulse = refreshed
                    if (refreshed.data_health != "pending") return@launch
                }
            }
        }.onFailure { error = "无法读取行情缓存：${it.message ?: "请检查服务连接"}" }
        loading = false
    }

    LaunchedEffect(Unit) { refresh() }

    LaunchedEffect(selectedSector?.name) {
        val sector = selectedSector?.name ?: return@LaunchedEffect
        sectorLoading = true
        sectorDetail = null
        val first = runCatching { api.marketSectorIntelligence(sector, refresh = true) }
            .getOrElse { MarketSectorDetailDto(sector = sector, data_health = "unavailable", error_message = it.message ?: "板块数据暂不可用") }
        sectorDetail = first
        if (first.data_health != "pending" && first.rows.isNotEmpty()) sectorLoading = false

        repeat(12) {
            if (!sectorLoading) return@LaunchedEffect
            delay(600)
            val refreshed = runCatching { api.marketSectorIntelligence(sector) }.getOrNull() ?: return@repeat
            sectorDetail = refreshed
            if (refreshed.data_health != "pending") {
                sectorLoading = false
                return@LaunchedEffect
            }
        }
        sectorLoading = false
    }

    Scaffold(
        topBar = {
            TradingPageHeader("行情中心", "全市场实时快照与深度数据") {
                IconButton(onClick = ::refresh, enabled = !loading) {
                    if (loading) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Filled.Refresh, "刷新行情", tint = MaterialTheme.colorScheme.primary)
                }
            }
        }
    ) { paddingValues ->
        LazyColumn(
            Modifier.fillMaxSize().padding(paddingValues),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge)
        ) {
            item {
                SearchBarProxy(onClick = { searchOpen = true })
            }
            if (loading && quotes.isEmpty()) {
                item { LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge)) }
            }
            error?.let { item { ErrorBanner(it) } }

            stickyHeader {
                Surface(Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.surface, shadowElevation = 1.dp) {
                    TabRow(
                        selectedTabIndex = selectedTab,
                        containerColor = Color.Transparent,
                        divider = {},
                        indicator = { tabPositions ->
                            if (selectedTab < tabPositions.size) {
                                TabRowDefaults.SecondaryIndicator(
                                    Modifier.tabIndicatorOffset(tabPositions[selectedTab]),
                                    color = MaterialTheme.colorScheme.primary
                                )
                            }
                        }
                    ) {
                        listOf("概览", "行业板块", "自选个股").forEachIndexed { index, label ->
                            Tab(
                                selected = selectedTab == index,
                                onClick = { selectedTab = index },
                                text = {
                                    Text(
                                        label,
                                        fontWeight = if (selectedTab == index) FontWeight.Bold else FontWeight.Normal,
                                        style = MaterialTheme.typography.labelLarge
                                    )
                                }
                            )
                        }
                    }
                }
            }

            when (selectedTab) {
                0 -> marketOverview(pulse)
                1 -> marketSectorRanking(pulse, onOpenSector = {
                    sectorLoading = true
                    sectorDetail = null
                    selectedSector = it
                })
                else -> stockList(quotes, pulse, paperSymbols, stockRanking, loading, onOpenDetail) { stockRanking = it }
            }
        }
    }

    if (searchOpen) {
        ModalBottomSheet(
            onDismissRequest = { searchOpen = false },
            dragHandle = { BottomSheetDefaults.DragHandle() },
            containerColor = MaterialTheme.colorScheme.surface
        ) {
            StockSearchScreen(onSelect = { candidate ->
                searchOpen = false
                onOpenDetail(ResearchTargetDto(candidate.symbol, candidate.name, "market", ""))
            })
        }
    }

    selectedSector?.let { sector ->
        ModalBottomSheet(
            onDismissRequest = { selectedSector = null; sectorDetail = null; sectorLoading = false },
            dragHandle = { BottomSheetDefaults.DragHandle() }
        ) {
            SectorDrillDownSheet(sector, sectorDetail, sectorLoading, onOpenDetail)
        }
    }
}

@Composable
private fun SearchBarProxy(onClick: () -> Unit) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium)
            .clickable(onClick = onClick),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
        shape = MaterialTheme.shapes.medium
    ) {
        Row(
            Modifier.padding(horizontal = AppSpacing.large, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                Icons.Filled.Search,
                contentDescription = null,
                modifier = Modifier.size(20.dp),
                tint = MaterialTheme.colorScheme.primary
            )
            Spacer(Modifier.width(AppSpacing.medium))
            Text(
                "搜索股票名称 / 代码",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun ErrorBanner(message: String) {
    Surface(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.small),
        color = MaterialTheme.colorScheme.errorContainer,
        shape = MaterialTheme.shapes.small
    ) {
        Text(
            message,
            Modifier.padding(AppSpacing.medium),
            color = MaterialTheme.colorScheme.onErrorContainer,
            style = MaterialTheme.typography.bodySmall
        )
    }
}

private fun LazyListScope.marketOverview(pulse: MarketIntelligenceDto?) {
    item { MarketSessionCard(pulse) }
    item { TradingSection("核心指数") }
    item { IndexGrid(pulse) }
    item { MarketBreadthSection(pulse) }
    item { TradingSection("龙虎榜单", "实时资金博弈排行") }
    item { RankingPreviewGrid(pulse) }
}

@Composable
private fun IndexGrid(pulse: MarketIntelligenceDto?) {
    val colors = MaterialTheme.marketColors
    Row(Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.small), horizontalArrangement = Arrangement.spacedBy(AppSpacing.medium)) {
        pulse?.indices?.take(3)?.forEach { index ->
            val change = index.change_percent ?: 0.0
            Surface(
                Modifier.weight(1f),
                color = MaterialTheme.colorScheme.surface,
                shape = MaterialTheme.shapes.medium,
                border = androidx.compose.foundation.BorderStroke(0.5.dp, MaterialTheme.colorScheme.outlineVariant)
            ) {
                Column(Modifier.padding(AppSpacing.medium), horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(index.name, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(index.price?.let { "%.2f".format(it) } ?: "--", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                    Text(
                        "${if (change > 0) "+" else ""}${"%.2f".format(change)}%",
                        color = if (change >= 0) colors.rise else colors.fall,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

@Composable
private fun MarketBreadthSection(pulse: MarketIntelligenceDto?) {
    val breadth = pulse?.breadth.orEmpty()
    val colors = MaterialTheme.marketColors
    val rise = breadth["rise_count"]?.toInt() ?: 0
    val fall = breadth["fall_count"]?.toInt() ?: 0
    val total = rise + fall + (breadth["flat_count"]?.toInt() ?: 0)

    Column(Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("市场广度", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
            Text("上涨 $rise / 下跌 $fall", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.height(AppSpacing.small))
        // Simplified breadth bar
        Row(Modifier.fillMaxWidth().height(8.dp).clip(CircleShape).background(MaterialTheme.colorScheme.outlineVariant)) {
            if (total > 0) {
                Box(Modifier.fillMaxHeight().weight(rise.toFloat().coerceAtLeast(0.1f)).background(colors.rise))
                Box(Modifier.fillMaxHeight().weight((total - rise - fall).toFloat().coerceAtLeast(0.1f)).background(colors.neutral))
                Box(Modifier.fillMaxHeight().weight(fall.toFloat().coerceAtLeast(0.1f)).background(colors.fall))
            }
        }
    }
}

@Composable
private fun RankingPreviewGrid(pulse: MarketIntelligenceDto?) {
    val colors = MaterialTheme.marketColors
    Column(Modifier.padding(horizontal = AppSpacing.xxLarge)) {
        Row(Modifier.fillMaxWidth(), Arrangement.spacedBy(AppSpacing.large)) {
            MarketRankingPreview("涨幅榜", pulse?.rankings?.get("gainers").orEmpty(), colors.rise, Modifier.weight(1f))
            MarketRankingPreview("跌幅榜", pulse?.rankings?.get("losers").orEmpty(), colors.fall, Modifier.weight(1f))
        }
        Spacer(Modifier.height(AppSpacing.medium))
        Row(Modifier.fillMaxWidth(), Arrangement.spacedBy(AppSpacing.large)) {
            MarketRankingPreview("资金流入", pulse?.rankings?.get("main_inflow").orEmpty(), colors.rise, Modifier.weight(1f), showNetAmount = true)
            MarketRankingPreview("资金流出", pulse?.rankings?.get("main_outflow").orEmpty(), colors.fall, Modifier.weight(1f), showNetAmount = true)
        }
    }
}

private fun LazyListScope.marketSectorRanking(pulse: MarketIntelligenceDto?, onOpenSector: (MarketSectorDto) -> Unit) {
    item { TradingSection("主力资金流", "行业板块活跃度与大单监控") }
    val sectors = pulse?.sectors ?: emptyList()
    items(sectors.take(15)) { sector ->
        SectorRow(sector, onClick = { onOpenSector(sector) })
        TradingRowDivider()
    }
}

@Composable
private fun SectorRow(sector: MarketSectorDto, onClick: () -> Unit) {
    val colors = MaterialTheme.marketColors
    val change = sector.change_percent ?: 0.0
    val netAmount = sector.net_amount ?: 0.0

    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.large),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(Modifier.weight(1f)) {
            Text(sector.name, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
            Text("领涨：${sector.leader}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(
                "${if (change > 0) "+" else ""}${"%.2f".format(change)}%",
                color = if (change >= 0) colors.rise else colors.fall,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Bold
            )
            Text(
                "净流入 ${"%.2f".format(netAmount / 100000000)}亿",
                style = MaterialTheme.typography.labelSmall,
                color = if (netAmount >= 0) colors.rise.copy(alpha = 0.8f) else colors.fall.copy(alpha = 0.8f)
            )
        }
        Icon(Icons.Default.ChevronRight, null, modifier = Modifier.size(20.dp), tint = MaterialTheme.colorScheme.outlineVariant)
    }
}

private fun LazyListScope.stockList(
    quotes: List<MarketQuoteDto>,
    pulse: MarketIntelligenceDto?,
    paperSymbols: Set<String>,
    rankingType: String,
    loading: Boolean,
    onOpenDetail: (ResearchTargetDto) -> Unit,
    onRankingChange: (String) -> Unit
) {
    item {
        LazyRow(Modifier.fillMaxWidth(), contentPadding = PaddingValues(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium)) {
            items(listOf("全部", "涨幅", "跌幅", "成交额", "主力流入", "主力流出")) { label ->
                FilterChip(
                    selected = rankingType == label,
                    onClick = { onRankingChange(label) },
                    label = { Text(label) },
                    modifier = Modifier.padding(end = AppSpacing.small),
                    shape = MaterialTheme.shapes.small
                )
            }
        }
    }

    val rankKey = mapOf("涨幅" to "gainers", "跌幅" to "losers", "成交额" to "amount", "主力流入" to "main_inflow", "主力流出" to "main_outflow")[rankingType]
    if (rankKey == null) {
        if (quotes.isEmpty() && !loading) {
            item { EmptyState("暂无个股数据，请尝试搜索或同步") }
        }
        items(quotes, key = { it.symbol }) { quote ->
            MarketQuoteRow(quote, quote.symbol in paperSymbols, onOpenDetail)
        }
    } else {
        val rows = pulse?.rankings?.get(rankKey).orEmpty()
        items(rows, key = { it.symbol }) { row ->
            MarketRankingRow(row, rankingType, pulse?.retrieved_at, onOpenDetail)
        }
    }
}

@Composable
private fun EmptyState(msg: String) {
    Box(Modifier.fillMaxWidth().padding(AppSpacing.xxLarge), contentAlignment = Alignment.Center) {
        Text(msg, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun MarketSessionCard(pulse: MarketIntelligenceDto?) {
    val colors = MaterialTheme.marketColors
    val mainNet = pulse?.fund_flow?.get("主力")?.get("net_amount")

    Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.large),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primary),
        shape = MaterialTheme.shapes.large
    ) {
        Column(Modifier.padding(AppSpacing.large)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Surface(color = Color.White.copy(alpha = 0.2f), shape = CircleShape) {
                            Box(Modifier.size(8.dp).padding(2.dp).background(Color.Green, CircleShape))
                        }
                        Spacer(Modifier.width(8.dp))
                        Text("交易进行中", style = MaterialTheme.typography.titleMedium, color = Color.White, fontWeight = FontWeight.Bold)
                    }
                    Text(marketFreshnessLabel(pulse), style = MaterialTheme.typography.labelSmall, color = Color.White.copy(alpha = 0.7f))
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text("全场主力净额", style = MaterialTheme.typography.labelSmall, color = Color.White.copy(alpha = 0.8f))
                    Text(
                        mainNet?.let { "${if (it >= 0) "+" else ""}${"%.2f".format(it / 100000000)}亿" } ?: "--",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.ExtraBold,
                        color = Color.White
                    )
                }
            }
        }
    }
}

@Composable
private fun MarketRankingPreview(title: String, rows: List<MarketRankingDto>, color: Color, modifier: Modifier = Modifier, showNetAmount: Boolean = false) {
    Surface(
        modifier = modifier,
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f),
        shape = MaterialTheme.shapes.medium
    ) {
        Column(Modifier.padding(AppSpacing.medium)) {
            Text(title, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(AppSpacing.xs))
            rows.take(3).forEach { row ->
                Row(Modifier.fillMaxWidth().padding(vertical = 2.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(row.name.ifBlank { row.symbol }, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.labelSmall, modifier = Modifier.weight(1f))
                    Text(
                        if (showNetAmount) row.net_amount?.let { "${"%.1f".format(it / 100000000)}亿" } ?: "--"
                        else row.change_percent?.let { "${if (it > 0) "+" else ""}${"%.1f".format(it)}%" } ?: "--",
                        color = color,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

@Composable
private fun MarketQuoteRow(quote: MarketQuoteDto, isPaperPosition: Boolean, onOpenDetail: (ResearchTargetDto) -> Unit) {
    val change = quote.change_percent ?: 0.0
    val colors = MaterialTheme.marketColors
    val color = when {
        change > 0 -> colors.rise
        change < 0 -> colors.fall
        else -> colors.neutral
    }

    Column(Modifier.fillMaxWidth().clickable { onOpenDetail(ResearchTargetDto(quote.symbol, quote.name, "market", quote.as_of ?: "")) }) {
        Row(
            Modifier.padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.large),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(quote.name.ifBlank { quote.symbol }, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
                    if (isPaperPosition) {
                        Spacer(Modifier.width(AppSpacing.small))
                        Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = RoundedCornerShape(4.dp)) {
                            Text("持仓", Modifier.padding(horizontal = 4.dp, vertical = 1.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                        }
                    }
                }
                Text(quote.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(quote.price?.let { "%.2f".format(it) } ?: "--", style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
                Text(
                    "${if (change > 0) "+" else ""}${"%.2f".format(change)}%",
                    color = color,
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold
                )
            }
        }
        TradingRowDivider()
    }
}

@Composable
private fun MarketRankingRow(row: MarketRankingDto, ranking: String, asOf: String?, onOpenDetail: (ResearchTargetDto) -> Unit) {
    val value = if (ranking.startsWith("主力")) row.net_amount else row.change_percent
    val colors = MaterialTheme.marketColors
    val color = if ((value ?: 0.0) >= 0) colors.rise else colors.fall

    Column(Modifier.fillMaxWidth().clickable { onOpenDetail(ResearchTargetDto(row.symbol, row.name, "market", asOf ?: "")) }) {
        Row(
            Modifier.padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.large),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(Modifier.weight(1f)) {
                Text(row.name.ifBlank { row.symbol }, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
                Text(row.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(row.price?.let { "%.2f".format(it) } ?: "--", style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
                Text(
                    if (ranking.startsWith("主力")) row.net_amount?.let { "${if (it > 0) "+" else ""}${"%.2f".format(it / 100000000)}亿" } ?: "--"
                    else row.change_percent?.let { "${if (it > 0) "+" else ""}%.2f%%".format(it) } ?: "--",
                    color = color,
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold
                )
            }
        }
        TradingRowDivider()
    }
}

@Composable
private fun SectorDrillDownSheet(sector: MarketSectorDto, detail: MarketSectorDetailDto?, loading: Boolean, onOpenDetail: (ResearchTargetDto) -> Unit) {
    var visibleRows by remember(sector.name, detail?.retrieved_at) { mutableIntStateOf(10) }
    val allRows = detail?.rows.orEmpty().take(50)

    Column(Modifier.fillMaxWidth().fillMaxHeight(0.8f).padding(horizontal = AppSpacing.xxLarge)) {
        Text(sector.name, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.ExtraBold)
        Text("板块成分股实时资金表现", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)

        Spacer(Modifier.height(AppSpacing.medium))

        if (loading) {
            LinearProgressIndicator(Modifier.fillMaxWidth())
        }

        LazyColumn(Modifier.weight(1f)) {
            items(allRows.take(visibleRows)) { row ->
                Row(
                    Modifier.fillMaxWidth().clickable { onOpenDetail(ResearchTargetDto(row.symbol, row.name, "market", detail?.retrieved_at ?: "")) }.padding(vertical = AppSpacing.large),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(row.name.ifBlank { row.symbol }, fontWeight = FontWeight.Bold)
                        Text(row.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Column(horizontalAlignment = Alignment.End) {
                        Text(row.price?.let { "%.2f".format(it) } ?: "--", fontWeight = FontWeight.Bold)
                        Text(
                            row.net_amount?.let { "${if (it > 0) "+" else ""}${"%.2f".format(it / 100000000)}亿" } ?: "--",
                            color = if ((row.net_amount ?: 0.0) >= 0) MaterialTheme.marketColors.rise else MaterialTheme.marketColors.fall,
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
                TradingRowDivider()
            }
        }
    }
}

private fun marketFreshnessLabel(pulse: MarketIntelligenceDto?): String = when (pulse?.data_health) {
    "fresh" -> "更新于 ${pulse.retrieved_at?.substringAfter('T')?.substringBefore('+')?.take(5) ?: "刚刚"}"
    "stale_fallback" -> "数据延迟 · 缓存显示"
    "pending" -> "正在同步最新行情..."
    else -> "离线模式"
}
