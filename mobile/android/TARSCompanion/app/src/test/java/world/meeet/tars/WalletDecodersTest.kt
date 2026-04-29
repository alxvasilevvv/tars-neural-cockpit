/*
 * Mirrors mobile/ios/.../TARSCompanionTests.swift wallet-decoder
 * fixtures. Pure JVM, no Android framework dependencies.
 */

package world.meeet.tars

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import world.meeet.tars.net.CompanionWallet
import world.meeet.tars.net.WalletClient
import world.meeet.tars.net.WalletClientError

class WalletDecodersTest {
    @Test
    fun list_decoder_two_rows() {
        val raw = """
            {"ok":true,"count":2,"wallets":[
              {"id":"wlt_1","label":"sol-main","chain":"solana",
               "address":"AbCDEF1234567890zZyYxXwWvVuUtT","public_key_hex":"00",
               "derivation_path":"m/tars/v1/solana/0","seed_fingerprint":"abcd",
               "signing_supported":true,"created_at":100.0,"updated_at":100.0,
               "derivation_scheme":"tars-v1"},
              {"id":"wlt_2","label":"evm-main","chain":"evm",
               "address":"0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
               "public_key_hex":"00","derivation_path":"m/44'/60'/0'/0/0",
               "seed_fingerprint":"efgh","signing_supported":true,
               "created_at":200.0,"updated_at":200.0}
            ]}
        """.trimIndent()
        val wallets = WalletClient.decodeList(raw)
        assertEquals(2, wallets.size)
        assertEquals("solana", wallets[0].chain)
        assertEquals("tars-v1", wallets[0].derivationScheme)
        assertNull(wallets[1].derivationScheme)
        assertTrue(wallets[1].signingSupported)
    }

    @Test
    fun list_rejects_missing_array() {
        assertThrows(WalletClientError.Malformed::class.java) {
            WalletClient.decodeList("""{"ok":true,"count":0}""")
        }
    }

    @Test
    fun balance_decoder_happy_path() {
        val raw = """
            {"ok":true,"trace_id":"t","balance":{
                "chain":"solana",
                "address":"AbCDEF","raw":"500000000","decimals":9,
                "symbol":"SOL","display":"0.5","rpc_url":"https://x"
            }}
        """.trimIndent()
        val bal = WalletClient.decodeBalance(raw)
        assertNotNull(bal)
        assertEquals("solana", bal!!.chain)
        assertEquals("0.5", bal.display)
        assertEquals(9, bal.decimals)
    }

    @Test
    fun balance_decoder_returns_null_when_absent() {
        val raw = """{"ok":false,"error":"rpc unreachable"}"""
        assertNull(WalletClient.decodeBalance(raw))
    }

    @Test
    fun signature_decoder_happy() {
        val raw = """{"ok":true,"signature_b64":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="}"""
        val sig = WalletClient.decodeSignature(raw)
        assertEquals(32, sig.length)
    }

    @Test
    fun signature_decoder_rejects_empty() {
        assertThrows(WalletClientError.Malformed::class.java) {
            WalletClient.decodeSignature("""{"ok":true,"signature_b64":""}""")
        }
    }

    @Test
    fun shortened_address_truncates() {
        val w = CompanionWallet(
            id = "x",
            label = "y",
            chain = "evm",
            address = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
            signingSupported = true,
            derivationScheme = null,
            createdAt = 0.0,
        )
        assertEquals("0x7099…79C8", w.shortenedAddress)
    }

    @Test
    fun shortened_address_passthrough_short() {
        val w = CompanionWallet(
            id = "x",
            label = "y",
            chain = "evm",
            address = "0x1234",
            signingSupported = true,
            derivationScheme = null,
            createdAt = 0.0,
        )
        assertEquals("0x1234", w.shortenedAddress)
    }
}
