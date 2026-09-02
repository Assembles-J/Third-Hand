package com.thirdhand.app.ui.components

import android.graphics.Paint
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thirdhand.app.DailyPriceDto
import com.thirdhand.app.MarketQuoteDto
import com.thirdhand.app.PaperTradingLogDto
import com.thirdhand.app.ui.theme.marketColors
import java.util.Locale
import kotlin.math.abs
import kotlin.math.roundToInt

private const val DEFAULT_VISIBLE_CANDLES = 64
private const val MIN_VISIBLE_CANDLES = 24
private const val MAX_VISIBLE_CANDLES = 120
private const val PRICE_GRID_LINES = 4

/**
 * Compact stock chart used by the position-detail surface.
 *
 * Historical periods render a bounded viewport instead of squeezing the entire
 * history into one canvas. Drag the main chart to pan through history, pinch to
 * zoom the historical candle window, or drag the mini navigator to jump to a
 * different range. Intraday data is already constrained to one trading session
 * by [TradingPeriodKLinePanel] and renders as a close-price line rather than
 * hundreds of one-minute candle bodies.
 */
@Composable
fun KLineChart(
    bars: List<DailyPriceDto>,
    quote: MarketQuoteDto? = null,
    useTimeAxis: Boolean = false,
    paperMarkers: List<PaperTradingLogDto> = emptyList(),
    showMovingAverages: Boolean = true,
    modifier: Modifier = Modifier,
) {
    if (bars.isEmpty()) return

    val initialWindowSize = if (useTimeAxis) bars.size else minOf(DEFAULT_VISIBLE_CANDLES, bars.size)
    var windowSize by remember(bars.size, useTimeAxis) { mutableIntStateOf(initialWindowSize.coerceAtLeast(1)) }
    var windowStart by remember(bars.size, useTimeAxis) {
        mutableIntStateOf((bars.size - initialWindowSize).coerceAtLeast(0))
    }
    var selectedGlobalIndex by remember(bars.lastOrNull()?.trading_date) { mutableIntStateOf(bars.lastIndex) }
    var showCrosshair by remember(bars.lastOrNull()?.trading_date) { mutableStateOf(false) }

    LaunchedEffect(bars.size, useTimeAxis) {
        windowSize = if (useTimeAxis) bars.size else minOf(DEFAULT_VISIBLE_CANDLES, bars.size)
        windowSize = windowSize.coerceAtLeast(1)
        windowStart = (bars.size - windowSize).coerceAtLeast(0)
        selectedGlobalIndex = bars.lastIndex
        showCrosshair = false
    }

    val maxStart = (bars.size - windowSize).coerceAtLeast(0)
    windowStart = windowStart.coerceIn(0, maxStart)
    val windowEnd = (windowStart + windowSize).coerceAtMost(bars.size)
    val visible = bars.subList(windowStart, windowEnd)

    if (selectedGlobalIndex !in windowStart until windowEnd) {
        selectedGlobalIndex = (windowEnd - 1).coerceAtLeast(windowStart)
    }
    val selected = bars[selectedGlobalIndex.coerceIn(0, bars.lastIndex)]
    val previousClose = bars.getOrNull(selectedGlobalIndex - 1)?.close ?: selected.close
    val change = if (previousClose != 0.0) (selected.close / previousClose - 1) * 100 else 0.0

    val values = visible.flatMap { listOfNotNull(it.high, it.low, it.close, it.open) }
    val rawMinimum = values.minOrNull() ?: 0.0
    val rawMaximum = values.maxOrNull() ?: 1.0
    val rawSpan = (rawMaximum - rawMinimum).coerceAtLeast(0.01)
    val pricePadding = (rawSpan * 0.06).coerceAtLeast(0.01)
    val minimum = rawMinimum - pricePadding
    val maximum = rawMaximum + pricePadding
    val priceSpan = (maximum - minimum).coerceAtLeast(0.01)

    val colors = MaterialTheme.marketColors
    val gridColor = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.38f)
    val axisColor = MaterialTheme.colorScheme.onSurfaceVariant
    val surfaceColor = MaterialTheme.colorScheme.surface
    val primary = MaterialTheme.colorScheme.primary
    val changeColor = if (change >= 0) colors.rise else colors.fall
    val ma5 = remember(bars) { movingAverage(bars, 5) }
    val ma10 = remember(bars) { movingAverage(bars, 10) }
    val ma20 = remember(bars) { movingAverage(bars, 20) }
    val ma5Color = Color(0xFFF59E0B)
    val ma10Color = Color(0xFF4F6BED)
    val ma20Color = Color(0xFF8B5CF6)

    Column(modifier = modifier.fillMaxWidth()) {
        ChartSnapshot(
            selected = selected,
            change = change,
            changeColor = changeColor,
        )

        if (!useTimeAxis && showMovingAverages) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 6.dp, bottom = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                MovingAverageLegend("MA5", ma5.getOrNull(selectedGlobalIndex), ma5Color)
                MovingAverageLegend("MA10", ma10.getOrNull(selectedGlobalIndex), ma10Color)
                MovingAverageLegend("MA20", ma20.getOrNull(selectedGlobalIndex), ma20Color)
            }
        }

        Row(Modifier.fillMaxWidth()) {
            PriceAxis(
                maximum = maximum,
                minimum = minimum,
                color = axisColor,
                modifier = Modifier
                    .width(38.dp)
                    .height(228.dp),
            )

            Canvas(
                modifier = Modifier
                    .weight(1f)
                    .height(228.dp)
                    .pointerInput(bars, useTimeAxis) {
                        if (useTimeAxis) {
                            fun selectAt(x: Float) {
                                if (visible.isEmpty()) return
                                val local = ((x / size.width.toFloat().coerceAtLeast(1f)) * visible.size)
                                    .toInt()
                                    .coerceIn(0, visible.lastIndex)
                                selectedGlobalIndex = windowStart + local
                            }

                            detectDragGestures(
                                onDragStart = { point ->
                                    showCrosshair = true
                                    selectAt(point.x)
                                },
                                onDragEnd = { showCrosshair = false },
                                onDragCancel = { showCrosshair = false },
                                onDrag = { changeEvent, _ ->
                                    selectAt(changeEvent.position.x)
                                },
                            )
                        } else {
                            var carriedPan = 0f
                            detectTransformGestures(panZoomLock = true) { centroid, pan, zoom, _ ->
                                val canvasWidth = size.width.toFloat().coerceAtLeast(1f)
                                val oldWindowSize = windowSize.coerceAtLeast(1)
                                val minVisible = minOf(MIN_VISIBLE_CANDLES, bars.size).coerceAtLeast(1)
                                val maxVisible = minOf(MAX_VISIBLE_CANDLES, bars.size).coerceAtLeast(minVisible)

                                if (abs(zoom - 1f) > 0.002f) {
                                    val targetWindowSize = (oldWindowSize / zoom)
                                        .roundToInt()
                                        .coerceIn(minVisible, maxVisible)
                                    if (targetWindowSize != oldWindowSize) {
                                        val anchorRatio = (centroid.x / canvasWidth).coerceIn(0f, 1f)
                                        val oldAnchor = windowStart +
                                            anchorRatio * (oldWindowSize - 1).coerceAtLeast(0)
                                        val zoomMaxStart = (bars.size - targetWindowSize).coerceAtLeast(0)
                                        windowSize = targetWindowSize
                                        windowStart = (oldAnchor -
                                            anchorRatio * (targetWindowSize - 1).coerceAtLeast(0))
                                            .roundToInt()
                                            .coerceIn(0, zoomMaxStart)
                                        carriedPan = 0f
                                    }
                                }

                                if (abs(pan.x) > 0f && bars.size > windowSize) {
                                    val candleWidthPx = canvasWidth / windowSize.coerceAtLeast(1)
                                    carriedPan += pan.x
                                    val steps = (carriedPan / candleWidthPx.coerceAtLeast(1f)).toInt()
                                    if (steps != 0) {
                                        val panMaxStart = (bars.size - windowSize).coerceAtLeast(0)
                                        windowStart = (windowStart - steps).coerceIn(0, panMaxStart)
                                        carriedPan -= steps * candleWidthPx
                                    }
                                }

                                selectedGlobalIndex = (windowStart + windowSize - 1)
                                    .coerceAtMost(bars.lastIndex)
                            }
                        }
                    },
            ) {
                val step = size.width / visible.size.coerceAtLeast(1)
                val candleWidth = (step * 0.52f).coerceIn(1.dp.toPx(), 6.dp.toPx())

                fun y(value: Double): Float =
                    size.height - (((value - minimum) / priceSpan) * size.height).toFloat()

                repeat(PRICE_GRID_LINES) { gridIndex ->
                    val gridY = size.height * gridIndex / (PRICE_GRID_LINES - 1).toFloat()
                    drawLine(
                        color = gridColor,
                        start = Offset(0f, gridY),
                        end = Offset(size.width, gridY),
                        strokeWidth = 0.5.dp.toPx(),
                    )
                }

                if (useTimeAxis) {
                    val path = Path()
                    visible.forEachIndexed { index, bar ->
                        val x = step * index + step / 2f
                        val pointY = y(bar.close)
                        if (index == 0) path.moveTo(x, pointY) else path.lineTo(x, pointY)
                    }
                    drawPath(path, color = primary, style = Stroke(width = 1.4.dp.toPx()))
                } else {
                    visible.forEachIndexed { localIndex, bar ->
                        val x = step * localIndex + step / 2f
                        val open = bar.open ?: bar.close
                        val high = bar.high ?: maxOf(open, bar.close)
                        val low = bar.low ?: minOf(open, bar.close)
                        val candleColor = if (bar.close >= open) colors.rise else colors.fall

                        drawLine(
                            color = candleColor,
                            start = Offset(x, y(high)),
                            end = Offset(x, y(low)),
                            strokeWidth = 0.8.dp.toPx(),
                        )

                        val bodyTop = minOf(y(open), y(bar.close))
                        val bodyBottom = maxOf(y(open), y(bar.close))
                        val bodyHeight = (bodyBottom - bodyTop).coerceAtLeast(1.dp.toPx())
                        drawRect(
                            color = candleColor,
                            topLeft = Offset(x - candleWidth / 2f, bodyTop),
                            size = Size(candleWidth, bodyHeight),
                        )
                    }

                    if (showMovingAverages) {
                        drawMovingAverage(ma5, windowStart, visible.size, step, ::y, ma5Color)
                        drawMovingAverage(ma10, windowStart, visible.size, step, ::y, ma10Color)
                        drawMovingAverage(ma20, windowStart, visible.size, step, ::y, ma20Color)
                    }
                }

                paperMarkers.forEach { marker ->
                    val markerDate = marker.executed_at.take(10)
                    val globalIndex = bars.indexOfLast { it.trading_date.take(10) == markerDate }
                    if (globalIndex !in windowStart until windowEnd) return@forEach

                    val localIndex = globalIndex - windowStart
                    val markerX = step * localIndex + step / 2f
                    val anchorY = y(marker.price.coerceIn(minimum, maximum))
                    val isBuy = marker.side.equals("BUY", ignoreCase = true)
                    val markerColor = if (isBuy) Color(0xFF5267D8) else Color(0xFFE85375)
                    val markerRadius = 5.dp.toPx()
                    val markerY = (anchorY + if (isBuy) 8.dp.toPx() else -8.dp.toPx())
                        .coerceIn(markerRadius, size.height - markerRadius)

                    drawLine(
                        color = markerColor.copy(alpha = 0.55f),
                        start = Offset(markerX, anchorY),
                        end = Offset(markerX, markerY),
                        strokeWidth = 0.6.dp.toPx(),
                    )
                    drawCircle(surfaceColor, radius = markerRadius, center = Offset(markerX, markerY))
                    drawCircle(
                        color = markerColor,
                        radius = markerRadius,
                        center = Offset(markerX, markerY),
                        style = Stroke(width = 1.dp.toPx()),
                    )
                    drawContext.canvas.nativeCanvas.drawText(
                        if (isBuy) "B" else "S",
                        markerX,
                        markerY + 2.4.dp.toPx(),
                        Paint().apply {
                            isAntiAlias = true
                            color = markerColor.toArgb()
                            textSize = 7.sp.toPx()
                            isFakeBoldText = true
                            textAlign = Paint.Align.CENTER
                        },
                    )
                }

                if (showCrosshair) {
                    val localIndex = (selectedGlobalIndex - windowStart).coerceIn(0, visible.lastIndex)
                    val crossX = step * localIndex + step / 2f
                    val crossY = y(selected.close)
                    drawLine(
                        primary.copy(alpha = 0.46f),
                        Offset(crossX, 0f),
                        Offset(crossX, size.height),
                        strokeWidth = 0.7.dp.toPx(),
                    )
                    drawLine(
                        primary.copy(alpha = 0.32f),
                        Offset(0f, crossY),
                        Offset(size.width, crossY),
                        strokeWidth = 0.6.dp.toPx(),
                    )
                }

                if (!useTimeAxis && windowEnd == bars.size) {
                    val latest = visible.last()
                    val latestPrice = quote?.price ?: latest.close
                    val latestY = y(latestPrice.coerceIn(minimum, maximum))
                    val tagColor = quote?.change_percent?.let { quoteChange ->
                        when {
                            quoteChange > 0.0 -> colors.rise
                            quoteChange < 0.0 -> colors.fall
                            else -> colors.neutral
                        }
                    } ?: if (latest.close >= (latest.open ?: latest.close)) colors.rise else colors.fall
                    val tagWidth = 42.dp.toPx()
                    val tagHeight = 20.dp.toPx()
                    val tagLeft = (size.width - tagWidth).coerceAtLeast(0f)
                    val tagTop = (latestY - tagHeight / 2f).coerceIn(0f, size.height - tagHeight)

                    drawLine(
                        color = tagColor.copy(alpha = 0.32f),
                        start = Offset((tagLeft - 18.dp.toPx()).coerceAtLeast(0f), latestY),
                        end = Offset(tagLeft, latestY),
                        strokeWidth = 0.6.dp.toPx(),
                    )
                    drawRoundRect(
                        color = tagColor,
                        topLeft = Offset(tagLeft, tagTop),
                        size = Size(tagWidth, tagHeight),
                        cornerRadius = CornerRadius(4.dp.toPx()),
                    )
                    drawContext.canvas.nativeCanvas.drawText(
                        "%.2f".format(Locale.US, latestPrice),
                        tagLeft + tagWidth / 2f,
                        tagTop + 13.7.dp.toPx(),
                        Paint().apply {
                            isAntiAlias = true
                            color = android.graphics.Color.WHITE
                            textSize = 10.sp.toPx()
                            textAlign = Paint.Align.CENTER
                        },
                    )
                }
            }
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "成交量",
                modifier = Modifier.width(38.dp),
                style = MaterialTheme.typography.labelSmall,
                color = axisColor,
            )
            VolumeChart(
                visible = visible,
                riseColor = colors.rise,
                fallColor = colors.fall,
                modifier = Modifier
                    .weight(1f)
                    .height(62.dp),
            )
        }

        Row(Modifier.fillMaxWidth()) {
            Spacer(Modifier.width(38.dp))
            TimeAxis(
                visible = visible,
                useTimeAxis = useTimeAxis,
                modifier = Modifier.weight(1f),
            )
        }

        if (!useTimeAxis && bars.size > windowSize) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
            ) {
                Spacer(Modifier.width(38.dp))
                MiniRangeNavigator(
                    bars = bars,
                    windowStart = windowStart,
                    windowSize = windowSize,
                    onWindowStartChange = { start ->
                        windowStart = start.coerceIn(0, maxStart)
                        selectedGlobalIndex = (windowStart + windowSize - 1).coerceAtMost(bars.lastIndex)
                    },
                    modifier = Modifier
                        .weight(1f)
                        .height(42.dp),
                )
            }
        }
    }
}

