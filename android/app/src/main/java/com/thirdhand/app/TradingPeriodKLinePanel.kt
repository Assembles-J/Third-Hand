package com.thirdhand.app

import androidx.compose.foundation.BorderStroke
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
    var period by remember(symbol) { mutableStateOf("日线") }
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

    LaunchedEffect(symbol) { loadData() }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.xxLarge),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = MaterialTheme.shapes.large,
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = BorderStroke(0.5.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.55f)),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = AppSpacing.large, vertical = AppSpacing.medium),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.small),
        ) {
            Text(
                text = quote?.let { "${it.name.ifBlank { symbol }} · ${it.symbol}" } ?: symbol,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                listOf("分时", "日线", "周线", "月线").forEach { item ->
                    val selected = period == item
                    TextButton(
                        onClick = { period = item },
                        modifier = Modifier.weight(1f).height(32.dp),
                        contentPadding = PaddingValues(horizontal = 4.dp, vertical = 0.dp),
                        colors = ButtonDefaults.textButtonColors(
                            containerColor = if (selected) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.55f) else MaterialTheme.colorScheme.surface,
                            contentColor = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                        ),
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Text(
                            text = item,
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                        )
                    }
                }
            }

            when {
                loading -> {
                    Box(
                        modifier = Modifier.fillMaxWidth().height(248.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp)
                    }
                }
                error != null -> {
                    Box(
                        modifier = Modifier.fillMaxWidth().height(200.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(error!!, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                            TextButton(onClick = { loadData() }) { Text("重新加载") }
                        }
                    }
                }
                else -> {
                    val chartBars = chartBarsForPeriod(period, bars, intradayBars)
                    if (chartBars.isNotEmpty()) {
                        KLineChart(
                            bars = chartBars,
                            quote = quote,
                            useTimeAxis = period == "分时",
                            paperMarkers = paperLogs,
                        )
                    } else {
                        Box(
                            modifier = Modifier.fillMaxWidth().height(180.dp),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text("暂无数据", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }
}

internal fun chartBarsForPeriod(
    period: String,
    dailyBars: List<DailyPriceDto>,
    intradayBars: List<DailyPriceDto>,
): List<DailyPriceDto> = when (period) {
    "分时" -> intradayBars
    "周线" -> aggregateBars(dailyBars, "周线")
    "月线" -> aggregateBars(dailyBars, "月线")
    else -> dailyBars
}

internal fun aggregateBars(bars: List<DailyPriceDto>, period: String): List<DailyPriceDto> {
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
