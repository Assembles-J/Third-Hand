package com.thirdhand.app.paperruntime

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ThirdHandTheme
import com.thirdhand.app.ThemeMode
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.CompactTypography
import kotlinx.coroutines.launch
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

@Composable
fun PaperRuntimePanel(
    defaultInitialCash: Double,
    onRestarted: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current.applicationContext
    val controller = remember(context) {
        PaperRuntimeController(PaperRuntimeFeature.repository(context))
    }
    val state by controller.state.collectAsState()
    val scope = rememberCoroutineScope()

    LaunchedEffect(controller) {
        controller.load()
    }

    PaperRuntimeContent(
        state = state,
        modifier = modifier,
        onRefresh = { scope.launch { controller.load() } },
        onOpenRestart = { controller.openRestartDialog(defaultInitialCash) },
        onCloseRestart = controller::closeRestartDialog,
        onInitialCashChange = controller::updateInitialCash,
        onConfirmRestart = {
            scope.launch {
                if (controller.restart()) onRestarted()
            }
        },
    )
}

@Composable
internal fun PaperRuntimeContent(
    state: PaperRuntimeUiState,
    onRefresh: () -> Unit,
    onOpenRestart: () -> Unit,
    onCloseRestart: () -> Unit,
    onInitialCashChange: (String) -> Unit,
    onConfirmRestart: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal),
        verticalArrangement = Arrangement.spacedBy(AppSpacing.small),
    ) {
        when {
            state.runtime != null -> RuntimeFactsCard(
                runtime = state.runtime,
                loading = state.loading,
                onRefresh = onRefresh,
            )
            state.loading -> RuntimeLoadingCard()
            else -> RuntimeUnavailableCard(
                message = state.errorMessage ?: "暂无运行状态",
                onRefresh = onRefresh,
            )
        }

        state.successMessage?.let { message ->
            RuntimeMessage(message = message, error = false)
        }
        if (state.runtime != null) {
            state.errorMessage?.let { message ->
                RuntimeMessage(message = message, error = true)
            }
        }

        OutlinedButton(
            onClick = onOpenRestart,
            enabled = !state.restarting,
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = AppSpacing.touchTarget),
        ) {
            Text("归档本轮并重新开始")
        }

        Text(
            "重开不会伪造清仓成交。旧成交、决策和权益记录继续保留为历史；新一轮从空仓与新的初始资金重新计算收益。",
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            "下方执行链路与成交列表包含历史轮次，用于复盘；是否属于当前轮次请以这里显示的轮次编号和开始时间为准。",
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }

    if (state.restartDialogVisible) {
        PaperRestartDialog(
            state = state,
            onDismiss = onCloseRestart,
            onInitialCashChange = onInitialCashChange,
            onConfirm = onConfirmRestart,
        )
    }
}

