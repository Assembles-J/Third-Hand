package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.components.DenseStateTag
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.components.TradingSection
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.CompactTypography
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
            val sorted = api.cachedMarketQuotes().sortedWith(
                compareByDescending<MarketQuoteDto> { it.symbol in positions }
                    .thenBy { it.name.ifBlank { it.symbol } }
            )
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
            .getOrElse {
                MarketSectorDetailDto(
                    sector = sector,
                    data_health = "unavailable",
                    error_message = it.message ?: "板块数据暂不可用",
                )
            }
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
            TradingPageHeader("行情", "指数、板块与个股行情") {
                IconButton(onClick = ::refresh, enabled = !loading) {
                    if (loading) {
                        CircularProgressIndicator(Modifier.size(AppSpacing.xLarge), strokeWidth = 2.dp)
                    } else {
                        Icon(Icons.Filled.Refresh, "刷新行情", tint = MaterialTheme.colorScheme.primary)
                    }
                }
            }
        }
    ) { paddingValues ->
        LazyColumn(
            Modifier.fillMaxSize().padding(paddingValues),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
        ) {
            item { SearchBarProxy(onClick = { searchOpen = true }) }

            if (loading && quotes.isEmpty()) {
                item {
                    LinearProgressIndicator(
                        Modifier.fillMaxWidth().padding(horizontal = AppSpacing.contentHorizontal)
                    )
                }
            }
            error?.let { item { ErrorBanner(it) } }

            stickyHeader {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    color = MaterialTheme.colorScheme.surface,
                ) {
                    TabRow(
                        selectedTabIndex = selectedTab,
                        containerColor = Color.Transparent,
                        divider = { TradingRowDivider() },
                        indicator = { tabPositions ->
                            if (selectedTab < tabPositions.size) {
                                TabRowDefaults.SecondaryIndicator(
                                    Modifier.tabIndicatorOffset(tabPositions[selectedTab]),
                                    color = MaterialTheme.colorScheme.primary,
                                )
                            }
                        },
                    ) {
                        listOf("概览", "行业板块", "自选个股").forEachIndexed { index, label ->
                            Tab(
                                selected = selectedTab == index,
                                onClick = { selectedTab = index },
                                modifier = Modifier.heightIn(min = AppSpacing.touchTarget),
                                text = {
                                    Text(
                                        label,
                                        fontWeight = if (selectedTab == index) FontWeight.SemiBold else FontWeight.Normal,
                                        style = CompactTypography.secondary,
                                    )
                                },
                            )
                        }
                    }
                }
            }

            when (selectedTab) {
                0 -> marketOverview(pulse)
                1 -> marketSectorRanking(
                    pulse,
                    onOpenSector = {
                        sectorLoading = true
                        sectorDetail = null
                        selectedSector = it
                    },
                )
                else -> stockList(
                    quotes,
                    pulse,
                    paperSymbols,
                    stockRanking,
                    loading,
                    onOpenDetail,
                ) { stockRanking = it }
            }
        }
    }

    if (searchOpen) {
        ModalBottomSheet(
            onDismissRequest = { searchOpen = false },
            dragHandle = { BottomSheetDefaults.DragHandle() },
            containerColor = MaterialTheme.colorScheme.surface,
        ) {
            StockSearchScreen(onSelect = { candidate ->
                searchOpen = false
                onOpenDetail(ResearchTargetDto(candidate.symbol, candidate.name, "market", ""))
            })
        }
    }

    selectedSector?.let { sector ->
        ModalBottomSheet(
            onDismissRequest = {
                selectedSector = null
                sectorDetail = null
                sectorLoading = false
            },
            dragHandle = { BottomSheetDefaults.DragHandle() },
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
            .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.xs)
            .heightIn(min = AppSpacing.touchTarget)
            .clickable(onClick = onClick),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f),
        shape = MaterialTheme.shapes.small,
    ) {
        Row(
            Modifier.padding(horizontal = AppSpacing.medium),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                Icons.Filled.Search,
                contentDescription = null,
                modifier = Modifier.size(AppSpacing.xLarge),
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.width(AppSpacing.small))
            Text(
                "搜索股票名称 / 代码",
                style = CompactTypography.secondary,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun ErrorBanner(message: String) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.small),
        color = MaterialTheme.colorScheme.errorContainer,
        shape = MaterialTheme.shapes.small,
    ) {
        Text(
            message,
            Modifier.padding(AppSpacing.medium),
            color = MaterialTheme.colorScheme.onErrorContainer,
            style = CompactTypography.secondary,
        )
    }
}

