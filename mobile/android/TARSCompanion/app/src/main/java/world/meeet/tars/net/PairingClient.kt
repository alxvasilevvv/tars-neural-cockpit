/*
 * PairingClient — OkHttp driver for the L5 pairing handshake.
 *
 * Mirrors the iOS PairingClient surface 1:1 so the contract tests
 * can compare both sides against a single source of truth.
 */

package world.meeet.tars.net

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import world.meeet.tars.TARSCompanion
import java.util.concurrent.TimeUnit

data class PairingHostBegin(
    val pairID: String,
    val acceptToken: String,
    val hostID: String,
    val hostFingerprint: String,
    val hostPublicKey: String,
    val expiresAt: Double,
    val traceID: String?,
)

enum class PairingState(val raw: String) {
    PENDING("pending"),
    LINKED("linked"),
    EXPIRED("expired"),
    REJECTED("rejected"),
    UNKNOWN("unknown");

    companion object {
        fun fromRaw(raw: String?): PairingState =
            values().firstOrNull { it.raw == raw } ?: UNKNOWN
    }
}

data class PairingStatus(
    val pairID: String,
    val state: PairingState,
    val deviceID: String?,
    val hostFingerprint: String?,
)

sealed class PairingClientError(message: String) : Exception(message) {
    object InvalidURL : PairingClientError("invalid url")
    class Http(val code: Int, val body: String) : PairingClientError("HTTP $code")
    class Malformed(val reason: String) : PairingClientError("malformed: $reason")
    class Network(val reason: String) : PairingClientError("network: $reason")
}

class PairingClient(
    private val baseURL: String,
    private val client: OkHttpClient = defaultClient(),
) {
    fun begin(clientEphemeralKeyBase64: String): PairingHostBegin {
        val body = JSONObject()
            .put("client_epk", clientEphemeralKeyBase64)
            .put("kind", TARSCompanion.DEVICE_KIND)
            .toString()
        val request = Request.Builder()
            .url(resolve("/api/pairing/begin"))
            .post(body.toRequestBody("application/json".toMediaType()))
            .build()
        val data = perform(request)
        return decodeBegin(data)
    }

    fun pollStatus(pairID: String): PairingStatus {
        val url = resolve("/api/pairing/status").toHttpUrlOrNull()
            ?: throw PairingClientError.InvalidURL
        val request = Request.Builder()
            .url(url.newBuilder().addQueryParameter("pair_id", pairID).build())
            .get()
            .build()
        val data = perform(request)
        return decodeStatus(data)
    }

    private fun perform(request: Request): String {
        try {
            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (!response.isSuccessful) {
                    throw PairingClientError.Http(response.code, body)
                }
                return body
            }
        } catch (t: PairingClientError) {
            throw t
        } catch (t: Throwable) {
            throw PairingClientError.Network(t.message ?: t.toString())
        }
    }

    private fun resolve(path: String): String {
        val base = baseURL.trimEnd('/')
        return base + path
    }

    companion object {
        fun defaultClient(): OkHttpClient =
            OkHttpClient.Builder()
                .connectTimeout(8, TimeUnit.SECONDS)
                .readTimeout(15, TimeUnit.SECONDS)
                .build()

        fun decodeBegin(raw: String): PairingHostBegin {
            val json = parseObject(raw)
            return PairingHostBegin(
                pairID = json.requireString("pair_id"),
                acceptToken = json.requireString("accept_token"),
                hostID = json.requireString("host_id"),
                hostFingerprint = json.requireString("host_fingerprint"),
                hostPublicKey = json.requireString("host_public_key"),
                expiresAt = json.optDouble("expires_at"),
                traceID = json.optStringOrNull("trace_id"),
            )
        }

        fun decodeStatus(raw: String): PairingStatus {
            val json = parseObject(raw)
            return PairingStatus(
                pairID = json.requireString("pair_id"),
                state = PairingState.fromRaw(json.optStringOrNull("state")),
                deviceID = json.optStringOrNull("device_id"),
                hostFingerprint = json.optStringOrNull("host_fingerprint"),
            )
        }

        private fun parseObject(raw: String): JSONObject = try {
            JSONObject(raw)
        } catch (t: Throwable) {
            throw PairingClientError.Malformed("not a JSON object: ${t.message}")
        }

        private fun JSONObject.requireString(key: String): String {
            if (!has(key)) throw PairingClientError.Malformed("missing $key")
            return optString(key, "").ifEmpty {
                throw PairingClientError.Malformed("empty $key")
            }
        }

        private fun JSONObject.optStringOrNull(key: String): String? {
            if (!has(key) || isNull(key)) return null
            val v = optString(key, "")
            return if (v.isEmpty()) null else v
        }
    }
}

private fun String.toHttpUrlOrNull(): okhttp3.HttpUrl? = okhttp3.HttpUrl.parse(this)