@Composable
private fun RuntimeFactsCard(
    runtime: PaperRuntimeStateDto,
    loading: Boolean,
    onRefresh: () -> Unit,
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        tonalElevation = 1.dp,
        shape = MaterialTheme.shapes.medium,
    ) {
        Column(
            modifier = Modifier.padding(AppSpacing.medium),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.small),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(
                        runtime.headline,
                        style = CompactTypography.rowTitle,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        "第 ${runtime.epoch.sequence} 轮 · ${runtime.mode_label}",
                        style = CompactTypography.caption,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                RuntimeStatusTag(runtime.runtime_status)
            }

            Text(
                "本轮开始 ${runtime.epoch.started_at.shortTime()} · 初始资金 ¥${runtime.epoch.initial_cash.moneyText()}",
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            HorizontalDivider()

            RuntimeFactRow("最近行情刷新", runtime.last_market_refresh_at.shortTimeOrNever())
            RuntimeFactRow("最近完整复核", runtime.last_cycle_at.shortTimeOrNever())
            RuntimeFactRow("最近执行轮询", runtime.last_execution_poll_at.shortTimeOrNever())
            RuntimeFactRow("最近候选扫描", runtime.last_candidate_scan_at.shortTimeOrNever())
            RuntimeFactRow("最近研究", runtime.last_research_at.shortTimeOrNever())
            RuntimeFactRow("最近决策", runtime.last_decision_at.shortTimeOrNever())
            RuntimeFactRow("待执行 BUY / SELL", "${runtime.pending_execution_count} 个")
            RuntimeFactRow("到期复核", "${runtime.due_review_count} 个")

            val nextReview = runtime.seconds_until_review.secondsText()
            val nextCandidate = if (runtime.candidate_scan_enabled) {
                runtime.seconds_until_candidate_scan.secondsText()
            } else {
                "当前模式不扫描新标的"
            }
            RuntimeFactRow("下次完整复核", nextReview)
            RuntimeFactRow("下次候选扫描", nextCandidate)

            Surface(
                color = MaterialTheme.colorScheme.surfaceVariant,
                shape = MaterialTheme.shapes.small,
            ) {
                Column(
                    modifier = Modifier.padding(AppSpacing.small),
                    verticalArrangement = Arrangement.spacedBy(2.dp),
                ) {
                    Text(
                        "为什么现在没有成交",
                        style = CompactTypography.caption,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        runtime.no_trade_reason,
                        style = CompactTypography.caption,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            TextButton(
                onClick = onRefresh,
                enabled = !loading,
                modifier = Modifier.align(Alignment.End),
            ) {
                if (loading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                    )
                    Spacer(Modifier.size(AppSpacing.small))
                }
                Text(if (loading) "刷新中" else "刷新运行状态")
            }
        }
    }
}

@Composable
private fun RuntimeStatusTag(status: String) {
    val text = when (status) {
        "running" -> "运行中"
        "waiting_execution" -> "等待成交"
        "paused" -> "已暂停"
        "monitoring" -> "监控中"
        else -> status.ifBlank { "未知" }
    }
    Surface(
        color = MaterialTheme.colorScheme.secondaryContainer,
        contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
        shape = MaterialTheme.shapes.small,
    ) {
        Text(
            text,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            style = CompactTypography.caption,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
private fun RuntimeFactRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(AppSpacing.small),
    ) {
        Text(
            label,
            modifier = Modifier.weight(1f),
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            value,
            style = CompactTypography.caption,
            fontWeight = FontWeight.Medium,
        )
    }
}

@Composable
private fun RuntimeLoadingCard() {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        tonalElevation = 1.dp,
        shape = MaterialTheme.shapes.medium,
    ) {
        Row(
            modifier = Modifier.padding(AppSpacing.medium),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            CircularProgressIndicator(
                modifier = Modifier.size(18.dp),
                strokeWidth = 2.dp,
            )
            Spacer(Modifier.size(AppSpacing.small))
            Text("正在读取系统现在在做什么…", style = CompactTypography.secondary)
        }
    }
}

@Composable
private fun RuntimeUnavailableCard(message: String, onRefresh: () -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        tonalElevation = 1.dp,
        shape = MaterialTheme.shapes.medium,
    ) {
        Column(
            modifier = Modifier.padding(AppSpacing.medium),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.small),
        ) {
            Text(message, style = CompactTypography.secondary)
            TextButton(onClick = onRefresh) { Text("重试") }
        }
    }
}

@Composable
private fun RuntimeMessage(message: String, error: Boolean) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = if (error) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.secondaryContainer,
        shape = MaterialTheme.shapes.small,
    ) {
        Text(
            message,
            modifier = Modifier.padding(AppSpacing.small),
            style = CompactTypography.caption,
            color = if (error) MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.onSecondaryContainer,
        )
    }
}

@Composable
private fun PaperRestartDialog(
    state: PaperRuntimeUiState,
    onDismiss: () -> Unit,
    onInitialCashChange: (String) -> Unit,
    onConfirm: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("重新开始模拟账户") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
                Text(
                    "当前轮次会被归档，不会删除历史成交、决策和权益记录。新轮次会清空当前模拟持仓、T+1 锁定和旧的待执行决策。",
                    style = CompactTypography.secondary,
                )
                Text(
                    "系统不会为了归零而生成虚假的卖出成交；新轮次会从空仓进入“空仓找机会”。",
                    style = CompactTypography.caption,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedTextField(
                    value = state.initialCashText,
                    onValueChange = onInitialCashChange,
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    label = { Text("新轮次初始资金（CNY）") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    enabled = !state.restarting,
                )
                state.errorMessage?.let { message ->
                    Text(
                        message,
                        style = CompactTypography.caption,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = onConfirm,
                enabled = state.canRestart,
            ) {
                if (state.restarting) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                    )
                    Spacer(Modifier.size(AppSpacing.small))
                    Text("正在重开")
                } else {
                    Text("归档并重新开始")
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !state.restarting) {
                Text("取消")
            }
        },
    )
}

