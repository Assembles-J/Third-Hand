package com.thirdhand.app

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.CompactTypography
import com.thirdhand.app.ui.theme.marketColors
import java.util.Locale

internal data class PaperPositionPresentation(
    val quotesBySymbol: Map<String, MarketQuoteDto> = emptyMap(),
    val namesBySymbol: Map<String, String> = emptyMap(),
)

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
    return PaperPositionPresentation(quotesBySymbol = quotes, namesBySymbol = resolved)
}

@Composable
internal fun PaperPositionsTable(
    positions: List<PaperTradingPositionDto>,
    presentation: PaperPositionPresentation,
    onOpenDetail: (PaperTradingPositionDto, String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val horizontal = rememberScrollState()

    Surface(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal),
        color = MaterialTheme.colorScheme.surface,
        shape = RoundedCornerShape(6.dp),
        border = BorderStroke(0.5.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column {
            Row(
                Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.28f)),
            ) {
                Box(
                    Modifier
                        .width(116.dp)
                        .padding(horizontal = AppSpacing.small, vertical = AppSpacing.denseGap),
                    contentAlignment = Alignment.CenterStart,
                ) {
                    Text(
                        "证券",
                        style = CompactTypography.caption,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Row(Modifier.weight(1f).horizontalScroll(horizontal)) {
                    TableHeaderCell("当前盈亏", 92.dp)
                    TableHeaderCell("持仓/可卖", 92.dp)
                    TableHeaderCell("成本/现价", 92.dp)
                    TableHeaderCell("市值", 92.dp)
                }
            }

            positions.forEachIndexed { index, position ->
                val name = presentation.namesBySymbol[position.symbol] ?: position.symbol
                PositionRow(
                    position = position,
                    name = name,
                    horizontalScrollState = horizontal,
                    onClick = { onOpenDetail(position, name) },
                )
                if (index < positions.lastIndex) {
                    HorizontalDivider(
                        thickness = 0.5.dp,
                        color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.55f),
                    )
                }
            }
        }
    }
}

@Composable
private fun TableHeaderCell(text: String, width: Dp) {
    Box(
        Modifier
            .width(width)
            .padding(horizontal = AppSpacing.small, vertical = AppSpacing.denseGap),
        contentAlignment = Alignment.CenterEnd,
    ) {
        Text(
            text,
            style = CompactTypography.caption,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun PositionRow(
    position: PaperTradingPositionDto,
    name: String,
    horizontalScrollState: androidx.compose.foundation.ScrollState,
    onClick: () -> Unit,
) {
    val colors = MaterialTheme.marketColors
    val pnlColor = if (position.unrealized_pnl >= 0) colors.rise else colors.fall

    Row(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .heightIn(min = AppSpacing.touchTarget)
            .padding(vertical = AppSpacing.xs),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(
            Modifier
                .width(116.dp)
                .padding(horizontal = AppSpacing.small),
        ) {
            Text(
                name,
                style = CompactTypography.rowTitle,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                position.symbol,
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        Row(Modifier.weight(1f).horizontalScroll(horizontalScrollState)) {
            TableCell(
                main = position.unrealized_pnl.paperSignedMoney(),
                sub = position.unrealized_return_percent.paperSignedPercent(),
                color = pnlColor,
                width = 92.dp,
            )
            TableCell(
                main = position.quantity.paperQuantity(),
                sub = "可卖 ${position.sellable_quantity?.paperQuantity() ?: "--"}",
                width = 92.dp,
            )
            TableCell(
                main = position.average_cost.paperMoney(),
                sub = "现价 ${position.last_price.paperMoney()}",
                width = 92.dp,
            )
            TableCell(
                main = "¥${position.market_value.paperMoney()}",
                sub = position.locked_quantity?.takeIf { it > 0 }?.let { "锁定 ${it.paperQuantity()}" } ?: "--",
                width = 92.dp,
            )
        }
    }
}

@Composable
private fun TableCell(
    main: String,
    sub: String,
    width: Dp,
    color: Color = MaterialTheme.colorScheme.onSurface,
) {
    Column(
        Modifier
            .width(width)
            .padding(horizontal = AppSpacing.small),
        horizontalAlignment = Alignment.End,
    ) {
        Text(
            main,
            style = CompactTypography.secondary,
            fontWeight = FontWeight.SemiBold,
            color = color,
            maxLines = 1,
        )
        Text(
            sub,
            style = CompactTypography.caption,
            color = if (color == MaterialTheme.colorScheme.onSurface) {
                MaterialTheme.colorScheme.onSurfaceVariant
            } else {
                color.copy(alpha = 0.82f)
            },
            maxLines = 1,
        )
    }
}

private fun Double.paperMoney(): String = "%.2f".format(Locale.US, this)
private fun Double.paperSignedMoney(): String = "%+.2f".format(Locale.US, this)
private fun Double.paperSignedPercent(): String = "%+.2f%%".format(Locale.US, this)
private fun Double.paperQuantity(): String = if (this % 1.0 == 0.0) toLong().toString() else "%.2f".format(Locale.US, this)
