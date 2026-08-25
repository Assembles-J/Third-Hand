package com.thirdhand.app.ui.components

import android.graphics.Paint
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thirdhand.app.DailyPriceDto
import com.thirdhand.app.MarketQuoteDto
import com.thirdhand.app.PaperTradingLogDto
import com.thirdhand.app.ui.theme.marketColors
import java.util.*

@Composable
fun KLineChart(
    bars: List<DailyPriceDto>,
    quote: MarketQuoteDto? = null,
    useTimeAxis: Boolean = false,
    paperMarkers: List<PaperTradingLogDto> = emptyList(),
    modifier: Modifier = Modifier
) {
    if (bars.isEmpty()) return

    val visible = if (useTimeAxis) bars else bars.takeLast(60)
    var selectedIndex by remember(visible.lastOrNull()?.trading_date) { mutableIntStateOf(visible.lastIndex) }
    val selected = visible[selectedIndex.coerceIn(0, visible.lastIndex)]

    val values = visible.flatMap { listOfNotNull(it.high, it.low, it.close, it.open) }
    val minimum = values.minOrNull() ?: 0.0
    val maximum = values.maxOrNull() ?: 1.0

    val colors = MaterialTheme.marketColors
    val crosshairColor = MaterialTheme.colorScheme.primary

    Column(modifier = modifier.fillMaxWidth()) {
        // 十字线定位数据展示
        Column(Modifier.fillMaxWidth().padding(bottom = 8.dp)) {
            val previousClose = visible.getOrNull((selectedIndex - 1).coerceAtMost(visible.lastIndex))?.close ?: selected.close
            val change = if (previousClose != 0.0) (selected.close / previousClose - 1) * 100 else 0.0
            val changeColor = if (change >= 0) colors.rise else colors.fall

            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(
                    text = "${selected.trading_date}  ${if (change >= 0) "▲" else "▼"} ${"%.2f%%".format(change)}",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold,
                    color = changeColor
                )
            }
            Row(Modifier.fillMaxWidth().padding(top = 2.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                ChartMiniMetric("开", "%.2f".format(selected.open ?: selected.close))
                ChartMiniMetric("高", "%.2f".format(selected.high ?: selected.close))
                ChartMiniMetric("低", "%.2f".format(selected.low ?: selected.close))
                ChartMiniMetric("收", "%.2f".format(selected.close))
            }
        }

        Row(Modifier.fillMaxWidth().height(240.dp)) {
            // Y 轴刻度
            Column(Modifier.width(42.dp).fillMaxHeight(), verticalArrangement = Arrangement.SpaceBetween) {
                Text("%.1f".format(maximum), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("%.1f".format((maximum + minimum) / 2), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("%.1f".format(minimum), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("VOL", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }

            // 图表画布
            Canvas(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxHeight()
                    .pointerInput(visible) {
                        fun xFor(index: Int): Float = (index + .5f) / visible.size * size.width
                        fun selectAt(x: Float) {
                            selectedIndex = visible.indices.minByOrNull { index -> Math.abs(xFor(index) - x) } ?: visible.lastIndex
                        }
                        detectDragGestures(onDragStart = { selectAt(it.x) }, onDrag = { change, _ -> selectAt(change.position.x) })
                    }
            ) {
                val priceHeight = size.height * 0.75f
                val volumeTop = priceHeight + 10f
                val span = (maximum - minimum).coerceAtLeast(0.01)
                val step = size.width / visible.size
                val candleWidth = (step * 0.7f).coerceAtLeast(1f)
                val maxVolume = visible.maxOfOrNull { it.volume ?: 0.0 }?.coerceAtLeast(1.0) ?: 1.0

                fun y(value: Double) = priceHeight - ((value - minimum) / span * priceHeight).toFloat()

                visible.forEachIndexed { index, bar ->
                    val x = step * index + step / 2
                    val open = bar.open ?: bar.close
                    val color = if (bar.close >= open) colors.rise else colors.fall

                    // K 线
                    drawLine(color, Offset(x, y(bar.high ?: bar.close)), Offset(x, y(bar.low ?: bar.close)), strokeWidth = 1.dp.toPx())
                    drawLine(color, Offset(x, y(open)), Offset(x, y(bar.close)), strokeWidth = candleWidth)

                    // 成交量
                    val volHeight = ((bar.volume ?: 0.0) / maxVolume * (size.height - volumeTop)).toFloat()
                    drawLine(color.copy(alpha = 0.5f), Offset(x, size.height), Offset(x, size.height - volHeight), strokeWidth = candleWidth)
                }

                // 交易标记 (B/S)
                paperMarkers.forEach { marker ->
                    val markerDate = marker.executed_at.take(10)
                    val markerIndex = visible.indexOfLast { it.trading_date.take(10) == markerDate }
                    if (markerIndex >= 0) {
                        val markerX = step * markerIndex + step / 2
                        val markerY = y(marker.price.coerceIn(minimum, maximum))
                        val isBuy = marker.side == "BUY"
                        val markerColor = if (isBuy) Color(0xFF7E57C2) else Color(0xFFEC407A)

                        drawCircle(markerColor, radius = 8.dp.toPx(), center = Offset(markerX, markerY))
                        drawContext.canvas.nativeCanvas.drawText(
                            if (isBuy) "B" else "S",
                            markerX - 4.dp.toPx(),
                            markerY + 4.dp.toPx(),
                            Paint().apply {
                                color = android.graphics.Color.WHITE
                                textSize = 11.sp.toPx()
                                isFakeBoldText = true
                                textAlign = Paint.Align.CENTER
                            }
                        )
                    }
                }

                // 十字线
                val crossX = step * selectedIndex + step / 2
                val crossY = y(selected.close)
                drawLine(crosshairColor.copy(alpha = 0.6f), Offset(crossX, 0f), Offset(crossX, size.height), strokeWidth = 1.dp.toPx())
                drawLine(crosshairColor.copy(alpha = 0.4f), Offset(0f, crossY), Offset(size.width, crossY), strokeWidth = 0.5.dp.toPx())
            }
        }
    }
}

@Composable
private fun ChartMiniMetric(label: String, value: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.width(2.dp))
        Text(value, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
    }
}
