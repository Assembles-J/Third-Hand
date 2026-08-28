package com.thirdhand.app

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoGraph
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.components.DenseRowDivider
import com.thirdhand.app.ui.components.DenseStateTag
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.CompactTypography
import com.thirdhand.app.ui.theme.marketColors
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import kotlinx.coroutines.supervisorScope
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale

internal data class HomeDashboardSnapshot(
    val paperDashboard: PaperTradingDashboardDto? = null,
    val news: List<NewsItemDto> = emptyList(),
    val partialErrors: List<String> = emptyList(),
)

/**
 * UIX7 Home composition.
 *
 * Home deliberately aggregates only already-authoritative read facts: the
 * simulated-account dashboard, its execution log and cached news. It does not
 * synthesize an AI trade signal, confidence score, review plan or broker order.
 */
@Composable
fun HomeScreen() {
    val context = LocalContext.current
    val uriHandler = LocalUriHandler.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var snapshot by remember { mutableStateOf(HomeDashboardSnapshot()) }
    var loading by remember { mutableStateOf(true) }

    fun refresh() {
        if (loading && snapshot.paperDashboard != null) return
        scope.launch {
            loading = true
            supervisorScope {
                val dashboardResult = async { runCatching { api.paperTradingDashboard() } }
                val newsResult = async { runCatching { api.cachedNews(limit = 4, offset = 0, scope = "all") } }
                val dashboard = dashboardResult.await()
                val news = newsResult.await()
                snapshot = HomeDashboardSnapshot(
                    paperDashboard = dashboard.getOrNull() ?: snapshot.paperDashboard,
                    news = news.getOrNull() ?: snapshot.news,
                    partialErrors = buildList {
                        if (dashboard.isFailure) add("模拟账套暂时无法同步")
                        if (news.isFailure) add("最新资讯暂时无法同步")
                    },
                )
            }
            loading = false
        }
    }

    LaunchedEffect(Unit) { refresh() }

    HomeDashboardContent(
        snapshot = snapshot,
        loading = loading,
        onRefresh = ::refresh,
        onOpenNews = { item ->
            if (item.source_url.isNotBlank()) uriHandler.openUri(item.source_url)
        },
    )
}

@Composable
internal fun HomeDashboardContent(
    snapshot: HomeDashboardSnapshot,
    loading: Boolean,
    onRefresh: () -> Unit,
    onOpenNews: (NewsItemDto) -> Unit,
) {
    val dashboard = snapshot.paperDashboard
    val executedLogs = dashboard?.logs.orEmpty().filter { it.status == "executed" }.take(3)
    val attentionItems = remember(dashboard) { homeAttentionItems(dashboard) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(bottom = 0.dp),
    ) {
        HomeBrandHeader(loading = loading, onRefresh = onRefresh)

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
        ) {
            if (loading && dashboard == null) {
                item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            }

            item {
                HomeAccountOverview(
                    account = dashboard?.account,
                    snapshots = dashboard?.snapshots.orEmpty(),
                )
            }

            snapshot.partialErrors.forEach { message ->
                item { HomeStatusMessage(message) }
            }

            item {
                HomeSectionHeader(
                    title = "最近策略执行",
                    detail = if (executedLogs.isEmpty()) "暂无模拟成交" else "${executedLogs.size} 条模拟成交",
                )
            }
            if (executedLogs.isEmpty()) {
                item { HomeEmptyRow("暂无已执行的模拟成交记录") }
            } else {
                items(executedLogs, key = { it.id }) { log ->
                    HomeExecutionRow(log)
                }
            }

            item {
                HomeSectionHeader(
                    title = "待处理事项",
                    detail = if (attentionItems.isEmpty()) "当前无阻断" else "${attentionItems.size} 项",
                )
            }
            if (attentionItems.isEmpty()) {
                item { HomeEmptyRow("当前没有需要立即处理的模拟执行事项") }
            } else {
                items(attentionItems, key = { it.title }) { item ->
                    HomeAttentionRow(item)
                }
            }

            item {
                HomeSectionHeader(
                    title = "最新资讯",
                    detail = if (snapshot.news.isEmpty()) "暂无缓存资讯" else "${snapshot.news.size} 条",
                )
            }
            if (snapshot.news.isEmpty()) {
                item { HomeEmptyRow("暂无最新资讯") }
            } else {
                items(snapshot.news.take(4), key = { it.id }) { item ->
                    HomeNewsRow(item = item, onClick = { onOpenNews(item) })
                }
            }

            item {
                Text(
                    text = "首页只聚合现有模拟账套、执行与资讯事实；不会在 Android 本地生成新的 AI 交易建议。",
                    modifier = Modifier.padding(
                        horizontal = AppSpacing.contentHorizontal,
                        vertical = AppSpacing.medium,
                    ),
                    style = CompactTypography.caption,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun HomeBrandHeader(
    loading: Boolean,
    onRefresh: () -> Unit,
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = MaterialTheme.colorScheme.primary,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 56.dp)
                .padding(
                    start = AppSpacing.contentHorizontal,
                    end = AppSpacing.small,
                    top = AppSpacing.small,
                    bottom = AppSpacing.small,
                ),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = Icons.Default.AutoGraph,
                contentDescription = null,
                tint = Color.White,
                modifier = Modifier.size(22.dp),
            )
            Spacer(Modifier.width(AppSpacing.small))
            Column(Modifier.weight(1f)) {
                Text(
                    text = "Third-Hand",
                    style = CompactTypography.sectionTitle,
                    fontWeight = FontWeight.Bold,
                    color = Color.White,
                )
                Text(
                    text = "AI 决策助手",
                    style = CompactTypography.caption,
                    color = Color.White.copy(alpha = 0.78f),
                )
            }
            IconButton(
                onClick = onRefresh,
                enabled = !loading,
                modifier = Modifier.size(AppSpacing.touchTarget),
            ) {
                if (loading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(19.dp),
                        strokeWidth = 2.dp,
                        color = Color.White,
                    )
                } else {
                    Icon(
                        Icons.Default.Refresh,
                        contentDescription = "刷新首页",
                        tint = Color.White,
                    )
                }
            }
        }
    }
}

