// PairingView — minimal SwiftUI shell for the L1 pairing-first slice.
//
// Three states the operator sees:
//   1. idle / failed → "Paste host envelope" textbox + Begin button.
//   2. awaitingHostAccept → big fingerprint, "Confirm on the cockpit".
//   3. linked → "Paired ✓" + fingerprint + device id.
//
// Camera capture is wired separately in QRScannerView; the entry-point
// here accepts both QR-scanned and pasted text uniformly.

#if canImport(SwiftUI)
import SwiftUI

@available(iOS 16.0, macOS 13.0, *)
public struct PairingView: View {
    @StateObject private var viewModel: PairingViewModel
    @State private var rawEnvelope: String = ""

    public init(client: PairingClient, store: PairingSecretStore = InMemorySecretStore()) {
        _viewModel = StateObject(
            wrappedValue: PairingViewModel(client: client, store: store)
        )
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            header
            content
            log
        }
        .padding(20)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("TARS · Pair this device")
                .font(.title2.weight(.medium))
            Text(stateSummary)
                .font(.footnote.monospaced())
                .foregroundStyle(.secondary)
        }
    }

    @ViewBuilder
    private var content: some View {
        switch viewModel.phase {
        case .idle, .failed:
            VStack(alignment: .leading, spacing: 10) {
                Text("Paste host envelope")
                    .font(.subheadline.weight(.medium))
                #if !os(macOS)
                TextEditor(text: $rawEnvelope)
                    .frame(minHeight: 120)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(.tertiary, lineWidth: 1)
                    )
                #else
                TextField("Pasteable JSON envelope", text: $rawEnvelope, axis: .vertical)
                    .lineLimit(4...10)
                    .textFieldStyle(.roundedBorder)
                #endif

                HStack {
                    Button {
                        Task {
                            await viewModel.handleScannedEnvelope(rawEnvelope)
                        }
                    } label: {
                        Label("Begin pairing", systemImage: "arrow.right.circle.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(rawEnvelope.trimmingCharacters(in: .whitespaces).isEmpty)

                    Button(role: .destructive) {
                        viewModel.reset()
                        rawEnvelope = ""
                    } label: {
                        Text("Reset")
                    }
                    .buttonStyle(.bordered)
                }

                if case .failed(let msg) = viewModel.phase {
                    Text(msg)
                        .font(.footnote)
                        .foregroundStyle(.red)
                }
            }

        case .scanning:
            ProgressView("Beginning handshake…")

        case .awaitingHostAccept(let begin):
            VStack(alignment: .leading, spacing: 12) {
                Label("Awaiting host accept", systemImage: "iphone.slash")
                    .font(.headline)
                fingerprintBadge(
                    title: "Host fingerprint",
                    fingerprint: begin.hostFingerprint
                )
                Text("Open Cockpit on the host, paste this token, confirm fingerprint matches above.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                Text(begin.acceptToken)
                    .font(.system(.body, design: .monospaced))
                    .padding(.vertical, 8)
                    .padding(.horizontal, 12)
                    .background(.secondary.opacity(0.12), in: RoundedRectangle(cornerRadius: 8))
                    .textSelection(.enabled)
            }

        case .linked(let status, let fingerprint):
            VStack(alignment: .leading, spacing: 12) {
                Label("Paired ✓", systemImage: "checkmark.seal.fill")
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(.green)
                fingerprintBadge(title: "Verified host", fingerprint: fingerprint)
                if let deviceID = status.deviceID {
                    HStack {
                        Text("device_id")
                            .font(.footnote.monospaced())
                            .foregroundStyle(.secondary)
                        Text(deviceID)
                            .font(.footnote.monospaced())
                    }
                }
            }
        }
    }

    private var log: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Trace")
                .font(.footnote.weight(.medium))
                .foregroundStyle(.secondary)
            ScrollView {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(viewModel.statusLog, id: \.self) { line in
                        Text(line)
                            .font(.footnote.monospaced())
                            .foregroundStyle(.secondary)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxHeight: 140)
        }
    }

    private var stateSummary: String {
        switch viewModel.phase {
        case .idle: return "idle"
        case .scanning: return "begin → host"
        case .awaitingHostAccept: return "awaiting host accept"
        case .linked: return "linked"
        case .failed: return "failed"
        }
    }

    private func fingerprintBadge(title: String, fingerprint: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title.uppercased())
                .font(.caption2.monospaced())
                .foregroundStyle(.secondary)
            Text(PairingCrypto.formatFingerprint(fingerprint))
                .font(.title3.monospaced().weight(.semibold))
                .textSelection(.enabled)
        }
    }
}
#endif
