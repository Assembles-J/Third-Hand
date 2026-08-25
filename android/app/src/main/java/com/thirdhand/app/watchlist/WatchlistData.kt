package com.thirdhand.app.watchlist

import android.content.Context
import com.thirdhand.app.EndpointStore
import com.thirdhand.app.HoldingDto
import kotlinx.coroutines.CancellationException
import okhttp3.OkHttpClient
import okhttp3.ResponseBody
import retrofit2.HttpException
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import java.io.IOException
import java.util.Locale
import java.util.concurrent.TimeUnit

data class PersonalUniverseCountsDto(
    val positions: Int = 0,
    val watchlist: Int = 0,
    val combined: Int = 0,
)

data class PersonalUniverseItemDto(
    val symbol: String,
    val name: String,
    val membership: String,
    val market: String? = null,
    val watchlist_priority: String? = null,
    val watchlist_note: String? = null,
    val watchlist_enabled: Boolean? = null,
    val position_quantity: Double? = null,
    val position_market_value: Double? = null,
    val sellable_quantity: Double? = null,
    val locked_quantity: Double? = null,
    val last_price: Double? = null,
    val change_percent: Double? = null,
    val quote_display_state: String = "unavailable",
    val quote_as_of: String? = null,
    val formal_action: String? = null,
    val decision_id: String? = null,
    val decision_updated_at: String? = null,
    val review_mode: String? = null,
    val next_review_at: String? = null,
) {
    val isPosition: Boolean get() = membership.contains("POSITION")
    val isWatchlist: Boolean get() = membership.contains("WATCHLIST")
}

data class PersonalUniverseResponseDto(
    val generated_at: String,
    val items: List<PersonalUniverseItemDto> = emptyList(),
    val counts: PersonalUniverseCountsDto = PersonalUniverseCountsDto(),
    val data_state: String = "ready",
    val warnings: List<String> = emptyList(),
)

data class WatchlistCreateRequestDto(val symbol: String, val name: String = "")

data class WatchlistUpdateRequestDto(
    val name: String? = null,
    val enabled: Boolean? = null,
    val priority: String? = null,
    val note: String? = null,
)

data class WatchlistMetadataDto(
    val symbol: String,
    val name: String,
    val enabled: Boolean = true,
    val priority: String = "NORMAL",
    val note: String = "",
    val created_at: String = "",
    val updated_at: String = "",
)

internal data class LegacyWatchlistItemDto(
    val symbol: String,
    val name: String = "",
    val enabled: Boolean = true,
    val priority: String = "NORMAL",
    val note: String = "",
)

sealed interface WatchlistLoadResult {
    data class Success(val response: PersonalUniverseResponseDto) : WatchlistLoadResult
    data class Failure(val message: String, val recoverable: Boolean = true) : WatchlistLoadResult
}

interface WatchlistRepository {
    suspend fun load(): WatchlistLoadResult
    suspend fun add(symbol: String, name: String): WatchlistLoadResult
    suspend fun update(symbol: String, enabled: Boolean, priority: String, note: String): WatchlistLoadResult
    suspend fun remove(symbol: String): WatchlistLoadResult
}

private interface WatchlistApi {
    @GET("v1/personal-universe")
    suspend fun personalUniverse(): PersonalUniverseResponseDto

    @GET("v1/watchlist")
    suspend fun legacyWatchlist(): List<LegacyWatchlistItemDto>

    @GET("v1/holdings")
    suspend fun holdings(): List<HoldingDto>

    @POST("v1/watchlist")
    suspend fun addWatchlist(@Body request: WatchlistCreateRequestDto): Response<ResponseBody>

    @PUT("v1/watchlist/{symbol}")
    suspend fun updateWatchlist(
        @Path("symbol") symbol: String,
        @Body request: WatchlistUpdateRequestDto,
    ): WatchlistMetadataDto

    @DELETE("v1/watchlist/{symbol}")
    suspend fun deleteWatchlist(@Path("symbol") symbol: String): Response<ResponseBody>
}

