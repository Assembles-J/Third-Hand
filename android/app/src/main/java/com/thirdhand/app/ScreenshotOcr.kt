package com.thirdhand.app

import android.content.Context
import android.net.Uri
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions
import kotlinx.coroutines.tasks.await
import kotlin.math.abs

data class RecognizedHolding(val name: String, val quantity: Double, val averageCost: Double)

/** On-device OCR: screenshots stay on the phone and are never uploaded to Third-Hand. */
object ScreenshotOcr {
    suspend fun scan(context: Context, imageUri: Uri): List<RecognizedHolding> {
        val image = InputImage.fromFilePath(context, imageUri)
        val recognizer = TextRecognition.getClient(ChineseTextRecognizerOptions.Builder().build())
        val lines = try { recognizer.process(image).await().textBlocks.flatMap { it.lines } } finally { recognizer.close() }
        val imageWidth = image.width.toFloat()
        return lines.mapNotNull { nameLine ->
            val box = nameLine.boundingBox ?: return@mapNotNull null
            val name = nameLine.text.trim()
            if (box.left.toFloat() > imageWidth * 0.32f || !name.contains(Regex("[\\u4e00-\\u9fff]"))) return@mapNotNull null
            val rowLines = lines.filter { line ->
                val rowBox = line.boundingBox ?: return@filter false
                abs(rowBox.top - box.top) < 32
            }
            val quantity = rowLines.firstNotNullOfOrNull { line ->
                val rowBox = line.boundingBox ?: return@firstNotNullOfOrNull null
                if (rowBox.left.toFloat() in (imageWidth * 0.53f)..(imageWidth * 0.80f)) number(line.text) else null
            }
            val cost = rowLines.firstNotNullOfOrNull { line ->
                val rowBox = line.boundingBox ?: return@firstNotNullOfOrNull null
                if (rowBox.left.toFloat() > imageWidth * 0.80f) number(line.text) else null
            }
            if (quantity != null && quantity > 0 && cost != null && cost >= 0) RecognizedHolding(name, quantity, cost) else null
        }.distinctBy { it.name }
    }

    private fun number(value: String): Double? = value
        .replace("HK$", "", ignoreCase = true)
        .replace(",", "")
        .replace(Regex("[^0-9.]"), "")
        .toDoubleOrNull()
}
