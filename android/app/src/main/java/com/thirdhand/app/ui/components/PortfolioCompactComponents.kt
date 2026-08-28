package com.thirdhand.app.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thirdhand.app.HoldingDto
import com.thirdhand.app.MarketQuoteDto
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.CompactTypography
import com.thirdhand.app.ui.theme.marketColors
import java.util.Locale

/** Compact, fact-first portfolio summary for UIX4/UIX8. */
@Composable
fun CompactPortfolioSummary(
    availableCash: Double,
    marketValue: Double,
    totalPnl: Double,
    holdingCount: Int,
    modifier: Modifier = Modifier,
) {
    val colors = MaterialTheme.marketColors
    val totalAssets = availableCash + marketValue
    val pnlColor = when {
        totalPnl > 0 -> colors.rise
        totalPnl < 0 -> colors.fall
        else -> colors.neutral
    }

    Surface(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.small, vertical = AppSpacing.small),
        color = MaterialTheme.colorScheme.surface,
        shape = RoundedCornerShape(8.dp),
        border = BorderStroke(0.5.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.65f)),
        tonalElevation = 0.dp,
    ) {
        Column(
            modifier = Modifier.padding(
                horizontal = AppSpacing.contentHorizontal,
                vertical = AppSpacing.medium,
            ),
        ) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Bottom) {
                Column(Modifier.weight(1f)) {
                    Text(
                        "总资产",
                        style = CompactTypography.caption,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        "¥${portfolioMoney(totalAssets)}",
                        style = CompactTypography.pageTitle.copy(fontSize = 21.sp, lineHeight = 26.sp),
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        "总盈亏",
                        style = CompactTypography.caption,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        "${if (totalPnl > 0) "+" else ""}¥${portfolioMoney(totalPnl)}",
                        style = CompactTypography.rowValue,
                        fontWeight = FontWeight.SemiBold,
                        color = pnlColor,
                    )
                }
            }

            HorizontalDivider(
                modifier = Modifier.padding(vertical = AppSpacing.small),
                thickness = 0.5.dp,
                color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.55f),
            )

            Row(Modifier.fillMaxWidth()) {
                SummaryFact("持仓市值", "¥${portfolioMoney(marketValue)}", Modifier.weight(1f))
                SummaryFact("可用现金", "¥${portfolioMoney(availableCash)}", Modifier.weight(1f))
                SummaryFact("持仓", "$holdingCount 只", Modifier.weight(0.72f), alignEnd = true)
            }
        }
    }
}

@Composable
private fun SummaryFact(label: String, value: String, modifier: Modifier, alignEnd: Boolean = false) {
    Column(modifier, horizontalAlignment = if (alignEnd) Alignment.End else Alignment.Start) {
        Text(label, style = CompactTypography.caption, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = CompactTypography.secondary, fontWeight = FontWeight.Medium)
    }
}

/** Table-like label row. Numeric columns line up with [CompactHoldingRow]. */
@Composable
fun CompactHoldingsHeader(modifier: Modifier = Modifier) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.small)
            .background(MaterialTheme.colorScheme.surface)
            .padding(horizontal = AppSpacing.rowHorizontal, vertical = AppSpacing.small),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            "标的 / 持仓事实",
            modifier = Modifier.weight(1f),
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            "现价",
            modifier = Modifier.width(76.dp),
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.End,
        )
        Text(
            "盈亏",
            modifier = Modifier.width(92.dp),
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.End,
        )
        Spacer(Modifier.width(AppSpacing.xLarge))
    }
    DenseRowDivider(modifier = Modifier.padding(horizontal = AppSpacing.small), inset = false)
}

/**
 * One dense holdings row. It only formats facts already present in Holding/Quote;
 * no portfolio analytics or decision logic is calculated here.
 */
@Composable
fun CompactHoldingRow(
    holding: HoldingDto,
    quote: MarketQuoteDto?,
    positionWeight: Double?,
    holdingDays: Long,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = MaterialTheme.marketColors
    val currentPrice = quote?.price ?: holding.average_cost
    val marketValue = currentPrice * holding.quantity
    val pnl = (currentPrice - holding.average_cost) * holding.quantity
    val pnlPercent = if (holding.average_cost != 0.0) {
        (currentPrice - holding.average_cost) / holding.average_cost * 100
    } else {
        0.0
    }
    val pnlColor = when {
        pnl > 0 -> colors.rise
        pnl < 0 -> colors.fall
        else -> colors.neutral
    }
    val symbol = currencySymbol(quote?.currency)

    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.small)
            .background(MaterialTheme.colorScheme.surface)
            .heightIn(min = AppSpacing.touchTarget)
            .clickable(onClick = onClick)
            .padding(horizontal = AppSpacing.rowHorizontal, vertical = AppSpacing.rowVertical),
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(
                    holding.name.ifBlank { holding.symbol },
                    style = CompactTypography.rowTitle,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    "${holding.symbol} · ${quoteStateLabel(quote?.display_freshness)} · ${holdingDays}天",
                    style = CompactTypography.caption,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                )
            }

            Column(Modifier.width(76.dp), horizontalAlignment = Alignment.End) {
                Text("$symbol${portfolioMoney(currentPrice)}", style = CompactTypography.rowValue)
                Text(
                    "成本 $symbol${portfolioMoney(holding.average_cost)}",
                    style = CompactTypography.caption,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Column(Modifier.width(92.dp), horizontalAlignment = Alignment.End) {
                Text(
                    "${if (pnlPercent > 0) "+" else ""}${"%.2f".format(Locale.US, pnlPercent)}%",
                    style = CompactTypography.rowValue,
                    color = pnlColor,
                )
                Text(
                    "${if (pnl > 0) "+" else ""}$symbol${portfolioMoney(pnl)}",
                    style = CompactTypography.caption,
                    color = pnlColor,
                )
            }

            Icon(
                Icons.Default.ChevronRight,
                contentDescription = "查看 ${holding.name} 持仓详情",
                modifier = Modifier.size(AppSpacing.xLarge),
                tint = MaterialTheme.colorScheme.outline,
            )
        }

        Spacer(Modifier.height(AppSpacing.xxs))
        Text(
            buildString {
                append("数量 ${portfolioQuantity(holding.quantity)}")
                append(" · 市值 $symbol${portfolioMoney(marketValue)}")
                append(" · 仓位 ")
                append(positionWeight?.let { "%.1f%%".format(Locale.US, it * 100) } ?: "--")
            },
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(end = AppSpacing.xLarge),
        )
    }
    DenseRowDivider(modifier = Modifier.padding(horizontal = AppSpacing.small), inset = true)
}

private fun quoteStateLabel(state: String?): String = when (state) {
    "live", "realtime" -> "实时"
    "session_close", "close" -> "收盘"
    "refreshing", "loading" -> "刷新中"
    "stale", "stale_fallback" -> "延迟"
    null -> "暂估"
    else -> "暂估"
}

private fun currencySymbol(currency: String?): String = when (currency?.uppercase(Locale.ROOT)) {
    "HKD" -> "HK$"
    "USD" -> "$"
    "CNY", "RMB", null, "" -> "¥"
    else -> "$currency "
}

private fun portfolioMoney(value: Double): String = "%.2f".format(Locale.US, value)
private fun portfolioQuantity(value: Double): String =
    if (value % 1.0 == 0.0) "${value.toLong()}股" else "%.2f股".format(Locale.US, value)