private fun LazyListScope.marketOverview(pulse: MarketIntelligenceDto?) {
    item { MarketSessionStrip(pulse) }
    item { TradingSection("核心指数") }
    item { IndexGrid(pulse) }
    item { MarketBreadthSection(pulse) }
    item { TradingSection("市场排行", "涨跌幅与主力资金") }
    item { RankingPreviewGrid(pulse) }
}

@Composable
private fun IndexGrid(pulse: MarketIntelligenceDto?) {
    val colors = MaterialTheme.marketColors
    val indices = pulse?.indices.orEmpty().take(3)

    Row(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.xs),
        horizontalArrangement = Arrangement.spacedBy(AppSpacing.large),
    ) {
        if (indices.isEmpty()) {
            Text(
                "暂无指数数据",
                modifier = Modifier
                    .weight(1f)
                    .padding(vertical = AppSpacing.medium),
                style = CompactTypography.secondary,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            indices.forEach { index ->
                val change = index.change_percent ?: 0.0
                val changeColor = when {
                    change > 0 -> colors.rise
                    change < 0 -> colors.fall
                    else -> colors.neutral
                }
                Column(
                    modifier = Modifier.weight(1f),
                    horizontalAlignment = Alignment.End,
                ) {
                    Text(
                        index.name,
                        style = CompactTypography.caption,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        index.price?.let { "%.2f".format(it) } ?: "--",
                        style = CompactTypography.rowValue,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                    Text(
                        "${if (change > 0) "+" else ""}${"%.2f".format(change)}%",
                        color = changeColor,
                        style = CompactTypography.caption,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }
        }
    }
    TradingRowDivider()
}

@Composable
private fun MarketBreadthSection(pulse: MarketIntelligenceDto?) {
    val breadth = pulse?.breadth.orEmpty()
    val colors = MaterialTheme.marketColors
    val rise = breadth["rise_count"]?.toInt() ?: 0
    val fall = breadth["fall_count"]?.toInt() ?: 0
    val flat = breadth["flat_count"]?.toInt() ?: 0
    val total = rise + fall + flat

    Column(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.rowVertical)
    ) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("市场广度", style = CompactTypography.sectionTitle)
            Text(
                "涨 $rise  平 $flat  跌 $fall",
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Spacer(Modifier.height(AppSpacing.small))
        Row(
            Modifier
                .fillMaxWidth()
                .height(6.dp)
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.outlineVariant)
        ) {
            if (total > 0) {
                Box(
                    Modifier
                        .fillMaxHeight()
                        .weight(rise.toFloat().coerceAtLeast(0.1f))
                        .background(colors.rise)
                )
                Box(
                    Modifier
                        .fillMaxHeight()
                        .weight(flat.toFloat().coerceAtLeast(0.1f))
                        .background(colors.neutral)
                )
                Box(
                    Modifier
                        .fillMaxHeight()
                        .weight(fall.toFloat().coerceAtLeast(0.1f))
                        .background(colors.fall)
                )
            }
        }
    }
    TradingRowDivider()
}

@Composable
private fun RankingPreviewGrid(pulse: MarketIntelligenceDto?) {
    val colors = MaterialTheme.marketColors
    Column(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.xs)
    ) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(AppSpacing.large)) {
            MarketRankingPreview(
                "涨幅榜",
                pulse?.rankings?.get("gainers").orEmpty(),
                colors.rise,
                Modifier.weight(1f),
            )
            MarketRankingPreview(
                "跌幅榜",
                pulse?.rankings?.get("losers").orEmpty(),
                colors.fall,
                Modifier.weight(1f),
            )
        }
        TradingRowDivider(inset = false)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(AppSpacing.large)) {
            MarketRankingPreview(
                "资金流入",
                pulse?.rankings?.get("main_inflow").orEmpty(),
                colors.rise,
                Modifier.weight(1f),
                showNetAmount = true,
            )
            MarketRankingPreview(
                "资金流出",
                pulse?.rankings?.get("main_outflow").orEmpty(),
                colors.fall,
                Modifier.weight(1f),
                showNetAmount = true,
            )
        }
    }
}

