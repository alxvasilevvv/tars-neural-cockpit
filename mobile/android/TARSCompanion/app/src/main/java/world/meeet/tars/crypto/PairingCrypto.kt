/*
 * PairingCrypto — X25519 ephemeral keypair via java.security (XDH,
 * available on Android 12+) and helpers shared with the iOS slice.
 *
 * Falls back to a SecureRandom-only "raw 32-byte secret" path on
 * pre-12 devices; the host's ECDH check rejects mismatched lengths,
 * so we still fail loud rather than silently producing a wrong key.
 */

package world.meeet.tars.crypto

import android.os.Build
import android.util.Base64
import java.security.KeyPairGenerator
import java.security.PublicKey
import java.security.SecureRandom

object PairingCrypto {
    /** 16-hex device id, matches docs/contracts/L5_PAIRING_DRAFT.md § 2. */
    fun freshDeviceID(): String {
        val bytes = ByteArray(8)
        SecureRandom().nextBytes(bytes)
        return bytes.joinToString("") { "%02x".format(it.toInt() and 0xFF) }
    }

    /** Format the host fingerprint into 4-char groups separated by '-'. */
    fun formatFingerprint(raw: String): String {
        val cleaned = raw.replace("-", "")
        if (cleaned.length < 9) return raw
        return cleaned.chunked(4).joinToString("-")
    }

    /** Pure helper — encode an arbitrary 32-byte raw public key as base64. */
    fun base64(rawPublicKey: ByteArray): String =
        Base64.encodeToString(rawPublicKey, Base64.NO_WRAP)

    /** Generate a fresh X25519 keypair on Android 12+. */
    fun generateEphemeral(): PairingEphemeral {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val kpg = KeyPairGenerator.getInstance("XDH")
            kpg.initialize(255)
            val kp = kpg.generateKeyPair()
            val publicKey = kp.public
            val rawPub = extractRawX25519(publicKey)
                ?: error("Failed to extract raw X25519 public key")
            return PairingEphemeral(
                deviceID = freshDeviceID(),
                privateKeyEncoded = kp.private.encoded,
                publicKeyBase64 = base64(rawPub)
            )
        }
        // Android 8–11 fallback: 32 random bytes used as the public-key
        // wire value. Real X25519 needs Bouncy Castle on these — we
        // raise loudly rather than silently degrade.
        error("X25519 not available on Android < 12; bundle Bouncy Castle.")
    }

    /** Parse the X.509 SubjectPublicKeyInfo wrapper Java emits on XDH keys. */
    private fun extractRawX25519(publicKey: PublicKey): ByteArray? {
        val encoded = publicKey.encoded ?: return null
        // The X.509 wrapper places the raw 32-byte key at the end.
        if (encoded.size < 32) return null
        return encoded.copyOfRange(encoded.size - 32, encoded.size)
    }
}

data class PairingEphemeral(
    val deviceID: String,
    val privateKeyEncoded: ByteArray,
    val publicKeyBase64: String,
) {
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is PairingEphemeral) return false
        return deviceID == other.deviceID &&
            privateKeyEncoded.contentEquals(other.privateKeyEncoded) &&
            publicKeyBase64 == other.publicKeyBase64
    }

    override fun hashCode(): Int {
        var result = deviceID.hashCode()
        result = 31 * result + privateKeyEncoded.contentHashCode()
        result = 31 * result + publicKeyBase64.hashCode()
        return result
    }
}
