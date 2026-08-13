package com.thirdhand.app

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.TrendingDown
import androidx.compose.material.icons.filled.TrendingFlat
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
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

@Composable
fun MarketScreen(onOpenDetail: (ResearchTargetDto) -> Unit) {
    val context = LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var quotes by remember { mutableStateOf<List<MarketQuoteDto>>(emptyList()) }
    var paperSymbols by remember { mutableStateOf<Set<String>>(emptySet()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    fun refresh() = scope.launch {
        loading = true
        runCatching {
            val positions = api.paperTradingAccount().positions.map { it.symbol }.toSet()
            val sorted = api.cachedMarketQuotes().sortedWith(
                compareByDescending<MarketQuoteDto> { it.symbol in positions }
                    .thenBy { it.name.ifBlank { it.symbol } },
            )
            positions to sorted
        }.onSuccess { (positions, sorted) ->
            paperSymbols = positions; quotes = sorted; error = null
        }.onFailure { error = "无法读取本地行情库：${it.message ?: "请检查服务连接"}" }
        loading = false
    }
    LaunchedEffect(Unit) { refresh() }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
        item { TradingPageHeader("行情", "数据库内保存的全部股票快照") { IconButton(onClick = ::refresh, enabled = !loading) { if (loading) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp) else Icon(Icons.Filled.Refresh, "刷新行情") } } }
        if (loading) item { LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) }
        error?.let { item { Text(it, Modifier.padding(horizontal = 20.dp, vertical = 12.dp), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) } }
        item { TradingSection("全部股票", if (quotes.isEmpty()) "等待本地数据" else "模拟持仓置顶 · 已收录 ${quotes.size} 只 · 点击查看详情与 K 线") }
        if (!loading && quotes.isEmpty()) item { Text("本地数据库还没有股票行情。完成一次市场扫描或模拟分析后，数据会显示在这里。", Modifier.padding(horizontal = 20.dp, vertical = 14.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(quotes, key = { it.symbol }) { quote ->
            val change = quote.change_percent ?: 0.0
            val color = when { change > 0 -> LocalMarketColors.current.rise; change < 0 -> LocalMarketColors.current.fall; else -> LocalMarketColors.current.neutral }
            Column(Modifier.fillMaxWidth().clickable { onOpenDetail(ResearchTargetDto(quote.symbol, quote.name, "market", quote.as_of ?: "")) }.padding(horizontal = 20.dp, vertical = 12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(quote.name.ifBlank { quote.symbol }, maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.SemiBold)
                            if (quote.symbol in paperSymbols) Text("模拟持仓", Modifier.padding(start = 6.dp), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelSmall)
                        }
                        Text("${quote.symbol} · ${quote.as_of?.replace('T', ' ')?.substringBefore("+")?.takeLast(11) ?: "时间未知"}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Column(horizontalAlignment = Alignment.End) {
                        Text(quote.price?.let { "%.2f".format(it) } ?: "--", fontWeight = FontWeight.SemiBold)
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = when { change > 0 -> Icons.Filled.TrendingUp; change < 0 -> Icons.Filled.TrendingDown; else -> Icons.Filled.TrendingFlat },
                                contentDescription = when { change > 0 -> "上涨"; change < 0 -> "下跌"; else -> "平盘" },
                                tint = color,
                                modifier = Modifier.size(16.dp),
                            )
                            Text("${if (change > 0) "+" else ""}${"%.2f".format(change)}%", color = color, style = MaterialTheme.typography.labelMedium)
                        }
                    }
                }
                androidx.compose.foundation.layout.Spacer(Modifier.padding(top = 10.dp)); TradingRowDivider()
            }
        }
    }
}