private val shortFormatter = DateTimeFormatter.ofPattern("MM-dd HH:mm", Locale.CHINA)

private fun String?.shortTimeOrNever(): String = this?.shortTime() ?: "尚未发生"

private fun String.shortTime(): String = runCatching {
    OffsetDateTime.parse(this).format(shortFormatter)
}.getOrElse {
    take(16).replace('T', ' ')
}

private fun Int?.secondsText(): String {
    if (this == null) return "待服务器确定"
    if (this <= 0) return "已到期"
    val minutes = this / 60
    val seconds = this % 60
    return when {
        minutes >= 60 -> "约 ${minutes / 60} 小时 ${minutes % 60} 分"
        minutes > 0 -> "约 $minutes 分 ${seconds} 秒"
        else -> "约 $seconds 秒"
    }
}

private fun Double.moneyText(): String = String.format(Locale.US, "%,.2f", this)

@Preview(showBackground = true, widthDp = 420)
@Composable
private fun PaperRuntimeMonitoringPreview() {
    ThirdHandTheme(ThemeMode.LIGHT) {
        PaperRuntimeContent(
            state = PaperRuntimeUiState(runtime = previewRuntime("monitoring", "空仓找机会")),
            onRefresh = {},
            onOpenRestart = {},
            onCloseRestart = {},
            onInitialCashChange = {},
            onConfirmRestart = {},
        )
    }
}

@Preview(showBackground = true, widthDp = 420)
@Composable
private fun PaperRuntimeWaitingPreview() {
    ThirdHandTheme(ThemeMode.LIGHT) {
        PaperRuntimeContent(
            state = PaperRuntimeUiState(
                runtime = previewRuntime(
                    status = "waiting_execution",
                    headline = "等待已冻结决策的可执行行情",
                    pending = 1,
                ),
            ),
            onRefresh = {},
            onOpenRestart = {},
            onCloseRestart = {},
            onInitialCashChange = {},
            onConfirmRestart = {},
        )
    }
}

private fun previewRuntime(
    status: String,
    headline: String,
    pending: Int = 0,
): PaperRuntimeStateDto = PaperRuntimeStateDto(
    epoch = PaperSimulationEpochDto(
        epoch_id = "paper-epoch-preview",
        sequence = 2,
        status = "active",
        started_at = "2026-09-02T09:30:00+08:00",
        initial_cash = 100_000.0,
    ),
    runtime_status = status,
    headline = headline,
    mode = "DISCOVERY",
    mode_label = if (pending > 0) "持仓优先" else "空仓找机会",
    auto_execution_enabled = true,
    running = false,
    no_trade_reason = if (pending > 0) {
        "当前有 1 个 BUY/SELL 执行义务；只等待新的合格行情，不会重新调用 AI 改写动作。"
    } else {
        "当前没有待执行 BUY/SELL；HOLD / WAIT / BLOCKED 不会形成成交任务。"
    },
    pending_execution_symbols = if (pending > 0) listOf("600000") else emptyList(),
    pending_execution_count = pending,
    last_market_refresh_at = "2026-09-02T11:16:20+08:00",
    last_cycle_at = "2026-09-02T11:15:00+08:00",
    last_candidate_scan_at = "2026-09-02T11:10:00+08:00",
    last_research_at = "2026-09-02T11:10:03+08:00",
    last_decision_at = "2026-09-02T11:10:08+08:00",
    seconds_until_review = 240,
    seconds_until_candidate_scan = 540,
    seconds_until_company_research = 1200,
    candidate_scan_enabled = true,
    generated_at = "2026-09-02T11:16:30+08:00",
)
