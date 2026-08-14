package com.thirdhand.app

import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.TrendingDown
import androidx.compose.material.icons.filled.TrendingFlat
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.components.TradingSection
import com.thirdhand.app.ui.theme.LocalMarketColors
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MarketScreen(onOpenDetail: (ResearchTargetDto) -> Unit) {
    val context = LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var quotes by remember { mutableStateOf<List<MarketQuoteDto>>(emptyList()) }
    var pulse by remember { mutableStateOf<MarketIntelligenceDto?>(null) }
    var paperSymbols by remember { mutableStateOf<Set<String>>(emptySet()) }
    var selectedTab by remember { mutableStateOf(0) }
    var stockRanking by remember { mutableStateOf("全部") }
    var selectedSector by remember { mutableStateOf<MarketSectorDto?>(null) }
    var sectorDetail by remember { mutableStateOf<MarketSectorDetailDto?>(null) }
    var sectorLoading by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    fun refresh() = scope.launch {
        loading = true
        runCatching {
            val positions = api.paperTradingAccount().positions.map { it.symbol }.toSet()
            val sorted = api.cachedMarketQuotes().sortedWith(compareByDescending<MarketQuoteDto> { it.symbol in positions }.thenBy { it.name.ifBlank { it.symbol } })
            Triple(positions, sorted, api.marketIntelligence(refresh = true))
        }.onSuccess { (positions, cachedQuotes, intelligence) ->
            paperSymbols = positions; quotes = cachedQuotes; pulse = intelligence; error = null
            // The server starts AKShare collection in the background.  Show the
            // cached snapshot immediately, then quietly read it again instead
            // of making the user press refresh a second time.
            scope.launch {
                delay(1400)
                runCatching { api.marketIntelligence() }.onSuccess { refreshed ->
                    if (refreshed.data_health != "pending" || refreshed.indices.isNotEmpty()) pulse = refreshed
                }
            }
        }.onFailure { error = "无法读取行情缓存：${it.message ?: "请检查服务连接"}" }
        loading = false
    }
    LaunchedEffect(Unit) { refresh() }
    LaunchedEffect(selectedSector?.name) {
        val sector = selectedSector?.name ?: return@LaunchedEffect
        sectorLoading = true
        sectorDetail = runCatching {
            api.marketSectorIntelligence(sector, refresh = true)
            delay(900)
            api.marketSectorIntelligence(sector)
        }.getOrElse { MarketSectorDetailDto(sector = sector, data_health = "unavailable", error_message = it.message ?: "板块数据暂不可用") }
        sectorLoading = false
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
        item { TradingPageHeader("行情", "全市场快照、资金流与模拟持仓") { IconButton(onClick = ::refresh, enabled = !loading) { if (loading) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp) else Icon(Icons.Filled.Refresh, "刷新行情") } } }
        if (loading) item { LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) }
        error?.let { item { Text(it, Modifier.padding(horizontal = 20.dp, vertical = 12.dp), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) } }
        item { TabRow(selectedTabIndex = selectedTab) { listOf("大盘", "板块", "个股").forEachIndexed { index, label -> Tab(selected = selectedTab == index, onClick = { selectedTab = index }, text = { Text(label) }) } } }
        when (selectedTab) {
            0 -> item { MarketOverview(pulse) }
            1 -> item { MarketSectorRanking(pulse, onOpenSector = { selectedSector = it; sectorDetail = null }) }
            else -> {
                item { TradingSection("全部股票", if (quotes.isEmpty()) "等待本地数据" else "模拟持仓置顶 · 共 ${quotes.size} 只 · 点击查看详情与 K 线") }
                item { StockRankingFilters(stockRanking) { stockRanking = it } }
                if (!loading && quotes.isEmpty()) item { Text("数据库还没有股票行情。完成一次市场扫描或模拟分析后，数据会显示在这里。", Modifier.padding(horizontal = 20.dp, vertical = 14.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                val rankKey = mapOf("涨幅" to "gainers", "跌幅" to "losers", "成交额" to "amount", "主力流入" to "main_inflow", "主力流出" to "main_outflow")[stockRanking]
                if (rankKey == null) {
                    items(quotes, key = { it.symbol }) { quote -> MarketQuoteRow(quote, quote.symbol in paperSymbols, onOpenDetail) }
                } else {
                    items(pulse?.rankings?.get(rankKey).orEmpty(), key = { it.symbol }) { row -> MarketRankingRow(row, stockRanking, pulse?.retrieved_at, onOpenDetail) }
                }
            }
        }
    }
    selectedSector?.let { sector ->
        ModalBottomSheet(onDismissRequest = { selectedSector = null; sectorDetail = null }) {
            SectorDrillDownSheet(sector, sectorDetail, sectorLoading, onOpenDetail)
        }
    }
}

@Composable private fun StockRankingFilters(selected: String, onSelected: (String) -> Unit) {
    LazyRow(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
        items(listOf("全部", "涨幅", "跌幅", "成交额", "主力流入", "主力流出")) { label ->
            FilterChip(selected = selected == label, onClick = { onSelected(label) }, label = { Text(label) }, modifier = Modifier.padding(end = 8.dp))
        }
    }
}

@Composable private fun MarketOverview(pulse: MarketIntelligenceDto?) {
    val colors = LocalMarketColors.current
    val breadth = pulse?.breadth.orEmpty()
    MarketSessionCard(pulse)
    TradingSection("市场概览", marketFreshnessLabel(pulse))
    androidx.compose.material3.Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
        colors = androidx.compose.material3.CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
    Row(Modifier.fillMaxWidth().padding(12.dp)) {
        pulse?.indices?.take(3)?.forEach { index ->
            val change = index.change_percent ?: 0.0
            Column(Modifier.weight(1f).padding(end = 8.dp)) {
                Text(index.name, style = MaterialTheme.typography.labelMedium)
                Text(index.price?.let { "%.2f".format(it) } ?: "--", fontWeight = FontWeight.SemiBold)
                Text("${if (change > 0) "+" else ""}${"%.2f".format(change)}%", color = if (change >= 0) colors.rise else colors.fall, style = MaterialTheme.typography.labelSmall)
            }
        }
    }
    }
    Text("涨 ${breadth["rise_count"]?.toInt() ?: "--"} · 平 ${breadth["flat_count"]?.toInt() ?: "--"} · 跌 ${breadth["fall_count"]?.toInt() ?: "--"}", Modifier.padding(horizontal = 20.dp, vertical = 12.dp), style = MaterialTheme.typography.bodyMedium)
    val mainNet = pulse?.fund_flow?.get("主力")?.get("net_amount")
    Text("主力净流入  ${mainNet?.let { "%.2f 亿".format(it / 100000000) } ?: "数据待补齐"}", Modifier.padding(horizontal = 20.dp), color = if ((mainNet ?: 0.0) >= 0) colors.rise else colors.fall, style = MaterialTheme.typography.titleSmall)
    TradingSection("股票排行", "涨幅与成交额 · 点击个股页查看完整列表")
    Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) {
        MarketRankingPreview("涨幅榜", pulse?.rankings?.get("gainers").orEmpty(), colors.rise, Modifier.weight(1f))
        MarketRankingPreview("跌幅榜", pulse?.rankings?.get("losers").orEmpty(), colors.fall, Modifier.weight(1f))
    }
    TradingSection("主力资金榜", "个股净流入 / 净流出")
    Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) {
        MarketRankingPreview("主力流入", pulse?.rankings?.get("main_inflow").orEmpty(), colors.rise, Modifier.weight(1f), showNetAmount = true)
        MarketRankingPreview("主力流出", pulse?.rankings?.get("main_outflow").orEmpty(), colors.fall, Modifier.weight(1f), showNetAmount = true)
    }
    pulse?.northbound?.firstOrNull()?.let { northbound ->
        Text("北向 ${northbound.direction.ifBlank { northbound.type }}  ${northbound.net_amount?.let { "%.2f 亿".format(it) } ?: "--"}", Modifier.padding(horizontal = 20.dp, vertical = 14.dp), style = MaterialTheme.typography.bodyMedium, color = if ((northbound.net_amount ?: 0.0) >= 0) colors.rise else colors.fall)
    }
    pulse?.error_message?.let { Text("数据降级：$it", Modifier.padding(20.dp), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.labelSmall) }
}