@Composable
private fun HomeAccountOverview(
    account: PaperTradingAccountDto?,
    snapshots: List<PaperEquitySnapshotDto>,
) {
    val colors = MaterialTheme.marketColors
    val pnl = account?.total_pnl
    val pnlColor = when {
        pnl == null || pnl == 0.0 -> colors.neutral
        pnl > 0 -> colors.rise
        else -> colors.fall
    }

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(
                horizontal = AppSpacing.contentHorizontal,
                vertical = AppSpacing.medium,
            ),
        color = MaterialTheme.colorScheme.surface,
        shape = RoundedCornerShape(10.dp),
        border = androidx.compose.foundation.BorderStroke(
            0.5.dp,
            MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f),
        ),
    ) {
        Column(
            modifier = Modifier.padding(
                horizontal = AppSpacing.medium,
                vertical = AppSpacing.medium,
            ),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("组合总览", style = CompactTypography.sectionTitle)
                    Text(
                        "模拟账套 · 现有执行账户",
                        style = CompactTypography.caption,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                DenseStateTag("模拟账户", MaterialTheme.colorScheme.primary)
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = AppSpacing.medium),
                verticalAlignment = Alignment.Bottom,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(
                        "累计盈亏",
                        style = CompactTypography.caption,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Row(verticalAlignment = Alignment.Bottom) {
                        Text(
                            text = pnl?.let { "%+.2f".format(Locale.US, it) } ?: "--",
                            style = CompactTypography.pageTitle,
                            fontWeight = FontWeight.Bold,
                            color = pnlColor,
                        )
                        Spacer(Modifier.width(AppSpacing.small))
                        Text(
                            text = account?.total_return_percent?.let { "%+.2f%%".format(Locale.US, it) } ?: "--",
                            style = CompactTypography.secondary,
                            color = pnlColor,
                        )
                    }
                }
                HomeEquitySparkline(
                    snapshots = snapshots,
                    fallbackColor = pnlColor,
                    modifier = Modifier
                        .width(112.dp)
                        .height(42.dp),
                )
            }

            DenseRowDivider(
                modifier = Modifier.padding(vertical = AppSpacing.small),
                inset = false,
            )

            Row(Modifier.fillMaxWidth()) {
                HomeMetric(
                    label = "总资产",
                    value = account?.total_equity?.let { "¥${it.homeMoney()}" } ?: "--",
                    modifier = Modifier.weight(1f),
                )
                HomeMetric(
                    label = "现金",
                    value = account?.available_cash?.let { "¥${it.homeMoney()}" } ?: "--",
                    modifier = Modifier.weight(1f),
                )
                HomeMetric(
                    label = "持仓市值",
                    value = account?.market_value?.let { "¥${it.homeMoney()}" } ?: "--",
                    modifier = Modifier.weight(1f),
                    alignEnd = true,
                )
            }
        }
    }
}

