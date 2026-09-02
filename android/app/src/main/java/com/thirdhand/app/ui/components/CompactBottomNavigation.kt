package com.thirdhand.app.ui.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.weight
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.theme.CompactTypography

data class CompactNavigationItem(
    val label: String,
    val icon: ImageVector,
    val targetTab: Int,
)

/**
 * Shared five-entry securities navigation.
 *
 * Existing primary-shell call sites keep the Material3 NavigationBar baseline.
 * Reference-constrained detail screens can opt into the exact 56dp row so the
 * visual result is not inflated by Material3 NavigationBar minimum height.
 */
@Composable
fun CompactBottomNavigation(
    selectedTab: Int,
    items: List<CompactNavigationItem>,
    onTabSelected: (Int) -> Unit,
    modifier: Modifier = Modifier,
    exactReferenceHeight: Boolean = false,
) {
    if (exactReferenceHeight) {
        Surface(
            modifier = modifier
                .fillMaxWidth()
                .height(56.dp),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 0.dp,
        ) {
            Column(Modifier.fillMaxSize()) {
                HorizontalDivider(
                    thickness = 0.5.dp,
                    color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.55f),
                )
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                ) {
                    items.forEach { item ->
                        val selected = selectedTab == item.targetTab
                        val contentColor = if (selected) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        }
                        Column(
                            modifier = Modifier
                                .weight(1f)
                                .fillMaxHeight()
                                .clickable { onTabSelected(item.targetTab) },
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.Center,
                        ) {
                            Icon(
                                imageVector = item.icon,
                                contentDescription = item.label,
                                modifier = Modifier.size(20.dp),
                                tint = contentColor,
                            )
                            Spacer(Modifier.height(1.dp))
                            Text(
                                text = item.label,
                                style = CompactTypography.navLabel,
                                color = contentColor,
                            )
                        }
                    }
                }
            }
        }
        return
    }

    NavigationBar(
        modifier = modifier,
        containerColor = MaterialTheme.colorScheme.surface,
        tonalElevation = 0.dp,
    ) {
        items.forEach { item ->
            NavigationBarItem(
                selected = selectedTab == item.targetTab,
                onClick = { onTabSelected(item.targetTab) },
                icon = {
                    Icon(
                        imageVector = item.icon,
                        contentDescription = item.label,
                        modifier = Modifier.size(21.dp),
                    )
                },
                label = {
                    Text(
                        text = item.label,
                        style = CompactTypography.navLabel,
                    )
                },
                colors = NavigationBarItemDefaults.colors(
                    selectedIconColor = MaterialTheme.colorScheme.primary,
                    selectedTextColor = MaterialTheme.colorScheme.primary,
                    indicatorColor = Color.Transparent,
                    unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
                ),
            )
        }
    }
}
