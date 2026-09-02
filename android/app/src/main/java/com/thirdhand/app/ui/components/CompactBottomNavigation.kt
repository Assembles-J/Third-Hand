package com.thirdhand.app.ui.components

import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
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
 * Shared five-entry securities navigation. The 56dp bar follows the approved
 * phone reference while every NavigationBarItem still owns a full-width 44dp+
 * interaction region. Selection is icon/text-only: no Material pill.
 */
@Composable
fun CompactBottomNavigation(
    selectedTab: Int,
    items: List<CompactNavigationItem>,
    onTabSelected: (Int) -> Unit,
) {
    NavigationBar(
        modifier = Modifier.height(56.dp),
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
                        modifier = Modifier.size(20.dp),
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
