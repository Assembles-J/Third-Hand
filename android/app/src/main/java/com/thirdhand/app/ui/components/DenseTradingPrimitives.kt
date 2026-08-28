package com.thirdhand.app.ui.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.CompactTypography

/** Compact brand header for scan-heavy financial screens. */
@Composable
fun DensePageHeader(
    title: String,
    subtitle: String? = null,
    modifier: Modifier = Modifier,
    action: @Composable (() -> Unit)? = null,
) {
    val colors = MaterialTheme.colorScheme
    val typography = MaterialTheme.typography
    val shapes = MaterialTheme.shapes

    Surface(
        modifier = modifier.fillMaxWidth(),
        color = colors.primary,
        contentColor = colors.onPrimary,
        tonalElevation = 0.dp,
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = if (subtitle.isNullOrBlank()) 52.dp else 58.dp)
                .padding(horizontal = AppSpacing.small),
        ) {
            Column(
                modifier = Modifier
                    .align(Alignment.Center)
                    .padding(horizontal = 48.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(
                    text = title,
                    style = CompactTypography.pageTitle,
                    color = colors.onPrimary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    textAlign = TextAlign.Center,
                )
                if (!subtitle.isNullOrBlank()) {
                    Text(
                        text = subtitle,
                        style = CompactTypography.caption,
                        color = colors.onPrimary.copy(alpha = 0.78f),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.padding(top = AppSpacing.xxs),
                    )
                }
            }

            action?.let {
                Box(
                    modifier = Modifier.align(Alignment.CenterEnd),
                    contentAlignment = Alignment.Center,
                ) {
                    // Some legacy callers explicitly tint their action with
                    // MaterialTheme.primary. Remap that role locally so those
                    // actions remain visible on the brand-red header.
                    MaterialTheme(
                        colorScheme = colors.copy(primary = colors.onPrimary),
                        typography = typography,
                        shapes = shapes,
                    ) {
                        it()
                    }
                }
            }
        }
    }
}

/** Section label that uses spacing and dividers instead of another large card. */
@Composable
fun DenseSectionHeader(
    title: String,
    detail: String? = null,
    modifier: Modifier = Modifier,
    action: @Composable (() -> Unit)? = null,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .heightIn(min = AppSpacing.touchTarget)
            .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.small),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                text = title,
                style = CompactTypography.sectionTitle,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (!detail.isNullOrBlank()) {
                Text(
                    text = detail,
                    style = CompactTypography.caption,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = AppSpacing.xxs),
                )
            }
        }
        action?.let {
            Spacer(Modifier.width(AppSpacing.small))
            it()
        }
    }
}

/**
 * Reusable two-column value row for portfolio/watchlist/trading tables.
 * Values stay right aligned so a vertical list can be scanned like a securities app.
 */
@Composable
fun DenseValueRow(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    supportingText: String? = null,
    valueColor: Color = MaterialTheme.colorScheme.onSurface,
    onClick: (() -> Unit)? = null,
) {
    val rowModifier = modifier
        .fillMaxWidth()
        .heightIn(min = AppSpacing.touchTarget)
        .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier)
        .padding(horizontal = AppSpacing.rowHorizontal, vertical = AppSpacing.rowVertical)

    Row(
        modifier = rowModifier,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                text = label,
                style = CompactTypography.rowTitle,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (!supportingText.isNullOrBlank()) {
                Text(
                    text = supportingText,
                    style = CompactTypography.caption,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = AppSpacing.xxs),
                )
            }
        }
        Spacer(Modifier.width(AppSpacing.medium))
        Text(
            text = value,
            style = CompactTypography.rowValue,
            color = valueColor,
            textAlign = TextAlign.End,
            maxLines = 1,
        )
    }
}

/** Small text-first state tag. Color never carries state without a label. */
@Composable
fun DenseStateTag(
    text: String,
    color: Color,
    modifier: Modifier = Modifier,
    containerColor: Color = color.copy(alpha = 0.10f),
) {
    Surface(
        modifier = modifier,
        color = containerColor,
        shape = RoundedCornerShape(4.dp),
    ) {
        Text(
            text = text,
            style = CompactTypography.caption,
            color = color,
            modifier = Modifier.padding(horizontal = AppSpacing.denseGap, vertical = AppSpacing.xxs),
            maxLines = 1,
        )
    }
}

@Composable
fun DenseRowDivider(modifier: Modifier = Modifier, inset: Boolean = true) {
    HorizontalDivider(
        modifier = modifier.padding(horizontal = if (inset) AppSpacing.dividerInset else 0.dp),
        thickness = 0.5.dp,
        color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.55f),
    )
}
