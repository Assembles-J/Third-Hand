package com.thirdhand.app

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AutoGraph
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.thirdhand.app.researchchat.ResearchChatController
import com.thirdhand.app.researchchat.ResearchChatLine
import com.thirdhand.app.researchchat.ResearchChatScreen
import com.thirdhand.app.ui.theme.marketColors
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import kotlinx.coroutines.supervisorScope
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.temporal.ChronoUnit
import java.util.Locale

private data class PositionDetailUiState(
    val loading: Boolean = true,
    val quote: MarketQuoteDto? = null,
    val holding: HoldingDto? = null,
    val paperPosition: PaperTradingPositionDto? = null,
    val paperLogs: List<PaperTradingLogDto> = emptyList(),
    val resolvedName: String? = null,
    val error: String? = null,
)

/**
 * Data-first detail for an owned position.
 *
 * Strategy/AI prose deliberately lives behind the top-right secondary entry so
 * the primary surface remains useful as a compact position fact sheet.
 */
@Composable
fun PositionDetailRoute(
    target: ResearchTargetDto,
    onBack: () -> Unit,
) {
    var secondary by remember(target.symbol) { mutableStateOf<PositionSecondaryPage?>(null) }
    when (secondary) {
        PositionSecondaryPage.DECISION -> {
            PositionDecisionSecondaryScreen(
                target = target,
                onBack = { secondary = null },
                onOpenResearch = { secondary = PositionSecondaryPage.RESEARCH },
            )
            return
        }
        PositionSecondaryPage.RESEARCH -> {
            PositionResearchSubroute(target = target, onClose = { secondary = PositionSecondaryPage.DECISION })
            return
        }
        null -> Unit
    }

    val context = LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var state by remember(target.symbol) { mutableStateOf(PositionDetailUiState()) }

    fun load() = scope.launch {
        state = state.copy(loading = true, error = null)
        supervisorScope {
            val quoteDeferred = async {
                runCatching { loadLatestDisplayQuotes(api, listOf(target.symbol)).firstOrNull() }
            }
            val holdingDeferred = async {
                runCatching { api.holdings().firstOrNull { it.symbol == target.symbol } }
            }
            val accountDeferred = async { runCatching { api.paperTradingAccount() } }
            val logsDeferred = async { runCatching { api.paperTradingLogs(target.symbol, 100) } }

            val quote = quoteDeferred.await().getOrNull()
            val holding = holdingDeferred.await().getOrNull()
            val paperPosition = accountDeferred.await().getOrNull()?.positions?.firstOrNull { it.symbol == target.symbol }
            val logs = logsDeferred.await().getOrDefault(emptyList())
            var name = firstValidSecurityName(
                target.symbol,
                quote?.name,
                holding?.name,
                paperPosition?.name,
                target.name,
            )
            if (name == null) {
                name = runCatching {
                    api.symbolLookup(SymbolResolveRequestDto(listOf(target.symbol)))
                        .firstOrNull()
                        ?.matches
                        .orEmpty()
                        .firstOrNull { it.symbol == target.symbol }
                        ?.name
                        ?.takeIf { it.isValidSecurityName(target.symbol) }
                }.getOrNull()
            }
            state = PositionDetailUiState(
                loading = false,
                quote = quote,
                holding = holding,
                paperPosition = paperPosition,
                paperLogs = logs,
                resolvedName = name,
                error = if (quote == null && holding == null && paperPosition == null) "持仓和行情暂时都不可用，请稍后刷新。" else null,
            )
        }
    }

    LaunchedEffect(target.symbol) { load() }

    val quantity = state.paperPosition?.quantity ?: state.holding?.quantity
    val averageCost = state.paperPosition?.average_cost ?: state.holding?.average_cost
    val currentPrice = state.quote?.price ?: state.paperPosition?.last_price
    val marketValue = when {
        state.paperPosition != null -> state.paperPosition!!.market_value
        quantity != null && currentPrice != null -> quantity * currentPrice
        else -> null
    }
    val pnl = when {
        state.paperPosition != null -> state.paperPosition!!.unrealized_pnl
        quantity != null && currentPrice != null && averageCost != null -> (currentPrice - averageCost) * quantity
        else -> null
    }
    val pnlPercent = when {
        state.paperPosition != null -> state.paperPosition!!.unrealized_return_percent
        currentPrice != null && averageCost != null && averageCost != 0.0 -> (currentPrice / averageCost - 1.0) * 100.0
        else -> null
    }
    val displayName = state.resolvedName ?: "名称待同步"
    val holdingDays = state.holding?.created_at?.let(::calendarHoldingDays)
    val pnlColor = when {
        pnl == null -> MaterialTheme.colorScheme.onSurfaceVariant
        pnl >= 0 -> MaterialTheme.marketColors.rise
        else -> MaterialTheme.marketColors.fall
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 28.dp),
    ) {
        item {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回") }
                Column(Modifier.weight(1f)) {
                    Text(displayName, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text(target.symbol, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                IconButton(onClick = { secondary = PositionSecondaryPage.DECISION }) {
                    Icon(Icons.Filled.AutoGraph, contentDescription = "AI 决策与研究", tint = MaterialTheme.colorScheme.primary)
                }
                IconButton(onClick = ::load, enabled = !state.loading) {
                    if (state.loading) CircularProgressIndicator(Modifier.width(20.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Filled.Refresh, contentDescription = "刷新持仓详情")
                }
            }
        }
        if (state.resolvedName == null) {
            item {
                Text(
                    "证券名称尚未同步，系统已主动尝试行情与代码表查询；不会把证券代码伪装成名称。",
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }
        state.error?.let { message ->
            item { Text(message, modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        }
        item {
            Column(
                Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Row(Modifier.fillMaxWidth()) {
                    PositionFact("现价", currentPrice?.positionMoney() ?: "—", Modifier.weight(1f))
                    PositionFact("持仓市值", marketValue?.let { "¥${it.positionMoney()}" } ?: "—", Modifier.weight(1f))
                    PositionFact("浮动盈亏", pnl?.let { "${if (it >= 0) "+" else ""}¥${it.positionMoney()}" } ?: "—", Modifier.weight(1f), pnlColor)
                }
                Row(Modifier.fillMaxWidth()) {
                    PositionFact("盈亏比例", pnlPercent?.signedPositionPercent() ?: "—", Modifier.weight(1f), pnlColor)
                    PositionFact("持仓数量", quantity?.positionQuantity() ?: "—", Modifier.weight(1f))
                    PositionFact("平均成本", averageCost?.positionMoney() ?: "—", Modifier.weight(1f))
                }
                Row(Modifier.fillMaxWidth()) {
                    PositionFact(
                        "持仓天数",
                        holdingDays?.let { "$it 天" } ?: if (state.paperPosition != null) "账本待补" else "—",
                        Modifier.weight(1f),
                    )
                    PositionFact("可卖数量", state.paperPosition?.sellable_quantity?.positionQuantity() ?: "—", Modifier.weight(1f))
                    PositionFact("T+1 锁定", state.paperPosition?.locked_quantity?.positionQuantity() ?: "—", Modifier.weight(1f))
                }
                Text(
                    "行情 ${state.quote?.source ?: "—"} · 数据 ${state.quote?.as_of ?: state.quote?.retrieved_at ?: "待同步"}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        item { HorizontalDivider() }
        item { TradingPeriodKLinePanel(symbol = target.symbol, quote = state.quote) }
        item { HorizontalDivider() }
        item {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("事实成交记录", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text("这里只展示模拟账本实际成交事实；决策理由与复核时间请点右上角 AI 图标。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (state.paperLogs.none { it.status == "executed" }) {
                    Text("暂无模拟成交记录。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        items(state.paperLogs.filter { it.status == "executed" }.take(20), key = { it.id }) { log ->
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(if (log.side == "BUY") "买入" else "卖出", fontWeight = FontWeight.SemiBold)
                    Text(log.executed_at.replace('T', ' ').substringBefore("+").substringBefore("Z"), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Text("${log.quantity.positionQuantity()} @ ¥${log.price.positionMoney()}", style = MaterialTheme.typography.bodySmall)
            }
            HorizontalDivider(Modifier.padding(horizontal = 16.dp))
        }
    }
}

@Composable
private fun PositionDecisionSecondaryScreen(
    target: ResearchTargetDto,
    onBack: () -> Unit,
    onOpenResearch: () -> Unit,
) {
    LazyColumn(modifier = Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 28.dp)) {
        item {
            Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回持仓详情") }
                Column(Modifier.weight(1f)) {
                    Text("决策与研究", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text("${target.symbol} · 二级入口", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        item {
            DecisionWorkspaceSummaryPanel(
                symbol = target.symbol,
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
            )
        }
        item {
            Column(Modifier.padding(horizontal = 12.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("这里集中展示 Formal Decision、What Changed、T+1/下次可卖与复核时间。它们不再挤占持仓数据页。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                FilledTonalButton(onClick = onOpenResearch, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Filled.AutoGraph, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("进入 AI Research")
                }
            }
        }
    }
}

/** Real Research Chat host used by position and stock detail; it never falls through to News. */
@Composable
fun PositionResearchSubroute(
    target: ResearchTargetDto,
    onClose: () -> Unit,
) {
    val controller = remember(target.symbol) { ResearchChatController() }
    var conversation by remember(target.symbol) { mutableStateOf<List<ResearchChatLine>>(emptyList()) }
    var question by remember(target.symbol) { mutableStateOf("") }
    LaunchedEffect(target.symbol) { controller.beginNewResearch(target.symbol) }
    ResearchChatScreen(
        controller = controller,
        conversation = conversation,
        onConversationChange = { conversation = it },
        question = question,
        onQuestionChange = { question = it },
        initialTarget = target,
        onOpenTradePlan = {},
        onOpenPortfolio = onClose,
        onOpenRules = {},
        onClose = onClose,
    )
}

private enum class PositionSecondaryPage { DECISION, RESEARCH }

@Composable
private fun PositionFact(
    label: String,
    value: String,
    modifier: Modifier,
    valueColor: androidx.compose.ui.graphics.Color = MaterialTheme.colorScheme.onSurface,
) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold, color = valueColor, maxLines = 1)
    }
}

internal fun firstValidSecurityName(symbol: String, vararg values: String?): String? =
    values.firstOrNull { it.isValidSecurityName(symbol) }?.trim()

internal fun String?.isValidSecurityName(symbol: String): Boolean {
    val value = this?.trim().orEmpty()
    return value.isNotBlank() && !value.equals(symbol.trim(), ignoreCase = true)
}

private fun calendarHoldingDays(value: String): Long? {
    val start = runCatching { OffsetDateTime.parse(value).withOffsetSameInstant(ZoneOffset.ofHours(8)).toLocalDate() }
        .getOrElse { runCatching { LocalDate.parse(value.take(10)) }.getOrNull() }
        ?: return null
    return ChronoUnit.DAYS.between(start, LocalDate.now(ZoneOffset.ofHours(8))).coerceAtLeast(0) + 1
}

private fun Double.positionMoney(): String = "%.2f".format(Locale.US, this)
private fun Double.positionQuantity(): String = if (this % 1.0 == 0.0) "${toLong()} 股" else "%.2f 股".format(Locale.US, this)
private fun Double.signedPositionPercent(): String = "%+.2f%%".format(Locale.US, this)
