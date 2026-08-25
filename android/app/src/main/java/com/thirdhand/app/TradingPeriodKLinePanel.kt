package com.thirdhand.app

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.components.KLineChart
import com.thirdhand.app.ui.theme.AppSpacing
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.temporal.WeekFields
import java.util.Locale

@Composable
fun TradingPeriodKLinePanel(symbol: String, quote: MarketQuoteDto?) {
    val context = LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()

    var bars by remember(symbol) { mutableStateOf<List<DailyPriceDto>>(emptyList()) }
    var intradayBars by remember(symbol) { mutableStateOf<List<DailyPriceDto>>(emptyList()) }
    var period by remember { mutableStateOf("日线") }
    var loading by remember(symbol) { mutableStateOf(true) }
    var error by remember(symbol) { mutableStateOf<String?>(null) }
    var paperLogs by remember(symbol) { mutableStateOf<List<PaperTradingLogDto>>(emptyList()) }

    fun loadData() = scope.launch {
        loading = true
        error = null
        runCatching {
            val daily = api.marketHistory(symbol, limit = 5_000)
            val intraday = api.marketIntraday(symbol, limit = 2_000).map { bar ->
                DailyPriceDto(
                    trading_date = bar.bar_time,
                    open = bar.open,
                    close = bar.close,
                    high = bar.high,
                    low = bar.low,
                    volume = bar.volume,
                    amount = bar.amount,
                    adjustment = "1m"
                )
            }
            val logs = api.paperTradingLogs(symbol).filter { it.status == "executed" }
            Triple(daily, intraday, logs)
        }.onSuccess { (daily, intraday, logs) ->
            bars = daily
            val latestSession = intraday.maxOfOrNull { it.trading_date.take(10) }
            intradayBars = intraday.filter { it.trading_date.take(10) == latestSession }
            paperLogs = logs
        }.onFailure {
            error = "无法加载 K 线数据"
        }
        loading = false
    }

    LaunchedEffect(symbol) {
        loadData()
    }

    Column(Modifier.fillMaxWidth().padding(AppSpacing.large)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text("技术图表", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                    Text(
                        text = quote?.let { "${it.name.ifBlank { symbol }} · ${it.symbol}" } ?: symbol,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }

                Row {
                    listOf("分时", "日线", "周线", "月线").forEach { p ->
                        TextButton(
                            onClick = { period = p },
                            contentPadding = PaddingValues(horizontal = 8.dp, vertical = 0.dp),
                            modifier = Modifier.height(32.dp)
                        ) {
                            Text(
                                text = p,
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = if (period == p) FontWeight.Bold else FontWeight.Normal,
                                color = if (period == p) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
            }

            Spacer(Modifier.height(AppSpacing.medium))

            Box(
                modifier = Modifier.fillMaxWidth().height(240.dp),
                contentAlignment = Alignment.Center
            ) {
                if (loading) {
                    CircularProgressIndicator(Modifier.size(24.dp))
                } else if (error != null) {
                    Text(error!!, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                } else {
                    val chartBars = when (period) {
                        "分时" -> intradayBars
                        "日线" -> bars
                        "周线" -> aggregateBars(bars, "周线")
                        "月线" -> aggregateBars(bars, "月线")
                        else -> bars
                    }

                    if (chartBars.isNotEmpty()) {
                        KLineChart(
                            bars = chartBars,
                            quote = quote,
                            useTimeAxis = period == "分时",
                            paperMarkers = paperLogs
                        )
                    } else {
                        Text("暂无数据", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
    }
}

private fun aggregateBars(bars: List<DailyPriceDto>, period: String): List<DailyPriceDto> {
    if (period == "日线") return bars

    return bars.mapNotNull { bar ->
        runCatching {
            val trimmed = bar.trading_date.trim()
            if (Regex("\\d{8}").matches(trimmed)) LocalDate.parse(trimmed, DateTimeFormatter.BASIC_ISO_DATE)
            else LocalDate.parse(trimmed.take(10))
        }.getOrNull()?.let { it to bar }
    }.groupBy { (date, _) ->
        if (period == "周线") "${date.year}-W${date.get(WeekFields.of(Locale.US).weekOfWeekBasedYear())}"
        else "${date.year}-${date.monthValue}"
    }.values.map { group ->
        val rows = group.map { it.second }
        DailyPriceDto(
            trading_date = rows.last().trading_date,
            open = rows.first().open,
            close = rows.last().close,
            high = rows.maxOfOrNull { it.high ?: it.close },
            low = rows.minOfOrNull { it.low ?: it.close },
            volume = rows.sumOf { it.volume ?: 0.0 },
            amount = rows.sumOf { it.amount ?: 0.0 },
            adjustment = rows.last().adjustment,
            source = rows.last().source
        )
    }
}