@Composable
private fun HomeEquitySparkline(
    snapshots: List<PaperEquitySnapshotDto>,
    fallbackColor: Color,
    modifier: Modifier = Modifier,
) {
    val values = snapshots.takeLast(24).map { it.total_equity }
    val color = if (values.size >= 2) {
        when {
            values.last() > values.first() -> MaterialTheme.marketColors.rise
            values.last() < values.first() -> MaterialTheme.marketColors.fall
            else -> MaterialTheme.marketColors.neutral
        }
    } else {
        fallbackColor
    }

    Canvas(modifier) {
        if (values.size < 2) {
            drawLine(
                color = color.copy(alpha = 0.45f),
                start = Offset(0f, size.height / 2f),
                end = Offset(size.width, size.height / 2f),
                strokeWidth = 1.dp.toPx(),
            )
            return@Canvas
        }
        val min = values.minOrNull() ?: return@Canvas
        val max = values.maxOrNull() ?: return@Canvas
        val span = (max - min).takeIf { it > 0.000001 } ?: 1.0
        val step = size.width / (values.size - 1)
        values.zipWithNext().forEachIndexed { index, (left, right) ->
            val x1 = index * step
            val x2 = (index + 1) * step
            val y1 = size.height - (((left - min) / span).toFloat() * size.height)
            val y2 = size.height - (((right - min) / span).toFloat() * size.height)
            drawLine(
                color = color,
                start = Offset(x1, y1),
                end = Offset(x2, y2),
                strokeWidth = 1.6.dp.toPx(),
                cap = StrokeCap.Round,
            )
        }
    }
}

