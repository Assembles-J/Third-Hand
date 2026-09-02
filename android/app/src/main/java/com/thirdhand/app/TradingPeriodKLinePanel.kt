package com.thirdhand.app

import android.util.Log
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.components.KLineChart
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.CompactTypography
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
    var intradayLoading by remember(symbol) { mutableStateOf(true) }
    var error by remember(symbol) { mutableStateOf<String?>(null) }
    var paperLogs by remember(symbol) { mutableStateOf<List<PaperTradingLogDto>>(emptyList()) }
    var indicatorsVisible by remember(symbol) { mutableStateOf(true) }

    fun loadData() = scope.launch {
        loading = true
        intradayLoading = true
        error = null

        val daily = runCatching {
            api.marketHistory(symbol, limit = 800)
        }.onFailure { throwable ->
            Log.e(TAG_KLINE, "Failed to load daily K-line bars for symbol=$symbol", throwable)
        }.getOrElse {
            loading = false
            intradayLoading = false
            if (bars.isEmpty()) error = "无法加载 K 线数据"
            return@launch
        }

        // Daily history is the core chart contract. Render it immediately instead
        // of keeping the whole chart behind optional intraday/marker requests.
        bars = daily
        loading = false

        launch {
            intradayLoading = true
            intradayBars = runCatching {
                api.marketIntraday(symbol, limit = 1_500).map { bar ->
                    DailyPriceDto(
                        trading_date = bar.bar_time,
                        open = bar.open,
                        close = bar.close,
                        high = bar.high,
                        low = bar.low,
                        volume = bar.volume,
                        amount = bar.amount,
                        adjustment = "1m",
                    )
                }
            }.onFailure { throwable ->
                Log.w(TAG_KLINE, "Failed to load intraday bars for symbol=$symbol", throwable)
            }.getOrDefault(emptyList()).let(::latestIntradaySession)
            intradayLoading = false
        }

        launch {
            paperLogs = runCatching {
                api.paperTradingLogs(symbol).filter { it.status == "executed" }
            }.onFailure { throwable ->
                Log.w(TAG_KLINE, "Failed to load paper-trading markers for symbol=$symbol", throwable)
            }.getOrDefault(emptyList())
        }
    }

    LaunchedEffect(symbol) { loadData() }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = MaterialTheme.shapes.large,
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        border = BorderStroke(0.5.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.36f)),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = AppSpacing.large, vertical = AppSpacing.medium),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.small),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                listOf("分时", "日线", "周线", "月线").forEach { item ->
                    val selected = period == item
                    TextButton(
                        onClick = { period = item },
                        modifier = Modifier.weight(1f).height(36.dp),
                        contentPadding = PaddingValues(horizontal = 2.dp, vertical = 0.dp),
                        colors = ButtonDefaults.textButtonColors(
                            containerColor = MaterialTheme.colorScheme.surface,
                            contentColor = if (selected) {
                                MaterialTheme.colorScheme.primary
                            } else {
                                MaterialTheme.colorScheme.onSurfaceVariant
                            },
                        ),
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                text = item,
                                style = CompactTypography.body,
                                fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
                            )
                            Box(
                                modifier = Modifier
                                    .padding(top = 3.dp)
                                    .width(24.dp)
                                    .height(2.dp)
                                    .background(
                                        if (selected) MaterialTheme.colorScheme.primary else Color.Transparent,
                                        MaterialTheme.shapes.extraSmall,
                                    ),
                            )
                        }
                    }
                }

                TextButton(
                    onClick = { indicatorsVisible = !indicatorsVisible },
                    enabled = period != "分时",
                    modifier = Modifier.width(64.dp).height(36.dp),
                    contentPadding = PaddingValues(horizontal = 2.dp, vertical = 0.dp),
                    colors = ButtonDefaults.textButtonColors(
                        contentColor = if (indicatorsVisible && period != "分时") {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        },
                    ),
                ) {
                    Icon(Icons.Default.Tune, contentDescription = null, modifier = Modifier.size(15.dp))
                    Text("指标", style = CompactTypography.caption)
                }
            }

            Text(
                text = if (period == "分时") {
                    intradaySessionHint(intradayBars)
                } else {
                    "左右拖拽查看历史 · 双指缩放"
                },
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            when {
                loading && bars.isEmpty() -> {
                    Box(
                        modifier = Modifier.fillMaxWidth().height(220.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp)
                    }
                }
                error != null && bars.isEmpty() -> {
                    Box(
                        modifier = Modifier.fillMaxWidth().height(220.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(error!!, style = CompactTypography.secondary, color = MaterialTheme.colorScheme.error)
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
                            paperMarkers = if (period == "分时") emptyList() else paperLogs,
                            showMovingAverages = period != "分时" && indicatorsVisible,
                        )
                    } else if (period == "分时" && intradayLoading) {
                        Box(
                            modifier = Modifier.fillMaxWidth().height(180.dp),
                            contentAlignment = Alignment.Center,
                        ) {
                            CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
                        }
                    } else {
                        Box(
                            modifier = Modifier.fillMaxWidth().height(180.dp),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(
                                if (period == "分时") "最新交易日暂无分时数据" else "暂无数据",
                                style = CompactTypography.secondary,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
        }
    }
}

internal fun latestIntradaySession(intradayBars: List<DailyPriceDto>): List<DailyPriceDto> {
    val latestSession = intradayBars.maxOfOrNull { it.trading_date.take(10) } ?: return emptyList()
    return intradayBars.filter { it.trading_date.take(10) == latestSession }
}

internal fun intradaySessionHint(intradayBars: List<DailyPriceDto>): String {
    val date = intradayBars.lastOrNull()?.trading_date?.take(10)
    return if (date.isNullOrBlank()) {
        "分时仅展示最新单个交易日"
    } else {
        "分时仅展示 $date"
    }
}

internal fun chartBarsForPeriod(
    period: String,
    dailyBars: List<DailyPriceDto>,
    intradayBars: List<DailyPriceDto>,
): List<DailyPriceDto> = when (period) {
    "分时" -> latestIntradaySession(intradayBars)
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
            source = rows.last().source,
        )
    }
}

private const val TAG_KLINE = "KLine"