private fun LazyListScope.marketSectorRanking(
    pulse: MarketIntelligenceDto?,
    onOpenSector: (MarketSectorDto) -> Unit,
) {
    item { TradingSection("主力资金流", "行业板块活跃度与大单监控") }
    val sectors = pulse?.sectors ?: emptyList()
    if (sectors.isEmpty()) {
        item { EmptyState("暂无板块数据") }
    }
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
    val changeColor = when {
        change > 0 -> colors.rise
        change < 0 -> colors.fall
        else -> colors.neutral
    }

    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = AppSpacing.touchTarget)
            .clickable(onClick = onClick)
            .padding(horizontal = AppSpacing.rowHorizontal, vertical = AppSpacing.rowVertical),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                sector.name,
                style = CompactTypography.rowTitle,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                "领涨：${sector.leader.ifBlank { "--" }}",
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(
                "${if (change > 0) "+" else ""}${"%.2f".format(change)}%",
                color = changeColor,
                style = CompactTypography.rowValue,
            )
            Text(
                "${if (netAmount >= 0) "+" else ""}${"%.2f".format(netAmount / 100000000)}亿",
                style = CompactTypography.caption,
                color = if (netAmount >= 0) colors.rise else colors.fall,
            )
        }
        Spacer(Modifier.width(AppSpacing.small))
        Icon(
            Icons.Default.ChevronRight,
            null,
            modifier = Modifier.size(AppSpacing.xLarge),
            tint = MaterialTheme.colorScheme.outline,
        )
    }
}

private fun LazyListScope.stockList(
    quotes: List<MarketQuoteDto>,
    pulse: MarketIntelligenceDto?,
    paperSymbols: Set<String>,
    rankingType: String,
    loading: Boolean,
    onOpenDetail: (ResearchTargetDto) -> Unit,
    onRankingChange: (String) -> Unit,
) {
    item {
        LazyRow(
            Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(
                horizontal = AppSpacing.contentHorizontal,
                vertical = AppSpacing.xs,
            ),
        ) {
            items(listOf("全部", "涨幅", "跌幅", "成交额", "主力流入", "主力流出")) { label ->
                FilterChip(
                    selected = rankingType == label,
                    onClick = { onRankingChange(label) },
                    label = { Text(label, style = CompactTypography.caption) },
                    modifier = Modifier
                        .padding(end = AppSpacing.small)
                        .heightIn(min = AppSpacing.touchTarget),
                    shape = MaterialTheme.shapes.small,
                )
            }
        }
    }

    val rankKey = mapOf(
        "涨幅" to "gainers",
        "跌幅" to "losers",
        "成交额" to "amount",
        "主力流入" to "main_inflow",
        "主力流出" to "main_outflow",
    )[rankingType]

    if (rankKey == null) {
        if (quotes.isEmpty() && !loading) {
            item { EmptyState("暂无个股数据，请尝试搜索或同步") }
        }
        items(quotes, key = { it.symbol }) { quote ->
            MarketQuoteRow(quote, quote.symbol in paperSymbols, onOpenDetail)
        }
    } else {
        val rows = pulse?.rankings?.get(rankKey).orEmpty()
        if (rows.isEmpty() && !loading) {
            item { EmptyState("暂无排行数据") }
        }
        items(rows, key = { it.symbol }) { row ->
            MarketRankingRow(row, rankingType, pulse?.retrieved_at, onOpenDetail)
        }
    }
}

