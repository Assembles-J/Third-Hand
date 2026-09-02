package com.thirdhand.app.ui.components

import android.graphics.Paint
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
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
import com.thirdhand.app.ui.theme.CompactTypography
import com.thirdhand.app.ui.theme.marketColors
import java.util.Locale
import kotlin.math.abs
import kotlin.math.roundToInt

private const val REFERENCE_VISIBLE_CANDLES = 68
private const val REFERENCE_MIN_CANDLES = 28
private const val REFERENCE_MAX_CANDLES = 110
private const val REFERENCE_GRID_LINES = 5

/**
 * Stock-detail chart renderer dedicated to the approved red/white reference UI.
 * It owns presentation and viewport interaction only; source bars remain intact.
 */
@Composable
fun ReferenceKLineChart(
    bars: List<DailyPriceDto>,
    quote: MarketQuoteDto? = null,
    useTimeAxis: Boolean = false,
    paperMarkers: List<PaperTradingLogDto> = emptyList(),
    showMovingAverages: Boolean = true,
    modifier: Modifier = Modifier,
) {
    if (bars.isEmpty()) return

    val initialWindow = if (useTimeAxis) bars.size else minOf(REFERENCE_VISIBLE_CANDLES, bars.size)
    var windowSize by remember(bars.size, useTimeAxis) { mutableIntStateOf(initialWindow.coerceAtLeast(1)) }
    var windowStart by remember(bars.size, useTimeAxis) {
        mutableIntStateOf((bars.size - initialWindow).coerceAtLeast(0))
    }
    var selectedIndex by remember(bars.lastOrNull()?.trading_date) { mutableIntStateOf(bars.lastIndex) }
    var crosshairVisible by remember(bars.lastOrNull()?.trading_date) { mutableStateOf(false) }

    LaunchedEffect(bars.size, useTimeAxis) {
        windowSize = if (useTimeAxis) bars.size else minOf(REFERENCE_VISIBLE_CANDLES, bars.size)
        windowSize = windowSize.coerceAtLeast(1)
        windowStart = (bars.size - windowSize).coerceAtLeast(0)
        selectedIndex = bars.lastIndex
        crosshairVisible = false
    }

    val maxStart = (bars.size - windowSize).coerceAtLeast(0)
    val safeStart = windowStart.coerceIn(0, maxStart)
    val windowEnd = (safeStart + windowSize).coerceAtMost(bars.size)
    val visible = bars.subList(safeStart, windowEnd)
    val safeSelected = selectedIndex.coerceIn(safeStart, (windowEnd - 1).coerceAtLeast(safeStart))
    val selected = bars[safeSelected]
    val previousClose = bars.getOrNull(safeSelected - 1)?.close ?: selected.close
    val selectedChange = selected.change_percent ?: if (previousClose != 0.0) {
        (selected.close / previousClose - 1.0) * 100.0
    } else 0.0

    val priceValues = visible.flatMap { listOfNotNull(it.open, it.close, it.high, it.low) }
    val rawMin = priceValues.minOrNull() ?: 0.0
    val rawMax = priceValues.maxOrNull() ?: 1.0
    val rawSpan = (rawMax - rawMin).coerceAtLeast(0.01)
    val pricePadding = (rawSpan * 0.055).coerceAtLeast(0.01)
    val minimum = rawMin - pricePadding
    val maximum = rawMax + pricePadding
    val priceSpan = (maximum - minimum).coerceAtLeast(0.01)

    val marketColors = MaterialTheme.marketColors
    val axisColor = MaterialTheme.colorScheme.onSurfaceVariant
    val gridColor = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.34f)
    val surfaceColor = MaterialTheme.colorScheme.surface
    val primaryColor = MaterialTheme.colorScheme.primary
    val selectedColor = when {
        selectedChange > 0.0 -> marketColors.rise
        selectedChange < 0.0 -> marketColors.fall
        else -> marketColors.neutral
    }
    val ma5Color = Color(0xFFF59E0B)
    val ma10Color = Color(0xFF4F6BED)
    val ma20Color = Color(0xFF8B5CF6)
    val ma5 = remember(bars) { referenceMovingAverage(bars, 5) }
    val ma10 = remember(bars) { referenceMovingAverage(bars, 10) }
    val ma20 = remember(bars) { referenceMovingAverage(bars, 20) }

    Column(modifier = modifier.fillMaxWidth()) {
        ReferenceSnapshot(selected, selectedChange, selectedColor)

        if (!useTimeAxis && showMovingAverages) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                ReferenceMaLegend("MA5", ma5.getOrNull(safeSelected), ma5Color)
                ReferenceMaLegend("MA10", ma10.getOrNull(safeSelected), ma10Color)
                ReferenceMaLegend("MA20", ma20.getOrNull(safeSelected), ma20Color)
            }
        } else {
            Spacer(Modifier.height(3.dp))
        }

        Row(Modifier.fillMaxWidth()) {
            ReferencePriceAxis(
                maximum = maximum,
                minimum = minimum,
                color = axisColor,
                modifier = Modifier.width(38.dp).height(178.dp),
            )

            Canvas(
                modifier = Modifier
                    .weight(1f)
                    .height(178.dp)
                    .pointerInput(bars.size, useTimeAxis, safeStart, visible.size) {
                        if (!useTimeAxis) {
                            detectTapGestures(
                                onLongPress = { point ->
                                    val local = ((point.x / size.width.toFloat().coerceAtLeast(1f)) * visible.size)
                                        .toInt()
                                        .coerceIn(0, visible.lastIndex)
                                    selectedIndex = safeStart + local
                                    crosshairVisible = true
                                },
                                onTap = { crosshairVisible = false },
                            )
                        }
                    }
                    .pointerInput(bars.size, useTimeAxis, windowSize) {
                        if (useTimeAxis) {
                            fun selectAt(x: Float) {
                                if (visible.isEmpty()) return
                                val local = ((x / size.width.toFloat().coerceAtLeast(1f)) * visible.size)
                                    .toInt()
                                    .coerceIn(0, visible.lastIndex)
                                selectedIndex = safeStart + local
                            }
                            detectDragGestures(
                                onDragStart = { crosshairVisible = true; selectAt(it.x) },
                                onDragEnd = { crosshairVisible = false },
                                onDragCancel = { crosshairVisible = false },
                                onDrag = { change, _ -> selectAt(change.position.x) },
                            )
                        } else {
                            var carriedPan = 0f
                            detectTransformGestures(panZoomLock = true) { centroid, pan, zoom, _ ->
                                val width = size.width.toFloat().coerceAtLeast(1f)
                                val oldSize = windowSize.coerceAtLeast(1)
                                val minVisible = minOf(REFERENCE_MIN_CANDLES, bars.size).coerceAtLeast(1)
                                val maxVisible = minOf(REFERENCE_MAX_CANDLES, bars.size).coerceAtLeast(minVisible)

                                if (abs(zoom - 1f) > 0.002f) {
                                    val targetSize = (oldSize / zoom).roundToInt().coerceIn(minVisible, maxVisible)
                                    if (targetSize != oldSize) {
                                        val anchorRatio = (centroid.x / width).coerceIn(0f, 1f)
                                        val oldAnchor = windowStart + anchorRatio * (oldSize - 1).coerceAtLeast(0)
                                        val targetMaxStart = (bars.size - targetSize).coerceAtLeast(0)
                                        windowSize = targetSize
                                        windowStart = (oldAnchor - anchorRatio * (targetSize - 1).coerceAtLeast(0))
                                            .roundToInt()
                                            .coerceIn(0, targetMaxStart)
                                        carriedPan = 0f
                                    }
                                }

                                if (abs(pan.x) > 0f && bars.size > windowSize) {
                                    val candleWidthPx = width / windowSize.coerceAtLeast(1)
                                    carriedPan += pan.x
                                    val steps = (carriedPan / candleWidthPx.coerceAtLeast(1f)).toInt()
                                    if (steps != 0) {
                                        val targetMaxStart = (bars.size - windowSize).coerceAtLeast(0)
                                        windowStart = (windowStart - steps).coerceIn(0, targetMaxStart)
                                        carriedPan -= steps * candleWidthPx
                                    }
                                }
                                selectedIndex = (windowStart + windowSize - 1).coerceAtMost(bars.lastIndex)
                            }
                        }
                    },
            ) {
                val step = size.width / visible.size.coerceAtLeast(1)
                val candleWidth = (step * 0.52f).coerceIn(1.dp.toPx(), 6.dp.toPx())
                fun y(value: Double): Float =
                    size.height - (((value - minimum) / priceSpan) * size.height).toFloat()

                repeat(REFERENCE_GRID_LINES) { index ->
                    val gridY = size.height * index / (REFERENCE_GRID_LINES - 1).toFloat()
                    drawLine(gridColor, Offset(0f, gridY), Offset(size.width, gridY), 0.5.dp.toPx())
                }

                if (useTimeAxis) {
                    val path = Path()
                    visible.forEachIndexed { index, bar ->
                        val x = step * index + step / 2f
                        if (index == 0) path.moveTo(x, y(bar.close)) else path.lineTo(x, y(bar.close))
                    }
                    drawPath(path, primaryColor, style = Stroke(1.35.dp.toPx()))
                } else {
                    visible.forEachIndexed { localIndex, bar ->
                        val x = step * localIndex + step / 2f
                        val open = bar.open ?: bar.close
                        val high = bar.high ?: maxOf(open, bar.close)
                        val low = bar.low ?: minOf(open, bar.close)
                        val candleColor = if (bar.close >= open) marketColors.rise else marketColors.fall
                        drawLine(candleColor, Offset(x, y(high)), Offset(x, y(low)), 0.78.dp.toPx())
                        val top = minOf(y(open), y(bar.close))
                        val bottom = maxOf(y(open), y(bar.close))
                        drawRect(
                            candleColor,
                            Offset(x - candleWidth / 2f, top),
                            Size(candleWidth, (bottom - top).coerceAtLeast(1.dp.toPx())),
                        )
                    }
                    if (showMovingAverages) {
                        drawReferenceAverage(ma5, safeStart, visible.size, step, ::y, ma5Color)
                        drawReferenceAverage(ma10, safeStart, visible.size, step, ::y, ma10Color)
                        drawReferenceAverage(ma20, safeStart, visible.size, step, ::y, ma20Color)
                    }
                }

                paperMarkers.forEach { marker ->
                    val date = marker.executed_at.take(10)
                    val globalIndex = bars.indexOfLast { it.trading_date.take(10) == date }
                    if (globalIndex !in safeStart until windowEnd) return@forEach
                    val local = globalIndex - safeStart
                    val x = step * local + step / 2f
                    val anchorY = y(marker.price.coerceIn(minimum, maximum))
                    val isBuy = marker.side.equals("BUY", true)
                    val markerColor = if (isBuy) Color(0xFF5267D8) else Color(0xFFE85375)
                    val radius = 4.5.dp.toPx()
                    val markerY = (anchorY + if (isBuy) 7.dp.toPx() else -7.dp.toPx())
                        .coerceIn(radius, size.height - radius)
                    drawLine(markerColor.copy(alpha = 0.42f), Offset(x, anchorY), Offset(x, markerY), 0.55.dp.toPx())
                    drawCircle(surfaceColor, radius, Offset(x, markerY))
                    drawCircle(markerColor, radius, Offset(x, markerY), style = Stroke(0.9.dp.toPx()))
                    drawContext.canvas.nativeCanvas.drawText(
                        if (isBuy) "B" else "S",
                        x,
                        markerY + 2.15.dp.toPx(),
                        Paint().apply {
                            isAntiAlias = true
                            color = markerColor.toArgb()
                            textSize = 6.5.sp.toPx()
                            isFakeBoldText = true
                            textAlign = Paint.Align.CENTER
                        },
                    )
                }

                if (crosshairVisible) {
                    val local = (safeSelected - safeStart).coerceIn(0, visible.lastIndex)
                    val x = step * local + step / 2f
                    val selectedY = y(selected.close)
                    drawLine(primaryColor.copy(alpha = 0.34f), Offset(x, 0f), Offset(x, size.height), 0.65.dp.toPx())
                    drawLine(primaryColor.copy(alpha = 0.26f), Offset(0f, selectedY), Offset(size.width, selectedY), 0.55.dp.toPx())
                }

                if (!useTimeAxis && windowEnd == bars.size) {
                    val latest = visible.last()
                    val latestPrice = quote?.price ?: latest.close
                    val latestY = y(latestPrice.coerceIn(minimum, maximum))
                    val tagColor = quote?.change_percent?.let {
                        when {
                            it > 0.0 -> marketColors.rise
                            it < 0.0 -> marketColors.fall
                            else -> marketColors.neutral
                        }
                    } ?: if (latest.close >= (latest.open ?: latest.close)) marketColors.rise else marketColors.fall
                    val tagWidth = 39.dp.toPx()
                    val tagHeight = 19.dp.toPx()
                    val left = (size.width - tagWidth).coerceAtLeast(0f)
                    val top = (latestY - tagHeight / 2f).coerceIn(0f, size.height - tagHeight)
                    drawRoundRect(tagColor, Offset(left, top), Size(tagWidth, tagHeight), CornerRadius(4.dp.toPx()))
                    drawContext.canvas.nativeCanvas.drawText(
                        "%.2f".format(Locale.US, latestPrice),
                        left + tagWidth / 2f,
                        top + 13.dp.toPx(),
                        Paint().apply {
                            isAntiAlias = true
                            color = android.graphics.Color.WHITE
                            textSize = 9.5.sp.toPx()
                            textAlign = Paint.Align.CENTER
                        },
                    )
                }
            }
        }

        val maxVolume = visible.maxOfOrNull { it.volume ?: 0.0 } ?: 0.0
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 5.dp, bottom = 2.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "成交量 ${referenceCompactVolume(selected.volume)}",
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.weight(1f))
            Text(referenceCompactVolume(maxVolume), style = CompactTypography.caption, color = axisColor)
        }

        ReferenceVolumeChart(visible, marketColors.rise, marketColors.fall, Modifier.fillMaxWidth().height(42.dp))
        ReferenceTimeAxis(visible, useTimeAxis, Modifier.fillMaxWidth().padding(top = 2.dp))

        if (!useTimeAxis && bars.size > windowSize) {
            ReferenceMiniNavigator(
                bars = bars,
                windowStart = safeStart,
                windowSize = windowSize,
                onWindowStartChange = {
                    windowStart = it.coerceIn(0, maxStart)
                    selectedIndex = (windowStart + windowSize - 1).coerceAtMost(bars.lastIndex)
                    crosshairVisible = false
                },
                modifier = Modifier.fillMaxWidth().padding(top = 6.dp).height(30.dp),
            )
        }
    }
}

