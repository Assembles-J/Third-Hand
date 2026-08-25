package com.thirdhand.app

import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import com.android.tools.screenshot.PreviewTest

@PreviewTest
@Preview(name = "Profile - light", showBackground = true, widthDp = 420, heightDp = 900)
@Composable
fun ProfileScreenScreenshotTest() {
    ThirdHandTheme(ThemeMode.LIGHT) {
        ProfileScreen(
            themeMode = ThemeMode.LIGHT,
            onThemeModeChange = {},
        )
    }
}
