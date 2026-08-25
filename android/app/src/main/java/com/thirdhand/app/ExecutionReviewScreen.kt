package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Analytics
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.marketColors
import kotlinx.coroutines.launch
import java.util.Locale

@Composable
fun ExecutionReviewScreen() {
    val context = LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var reviews by remember { mutableStateOf<List<DailyReviewDto>>(emptyList()) }
    var refreshing by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }

    fun refresh() = scope.launch {
        refreshing = true
        runCatching { api.dailyReviews() }
            .onSuccess { reviews = it; message = null }
            .onFailure { message = "数据读取失败" }
        refreshing = false
    }

    fun evaluate(review: DailyReviewDto) = scope.launch {
        runCatching { api.evaluateDailyReview(review.id) }
            .onSuccess { refresh() }
            .onFailure { message = "行情尚未更新，暂无法评估" }
    }

    LaunchedEffect(Unit) { refresh() }

    LazyColumn(
        modifier = Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background),
        contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
    ) {
        item {
            TradingPageHeader("收益复盘", "回顾每日建议的预期表现与实际成交") {
                IconButton(onClick = ::refresh, enabled = !refreshing) {
                    if (refreshing) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Default.Refresh, null, tint = MaterialTheme.colorScheme.onPrimary)
                }
            }
        }

        item {
            Surface(
                modifier = Modifier.fillMaxWidth().padding(AppSpacing.xxLarge),
                color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.3f),
                shape = MaterialTheme.shapes.medium
            ) {
                Row(Modifier.padding(AppSpacing.large), verticalAlignment = Alignment.Top) {
                    Icon(Icons.Default.Info, null, tint = MaterialTheme.colorScheme.secondary, modifier = Modifier.size(20.dp))
                    Spacer(Modifier.width(AppSpacing.medium))
                    Text(
                        "系统在每日收盘后自动保存待执行项快照。次日行情更新后，您可手动触发收益计算。这有助于您客观评估决策质量，而非仅看账户盈亏。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSecondaryContainer
                    )
                }
            }
        }

        if (message != null) {
            item {
                Surface(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge),
                    color = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.5f),
                    shape = MaterialTheme.shapes.small
                ) {
                    Text(message!!, Modifier.padding(AppSpacing.medium), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }
            }
        }

        if (reviews.isEmpty() && !refreshing) {
            item {
                Box(Modifier.fillMaxWidth().padding(AppSpacing.xxLarge), contentAlignment = Alignment.Center) {
                    Text("暂无复盘记录，行情收盘后系统将自动生成", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }

        items(reviews, key = { it.id }) { review ->
            DailyExecutionCard(review, onEvaluate = { evaluate(review) })
        }
    }
}

@Composable
private fun DailyExecutionCard(review: DailyReviewDto, onEvaluate: () -> Unit) {
    val isEvaluated = review.status == "evaluated"
    val colors = MaterialTheme.marketColors

    Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.small),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = MaterialTheme.shapes.large,
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(Modifier.padding(AppSpacing.large)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text(
                    review.review_date,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                Surface(
                    color = (if (isEvaluated) colors.rise else colors.neutral).copy(alpha = 0.1f),
                    shape = CircleShape
                ) {
                    Text(
                        if (isEvaluated) "已完成评估" else "待行情更新",
                        Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = if (isEvaluated) colors.rise else colors.neutral
                    )
                }
            }

            Spacer(Modifier.height(AppSpacing.large))

            val executable = review.items.filter { it.action != "watch" }
            if (executable.isEmpty()) {
                Text("当日无交易建议，仅进行持仓观察。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                executable.forEach { item ->
                    ReviewItemRow(item)
                    if (item != executable.last()) {
                        HorizontalDivider(modifier = Modifier.padding(vertical = AppSpacing.medium), thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.3f))
                    }
                }
            }

            if (isEvaluated) {
                Spacer(Modifier.height(AppSpacing.large))
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.5f),
                    shape = MaterialTheme.shapes.medium
                ) {
                    Row(Modifier.padding(AppSpacing.medium), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text("预期合计表现", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
                        Text(
                            review.theoretical_pnl?.reviewSignedMoney() ?: "---",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.ExtraBold,
                            color = if((review.theoretical_pnl ?: 0.0) >= 0) colors.rise else colors.fall
                        )
                    }
                }
            } else if (executable.isNotEmpty()) {
                Spacer(Modifier.height(AppSpacing.large))
                Button(
                    onClick = onEvaluate,
                    modifier = Modifier.fillMaxWidth(),
                    shape = MaterialTheme.shapes.medium
                ) {
                    Icon(Icons.Default.Analytics, null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(AppSpacing.small))
                    Text("计算当日表现")
                }
            }
        }
    }
}

@Composable
private fun ReviewItemRow(item: DailyReviewItemDto) {
    val colors = MaterialTheme.marketColors
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Column {
                Text(item.name.ifBlank { item.symbol }, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
                Text(item.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    item.action.uppercase(Locale.ROOT),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.ExtraBold,
                    color = MaterialTheme.colorScheme.primary
                )
                Text("建议 ¥${item.reference_price.reviewMoney()}", style = MaterialTheme.typography.labelSmall)
            }
        }

        item.theoretical_pnl?.let { pnl ->
            Surface(
                color = (if (pnl >= 0) colors.rise else colors.fall).copy(alpha = 0.05f),
                shape = RoundedCornerShape(4.dp),
                modifier = Modifier.padding(top = 4.dp)
            ) {
                Text(
                    "预期收益: ${pnl.reviewSignedMoney()}",
                    Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = if (pnl >= 0) colors.rise else colors.fall
                )
            }
        }
    }
}

private fun Double.reviewMoney(): String = "%.2f".format(Locale.US, this)
private fun Double.reviewSignedMoney(): String = "${if (this >= 0) "+" else ""}${reviewMoney()}"
