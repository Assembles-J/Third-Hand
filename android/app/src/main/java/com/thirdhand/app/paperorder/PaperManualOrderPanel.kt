package com.thirdhand.app.paperorder

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
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
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale

@Composable
fun PaperManualOrderPanel(
    onOrderExecuted: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current.applicationContext
    val controller = remember(context) {
        PaperManualOrderController(PaperManualOrderFeature.repository(context))
    }
    val state by controller.state.collectAsState()
    val scope = rememberCoroutineScope()

    PaperManualOrderContent(
        state = state,
        modifier = modifier,
        onSymbolChange = controller::updateSymbol,
        onSideChange = controller::updateSide,
        onQuantityChange = controller::updateQuantity,
        onUseMaximum = controller::useServerMaximum,
        onCheckCapability = {
            scope.launch { controller.loadCapability() }
        },
        onSubmit = {
            scope.launch {
                if (controller.submit()) onOrderExecuted()
            }
        },
    )
}

@Composable
internal fun PaperManualOrderContent(
    state: PaperManualOrderUiState,
    onSymbolChange: (String) -> Unit,
    onSideChange: (PaperManualOrderSide) -> Unit,
    onQuantityChange: (String) -> Unit,
    onUseMaximum: () -> Unit,
    onCheckCapability: () -> Unit,
    onSubmit: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val capability = state.capability
    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal),
        verticalArrangement = Arrangement.spacedBy(AppSpacing.small),
    ) {
        Text(
            "用户手工模拟订单",
            style = CompactTypography.rowTitle,
            color = MaterialTheme.colorScheme.onSurface,
        )
        Text(
            "你决定买卖方向与数量；服务器决定当前是否允许成交，并使用最新合格行情写入同一模拟账本。",
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        OutlinedTextField(
            value = state.symbol,
            onValueChange = onSymbolChange,
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("证券代码") },
            placeholder = { Text("例如 002594") },
        )

        OutlinedButton(
            onClick = onCheckCapability,
            enabled = !state.loadingCapability && !state.submitting,
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = AppSpacing.touchTarget),
        ) {
            if (state.loadingCapability) {
                CircularProgressIndicator(
                    modifier = Modifier.size(18.dp),
                    strokeWidth = 2.dp,
                )
                Spacer(Modifier.size(AppSpacing.small))
                Text("正在检查服务器状态")
            } else {
                Text("检查当前可交易状态")
            }
        }

        capability?.let { item ->
            ManualCapabilityFacts(item)
        }

        state.errorMessage?.let { message ->
            ManualOrderMessage(
                message = message,
                error = true,
            )
        }
        state.successMessage?.let { message ->
            ManualOrderMessage(
                message = message,
                error = false,
            )
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(AppSpacing.small),
        ) {
            SideButton(
                selected = state.side == PaperManualOrderSide.BUY,
                text = "模拟买入",
                onClick = { onSideChange(PaperManualOrderSide.BUY) },
                modifier = Modifier.weight(1f),
            )
            SideButton(
                selected = state.side == PaperManualOrderSide.SELL,
                text = "模拟卖出",
                onClick = { onSideChange(PaperManualOrderSide.SELL) },
                modifier = Modifier.weight(1f),
            )
        }

        OutlinedTextField(
            value = state.quantityText,
            onValueChange = onQuantityChange,
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("数量（股）") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
            supportingText = {
                Text(
                    capability?.lot_size?.let { "服务器每手规则：$it 股" }
                        ?: "数量最终由服务器再次校验",
                )
            },
        )

        if (state.serverMaximum > 0) {
            TextButton(
                onClick = onUseMaximum,
                enabled = !state.submitting,
                contentPadding = PaddingValues(horizontal = 0.dp, vertical = 0.dp),
            ) {
                Text(
                    "使用服务器最大${if (state.side == PaperManualOrderSide.BUY) "可买" else "可卖"}：${state.serverMaximum.quantityText()} 股",
                    style = CompactTypography.caption,
                )
            }
        }

        Button(
            onClick = onSubmit,
            enabled = state.canSubmit,
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = AppSpacing.touchTarget),
        ) {
            if (state.submitting) {
                CircularProgressIndicator(
                    modifier = Modifier.size(18.dp),
                    strokeWidth = 2.dp,
                    color = MaterialTheme.colorScheme.onPrimary,
                )
                Spacer(Modifier.size(AppSpacing.small))
                Text("正在提交模拟订单")
            } else {
                Text(if (state.side == PaperManualOrderSide.BUY) "确认模拟买入" else "确认模拟卖出")
            }
        }

        Text(
            "仅影响模拟账套，不会向真实券商提交订单。客户端不能指定成交价；成交价、交易时段、现金、每手数量与 T+1 可卖数量均由服务器校验。",
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        HorizontalDivider(
            modifier = Modifier.padding(top = AppSpacing.small),
            thickness = 0.5.dp,
            color = MaterialTheme.colorScheme.outlineVariant,
        )
    }
}

@Composable
private fun SideButton(
    selected: Boolean,
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    if (selected) {
        Button(
            onClick = onClick,
            modifier = modifier.heightIn(min = AppSpacing.touchTarget),
        ) {
            Text(text)
        }
    } else {
        OutlinedButton(
            onClick = onClick,
            modifier = modifier.heightIn(min = AppSpacing.touchTarget),
        ) {
            Text(text)
        }
    }
}

