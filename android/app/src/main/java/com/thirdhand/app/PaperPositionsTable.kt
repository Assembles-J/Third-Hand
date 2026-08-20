package com.thirdhand.app

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.theme.marketColors
import java.util.Locale

internal data class PaperPositionPresentation(
    val quotesBySymbol: Map<String, MarketQuoteDto> = emptyMap(),
    val namesBySymbol: Map<String, String> = emptyMap(),
)

/** Resolve names for display without mutating the paper ledger. */
internal suspend fun loadPaperPositionPresentation(
    api: ThirdHandApi,
    positions: List<PaperTradingPositionDto>,
): PaperPositionPresentation {
    val symbols = positions.map { it.symbol }.distinct().filter { it.isNotBlank() }
    if (symbols.isEmpty()) return PaperPositionPresentation()

    val quotes = runCatching { loadLatestDisplayQuotes(api, symbols) }
        .getOrDefault(emptyList())
        .associateBy { it.symbol }
    val resolved = mutableMapOf<String, String>()
    positions.forEach { position ->
        firstValidSecurityName(
            position.symbol,
            quotes[position.symbol]?.name,
            position.name,
        )?.let { resolved[position.symbol] = it }
    }

    val unresolved = symbols.filterNot(resolved::containsKey)
    if (unresolved.isNotEmpty()) {
        runCatching { api.symbolLookup(SymbolResolveRequestDto(unresolved)) }
            .getOrDefault(emptyList())
            .flatMap { it.matches }
            .forEach { candidate ->
                if (candidate.symbol in unresolved && candidate.name.isValidSecurityName(candidate.symbol)) {
                    resolved.putIfAbsent(candidate.symbol, candidate.name.trim())
                }
            }
    }
    return PaperPositionPresentation(quotesBySymbol = quotes, namesBySymbol = resolved)
}

/**
 * Brokerage-style position table: security/value stays fixed while metric columns
 * move as one horizontally-scrollable surface.
 */
@Composable
internal fun PaperPositionsTable(
    positions: List<PaperTradingPositionDto>,
    presentation: PaperPositionPresentation,
    onOpenDetail: (PaperTradingPositionDto, String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val horizontal = rememberScrollState()
    Column(modifier.fillMaxWidth()) {
        Text(
            "左侧固定证券/市值 · 左右滑动查看更多持仓数据",
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
            Column(Modifier.width(142.dp)) {
                FixedPositionHeader()
                positions.forEach { position ->
                    val name = presentation.namesBySymbol[position.symbol] ?: "名称待同步"
                    FixedPositionCell(position, name) { onOpenDetail(position, name) }
                }
            }
            Row(Modifier.weight(1f).horizontalScroll(horizontal)) {
                PaperMetricColumn("盈亏 / 比例", 126.dp, positions) { position ->
                    val isUp = position.unrealized_pnl >= 0
                    val color = if (isUp) MaterialTheme.marketColors.rise else MaterialTheme.marketColors.fall
                    PositionMetricText(
                        main = position.unrealized_pnl.paperSignedMoney(),
                        sub = position.unrealized_return_percent.paperSignedPercent(),
                        color = color,
                    )
                }
                PaperMetricColumn("持仓 / 可卖", 118.dp, positions) { position ->
                    PositionMetricText(
                        main = position.quantity.paperQuantity(),
                        sub = position.sellable_quantity?.let { "可卖 ${it.paperQuantity()}" } ?: "可卖待同步",
                    )
                }
                PaperMetricColumn("成本 / 现价", 126.dp, positions) { position ->
                    PositionMetricText(
                        main = position.average_cost.paperMoney(),
                        sub = "现 ${position.last_price.paperMoney()}",
                    )
                }
                PaperMetricColumn("T+1 锁定", 110.dp, positions) { position ->
                    PositionMetricText(
                        main = position.locked_quantity?.paperQuantity() ?: "—",
                        sub = if ((position.locked_quantity ?: 0.0) > 0) "详情查看时间" else "无锁定",
                    )
                }
            }
        }
    }
}

@Composable
private fun FixedPositionHeader() {
    Column(Modifier.fillMaxWidth().height(TABLE_HEADER_HEIGHT).padding(start = 16.dp, end = 8.dp), verticalArrangement = androidx.compose.foundation.layout.Arrangement.Center) {
        Text("证券 / 市值", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    HorizontalDivider()
}

@Composable
private fun FixedPositionCell(position: PaperTradingPositionDto, name: String, onClick: () -> Unit) {
    Column(
        Modifier.fillMaxWidth().height(TABLE_ROW_HEIGHT).clickable(onClick = onClick).padding(start = 16.dp, end = 8.dp, top = 8.dp, bottom = 6.dp),
    ) {
        Text(name, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
        Text("¥${position.market_value.paperMoney()}", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
        Text(position.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    HorizontalDivider()
}

@Composable
private fun PaperMetricColumn(
    title: String,
    width: androidx.compose.ui.unit.Dp,
    positions: List<PaperTradingPositionDto>,
    content: @Composable (PaperTradingPositionDto) -> Unit,
) {
    Column(Modifier.width(width)) {
        Text(
            title,
            modifier = Modifier.fillMaxWidth().height(TABLE_HEADER_HEIGHT).padding(end = 12.dp, top = 11.dp),
            textAlign = TextAlign.End,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        HorizontalDivider()
        positions.forEach { position ->
            Column(
                Modifier.fillMaxWidth().height(TABLE_ROW_HEIGHT).padding(horizontal = 10.dp, vertical = 10.dp),
                horizontalAlignment = Alignment.End,
            ) {
                content(position)
            }
            HorizontalDivider()
        }
    }
}

@Composable
private fun PositionMetricText(
    main: String,
    sub: String,
    color: Color = MaterialTheme.colorScheme.onSurface,
) {
    Text(main, color = color, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold, textAlign = TextAlign.End, maxLines = 1)
    Text(sub, color = color.copy(alpha = .82f), style = MaterialTheme.typography.labelSmall, textAlign = TextAlign.End, maxLines = 1)
}

private val TABLE_HEADER_HEIGHT = 42.dp
private val TABLE_ROW_HEIGHT = 72.dp

private fun Double.paperMoney(): String = "%.2f".format(Locale.US, this)
private fun Double.paperSignedMoney(): String = "%+.2f".format(Locale.US, this)
private fun Double.paperSignedPercent(): String = "%+.2f%%".format(Locale.US, this)
private fun Double.paperQuantity(): String = if (this % 1.0 == 0.0) toLong().toString() else "%.2f".format(Locale.US, this)