@Composable
private fun ChartSnapshot(
    selected: DailyPriceDto,
    change: Double,
    changeColor: Color,
) {
    Column(Modifier.fillMaxWidth()) {
        Text(
            text = "${selected.trading_date}  ${if (change >= 0) "+" else ""}${"%.2f".format(Locale.US, change)}%",
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold,
            color = changeColor,
        )
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 3.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            ChartMiniMetric("开", selected.open ?: selected.close)
            ChartMiniMetric("高", selected.high ?: selected.close)
            ChartMiniMetric("低", selected.low ?: selected.close)
            ChartMiniMetric("收", selected.close)
        }
    }
}

@Composable
private fun ChartMiniMetric(label: String, value: Double) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(
            label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.width(2.dp))
        Text(
            "%.2f".format(Locale.US, value),
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
private fun MovingAverageLegend(label: String, value: Double?, color: Color) {
    Text(
        text = "$label ${value?.let { "%.2f".format(Locale.US, it) } ?: "--"}",
        style = MaterialTheme.typography.labelSmall,
        color = color,
    )
}

@Composable
private fun PriceAxis(
    maximum: Double,
    minimum: Double,
    color: Color,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.padding(end = 5.dp),
        verticalArrangement = Arrangement.SpaceBetween,
        horizontalAlignment = Alignment.End,
    ) {
        repeat(PRICE_GRID_LINES) { index ->
            val ratio = index / (PRICE_GRID_LINES - 1).toDouble()
            val value = maximum - (maximum - minimum) * ratio
            Text(
                text = "%.2f".format(Locale.US, value),
                style = MaterialTheme.typography.labelSmall,
                color = color,
                textAlign = TextAlign.End,
                maxLines = 1,
            )
        }
    }
}

