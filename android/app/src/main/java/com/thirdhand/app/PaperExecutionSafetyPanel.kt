package com.thirdhand.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale

/**
 * Read-only execution-safety projection.
 *
 * T+1 and deferral facts come from the backend ledger. The UI never calculates
 * sellability from local dates and never upgrades a blocked/deferred action.
 */
@Composable
fun PaperExecutionSafetyPanel(
    positions: List<PaperTradingPositionDto>,
    modifier: Modifier = Modifier,
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    var deferrals by remember { mutableStateOf<List<PaperExecutionDeferralDto>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(positions.map { it.symbol to it.updated_at }) {
        loading = true
        runCatching { api.paperExecutionDeferrals(state = "active", limit = 100) }
            .onSuccess { deferrals = it; error = null }
            .onFailure { error = it.message ?: "无法读取执行延迟状态" }
        loading = false
    }

    Column(
        modifier = modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(7.dp),
    ) {
        Text("执行安全", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
        Text(
            "可卖、T+1 锁定和延迟状态来自模拟账本；这里不自行推算交易权限。",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        if (positions.isEmpty()) {
            Text("当前无持仓，无 T+1 可卖状态。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            positions.forEach { position ->
                val sellable = position.sellable_quantity
                val locked = position.locked_quantity
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(position.name.ifBlank { position.symbol } + " · " + position.symbol, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        SafetyMetric("总持仓", "${position.quantity.paperQuantity()} 股", Modifier.weight(1f))
                        SafetyMetric("可卖", sellable?.let { "${it.paperQuantity()} 股" } ?: "未提供", Modifier.weight(1f))
                        SafetyMetric("T+1 锁定", locked?.let { "${it.paperQuantity()} 股" } ?: "未提供", Modifier.weight(1f))
                    }
                    if ((locked ?: 0.0) > 0.0) {
                        Text(
                            position.next_eligible_sell_at?.let { "下次可卖/复核：${paperSafetyTimestamp(it)}" }
                                ?: "存在 T+1 锁定，但服务未提供下次可卖时间。",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    deferrals.filter { it.symbol == position.symbol }.forEach { deferral ->
                        Text(
                            "等待执行：${paperDeferralAction(deferral.action)} · ${paperDeferralReason(deferral.reason_code)} · 下次复核 ${paperSafetyTimestamp(deferral.next_eligible_at)}",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                }
            }
        }

        when {
            loading -> Text("正在核对活动延迟状态…", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            error != null -> Text("延迟状态暂不可用：$error", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.error)
            deferrals.isNotEmpty() && deferrals.none { d -> positions.any { it.symbol == d.symbol } } -> Text(
                "还有 ${deferrals.size} 条活动延迟不属于当前持仓列表；请查看执行链路确认是否已被新决策取代。",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun SafetyMetric(label: String, value: String, modifier: Modifier) {
    Column(modifier) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
    }
}

private fun paperDeferralAction(value: String): String = when (value.uppercase(Locale.ROOT)) {
    "REDUCE" -> "减仓"
    "EXIT" -> "退出"
    "SELL" -> "卖出"
    else -> value
}

private fun paperDeferralReason(value: String): String = when {
    value.contains("paper_t1_unsellable_quantity") -> "A 股 T+1 锁定"
    value.contains("execution_quote") -> "等待合格成交报价"
    value.contains("cooldown") -> "冷却期未结束"
    else -> value.ifBlank { "等待重新评估" }
}

private fun paperSafetyTimestamp(value: String): String = runCatching {
    OffsetDateTime.parse(value)
        .withOffsetSameInstant(ZoneOffset.ofHours(8))
        .format(DateTimeFormatter.ofPattern("MM-dd HH:mm"))
}.getOrElse { value.replace('T', ' ').substringBefore("+").substringBefore("Z") }

private fun Double.paperQuantity(): String = if (this % 1.0 == 0.0) toLong().toString() else "%.2f".format(Locale.US, this)
