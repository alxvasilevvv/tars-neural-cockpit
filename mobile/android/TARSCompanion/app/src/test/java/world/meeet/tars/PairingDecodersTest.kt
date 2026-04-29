/*
 * Mirrors mobile/ios/.../TARSCompanionTests.swift.
 *
 * JVM-only — no Android framework calls; runs as a plain JUnit suite
 * once `./gradlew test` works on a machine with the Android SDK.
 */

package world.meeet.tars

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import world.meeet.tars.net.PairingClient
import world.meeet.tars.net.PairingState

class PairingDecodersTest {
    @Test
    fun version_metadata_stable() {
        assertEquals("1.0.0", TARSCompanion.CONTRACT_VERSION)
        assertEquals("mobile_android", TARSCompanion.DEVICE_KIND)
    }

    @Test
    fun envelope_json_parse() {
        val raw = """
            {"v":"1","host_id":"a1b2c3d4e5f60718","pair_id":"9988aa77ccd00ff1",
             "expires_at":1745798400,"lan_url":"http://192.168.1.42:8765",
             "fingerprint":"QXr7-8mB9-nJ2L"}
        """.trimIndent()
        val env = PairingEnvelopeParser.parse(raw)
        assertEquals("1", env.version)
        assertEquals("a1b2c3d4e5f60718", env.hostID)
        assertEquals("9988aa77ccd00ff1", env.pairID)
        assertEquals("QXr7-8mB9-nJ2L", env.fingerprint)
        assertEquals("http://192.168.1.42:8765", env.lanURL)
    }

    @Test
    fun envelope_url_parse() {
        val raw = "tars-pair://a1b2c3d4e5f60718/9988aa77ccd00ff1?fp=QXr7-8mB9-nJ2L&port=9000"
        val env = PairingEnvelopeParser.parse(raw)
        assertEquals("a1b2c3d4e5f60718", env.hostID)
        assertEquals("9988aa77ccd00ff1", env.pairID)
        assertEquals("QXr7-8mB9-nJ2L", env.fingerprint)
        assertEquals("http://a1b2c3d4e5f60718:9000", env.lanURL)
    }

    @Test
    fun envelope_rejects_empty_and_unknown() {
        assertThrows(PairingEnvelopeError.Empty::class.java) {
            PairingEnvelopeParser.parse("")
        }
        assertThrows(PairingEnvelopeError::class.java) {
            PairingEnvelopeParser.parse("garbage")
        }
    }

    @Test
    fun begin_response_decoder() {
        val raw = """
            {"ok":true,"trace_id":"trace-9","pair_id":"9988aa77ccd00ff1",
             "accept_token":"tok-123","host_id":"a1b2c3d4e5f60718",
             "host_fingerprint":"QXr7-8mB9-nJ2L",
             "host_public_key":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
             "expires_at":1745798400.0}
        """.trimIndent()
        val begin = PairingClient.decodeBegin(raw)
        assertEquals("9988aa77ccd00ff1", begin.pairID)
        assertEquals("tok-123", begin.acceptToken)
        assertEquals("QXr7-8mB9-nJ2L", begin.hostFingerprint)
        assertEquals(1745798400.0, begin.expiresAt, 0.0)
        assertEquals("trace-9", begin.traceID)
    }

    @Test
    fun begin_response_decoder_missing_fields() {
        assertThrows(Throwable::class.java) {
            PairingClient.decodeBegin("""{"ok":true,"pair_id":"x"}""")
        }
    }

    @Test
    fun status_response_decoder() {
        val raw = """
            {"ok":true,"pair_id":"9988aa77ccd00ff1","state":"linked",
             "device_id":"feedface00112233","host_fingerprint":"QXr7-8mB9-nJ2L"}
        """.trimIndent()
        val status = PairingClient.decodeStatus(raw)
        assertEquals(PairingState.LINKED, status.state)
        assertEquals("feedface00112233", status.deviceID)
    }

    @Test
    fun status_response_decoder_unknown_state() {
        val raw = """{"ok":true,"pair_id":"x","state":"weird"}"""
        val status = PairingClient.decodeStatus(raw)
        assertEquals(PairingState.UNKNOWN, status.state)
    }
}