@Composable
private fun HomeMetric(
    label: String,
    value: String,
    modifier: Modifier,
    alignEnd: Boolean = false,
) {
    Column(
        modifier = modifier,
        horizontalAlignment = if (alignEnd) Alignment.End else Alignment.Start,
    ) {
        Text(
            label,
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            value,
            style = CompactTypography.rowValue,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun HomeSectionHeader(
    title: String,
    detail: String,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(
                start = AppSpacing.contentHorizontal,
                end = AppSpacing.contentHorizontal,
                top = AppSpacing.sectionVertical,
                bottom = AppSpacing.xs,
            ),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(title, style = CompactTypography.sectionTitle, modifier = Modifier.weight(1f))
        Text(
            detail,
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun HomeExecutionRow(log: PaperTradingLogDto) {
    val colors = MaterialTheme.marketColors
    val isBuy = log.side.equals("BUY", ignoreCase = true)
    val actionColor = if (isBuy) colors.rise else colors.fall

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(
                horizontal = AppSpacing.rowHorizontal,
                vertical = AppSpacing.rowVertical,
            ),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        log.name.ifBlank { log.symbol },
                        style = CompactTypography.rowTitle,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Spacer(Modifier.width(AppSpacing.small))
                    DenseStateTag(if (isBuy) "模拟买入" else "模拟卖出", actionColor)
                }
                Text(
                    "${log.symbol} · ${homeTimestamp(log.executed_at)}",
                    style = CompactTypography.caption,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    "¥${log.price.homeMoney()}",
                    style = CompactTypography.rowValue,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    "${log.quantity.homeQuantity()} 股",
                    style = CompactTypography.caption,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
    DenseRowDivider()
}

internal data class HomeAttentionItem(
    val title: String,
    val detail: String,
    val tone: HomeAttentionTone,
)

internal enum class HomeAttentionTone { PRIMARY, WARNING, ERROR }

private fun homeAttentionItems(dashboard: PaperTradingDashboardDto?): List<HomeAttentionItem> {
    if (dashboard == null) return emptyList()
    val items = mutableListOf<HomeAttentionItem>()
    val status = dashboard.status

    if (status.last_status.equals("failed", ignoreCase = true)) {
        items += HomeAttentionItem(
            title = "最近一次模拟执行失败",
            detail = status.last_message.ifBlank { "执行链路返回失败状态，请在策略页查看链路记录" },
            tone = HomeAttentionTone.ERROR,
        )
    }
    if (status.running) {
        items += HomeAttentionItem(
            title = "模拟决策轮换执行中",
            detail = "既有决策与风控链正在处理，本页仅展示执行状态",
            tone = HomeAttentionTone.PRIMARY,
        )
    } else if (!status.enabled) {
        items += HomeAttentionItem(
            title = "模拟账户自动执行已暂停",
            detail = "前往策略页可重新开启现有模拟账套调度",
            tone = HomeAttentionTone.WARNING,
        )
    }

    val lockedPositions = dashboard.account.positions.filter { (it.locked_quantity ?: 0.0) > 0.0 }
    if (lockedPositions.isNotEmpty()) {
        val lockedQuantity = lockedPositions.sumOf { it.locked_quantity ?: 0.0 }
        items += HomeAttentionItem(
            title = "${lockedPositions.size} 个模拟持仓存在 T+1 锁定",
            detail = "合计锁定 ${lockedQuantity.homeQuantity()} 股，卖出仍受现有执行安全规则约束",
            tone = HomeAttentionTone.WARNING,
        )
    }
    return items
}

@Composable
private fun HomeAttentionRow(item: HomeAttentionItem) {
    val color = when (item.tone) {
        HomeAttentionTone.PRIMARY -> MaterialTheme.colorScheme.primary
        HomeAttentionTone.WARNING -> MaterialTheme.marketColors.warning
        HomeAttentionTone.ERROR -> MaterialTheme.colorScheme.error
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = AppSpacing.touchTarget)
            .padding(
                horizontal = AppSpacing.rowHorizontal,
                vertical = AppSpacing.rowVertical,
            ),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(6.dp)
                .padding(end = 0.dp),
        ) {
            Surface(
                modifier = Modifier.fillMaxSize(),
                shape = RoundedCornerShape(50),
                color = color,
            ) {}
        }
        Spacer(Modifier.width(AppSpacing.small))
        Column(Modifier.weight(1f)) {
            Text(item.title, style = CompactTypography.rowTitle, fontWeight = FontWeight.SemiBold)
            Text(
                item.detail,
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
    DenseRowDivider()
}

@Composable
private fun HomeNewsRow(
    item: NewsItemDto,
    onClick: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(enabled = item.source_url.isNotBlank(), onClick = onClick)
            .heightIn(min = AppSpacing.touchTarget)
            .padding(
                horizontal = AppSpacing.rowHorizontal,
                vertical = AppSpacing.rowVertical,
            ),
    ) {
        Text(
            item.title,
            style = CompactTypography.rowTitle,
            fontWeight = FontWeight.SemiBold,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        Row(
            modifier = Modifier.padding(top = AppSpacing.xs),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                item.source_name.ifBlank { "资讯" },
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.primary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            Text(
                homeTimestamp(item.published_at),
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
    DenseRowDivider()
}

@Composable
private fun HomeStatusMessage(message: String) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(
                horizontal = AppSpacing.contentHorizontal,
                vertical = AppSpacing.xs,
            ),
        color = MaterialTheme.colorScheme.errorContainer,
        shape = MaterialTheme.shapes.small,
    ) {
        Text(
            message,
            modifier = Modifier.padding(
                horizontal = AppSpacing.medium,
                vertical = AppSpacing.small,
            ),
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onErrorContainer,
        )
    }
}

@Composable
private fun HomeEmptyRow(message: String) {
    Text(
        message,
        modifier = Modifier
            .fillMaxWidth()
            .padding(
                horizontal = AppSpacing.rowHorizontal,
                vertical = AppSpacing.medium,
            ),
        style = CompactTypography.secondary,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    DenseRowDivider()
}

private fun homeTimestamp(value: String?): String {
    if (value.isNullOrBlank()) return ""
    return runCatching {
        OffsetDateTime.parse(value)
            .withOffsetSameInstant(ZoneOffset.ofHours(8))
            .format(DateTimeFormatter.ofPattern("MM-dd HH:mm"))
    }.getOrElse {
        value.replace('T', ' ').substringBefore('+').substringBefore('Z').take(16)
    }
}

private fun Double.homeMoney(): String = "%,.2f".format(Locale.US, this)
private fun Double.homeQuantity(): String =
    if (this % 1.0 == 0.0) toLong().toString() else "%.2f".format(Locale.US, this)