@Composable
private fun EmptyState(msg: String) {
    Box(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.xLarge),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            msg,
            style = CompactTypography.secondary,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun MarketSessionStrip(pulse: MarketIntelligenceDto?) {
    val colors = MaterialTheme.marketColors
    val mainNet = pulse?.fund_flow?.get("主力")?.get("net_amount")
    val mainNetColor = when {
        mainNet == null -> MaterialTheme.colorScheme.onSurface
        mainNet > 0 -> colors.rise
        mainNet < 0 -> colors.fall
        else -> colors.neutral
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = AppSpacing.touchTarget)
            .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.rowVertical),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        DenseStateTag(
            text = when (pulse?.data_health) {
                "fresh" -> "实时"
                "stale_fallback" -> "缓存"
                "pending" -> "同步中"
                else -> "离线"
            },
            color = MaterialTheme.colorScheme.primary,
        )
        Spacer(Modifier.width(AppSpacing.small))
        Text(
            marketFreshnessLabel(pulse),
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.weight(1f),
        )
        Column(horizontalAlignment = Alignment.End) {
            Text(
                "主力净额",
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                mainNet?.let {
                    "${if (it >= 0) "+" else ""}${"%.2f".format(it / 100000000)}亿"
                } ?: "--",
                style = CompactTypography.rowValue,
                color = mainNetColor,
            )
        }
    }
    TradingRowDivider()
}

