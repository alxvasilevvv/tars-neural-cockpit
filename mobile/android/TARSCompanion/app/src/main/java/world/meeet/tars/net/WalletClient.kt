/*
 * WalletClient — read-only wallet surface for the Android companion.
 *
 * Mirrors the iOS WalletClient one-for-one so the contract tests
 * stay symmetric. Endpoints used:
 *
 *   GET  /api/wallet                   → list wallets (no secrets).
 *   GET  /api/wallet/{id}              → single wallet record.
 *   GET  /api/wallet/{id}/balance      → live JSON-RPC balance.
 *   POST /api/wallet/{id}/sign         → prove ownership (signs an
 *                                        ephemeral message; private
 *                                        key never leaves the host).
 *
 * Mutating actions (send / delete / mint) stay on the host. The
 * mobile surface is a viewer + audit lens, not a hot wallet.
 */

package world.meeet.tars.net

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.TimeUnit

data class CompanionWallet(
    val id: String,
    val label: String,
    val chain: String,
    val address: String,
    val signingSupported: Boolean,
    val derivationScheme: String?,
    val createdAt: Double,
) {
    /** "AB12…CD34" for confident, glanceable rendering on small screens. */
    val shortenedAddress: String
        get() = if (address.length > 12)
            "${address.take(6)}…${address.takeLast(4)}"
        else address
}

data class CompanionBalance(
    val chain: String,
    val address: String,
    val raw: String,
    val decimals: Int,
    val symbol: String,
    val display: String,
    val rpcURL: String,
)

sealed class WalletClientError(message: String) : Exception(message) {
    object InvalidURL : WalletClientError("invalid url")
    class Http(val code: Int, val body: String) : WalletClientError("HTTP $code")
    class Malformed(val reason: String) : WalletClientError("malformed: $reason")
    class Network(val reason: String) : WalletClientError("network: $reason")
}

class WalletClient(
    private val baseURL: String,
    private val client: OkHttpClient = defaultClient(),
) {
    fun listWallets(): List<CompanionWallet> {
        val data = perform(
            Request.Builder()
                .url(resolve("/api/wallet"))
                .get()
                .build()
        )
        return decodeList(data)
    }

    fun getWallet(id: String): CompanionWallet {
        val data = perform(
            Request.Builder()
                .url(resolve("/api/wallet/${urlEncode(id)}"))
                .get()
                .build()
        )
        return decodeSingle(data)
    }

    fun fetchBalance(walletID: String): CompanionBalance? {
        val data = perform(
            Request.Builder()
                .url(resolve("/api/wallet/${urlEncode(walletID)}/balance"))
                .get()
                .build()
        )
        return decodeBalance(data)
    }

    fun signOwnershipProof(walletID: String, timestampMs: Long = System.currentTimeMillis()): String {
        val iso = isoFormatter.format(Date(timestampMs))
        val proof = "tars-companion://ownership-proof@$iso"
        val body = JSONObject().put("message", proof).toString()
        val data = perform(
            Request.Builder()
                .url(resolve("/api/wallet/${urlEncode(walletID)}/sign"))
                .post(body.toRequestBody("application/json".toMediaType()))
                .build()
        )
        return decodeSignature(data)
    }

    private fun perform(request: Request): String {
        try {
            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (!response.isSuccessful) {
                    throw WalletClientError.Http(response.code, body)
                }
                return body
            }
        } catch (t: WalletClientError) {
            throw t
        } catch (t: Throwable) {
            throw WalletClientError.Network(t.message ?: t.toString())
        }
    }

    private fun resolve(path: String): String =
        baseURL.trimEnd('/') + path

    private fun urlEncode(raw: String): String =
        java.net.URLEncoder.encode(raw, "UTF-8").replace("+", "%20")

    companion object {
        private val isoFormatter = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }

        fun defaultClient(): OkHttpClient =
            OkHttpClient.Builder()
                .connectTimeout(8, TimeUnit.SECONDS)
                .readTimeout(15, TimeUnit.SECONDS)
                .build()

        fun decodeList(raw: String): List<CompanionWallet> {
            val json = parseObject(raw)
            if (!json.has("wallets")) {
                throw WalletClientError.Malformed("missing 'wallets' array")
            }
            val arr = json.optJSONArray("wallets")
                ?: throw WalletClientError.Malformed("'wallets' is not an array")
            val out = mutableListOf<CompanionWallet>()
            for (i in 0 until arr.length()) {
                val row = arr.optJSONObject(i) ?: continue
                decodeWalletRow(row)?.let(out::add)
            }
            return out
        }

        fun decodeSingle(raw: String): CompanionWallet {
            val json = parseObject(raw)
            val obj = json.optJSONObject("wallet")
                ?: throw WalletClientError.Malformed("missing 'wallet' object")
            return decodeWalletRow(obj)
                ?: throw WalletClientError.Malformed("wallet shape unexpected")
        }

        fun decodeBalance(raw: String): CompanionBalance? {
            val json = parseObject(raw)
            // RPC failure path returns ok:false with no balance — surface
            // as null so the UI renders "unavailable" rather than
            // tearing down the whole list.
            if (!json.has("balance") || json.isNull("balance")) {
                return null
            }
            val obj = json.optJSONObject("balance") ?: return null
            return CompanionBalance(
                chain = obj.requireString("chain"),
                address = obj.requireString("address"),
                raw = obj.requireString("raw"),
                decimals = obj.requireInt("decimals"),
                symbol = obj.requireString("symbol"),
                display = obj.requireString("display"),
                rpcURL = obj.requireString("rpc_url"),
            )
        }

        fun decodeSignature(raw: String): String {
            val json = parseObject(raw)
            val sig = json.optString("signature_b64", "")
            if (sig.isEmpty()) {
                throw WalletClientError.Malformed("missing 'signature_b64'")
            }
            return sig
        }

        private fun decodeWalletRow(obj: JSONObject): CompanionWallet? = try {
            CompanionWallet(
                id = obj.requireString("id"),
                label = obj.requireString("label"),
                chain = obj.requireString("chain"),
                address = obj.requireString("address"),
                signingSupported = obj.optBoolean("signing_supported", false),
                derivationScheme = obj.optStringOrNull("derivation_scheme"),
                createdAt = obj.optDouble("created_at", 0.0),
            )
        } catch (_: WalletClientError) {
            null
        }

        private fun parseObject(raw: String): JSONObject = try {
            JSONObject(raw)
        } catch (t: Throwable) {
            throw WalletClientError.Malformed("not a JSON object: ${t.message}")
        }

        private fun JSONObject.requireString(key: String): String {
            if (!has(key)) throw WalletClientError.Malformed("missing $key")
            return optString(key, "").ifEmpty {
                throw WalletClientError.Malformed("empty $key")
            }
        }

        private fun JSONObject.requireInt(key: String): Int {
            if (!has(key)) throw WalletClientError.Malformed("missing $key")
            return optInt(key)
        }

        private fun JSONObject.optStringOrNull(key: String): String? {
            if (!has(key) || isNull(key)) return null
            val v = optString(key, "")
            return if (v.isEmpty()) null else v
        }
    }
}
