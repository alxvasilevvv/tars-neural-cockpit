// WalletView — read-only wallet surface for the iOS companion.
//
// Walks the operator through:
//   1. Pull the host's wallet list once on appear.
//   2. Per-wallet "refresh balance" tap that hits the live RPC.
//   3. Per-wallet "prove ownership" tap that signs a timestamped
//      message and displays a truncated signature so the operator
//      can demonstrate private-key control without a send.
//
// Send / delete / mint stays on the host. The companion is a
// viewer + audit lens, not a hot wallet.

#if canImport(SwiftUI)
import SwiftUI

@available(iOS 16.0, macOS 13.0, *)
public struct WalletView: View {
    @StateObject private var viewModel: WalletViewModel

    public init(client: WalletClient) {
        _viewModel = StateObject(wrappedValue: WalletViewModel(client: client))
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            header

            if viewModel.isLoading && viewModel.wallets.isEmpty {
                ProgressView("Loading wallets…")
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.top, 40)
            } else if let err = viewModel.error, viewModel.wallets.isEmpty {
                emptyStateBlock(
                    title: "Couldn't reach the host",
                    icon: "wifi.exclamationmark",
                    description: err
                )
            } else if viewModel.wallets.isEmpty {
                emptyStateBlock(
                    title: "No wallets yet",
                    icon: "wallet.pass",
                    description: "Mint one from the cockpit to see it here."
                )
            } else {
                List {
                    ForEach(viewModel.wallets, id: \.id) { wallet in
                        walletRow(wallet)
                    }
                }
                .listStyle(.plain)
            }
        }
        .padding(20)
        .task { await viewModel.load() }
        .refreshable { await viewModel.load() }
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Wallets")
                    .font(.title2.weight(.medium))
                Text("\(viewModel.wallets.count) on host · self-custodial")
                    .font(.footnote.monospaced())
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button {
                Task { await viewModel.load() }
            } label: {
                Label("Refresh", systemImage: "arrow.clockwise")
            }
            .labelStyle(.iconOnly)
            .disabled(viewModel.isLoading)
        }
    }

    @ViewBuilder
    private func walletRow(_ wallet: CompanionWallet) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(wallet.label)
                        .font(.body.weight(.medium))
                    Text(wallet.shortenedAddress)
                        .font(.footnote.monospaced())
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                }
                Spacer()
                chainBadge(wallet.chain)
            }

            if let balance = viewModel.balances[wallet.id] {
                HStack(spacing: 6) {
                    Text(balance.display)
                        .font(.body.monospacedDigit().weight(.semibold))
                    Text(balance.symbol)
                        .font(.footnote.monospaced())
                        .foregroundStyle(.secondary)
                }
            } else if viewModel.balanceErrors[wallet.id] != nil {
                Text("balance unavailable")
                    .font(.footnote.monospaced())
                    .foregroundStyle(.red)
            }

            if let proof = viewModel.proofs[wallet.id] {
                HStack(spacing: 6) {
                    Image(systemName: "checkmark.seal.fill")
                        .foregroundStyle(.green)
                    Text("signed · \(proof.prefix(20))…")
                        .font(.footnote.monospaced())
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                }
            }

            HStack(spacing: 8) {
                Button {
                    Task { await viewModel.refreshBalance(wallet.id) }
                } label: {
                    Label("Balance", systemImage: "arrow.down.circle")
                }
                .buttonStyle(.bordered)
                .disabled(viewModel.busyBalance.contains(wallet.id))

                if wallet.signingSupported {
                    Button {
                        Task { await viewModel.proveOwnership(wallet.id) }
                    } label: {
                        Label("Prove", systemImage: "signature")
                    }
                    .buttonStyle(.bordered)
                    .tint(.green)
                    .disabled(viewModel.busyProof.contains(wallet.id))
                }
            }
            .font(.footnote)
        }
        .padding(.vertical, 4)
    }

    private func chainBadge(_ chain: String) -> some View {
        Text(chain.uppercased())
            .font(.caption2.weight(.semibold).monospaced())
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(
                Capsule().fill(chainColor(chain).opacity(0.15))
            )
            .foregroundStyle(chainColor(chain))
    }

    private func chainColor(_ chain: String) -> Color {
        switch chain.lowercased() {
        case "solana": return .purple
        case "evm": return .blue
        case "ton": return .cyan
        default: return .secondary
        }
    }

    private func emptyStateBlock(
        title: String,
        icon: String,
        description: String
    ) -> some View {
        VStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 38))
                .foregroundStyle(.secondary)
            Text(title)
                .font(.title3.weight(.medium))
            Text(description)
                .font(.footnote)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 40)
    }
}

@available(iOS 16.0, macOS 13.0, *)
@MainActor
public final class WalletViewModel: ObservableObject {
    @Published public private(set) var wallets: [CompanionWallet] = []
    @Published public private(set) var balances: [String: CompanionBalance] = [:]
    @Published public private(set) var balanceErrors: [String: String] = [:]
    @Published public private(set) var proofs: [String: String] = [:]
    @Published public private(set) var busyBalance: Set<String> = []
    @Published public private(set) var busyProof: Set<String> = []
    @Published public private(set) var isLoading: Bool = false
    @Published public private(set) var error: String? = nil

    private let client: WalletClient

    public init(client: WalletClient) {
        self.client = client
    }

    public func load() async {
        isLoading = true
        error = nil
        defer { isLoading = false }
        do {
            let items = try await client.listWallets()
            // Stable sort so the UI doesn't flicker on re-fetch.
            self.wallets = items.sorted { lhs, rhs in
                if lhs.chain == rhs.chain {
                    return lhs.createdAt < rhs.createdAt
                }
                return lhs.chain < rhs.chain
            }
        } catch {
            self.error = "\(error)"
        }
    }

    public func refreshBalance(_ walletID: String) async {
        busyBalance.insert(walletID)
        defer { busyBalance.remove(walletID) }
        do {
            if let b = try await client.fetchBalance(walletID: walletID) {
                self.balances[walletID] = b
                self.balanceErrors.removeValue(forKey: walletID)
            } else {
                self.balanceErrors[walletID] = "rpc_unavailable"
            }
        } catch {
            self.balanceErrors[walletID] = "\(error)"
        }
    }

    public func proveOwnership(_ walletID: String) async {
        busyProof.insert(walletID)
        defer { busyProof.remove(walletID) }
        do {
            let sig = try await client.signOwnershipProof(walletID: walletID)
            self.proofs[walletID] = sig
        } catch {
            self.error = "\(error)"
        }
    }
}
#endif