@Composable
private fun ReferenceSnapshot(selected: DailyPriceDto, change: Double, color: Color) {
    Column(Modifier.fillMaxWidth()) {
        Text(
            buildString {
                append(selected.trading_date.take(10))
                append(" · 收 ")
                append("%.2f".format(Locale.US, selected.close))
                append("  ")
                append(if (change >= 0.0) "+" else "")
                append("%.2f%%".format(Locale.US, change))
            },
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold,
            color = color,
        )
        Row(Modifier.fillMaxWidth().padding(top = 4.dp), horizontalArrangement = Arrangement.spacedBy(13.dp)) {
            ReferenceMetric("开", selected.open ?: selected.close)
            ReferenceMetric("高", selected.high ?: selected.close)
            ReferenceMetric("低", selected.low ?: selected.close)
            selected.turnover_rate?.let {
                Text("换 ${"%.2f".format(Locale.US, it)}%", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun ReferenceMetric(label: String, value: Double) {
    Text("$label ${"%.2f".format(Locale.US, value)}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable
private fun ReferenceMaLegend(label: String, value: Double?, color: Color) {
    Text("$label ${value?.let { "%.2f".format(Locale.US, it) } ?: "--"}", style = MaterialTheme.typography.labelSmall, color = color)
}

@Composable
private fun ReferencePriceAxis(maximum: Double, minimum: Double, color: Color, modifier: Modifier = Modifier) {
    Column(modifier.padding(end = 5.dp), Arrangement.SpaceBetween, Alignment.End) {
        repeat(REFERENCE_GRID_LINES) { index ->
            val ratio = index / (REFERENCE_GRID_LINES - 1).toDouble()
            val value = maximum - (maximum - minimum) * ratio
            Text("%.2f".format(Locale.US, value), style = MaterialTheme.typography.labelSmall, color = color, textAlign = TextAlign.End, maxLines = 1)
        }
    }
}

@Composable
private fun ReferenceVolumeChart(
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
        drawLine(gridColor, Offset.Zero, Offset(size.width, 0f), 0.5.dp.toPx())
        visible.forEachIndexed { index, bar ->
            val open = bar.open ?: bar.close
            val color = if (bar.close >= open) riseColor else fallColor
            val height = (((bar.volume ?: 0.0) / maxVolume) * size.height).toFloat()
            val x = step * index + step / 2f
            drawRect(color.copy(alpha = 0.82f), Offset(x - barWidth / 2f, size.height - height), Size(barWidth, height.coerceAtLeast(1f)))
        }
    }
}

@Composable
private fun ReferenceTimeAxis(visible: List<DailyPriceDto>, useTimeAxis: Boolean, modifier: Modifier = Modifier) {
    if (visible.isEmpty()) return
    val indices = listOf(0, visible.lastIndex / 3, visible.lastIndex * 2 / 3, visible.lastIndex).distinct()
    Row(modifier) {
        indices.forEachIndexed { slot, index ->
            val alignment = when (slot) {
                0 -> TextAlign.Start
                indices.lastIndex -> TextAlign.End
                else -> TextAlign.Center
            }
            Text(
                referenceAxisLabel(visible[index].trading_date, useTimeAxis),
                modifier = Modifier.weight(1f),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = alignment,
                maxLines = 1,
            )
        }
    }
}

@Composable
private fun ReferenceMiniNavigator(
    bars: List<DailyPriceDto>,
    windowStart: Int,
    windowSize: Int,
    onWindowStartChange: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val lineColor = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.52f)
    val primaryColor = MaterialTheme.colorScheme.primary
    val outlineColor = MaterialTheme.colorScheme.outlineVariant
    val navigatorSurface = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.24f)
    val min = bars.minOfOrNull { it.close } ?: 0.0
    val max = bars.maxOfOrNull { it.close } ?: 1.0
    val span = (max - min).coerceAtLeast(0.01)
    val maxStart = (bars.size - windowSize).coerceAtLeast(0)

    Canvas(
        modifier.pointerInput(bars.size, windowSize) {
            fun moveTo(x: Float) {
                val ratio = (x / size.width.toFloat().coerceAtLeast(1f)).coerceIn(0f, 1f)
                val center = (ratio * (bars.size - 1).coerceAtLeast(0)).roundToInt()
                onWindowStartChange((center - windowSize / 2).coerceIn(0, maxStart))
            }
            detectDragGestures(onDragStart = { moveTo(it.x) }, onDrag = { change, _ -> moveTo(change.position.x) })
        },
    ) {
        drawRoundRect(navigatorSurface, size = size, cornerRadius = CornerRadius(6.dp.toPx()))
        val step = if (bars.size <= 1) size.width else size.width / (bars.size - 1)
        val path = Path()
        bars.forEachIndexed { index, bar ->
            val x = index * step
            val y = size.height - (((bar.close - min) / span) * size.height).toFloat()
            if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        drawPath(path, lineColor, style = Stroke(0.75.dp.toPx()))

        val left = windowStart.toFloat() / bars.size.coerceAtLeast(1) * size.width
        val right = (windowStart + windowSize).toFloat() / bars.size.coerceAtLeast(1) * size.width
        drawRoundRect(
            primaryColor.copy(alpha = 0.045f),
            Offset(left, 0f),
            Size((right - left).coerceAtLeast(1f), size.height),
            CornerRadius(5.dp.toPx()),
            style = Stroke(1.dp.toPx()),
        )
        drawLine(outlineColor, Offset(left, 0f), Offset(left, size.height), 1.dp.toPx())
        drawLine(outlineColor, Offset(right, 0f), Offset(right, size.height), 1.dp.toPx())
    }
}

private fun referenceMovingAverage(bars: List<DailyPriceDto>, days: Int): List<Double?> =
    bars.indices.map { index ->
        if (index + 1 < days) null else bars.subList(index + 1 - days, index + 1).map { it.close }.average()
    }

private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawReferenceAverage(
    values: List<Double?>,
    windowStart: Int,
    visibleSize: Int,
    step: Float,
    y: (Double) -> Float,
    color: Color,
) {
    val path = Path()
    var started = false
    repeat(visibleSize) { local ->
        val value = values.getOrNull(windowStart + local) ?: return@repeat
        val x = step * local + step / 2f
        if (!started) {
            path.moveTo(x, y(value))
            started = true
        } else path.lineTo(x, y(value))
    }
    if (started) drawPath(path, color, style = Stroke(1.dp.toPx()))
}

private fun referenceAxisLabel(raw: String, useTimeAxis: Boolean): String {
    val normalized = raw.replace('T', ' ')
    return if (useTimeAxis) {
        normalized.substringAfter(' ', "").take(5).ifBlank { normalized.takeLast(5) }
    } else {
        normalized.take(10)
    }
}

private fun referenceCompactVolume(value: Double?): String {
    val number = value ?: return "--"
    return when {
        number >= 100_000_000 -> "%.2f亿".format(Locale.US, number / 100_000_000)
        number >= 10_000 -> "%.2f万".format(Locale.US, number / 10_000)
        else -> "%.0f".format(Locale.US, number)
    }
}