@Composable
private fun VolumeChart(
    visible: List<DailyPriceDto>,
    riseColor: Color,
    fallColor: Color,
    modifier: Modifier = Modifier,
) {
    val maxVolume = visible.maxOfOrNull { it.volume ?: 0.0 }?.coerceAtLeast(1.0) ?: 1.0
    val gridColor = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.28f)

    Canvas(modifier) {
        val step = size.width / visible.size.coerceAtLeast(1)
        val barWidth = (step * 0.52f).coerceIn(1.dp.toPx(), 6.dp.toPx())
        drawLine(gridColor, Offset(0f, 0f), Offset(size.width, 0f), strokeWidth = 0.5.dp.toPx())

        visible.forEachIndexed { index, bar ->
            val open = bar.open ?: bar.close
            val color = if (bar.close >= open) riseColor else fallColor
            val height = (((bar.volume ?: 0.0) / maxVolume) * size.height).toFloat()
            val x = step * index + step / 2f
            drawRect(
                color = color.copy(alpha = 0.78f),
                topLeft = Offset(x - barWidth / 2f, size.height - height),
                size = Size(barWidth, height.coerceAtLeast(1f)),
            )
        }
    }
}

@Composable
private fun TimeAxis(
    visible: List<DailyPriceDto>,
    useTimeAxis: Boolean,
    modifier: Modifier = Modifier,
) {
    if (visible.isEmpty()) return
    val middle = visible[visible.size / 2]
    Row(
        modifier = modifier.padding(top = 3.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(
            axisLabel(visible.first().trading_date, useTimeAxis),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            axisLabel(middle.trading_date, useTimeAxis),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            axisLabel(visible.last().trading_date, useTimeAxis),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun MiniRangeNavigator(
    bars: List<DailyPriceDto>,
    windowStart: Int,
    windowSize: Int,
    onWindowStartChange: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val lineColor = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.56f)
    val windowColor = MaterialTheme.colorScheme.primary
    val trackColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.38f)
    val minimum = bars.minOfOrNull { it.close } ?: 0.0
    val maximum = bars.maxOfOrNull { it.close } ?: 1.0
    val span = (maximum - minimum).coerceAtLeast(0.01)
    val maxStart = (bars.size - windowSize).coerceAtLeast(0)

    Canvas(
        modifier = modifier.pointerInput(bars.size, windowSize) {
            fun moveWindowTo(x: Float) {
                val ratio = (x / size.width.toFloat().coerceAtLeast(1f)).coerceIn(0f, 1f)
                val centerIndex = (ratio * (bars.size - 1).coerceAtLeast(0)).roundToInt()
                onWindowStartChange((centerIndex - windowSize / 2).coerceIn(0, maxStart))
            }
            detectDragGestures(
                onDragStart = { moveWindowTo(it.x) },
                onDrag = { change, _ -> moveWindowTo(change.position.x) },
            )
        },
    ) {
        drawRoundRect(
            color = trackColor,
            size = size,
            cornerRadius = CornerRadius(6.dp.toPx()),
        )

        val step = if (bars.size <= 1) size.width else size.width / (bars.size - 1)
        val path = Path()
        bars.forEachIndexed { index, bar ->
            val x = index * step
            val y = size.height - (((bar.close - minimum) / span) * size.height).toFloat()
            if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        drawPath(path, color = lineColor, style = Stroke(width = 0.8.dp.toPx()))

        val left = windowStart.toFloat() / bars.size * size.width
        val right = (windowStart + windowSize).toFloat() / bars.size * size.width
        drawRoundRect(
            color = windowColor.copy(alpha = 0.08f),
            topLeft = Offset(left, 0f),
            size = Size((right - left).coerceAtLeast(2.dp.toPx()), size.height),
            cornerRadius = CornerRadius(6.dp.toPx()),
        )
        drawRoundRect(
            color = windowColor.copy(alpha = 0.62f),
            topLeft = Offset(left, 0f),
            size = Size((right - left).coerceAtLeast(2.dp.toPx()), size.height),
            cornerRadius = CornerRadius(6.dp.toPx()),
            style = Stroke(width = 1.dp.toPx()),
        )

        val handleWidth = 3.dp.toPx()
        val handleHeight = 18.dp.toPx()
        val handleTop = (size.height - handleHeight) / 2f
        drawRoundRect(
            color = windowColor.copy(alpha = 0.68f),
            topLeft = Offset((left - handleWidth / 2f).coerceAtLeast(0f), handleTop),
            size = Size(handleWidth, handleHeight),
            cornerRadius = CornerRadius(handleWidth / 2f),
        )
        drawRoundRect(
            color = windowColor.copy(alpha = 0.68f),
            topLeft = Offset((right - handleWidth / 2f).coerceAtMost(size.width - handleWidth), handleTop),
            size = Size(handleWidth, handleHeight),
            cornerRadius = CornerRadius(handleWidth / 2f),
        )
    }
}

private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawMovingAverage(
    values: List<Double?>,
    windowStart: Int,
    visibleSize: Int,
    step: Float,
    y: (Double) -> Float,
    color: Color,
) {
    var previous: Offset? = null
    repeat(visibleSize) { localIndex ->
        val value = values.getOrNull(windowStart + localIndex)
        if (value == null) {
            previous = null
            return@repeat
        }
        val point = Offset(step * localIndex + step / 2f, y(value))
        previous?.let {
            drawLine(color.copy(alpha = 0.82f), it, point, strokeWidth = 0.85.dp.toPx())
        }
        previous = point
    }
}

private fun movingAverage(bars: List<DailyPriceDto>, period: Int): List<Double?> {
    if (period <= 0) return List(bars.size) { null }
    val result = MutableList<Double?>(bars.size) { null }
    var sum = 0.0
    bars.forEachIndexed { index, bar ->
        sum += bar.close
        if (index >= period) sum -= bars[index - period].close
        if (index >= period - 1) result[index] = sum / period
    }
    return result
}

private fun axisLabel(value: String, useTimeAxis: Boolean): String {
    val trimmed = value.trim()
    if (useTimeAxis) {
        return when {
            trimmed.length >= 16 && trimmed[10] == 'T' -> trimmed.substring(11, 16)
            trimmed.length >= 16 && trimmed[10] == ' ' -> trimmed.substring(11, 16)
            else -> trimmed.takeLast(5)
        }
    }
    val date = trimmed.take(10)
    return if (date.length >= 10) date.substring(5) else date
}