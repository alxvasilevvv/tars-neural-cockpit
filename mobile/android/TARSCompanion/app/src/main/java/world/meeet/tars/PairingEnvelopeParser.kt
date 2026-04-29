/*
 * PairingEnvelopeParser — JSON / tars-pair:// parser for the host's QR
 * payload, mirroring the iOS PairingEnvelopeParser 1:1.
 */

package world.meeet.tars

import org.json.JSONException
import org.json.JSONObject
import java.net.URI
import java.net.URLDecoder

data class PairingEnvelope(
    val version: String,
    val hostID: String,
    val pairID: String?,
    val lanURL: String?,
    val relayURL: String?,
    val fingerprint: String?,
    val expiresAt: Double?,
)

sealed class PairingEnvelopeError(message: String) : Exception(message) {
    object Empty : PairingEnvelopeError("empty")
    object UnknownFormat : PairingEnvelopeError("unknown format")
    class MissingField(val field: String) : PairingEnvelopeError("missing $field")
    class MalformedJSON(val reason: String) : PairingEnvelopeError("malformed json: $reason")
}

object PairingEnvelopeParser {
    fun parse(raw: String): PairingEnvelope {
        val trimmed = raw.trim()
        if (trimmed.isEmpty()) throw PairingEnvelopeError.Empty
        if (trimmed.startsWith("{")) return parseJSON(trimmed)
        if (trimmed.startsWith("tars-pair://") || trimmed.startsWith("tars1")) {
            return parseURL(trimmed)
        }
        throw PairingEnvelopeError.UnknownFormat
    }

    internal fun parseJSON(trimmed: String): PairingEnvelope {
        val json = try {
            JSONObject(trimmed)
        } catch (e: JSONException) {
            throw PairingEnvelopeError.MalformedJSON(e.message ?: "")
        }
        val version = json.optString("v", "")
        if (version.isEmpty()) throw PairingEnvelopeError.MissingField("v")
        val hostID = json.optString("host_id", "")
        if (hostID.isEmpty()) throw PairingEnvelopeError.MissingField("host_id")
        return PairingEnvelope(
            version = version,
            hostID = hostID,
            pairID = json.optString("pair_id", "").ifEmpty { null },
            lanURL = json.optString("lan_url", "").ifEmpty { null },
            relayURL = json.optString("relay_url", "").ifEmpty { null },
            fingerprint = json.optString("fingerprint", "").ifEmpty { null },
            expiresAt = if (json.has("expires_at") && !json.isNull("expires_at")) {
                json.optDouble("expires_at")
            } else null,
        )
    }

    internal fun parseURL(trimmed: String): PairingEnvelope {
        val uri = try {
            URI(trimmed)
        } catch (e: Throwable) {
            throw PairingEnvelopeError.UnknownFormat
        }
        if (uri.scheme != "tars-pair") throw PairingEnvelopeError.UnknownFormat
        val host = uri.host ?: throw PairingEnvelopeError.MissingField("host_id")
        val pairID = uri.path?.trim('/')?.takeIf { it.isNotEmpty() }
        val query = uri.rawQuery.orEmpty().split('&')
            .mapNotNull {
                val parts = it.split('=', limit = 2)
                if (parts.size == 2) parts[0] to URLDecoder.decode(parts[1], "UTF-8") else null
            }.toMap()
        val port = query["port"] ?: "8765"
        return PairingEnvelope(
            version = query["v"] ?: "1",
            hostID = query["host_id"] ?: host,
            pairID = pairID,
            lanURL = "http://$host:$port",
            relayURL = null,
            fingerprint = query["fp"],
            expiresAt = query["expires_at"]?.toDoubleOrNull(),
        )
    }
}
