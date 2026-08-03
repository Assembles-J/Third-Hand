package com.thirdhand.app.researchchat

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import com.mikepenz.markdown.m3.Markdown

/** Full CommonMark renderer with Material 3 styling; streamed updates retain the prior layout. */
@Composable
fun ResearchMarkdown(markdown: String, modifier: Modifier = Modifier) {
    Markdown(content = markdown, modifier = modifier)
}
