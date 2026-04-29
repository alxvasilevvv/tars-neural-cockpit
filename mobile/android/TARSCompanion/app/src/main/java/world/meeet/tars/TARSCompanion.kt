/*
 * Root metadata for the TARS Android companion. Phase L10 L2 ships the
 * pairing-first slice — see `crypto/PairingCrypto.kt`, `net/PairingClient.kt`,
 * and `ui/PairingScreen.kt`.
 */

package world.meeet.tars

object TARSCompanion {
    const val VERSION = "0.1.0-alpha.2"
    const val CONTRACT_VERSION = "1.0.0"
    const val DEVICE_KIND = "mobile_android"
    const val DEFAULT_LAN_URL = "http://192.168.1.1:8765"
}
