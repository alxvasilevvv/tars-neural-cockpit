// TARSCompanion — root types for the iOS pairing-first slice (Phase L10 L1).
//
// Pure-Swift surface that the (Xcode-generated) iOS app wraps. Network
// + crypto helpers live in PairingClient.swift / PairingCrypto.swift.
// The SwiftUI flow lives in PairingView.swift.

import Foundation

public enum TARSCompanion {
    public static let version = "0.1.0-alpha.2"
    public static let contractVersion = "1.0.0"

    /// Device kind reported to the host on every pairing request.
    public static let deviceKind = "mobile_ios"

    /// Default LAN URL when the host runs `python serve.py` on the same machine.
    public static let defaultLANURL = URL(string: "http://192.168.1.1:8765")!
}
