package com.thirdhand.app.ui.theme

import android.app.Activity
import android.graphics.Color as AndroidColor
import android.os.Build
import android.view.View
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.platform.LocalView

/** Keep device chrome aligned with the red/white securities shell. */
@Composable
fun ThirdHandSystemBars(dark: Boolean) {
    val view = LocalView.current
    SideEffect {
        val activity = view.context as? Activity ?: return@SideEffect
        val window = activity.window
        window.statusBarColor = if (dark) {
            AndroidColor.rgb(122, 21, 32)
        } else {
            AndroidColor.rgb(245, 45, 58)
        }
        window.navigationBarColor = if (dark) AndroidColor.rgb(17, 19, 21) else AndroidColor.WHITE

        @Suppress("DEPRECATION")
        var flags = window.decorView.systemUiVisibility
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            flags = flags and View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR.inv()
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            flags = if (dark) {
                flags and View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR.inv()
            } else {
                flags or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
            }
        }
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = flags
    }
}