@Composable
private fun MarketRankingPreview(
    title: String,
    rows: List<MarketRankingDto>,
    color: Color,
    modifier: Modifier = Modifier,
    showNetAmount: Boolean = false,
) {
    Column(
        modifier = modifier.padding(vertical = AppSpacing.small),
    ) {
        Text(
            title,
            style = CompactTypography.caption,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(AppSpacing.xs))
        if (rows.isEmpty()) {
            Text(
                "--",
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            rows.take(3).forEach { row ->
                Row(
                    Modifier.fillMaxWidth().padding(vertical = AppSpacing.xxs),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(
                        row.name.ifBlank { row.symbol },
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        style = CompactTypography.caption,
                        modifier = Modifier.weight(1f),
                    )
                    Spacer(Modifier.width(AppSpacing.small))
                    Text(
                        if (showNetAmount) {
                            row.net_amount?.let { "${"%.1f".format(it / 100000000)}亿" } ?: "--"
                        } else {
                            row.change_percent?.let {
                                "${if (it > 0) "+" else ""}${"%.1f".format(it)}%"
                            } ?: "--"
                        },
                        color = color,
                        style = CompactTypography.caption,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }
        }
    }
}

@Composable
internal fun MarketQuoteRow(
    quote: MarketQuoteDto,
    isPaperPosition: Boolean,
    onOpenDetail: (ResearchTargetDto) -> Unit,
) {
    val change = quote.change_percent ?: 0.0
    val colors = MaterialTheme.marketColors
    val changeColor = when {
        change > 0 -> colors.rise
        change < 0 -> colors.fall
        else -> colors.neutral
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = AppSpacing.touchTarget)
            .clickable {
                onOpenDetail(
                    ResearchTargetDto(
                        quote.symbol,
                        quote.name,
                        "market",
                        quote.as_of ?: "",
                    )
                )
            }
            .padding(horizontal = AppSpacing.rowHorizontal, vertical = AppSpacing.rowVertical),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    quote.name.ifBlank { quote.symbol },
                    style = CompactTypography.rowTitle,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                if (isPaperPosition) {
                    Spacer(Modifier.width(AppSpacing.small))
                    DenseStateTag(
                        text = "持仓",
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }
            Text(
                quote.symbol,
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(
                quote.price?.let { "%.2f".format(it) } ?: "--",
                style = CompactTypography.rowValue,
            )
            Text(
                "${if (change > 0) "+" else ""}${"%.2f".format(change)}%",
                color = changeColor,
                style = CompactTypography.caption,
                fontWeight = FontWeight.SemiBold,
            )
        }
    }
    TradingRowDivider()
}

@Composable
private fun MarketRankingRow(
    row: MarketRankingDto,
    ranking: String,
    asOf: String?,
    onOpenDetail: (ResearchTargetDto) -> Unit,
) {
    val value = if (ranking.startsWith("主力")) row.net_amount else row.change_percent
    val colors = MaterialTheme.marketColors
    val valueColor = when {
        (value ?: 0.0) > 0 -> colors.rise
        (value ?: 0.0) < 0 -> colors.fall
        else -> colors.neutral
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = AppSpacing.touchTarget)
            .clickable {
                onOpenDetail(ResearchTargetDto(row.symbol, row.name, "market", asOf ?: ""))
            }
            .padding(horizontal = AppSpacing.rowHorizontal, vertical = AppSpacing.rowVertical),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                row.name.ifBlank { row.symbol },
                style = CompactTypography.rowTitle,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                row.symbol,
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(
                row.price?.let { "%.2f".format(it) } ?: "--",
                style = CompactTypography.rowValue,
            )
            Text(
                if (ranking.startsWith("主力")) {
                    row.net_amount?.let {
                        "${if (it > 0) "+" else ""}${"%.2f".format(it / 100000000)}亿"
                    } ?: "--"
                } else {
                    row.change_percent?.let {
                        "${if (it > 0) "+" else ""}${"%.2f".format(it)}%"
                    } ?: "--"
                },
                color = valueColor,
                style = CompactTypography.caption,
                fontWeight = FontWeight.SemiBold,
            )
        }
    }
    TradingRowDivider()
}

@Composable
private fun SectorDrillDownSheet(
    sector: MarketSectorDto,
    detail: MarketSectorDetailDto?,
    loading: Boolean,
    onOpenDetail: (ResearchTargetDto) -> Unit,
) {
    var visibleRows by remember(sector.name, detail?.retrieved_at) { mutableIntStateOf(10) }
    val allRows = detail?.rows.orEmpty().take(50)

    Column(
        Modifier
            .fillMaxWidth()
            .fillMaxHeight(0.8f)
            .padding(horizontal = AppSpacing.contentHorizontal)
    ) {
        Text(sector.name, style = CompactTypography.pageTitle)
        Text(
            "板块成分股实时资金表现",
            style = CompactTypography.secondary,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Spacer(Modifier.height(AppSpacing.medium))

        if (loading) {
            LinearProgressIndicator(Modifier.fillMaxWidth())
        }

        LazyColumn(Modifier.weight(1f)) {
            items(allRows.take(visibleRows)) { row ->
                Row(
                    Modifier
                        .fillMaxWidth()
                        .heightIn(min = AppSpacing.touchTarget)
                        .clickable {
                            onOpenDetail(
                                ResearchTargetDto(
                                    row.symbol,
                                    row.name,
                                    "market",
                                    detail?.retrieved_at ?: "",
                                )
                            )
                        }
                        .padding(vertical = AppSpacing.rowVertical),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(
                            row.name.ifBlank { row.symbol },
                            style = CompactTypography.rowTitle,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Text(
                            row.symbol,
                            style = CompactTypography.caption,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Column(horizontalAlignment = Alignment.End) {
                        Text(
                            row.price?.let { "%.2f".format(it) } ?: "--",
                            style = CompactTypography.rowValue,
                        )
                        Text(
                            row.net_amount?.let {
                                "${if (it > 0) "+" else ""}${"%.2f".format(it / 100000000)}亿"
                            } ?: "--",
                            color = if ((row.net_amount ?: 0.0) >= 0) {
                                MaterialTheme.marketColors.rise
                            } else {
                                MaterialTheme.marketColors.fall
                            },
                            style = CompactTypography.caption,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                }
                TradingRowDivider(inset = false)
            }
        }
    }
}

private fun marketFreshnessLabel(pulse: MarketIntelligenceDto?): String = when (pulse?.data_health) {
    "fresh" -> "更新于 ${pulse.retrieved_at?.substringAfter('T')?.substringBefore('+')?.take(5) ?: "刚刚"}"
    "stale_fallback" -> "数据延迟 · 缓存显示"
    "pending" -> "正在同步最新行情"
    else -> "离线模式"
}