@Composable
private fun ManualCapabilityFacts(capability: PaperManualOrderCapabilityDto) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
        shape = MaterialTheme.shapes.small,
    ) {
        Column(
            modifier = Modifier.padding(AppSpacing.medium),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.xs),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "${capability.market ?: "--"} · ${capability.currency ?: "--"}",
                    style = CompactTypography.rowTitle,
                )
                Spacer(Modifier.weight(1f))
                Text(
                    if (capability.executable) "当前可模拟成交" else "当前不可模拟成交",
                    style = CompactTypography.caption,
                    fontWeight = FontWeight.SemiBold,
                    color = if (capability.executable) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.error
                    },
                )
            }
            ManualFactRow(
                "最新成交参考",
                capability.quote_price?.let { "${capability.currency.currencySymbol()}${it.money()}" } ?: "--",
            )
            ManualFactRow("交易时段", if (capability.market_open) "开盘" else "闭市")
            ManualFactRow("行情时间", capability.quote_observed_at?.beijingTime() ?: "--")
            capability.quote_source?.let { ManualFactRow("行情来源", it) }
            ManualFactRow("模拟账套可用现金（CNY）", "¥${capability.available_cash.money()}")
            ManualFactRow(
                "持仓 / 可卖 / 锁定",
                "${capability.held_quantity.quantityText()} / ${capability.sellable_quantity.quantityText()} / ${capability.locked_quantity.quantityText()} 股",
            )
            ManualFactRow(
                "最大可买 / 可卖",
                "${capability.max_buy_quantity.quantityText()} / ${capability.max_sell_quantity.quantityText()} 股",
            )
            ManualFactRow("每手", capability.lot_size?.let { "$it 股" } ?: "未配置")
            capability.next_eligible_sell_at?.let {
                ManualFactRow("下次可卖检查", it.beijingTime())
            }
        }
    }
}

@Composable
private fun ManualFactRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth()) {
        Text(
            label,
            modifier = Modifier.weight(1f),
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            value,
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurface,
            fontWeight = FontWeight.Medium,
        )
    }
}

@Composable
private fun ManualOrderMessage(message: String, error: Boolean) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = if (error) {
            MaterialTheme.colorScheme.errorContainer
        } else {
            MaterialTheme.colorScheme.primaryContainer
        },
        shape = MaterialTheme.shapes.small,
    ) {
        Text(
            message,
            modifier = Modifier.padding(AppSpacing.medium),
            style = CompactTypography.caption,
            color = if (error) {
                MaterialTheme.colorScheme.onErrorContainer
            } else {
                MaterialTheme.colorScheme.onPrimaryContainer
            },
        )
    }
}

private fun Double.money(): String = "%.2f".format(Locale.US, this)

private fun Double.quantityText(): String = if (this % 1.0 == 0.0) {
    toLong().toString()
} else {
    "%.2f".format(Locale.US, this)
}

private fun String?.currencySymbol(): String = when (this?.uppercase()) {
    "HKD" -> "HK\$"
    "USD" -> "\$"
    else -> "¥"
}

private fun String.beijingTime(): String = runCatching {
    OffsetDateTime.parse(this)
        .withOffsetSameInstant(ZoneOffset.ofHours(8))
        .format(DateTimeFormatter.ofPattern("MM-dd HH:mm"))
}.getOrElse { replace('T', ' ').substringBefore('+').substringBefore('Z') }

@Preview(name = "Manual paper order - CN ready", widthDp = 420, showBackground = true)
@Composable
private fun ManualPaperOrderReadyPreview() {
    ThirdHandTheme(ThemeMode.LIGHT) {
        PaperManualOrderContent(
            state = PaperManualOrderUiState(
                symbol = "002594",
                side = PaperManualOrderSide.BUY,
                quantityText = "100",
                capability = PaperManualOrderCapabilityDto(
                    symbol = "002594",
                    market = "CN",
                    currency = "CNY",
                    executable = true,
                    lot_size = 100,
                    market_open = true,
                    quote_price = 87.92,
                    quote_observed_at = "2026-08-31T14:58:00+08:00",
                    quote_source = "Tencent",
                    available_cash = 76321.40,
                    held_quantity = 100.0,
                    sellable_quantity = 100.0,
                    locked_quantity = 0.0,
                    max_buy_quantity = 800.0,
                    max_sell_quantity = 100.0,
                ),
            ),
            onSymbolChange = {},
            onSideChange = {},
            onQuantityChange = {},
            onUseMaximum = {},
            onCheckCapability = {},
            onSubmit = {},
        )
    }
}

@Preview(name = "Manual paper order - HK blocked", widthDp = 420, showBackground = true)
@Composable
private fun ManualPaperOrderHongKongBlockedPreview() {
    val capability = PaperManualOrderCapabilityDto(
        symbol = "9863.HK",
        market = "HK",
        currency = "HKD",
        executable = false,
        reason_codes = listOf("paper_hk_execution_not_configured"),
        lot_size = 100,
        market_open = true,
        quote_price = 36.94,
        quote_observed_at = "2026-08-31T14:58:00+08:00",
        quote_source = "Tencent HK",
        available_cash = 76321.40,
        held_quantity = 200.0,
        sellable_quantity = 200.0,
        locked_quantity = 0.0,
        max_buy_quantity = 0.0,
        max_sell_quantity = 0.0,
    )
    ThirdHandTheme(ThemeMode.LIGHT) {
        PaperManualOrderContent(
            state = PaperManualOrderUiState(
                symbol = "9863.HK",
                side = PaperManualOrderSide.SELL,
                quantityText = "100",
                capability = capability,
                errorMessage = manualOrderReasonText(capability.reason_codes.first(), capability),
            ),
            onSymbolChange = {},
            onSideChange = {},
            onQuantityChange = {},
            onUseMaximum = {},
            onCheckCapability = {},
            onSubmit = {},
        )
    }
}