class NetworkWatchlistRepository(
    context: Context,
    private val httpClient: OkHttpClient = OkHttpClient.Builder()
        .callTimeout(30, TimeUnit.SECONDS)
        .build(),
) : WatchlistRepository {
    private val appContext = context.applicationContext
    private var configuredBaseUrl = ""
    private var configuredService: WatchlistApi? = null

    override suspend fun load(): WatchlistLoadResult = execute { loadPersonalUniverse(service()) }

    override suspend fun add(symbol: String, name: String): WatchlistLoadResult = execute {
        service().addWatchlist(WatchlistCreateRequestDto(symbol = symbol, name = name)).requireSuccess()
        loadPersonalUniverse(service())
    }

    override suspend fun update(symbol: String, enabled: Boolean, priority: String, note: String): WatchlistLoadResult = execute {
        service().updateWatchlist(
            symbol,
            WatchlistUpdateRequestDto(enabled = enabled, priority = priority, note = note),
        )
        loadPersonalUniverse(service())
    }

    override suspend fun remove(symbol: String): WatchlistLoadResult = execute {
        service().deleteWatchlist(symbol).requireSuccess()
        loadPersonalUniverse(service())
    }

    private suspend fun loadPersonalUniverse(api: WatchlistApi): PersonalUniverseResponseDto = try {
        api.personalUniverse()
    } catch (error: HttpException) {
        if (error.code() != 404) throw error
        legacyPersonalUniverse(api.legacyWatchlist(), api.holdings())
    }

    private suspend fun execute(block: suspend () -> PersonalUniverseResponseDto): WatchlistLoadResult = try {
        WatchlistLoadResult.Success(block())
    } catch (error: CancellationException) {
        throw error
    } catch (error: HttpException) {
        WatchlistLoadResult.Failure("自选读取失败（HTTP ${error.code()}）")
    } catch (error: IOException) {
        WatchlistLoadResult.Failure(error.message ?: "自选网络连接失败")
    } catch (error: Exception) {
        WatchlistLoadResult.Failure(error.message ?: "自选暂不可用")
    }

    private fun Response<*>.requireSuccess() {
        if (!isSuccessful) throw HttpException(this)
    }

    private fun service(): WatchlistApi {
        val baseUrl = EndpointStore.baseUrl(appContext)
        if (configuredService == null || configuredBaseUrl != baseUrl) {
            configuredBaseUrl = baseUrl
            configuredService = Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(httpClient)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(WatchlistApi::class.java)
        }
        return requireNotNull(configuredService)
    }
}

internal fun legacyPersonalUniverse(
    watchlist: List<LegacyWatchlistItemDto>,
    holdings: List<HoldingDto>,
): PersonalUniverseResponseDto {
    val watchBySymbol = watchlist.associateBy { it.symbol.trim().uppercase(Locale.ROOT) }
    val holdingBySymbol = holdings.associateBy { it.symbol.trim().uppercase(Locale.ROOT) }
    val symbols = (watchBySymbol.keys + holdingBySymbol.keys).distinct()
    val items = symbols.map { symbol ->
        val watch = watchBySymbol[symbol]
        val holding = holdingBySymbol[symbol]
        PersonalUniverseItemDto(
            symbol = symbol,
            name = holding?.name?.takeIf { it.isNotBlank() } ?: watch?.name.orEmpty(),
            membership = when {
                watch != null && holding != null -> "POSITION_AND_WATCHLIST"
                holding != null -> "POSITION"
                else -> "WATCHLIST"
            },
            watchlist_priority = watch?.priority,
            watchlist_note = watch?.note,
            watchlist_enabled = watch?.enabled,
            position_quantity = holding?.quantity,
            quote_display_state = "unavailable",
        )
    }
    return PersonalUniverseResponseDto(
        generated_at = "",
        items = items,
        counts = PersonalUniverseCountsDto(
            positions = holdingBySymbol.size,
            watchlist = watchBySymbol.size,
            combined = items.size,
        ),
        data_state = "legacy_fallback",
        warnings = listOf("服务器暂未提供 Personal Universe 聚合接口，已使用兼容数据"),
    )
}