private fun marketFreshnessLabel(pulse: MarketIntelligenceDto?): String = when (pulse?.data_health) {
    "fresh" -> "已更新 ${pulse.retrieved_at?.replace('T', ' ')?.substringBefore('+')?.takeLast(16) ?: "刚刚"}"
    "stale_fallback" -> "使用最近缓存 · 数据延迟"
    "pending" -> "正在后台采集"
    else -> "数据部分可用"
}

@Composable
private fun MarketSessionCard(pulse: MarketIntelligenceDto?) {
    val colors = LocalMarketColors.current
    val mainNet = pulse?.fund_flow?.get("主力")?.get("net_amount")
    androidx.compose.material3.Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp),
        colors = androidx.compose.material3.CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer,
            contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
        ),
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("开盘中", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text(marketFreshnessLabel(pulse), style = MaterialTheme.typography.labelSmall)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text("主力净流入", style = MaterialTheme.typography.labelSmall)
                    Text(
                        mainNet?.let { "%.2f 亿".format(it / 100000000) } ?: "--",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                        color = if ((mainNet ?: 0.0) >= 0) colors.rise else colors.fall,
                    )
                }
            }
            Text(
                "数据按市场快照刷新；涨跌颜色同时以数值与正负号表达。",
                modifier = Modifier.padding(top = 8.dp),
                style = MaterialTheme.typography.labelSmall,
            )
        }
    }
}

