package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.GppGood
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.marketColors
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale

@Composable
fun PaperExecutionSafetyPanel(
    positions: List<PaperTradingPositionDto>,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    var deferrals by remember { mutableStateOf<List<PaperExecutionDeferralDto>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(positions.map { it.symbol to it.updated_at }) {
        loading = true
        runCatching { api.paperExecutionDeferrals(state = "active", limit = 100) }
            .onSuccess { deferrals = it; error = null }
            .onFailure { error = "无法获取延迟执行状态" }
        loading = false
    }

    Card(
        modifier = modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = MaterialTheme.shapes.large,
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(Modifier.padding(AppSpacing.large), verticalArrangement = Arrangement.spacedBy(AppSpacing.medium)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.GppGood, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(AppSpacing.small))
                Text("执行安全检查", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.ExtraBold)
            }

            if (positions.isEmpty()) {
                Surface(
                    color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f),
                    shape = MaterialTheme.shapes.medium,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        "当前无模拟持仓，交易权限正常。",
                        Modifier.padding(AppSpacing.large),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            } else {
                positions.forEach { position ->
                    SafetyPositionItem(position, deferrals.filter { it.symbol == position.symbol })
                    if (position != positions.last()) {
                        HorizontalDivider(
                            modifier = Modifier.padding(vertical = AppSpacing.small),
                            thickness = 0.5.dp,
                            color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.3f)
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun SafetyPositionItem(position: PaperTradingPositionDto, activeDeferrals: List<PaperExecutionDeferralDto>) {
    val colors = MaterialTheme.marketColors
    val locked = (position.locked_quantity ?: 0.0) > 0.0

    Column(verticalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Column {
                Text(position.name.ifBlank { position.symbol }, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
                Text(position.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (locked) {
                Surface(
                    color = colors.warning.copy(alpha = 0.1f),
                    shape = RoundedCornerShape(4.dp)
                ) {
                    Row(Modifier.padding(horizontal = 6.dp, vertical = 2.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Lock, null, Modifier.size(10.dp), tint = colors.warning)
                        Spacer(Modifier.width(4.dp))
                        Text("T+1 锁定中", style = MaterialTheme.typography.labelSmall, color = colors.warning, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }

        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(AppSpacing.medium)) {
            SafetyFact("可用卖出", position.sellable_quantity?.let { "${it.toInt()} 股" } ?: "--", Modifier.weight(1f))
            SafetyFact("冻结锁定", position.locked_quantity?.let { "${it.toInt()} 股" } ?: "0 股", Modifier.weight(1f))
            SafetyFact("下次复核", position.next_eligible_sell_at?.let { paperSafetyTimestamp(it) } ?: "随时", Modifier.weight(1f))
        }

        activeDeferrals.forEach { deferral ->
            Surface(
                color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f),
                shape = MaterialTheme.shapes.small,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = "已拦截挂单：${paperDeferralAction(deferral.action)} · ${paperDeferralReason(deferral.reason_code)}",
                    modifier = Modifier.padding(horizontal = AppSpacing.medium, vertical = AppSpacing.small),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

@Composable
private fun SafetyFact(label: String, value: String, modifier: Modifier) {
    Column(modifier) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold)
    }
}

private fun paperDeferralAction(value: String): String = when (value.uppercase(Locale.ROOT)) {
    "REDUCE" -> "减仓"
    "EXIT" -> "清仓"
    "SELL" -> "卖出"
    "BUY", "OPEN" -> "买入"
    else -> value
}

private fun paperDeferralReason(value: String): String = when {
    value.contains("paper_t1_unsellable_quantity") -> "T+1 交易限制"
    value.contains("execution_quote") -> "行情不满足触发价"
    value.contains("cooldown") -> "冷却期内"
    else -> "策略暂未授权"
}

private fun paperSafetyTimestamp(value: String): String = runCatching {
    OffsetDateTime.parse(value)
        .withOffsetSameInstant(ZoneOffset.ofHours(8))
        .format(DateTimeFormatter.ofPattern("MM-dd HH:mm"))
}.getOrElse { "待定" }

private fun Double.paperQuantity(): String = if (this % 1.0 == 0.0) toLong().toString() else "%.2f".format(Locale.US, this)
