package com.thirdhand.app

import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import com.android.tools.screenshot.PreviewTest

@PreviewTest
@Preview(name = "News dense rows - light", showBackground = true, widthDp = 390)
@Composable
fun NewsDenseRowsScreenshotTest() {
    ThirdHandTheme(ThemeMode.LIGHT) {
        Column {
            NewsRow(
                item = NewsItemDto(
                    id = "announcement",
                    title = "宁德时代发布最新经营公告，核心业务数据保持稳定",
                    explanation = "公告披露最新经营进展，重点信息保持在两行内便于快速扫描。",
                    source_name = "交易所公告",
                    source_url = "",
                    published_at = "2026-08-28T10:32:00+08:00",
                ),
                onClick = {},
            )
            NewsRow(
                item = NewsItemDto(
                    id = "flash",
                    title = "A股主要指数午后波动，新能源板块成交活跃",
                    explanation = "市场快讯保持标题、来源、时间和简短解释的紧凑层级。",
                    source_name = "市场快讯",
                    source_url = "",
                    published_at = "2026-08-28T13:18:00+08:00",
                ),
                onClick = {},
            )
            NewsRow(
                item = NewsItemDto(
                    id = "holding",
                    title = "浙江新能盘中成交放大，关注后续量价变化",
                    explanation = "仅展示现有资讯事实，不在资讯列表中增加新的交易建议。",
                    source_name = "关联资讯",
                    source_url = "",
                    published_at = "2026-08-28T14:05:00+08:00",
                ),
                onClick = {},
            )
        }
    }
}
