package com.thirdhand.app.lab

import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import com.android.tools.screenshot.PreviewTest
import com.thirdhand.app.ThemeMode
import com.thirdhand.app.ThirdHandTheme

private const val LAB_PREVIEW_WIDTH = 420
private const val LAB_PREVIEW_HEIGHT = 900

@PreviewTest
@Preview(name = "Lab - ready", showBackground = true, widthDp = LAB_PREVIEW_WIDTH, heightDp = LAB_PREVIEW_HEIGHT)
@Composable
fun LabReadyScreenshotTest() {
    LabScreenshotFrame(LabUiState.Ready(labScreenshotDashboard()))
}

@PreviewTest
@Preview(name = "Lab - insufficient", showBackground = true, widthDp = LAB_PREVIEW_WIDTH, heightDp = LAB_PREVIEW_HEIGHT)
@Composable
fun LabInsufficientScreenshotTest() {
    LabScreenshotFrame(
        LabUiState.Ready(
            labScreenshotDashboard(sampleQuality = "INSUFFICIENT", benchmarkAvailable = false),
        ),
    )
}

@PreviewTest
@Preview(name = "Lab - empty", showBackground = true, widthDp = LAB_PREVIEW_WIDTH, heightDp = LAB_PREVIEW_HEIGHT)
@Composable
fun LabEmptyScreenshotTest() {
    LabScreenshotFrame(LabUiState.Empty())
}

@PreviewTest
@Preview(name = "Lab - error", showBackground = true, widthDp = LAB_PREVIEW_WIDTH, heightDp = LAB_PREVIEW_HEIGHT)
@Composable
fun LabErrorScreenshotTest() {
    LabScreenshotFrame(LabUiState.Error("服务暂不可用"))
}

@Composable
private fun LabScreenshotFrame(state: LabUiState) {
    ThirdHandTheme(ThemeMode.LIGHT) {
        LabScreenContent(state = state, onBack = {}, onRefresh = {})
    }
}
