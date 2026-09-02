package com.thirdhand.app

import android.util.Log
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
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
import com.thirdhand.app.ui.components.ReferenceKLineChart
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.CompactTypography
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.temporal.WeekFields
import java.util.Locale
import kotlin.math.abs

@Composable
fun TradingPeriodKLinePanel(symbol: String, quote: MarketQuoteDto?) {
    val context = LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()

    var bars by remember(symbol) { mutableStateOf<List<DailyPriceDto>>(emptyList()) }
    var intradayBars by remember(symbol) { mutableStateOf<List<DailyPriceDto>>(emptyList()) }
    var period by remember(symbol) { mutableStateOf("日线") }
    var loading by remember(symbol) { mutableStateOf(true) }
    var loadingMessage by remember(symbol) { mutableStateOf("正在加载历史 K 线") }
    var loadingDetail by remember(symbol) { mutableStateOf("正在读取已缓存行情；缺失部分会由服务端自动补齐。") }
    var intradayLoading by remember(symbol) { mutableStateOf(true) }
    var error by remember(symbol) { mutableStateOf<String?>(null) }
    var paperLogs by remember(symbol) { mutableStateOf<List<PaperTradingLogDto>>(emptyList()) }
    var indicatorsVisible by remember(symbol) { mutableStateOf(true) }

    fun loadData() = scope.launch {
        loading = true
        loadingMessage = "正在加载历史 K 线"
        loadingDetail = "正在读取已缓存行情；缺失部分会由服务端自动补齐。"
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

        // Daily is the core render contract: show it immediately and let optional
        // intraday / marker requests continue independently in the background.
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

    LaunchedEffect(symbol, loading, bars.isEmpty()) {
        if (!loading || bars.isNotEmpty()) return@LaunchedEffect
        delay(1_200)
        if (loading && bars.isEmpty()) {
            loadingMessage = "后台正在拉取历史 K 线"
            loadingDetail = "当前缓存不足，正在等待服务端行情源返回；完成后页面会自动更新。"
        }
        delay(5_000)
        if (loading && bars.isEmpty()) {
            loadingMessage = "行情源响应较慢，仍在获取"
            loadingDetail = "后台请求仍在进行，请稍候，不需要重复刷新。"
        }
    }

    TradingPeriodKLineContent(
        period = period,
        onPeriodChange = { period = it },
        dailyBars = bars,
        intradayBars = intradayBars,
        paperLogs = paperLogs,
        quote = quote,
        loading = loading,
        loadingMessage = loadingMessage,
        loadingDetail = loadingDetail,
        intradayLoading = intradayLoading,
        error = error,
        indicatorsVisible = indicatorsVisible,
        onIndicatorToggle = { indicatorsVisible = !indicatorsVisible },
        onRetry = { loadData() },
    )
}

/** Pure rendering half so screenshot tests exercise the same real card hierarchy. */
@Composable
internal fun TradingPeriodKLineContent(
    period: String,
    onPeriodChange: (String) -> Unit,
    dailyBars: List<DailyPriceDto>,
    intradayBars: List<DailyPriceDto>,
    paperLogs: List<PaperTradingLogDto>,
    quote: MarketQuoteDto?,
    loading: Boolean,
    loadingMessage: String,
    loadingDetail: String,
    intradayLoading: Boolean,
    error: String?,
    indicatorsVisible: Boolean,
    onIndicatorToggle: () -> Unit,
    onRetry: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = RoundedCornerShape(18.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 14.dp, top = 8.dp, bottom = 12.dp),
            verticalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                listOf("分时", "日线", "周线", "月线").forEach { item ->
                    val selected = period == item
                    TextButton(
                        onClick = { onPeriodChange(item) },
                        modifier = Modifier
                            .weight(1f)
                            .height(36.dp),
                        contentPadding = PaddingValues(horizontal = 2.dp, vertical = 0.dp),
                        colors = ButtonDefaults.textButtonColors(
                            containerColor = MaterialTheme.colorScheme.surface,
                            contentColor = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                        ),
                        shape = RoundedCornerShape(0.dp),
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                item,
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
                                        RoundedCornerShape(2.dp),
                                    ),
                            )
                        }
                    }
                }

                TextButton(
                    onClick = onIndicatorToggle,
                    enabled = period != "分时",
                    modifier = Modifier
                        .width(66.dp)
                        .height(36.dp),
                    contentPadding = PaddingValues(horizontal = 2.dp, vertical = 0.dp),
                    colors = ButtonDefaults.textButtonColors(
                        contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
                        disabledContentColor = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.45f),
                    ),
                ) {
                    Icon(Icons.Default.Tune, contentDescription = null, modifier = Modifier.size(15.dp))
                    Text("指标", style = CompactTypography.caption)
                }
            }

            HorizontalDivider(
                color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.58f),
                thickness = 0.5.dp,
            )

            Text(
                "分时仅当日 09:30–15:00  ⓘ",
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            when {
                loading && dailyBars.isEmpty() -> {
                    KLineLoadingState(
                        title = loadingMessage,
                        detail = loadingDetail,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(360.dp),
                    )
                }

                error != null && dailyBars.isEmpty() -> {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(320.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(error, style = CompactTypography.secondary, color = MaterialTheme.colorScheme.error)
                            TextButton(onClick = onRetry) { Text("重新加载") }
                        }
                    }
                }

                else -> {
                    // Clamp malformed source wicks before weekly/monthly grouping.
                    // Otherwise a bad daily wick can poison the aggregated period.
                    val safeDaily = sanitizeBarsForChart(dailyBars)
                    val safeIntraday = sanitizeBarsForChart(intradayBars)
                    val chartBars = chartBarsForPeriod(period, safeDaily.bars, safeIntraday.bars)
                    val anomalyCount = if (period == "分时") safeIntraday.anomalyCount else safeDaily.anomalyCount

                    if (chartBars.isNotEmpty()) {
                        if (anomalyCount > 0) {
                            Text(
                                "检测到 $anomalyCount 个异常高/低点，已仅修正图表缩放，不改动原始行情。",
                                style = CompactTypography.caption,
                                color = MaterialTheme.colorScheme.tertiary,
                            )
                        }
                        ReferenceKLineChart(
                            bars = chartBars,
                            quote = quote,
                            useTimeAxis = period == "分时",
                            paperMarkers = if (period == "分时") emptyList() else paperLogs,
                            showMovingAverages = period != "分时" && indicatorsVisible,
                        )
                    } else if (period == "分时" && intradayLoading) {
                        KLineLoadingState(
                            title = "正在拉取当日分时",
                            detail = "仅加载最新交易日 09:30–15:00 的分时数据。",
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(300.dp),
                        )
                    } else {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(300.dp),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(
                                if (period == "分时") "最新交易日暂无分时数据" else "暂无 K 线数据",
                                style = CompactTypography.secondary,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }

            Text(
                if (period == "分时") {
                    "按住分时曲线查看当日价格"
                } else {
                    "左右拖拽查看不同期间 · 长按K线查看详情"
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 3.dp),
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun KLineLoadingState(
    title: String,
    detail: String,
    modifier: Modifier = Modifier,
) {
    Box(modifier = modifier, contentAlignment = Alignment.Center) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(AppSpacing.small),
        ) {
            CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp)
            Text(
                title,
                style = CompactTypography.secondary,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Text(
                detail,
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

internal data class SanitizedChartBars(
    val bars: List<DailyPriceDto>,
    val anomalyCount: Int,
)

/**
 * Protect the render scale from a malformed provider wick without rewriting raw
 * persistence. Ordinary large candles are preserved; only structurally invalid
 * or locally impossible extreme wicks are clamped to the candle body for draw.
 */
internal fun sanitizeBarsForChart(bars: List<DailyPriceDto>): SanitizedChartBars {
    if (bars.isEmpty()) return SanitizedChartBars(emptyList(), 0)
    var anomalyCount = 0
    val safeBars = bars.mapIndexed { index, bar ->
        val open = bar.open ?: bar.close
        val bodyHigh = maxOf(open, bar.close)
        val bodyLow = minOf(open, bar.close)
        val high = bar.high ?: bodyHigh
        val low = bar.low ?: bodyLow
        val previousClose = bars.getOrNull(index - 1)?.close
        val referenceValues = listOfNotNull(previousClose, open, bar.close).filter { it > 0.0 }
        val reference = if (referenceValues.isEmpty()) 0.0 else referenceValues.average()
        val rangeRatio = if (reference > 0.0) abs(high - low) / reference else 0.0
        val wickRatio = if (reference > 0.0) {
            maxOf(abs(high - bodyHigh), abs(bodyLow - low)) / reference
        } else {
            0.0
        }
        val structurallyInvalid = high <= 0.0 || low <= 0.0 || high < bodyHigh || low > bodyLow || high < low
        val extremeProviderWick = rangeRatio > 0.60 && wickRatio > 0.35

        if (structurallyInvalid || extremeProviderWick) {
            anomalyCount += 1
            bar.copy(high = bodyHigh, low = bodyLow)
        } else {
            bar
        }
    }
    return SanitizedChartBars(safeBars, anomalyCount)
}

internal fun latestIntradaySession(intradayBars: List<DailyPriceDto>): List<DailyPriceDto> {
    val latestSession = intradayBars.maxOfOrNull { it.trading_date.take(10) } ?: return emptyList()
    return intradayBars.filter { it.trading_date.take(10) == latestSession }
}

internal fun intradaySessionHint(intradayBars: List<DailyPriceDto>): String {
    val date = intradayBars.lastOrNull()?.trading_date?.take(10)
    return if (date.isNullOrBlank()) "分时仅展示最新单个交易日" else "分时仅展示 $date"
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
            turnover_rate = rows.sumOf { it.turnover_rate ?: 0.0 }.takeIf { rows.any { row -> row.turnover_rate != null } },
            adjustment = rows.last().adjustment,
            source = rows.last().source,
        )
    }
}

private const val TAG_KLINE = "KLine"
