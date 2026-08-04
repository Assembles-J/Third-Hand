package com.thirdhand.app.ui.components

import android.content.res.Configuration
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Wallet
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import com.thirdhand.app.ThemeMode
import com.thirdhand.app.ThirdHandTheme
import com.thirdhand.app.ui.theme.AppElevation
import com.thirdhand.app.ui.theme.AppSpacing

@Composable
fun PortfolioCashCard(
    availableCash: String,
    onEdit: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
        elevation = CardDefaults.cardElevation(defaultElevation = AppElevation.card),
    ) {
        Row(
            modifier = Modifier.padding(AppSpacing.large),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(AppSpacing.medium),
        ) {
            Surface(
                color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.1f),
                shape = MaterialTheme.shapes.medium,
            ) {
                Icon(
                    imageVector = Icons.Filled.Wallet,
                    contentDescription = null,
                    modifier = Modifier.padding(AppSpacing.medium),
                    tint = MaterialTheme.colorScheme.onPrimaryContainer,
                )
            }
            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(AppSpacing.xxs)) {
                Text(
                    text = "可用资金",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.75f),
                )
                Text(
                    text = availableCash,
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                )
            }
            TextButton(onClick = onEdit) { Text("录入资金") }
        }
    }
}

@Preview(name = "Light", showBackground = true)
@Composable
private fun PortfolioCashCardLightPreview() {
    ThirdHandTheme(ThemeMode.LIGHT) {
        PortfolioCashCard(
            availableCash = "85,000.00",
            onEdit = {},
            modifier = Modifier.padding(AppSpacing.large),
        )
    }
}

@Preview(name = "Dark", showBackground = true, uiMode = Configuration.UI_MODE_NIGHT_YES)
@Composable
private fun PortfolioCashCardDarkPreview() {
    ThirdHandTheme(ThemeMode.DARK) {
        PortfolioCashCard(
            availableCash = "85,000.00",
            onEdit = {},
            modifier = Modifier.padding(AppSpacing.large),
        )
    }
}
