package com.thirdhand.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import java.util.Locale

/** The only review surface: server-generated close reports and paper performance. */
@Composable
fun ExecutionReviewScreen() {
    val context = androidx.compose.ui.platform.LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var reviews by remember { mutableStateOf<List<DailyReviewDto>>(emptyList()) }
    var message by remember { mutableStateOf<String?>(null) }

    fun refresh() = scope.launch {
        runCatching { api.dailyReviews() }
            .onSuccess { reviews = it; message = null }
            .onFailure { message = "暂时无法读取收盘复盘，请检查服务连接。" }
    }
    fun evaluate(review: DailyReviewDto) = scope.launch {
        runCatching { api.evaluateDailyReview(review.id) }
            .onSuccess { refresh() }
            .onFailure { message = "尚无下一交易日行情，或本次没有可评估的待执行项。" }
    }

    LaunchedEffect(Unit) { refresh() }
    LazyColumn(
        contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item { Column(Modifier.padding(horizontal = 20.dp, vertical = 20.dp)) {
            Text("执行与收益", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Text("收盘自动生成 · 交易收益与真实成交分开计算", color = MaterialTheme.colorScheme.onSurfaceVariant)
        } }
        item { Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("使用流程", fontWeight = FontWeight.Bold)
                Text("决策台分析自选股和持仓，读取行情、新闻、公告、行业与热点；工作台只给待执行项与建议仓位。你在同花顺或券商手动操作。", style = MaterialTheme.typography.bodySmall)
                Text("每个交易日收盘，服务端自动保存建议快照；次日有行情后，系统按建议价格与数量计算交易浮盈。观察/无建议不会参与计算。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        } }
        message?.let { item { Text(it, Modifier.padding(horizontal = 20.dp), color = MaterialTheme.colorScheme.error) } }
        if (reviews.isEmpty()) item { Text("还没有收盘报告。系统将在持仓或自选标的的交易日收盘后自动生成。", Modifier.padding(horizontal = 20.dp), color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(reviews, key = { it.id }) { review -> DailyExecutionCard(review, onEvaluate = { evaluate(review) }) }
    }
}

@Composable
private fun DailyExecutionCard(review: DailyReviewDto, onEvaluate: () -> Unit) = Card(
    Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
) {
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("${review.review_date} · ${if (review.status == "evaluated") "已评估" else "等待后续行情"}", fontWeight = FontWeight.Bold)
        val executable = review.items.filter { it.action != "watch" && (it.suggested_quantity ?: 0.0) > 0.0 }
        if (executable.isEmpty()) Text("当日没有待执行项，因此不计算交易收益。", style = MaterialTheme.typography.bodySmall)
        executable.forEach { item ->
            Text("${item.name.ifBlank { item.symbol }}：${item.action} · 参考价 ${item.reference_price.reviewMoney()} · 建议 ${item.suggested_quantity?.reviewQuantity()}", style = MaterialTheme.typography.bodySmall)
            item.theoretical_pnl?.let { Text("交易浮盈 ${it.reviewSignedMoney()}（未代表真实收益）", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold) }
        }
        if (review.status == "evaluated") {
            Text("本次交易合计 ${review.theoretical_pnl?.reviewSignedMoney() ?: "—"}", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
        } else if (executable.isNotEmpty()) {
            TextButton(onClick = onEvaluate) { Text("有新行情后计算交易收益") }
        }
    }
}

private fun Double.reviewMoney(): String = "%.2f".format(Locale.US, this)
private fun Double.reviewSignedMoney(): String = "${if (this >= 0) "+" else ""}${reviewMoney()}"
private fun Double.reviewQuantity(): String = if (this % 1.0 == 0.0) "${toLong()} 股" else "${reviewMoney()} 股"
