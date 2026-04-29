// TARSCompanionRoot — public SwiftUI shell that the (Xcode-generated)
// iOS app target wraps. Exposes a tab-based layout: pairing first,
// wallets second. The host app's `App` struct just imports this and
// returns a `Scene` containing `TARSCompanionRoot()`.
//
// Keeping it inside the Swift package means downstream Xcode
// integrations get a fully-wired entry point without rebuilding the
// view hierarchy themselves.

#if canImport(SwiftUI)
import Foundation
import SwiftUI

@available(iOS 16.0, macOS 13.0, *)
public struct TARSCompanionRoot: View {
    public let baseURL: URL
    public let secretStore: PairingSecretStore

    @State private var selectedTab: Tab = .pairing

    public enum Tab: Hashable {
        case pairing
        case wallets
    }

    public init(
        baseURL: URL = TARSCompanion.defaultLANURL,
        secretStore: PairingSecretStore = InMemorySecretStore()
    ) {
        self.baseURL = baseURL
        self.secretStore = secretStore
    }

    public var body: some View {
        TabView(selection: $selectedTab) {
            PairingView(
                client: PairingClient(baseURL: baseURL),
                store: secretStore
            )
            .tabItem {
                Label("Pair", systemImage: "iphone.gen3.radiowaves.left.and.right")
            }
            .tag(Tab.pairing)

            WalletView(client: WalletClient(baseURL: baseURL))
                .tabItem {
                    Label("Wallets", systemImage: "creditcard")
                }
                .tag(Tab.wallets)
        }
    }
}
#endif
