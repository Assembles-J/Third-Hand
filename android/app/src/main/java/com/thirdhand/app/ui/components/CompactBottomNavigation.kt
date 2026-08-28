package com.thirdhand.app.ui.components

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
 * Shared bottom navigation treatment for the current five-entry app shell.
 *
 * This intentionally keeps the existing navigation model and 44dp+ interactive
 * targets. UIX1 only reduces visual chrome: smaller labels/icons, no raised bar
 * and no large Material pill behind the selected destination.
 */
@Composable
fun CompactBottomNavigation(
    selectedTab: Int,
    items: List<CompactNavigationItem>,
    onTabSelected: (Int) -> Unit,
) {
    NavigationBar(
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