@Composable private fun MarketRankingPreview(title: String, rows: List<MarketRankingDto>, color: androidx.compose.ui.graphics.Color, modifier: Modifier = Modifier, showNetAmount: Boolean = false) {
    Column(modifier.padding(end = 12.dp)) {
        Text(title, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        rows.take(3).forEach { row -> Row(Modifier.fillMaxWidth().padding(top = 5.dp)) { Text(row.name.ifBlank { row.symbol }, Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.labelSmall); Text(if (showNetAmount) row.net_amount?.let { "%.2f 亿".format(it / 100000000) } ?: "--" else row.change_percent?.let { "%.2f%%".format(it) } ?: "--", color = color, style = MaterialTheme.typography.labelSmall) } }
    }
}

@Composable private fun MarketSectorRanking(pulse: MarketIntelligenceDto?, onOpenSector: (MarketSectorDto) -> Unit) {
    TradingSection("行业资金流", "涨跌幅 · 主力净流入 · 点击查看成分股")
    (pulse?.sectors ?: emptyList()).take(15).forEach { sector ->
        Row(Modifier.fillMaxWidth().clickable { onOpenSector(sector) }.padding(horizontal = 20.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(sector.name, Modifier.weight(1f), fontWeight = FontWeight.Medium)
            Column(Modifier.weight(1f), horizontalAlignment = Alignment.End) {
                val change = sector.change_percent ?: 0.0
                Text("${if (change > 0) "+" else ""}${"%.2f".format(change)}%", color = if (change >= 0) LocalMarketColors.current.rise else LocalMarketColors.current.fall, style = MaterialTheme.typography.labelMedium)
                Text(sector.leader, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            Text(sector.net_amount?.let { "%.2f 亿".format(it / 100000000) } ?: "--", Modifier.padding(start = 12.dp), color = if ((sector.net_amount ?: 0.0) >= 0) LocalMarketColors.current.rise else LocalMarketColors.current.fall)
        }
        TradingRowDivider()
    }
}

@Composable private fun MarketRankingRow(row: MarketRankingDto, ranking: String, asOf: String?, onOpenDetail: (ResearchTargetDto) -> Unit) {
    val value = if (ranking.startsWith("主力")) row.net_amount else row.change_percent
    val color = if ((value ?: 0.0) >= 0) LocalMarketColors.current.rise else LocalMarketColors.current.fall
    Column(Modifier.fillMaxWidth().clickable { onOpenDetail(ResearchTargetDto(row.symbol, row.name, "market", asOf ?: "")) }.padding(horizontal = 20.dp, vertical = 12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) { Text(row.name.ifBlank { row.symbol }, fontWeight = FontWeight.SemiBold); Text(row.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            Column(horizontalAlignment = Alignment.End) { Text(row.price?.let { "%.2f".format(it) } ?: "--", fontWeight = FontWeight.Medium); Text(if (ranking.startsWith("主力")) row.net_amount?.let { "%.2f 亿".format(it / 100000000) } ?: "--" else row.change_percent?.let { "${if (it > 0) "+" else ""}%.2f%%".format(it) } ?: "--", color = color, style = MaterialTheme.typography.labelMedium) }
        }
        TradingRowDivider()
    }
}

@Composable private fun SectorDrillDownSheet(sector: MarketSectorDto, detail: MarketSectorDetailDto?, loading: Boolean, onOpenDetail: (ResearchTargetDto) -> Unit) {
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 8.dp)) {
        Text(sector.name, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
        Text("行业成分股 · 按主力资金流查看", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (loading || detail?.data_health == "pending") LinearProgressIndicator(Modifier.fillMaxWidth().padding(vertical = 16.dp))
        detail?.error_message?.let { Text(it, Modifier.padding(vertical = 8.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
        detail?.rows?.take(30)?.forEach { row ->
            Row(Modifier.fillMaxWidth().clickable { onOpenDetail(ResearchTargetDto(row.symbol, row.name, "market", detail.retrieved_at ?: "")) }.padding(vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) { Text(row.name.ifBlank { row.symbol }, fontWeight = FontWeight.Medium); Text(row.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                Column(horizontalAlignment = Alignment.End) { Text(row.price?.let { "%.2f".format(it) } ?: "--"); Text(row.net_amount?.let { "%.2f 亿".format(it / 100000000) } ?: "--", color = if ((row.net_amount ?: 0.0) >= 0) LocalMarketColors.current.rise else LocalMarketColors.current.fall, style = MaterialTheme.typography.labelMedium) }
            }
            TradingRowDivider()
        }
        if (!loading && detail?.rows.isNullOrEmpty()) Text("暂无可用成分股资金流，请稍后在行情页点击刷新。", Modifier.padding(vertical = 20.dp), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable private fun MarketQuoteRow(quote: MarketQuoteDto, isPaperPosition: Boolean, onOpenDetail: (ResearchTargetDto) -> Unit) {
    val change = quote.change_percent ?: 0.0
    val color = when { change > 0 -> LocalMarketColors.current.rise; change < 0 -> LocalMarketColors.current.fall; else -> LocalMarketColors.current.neutral }
    Column(Modifier.fillMaxWidth().clickable { onOpenDetail(ResearchTargetDto(quote.symbol, quote.name, "market", quote.as_of ?: "")) }.padding(horizontal = 20.dp, vertical = 12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) { Text(quote.name.ifBlank { quote.symbol }, maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.SemiBold); if (isPaperPosition) Text("模拟持仓", Modifier.padding(start = 6.dp), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelSmall) }
                Text("${quote.symbol} · ${quote.as_of?.replace('T', ' ')?.substringBefore('+')?.takeLast(11) ?: "时间未知"}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Column(horizontalAlignment = Alignment.End) { Text(quote.price?.let { "%.2f".format(it) } ?: "--", fontWeight = FontWeight.SemiBold); Row(verticalAlignment = Alignment.CenterVertically) { Icon(when { change > 0 -> Icons.Filled.TrendingUp; change < 0 -> Icons.Filled.TrendingDown; else -> Icons.Filled.TrendingFlat }, if (change > 0) "上涨" else if (change < 0) "下跌" else "平盘", tint = color, modifier = Modifier.size(16.dp)); Text("${if (change > 0) "+" else ""}${"%.2f".format(change)}%", color = color, style = MaterialTheme.typography.labelMedium) } }
        }
        TradingRowDivider()
    }
}
