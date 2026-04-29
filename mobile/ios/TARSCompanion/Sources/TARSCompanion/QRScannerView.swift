// QRScannerView — minimal AVFoundation-backed QR scanner shimmed into
// SwiftUI via UIViewControllerRepresentable.
//
// Exposes a single callback: `onScan(String)` fires the very first
// time we read a non-empty QR payload, then the controller stops the
// session so we don't double-fire while the operator confirms on the
// host.

#if canImport(SwiftUI) && canImport(UIKit) && canImport(AVFoundation)
import AVFoundation
import SwiftUI
import UIKit

@available(iOS 16.0, *)
public struct QRScannerView: UIViewControllerRepresentable {
    public let onScan: (String) -> Void

    public init(onScan: @escaping (String) -> Void) {
        self.onScan = onScan
    }

    public func makeUIViewController(context: Context) -> QRScannerViewController {
        let vc = QRScannerViewController()
        vc.onScan = onScan
        return vc
    }

    public func updateUIViewController(_ uiViewController: QRScannerViewController, context: Context) {}
}

@available(iOS 16.0, *)
public final class QRScannerViewController: UIViewController, AVCaptureMetadataOutputObjectsDelegate {
    public var onScan: ((String) -> Void)?
    private let session = AVCaptureSession()
    private var preview: AVCaptureVideoPreviewLayer?
    private var didFire = false

    public override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        configureSession()
    }

    public override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        if !session.isRunning {
            DispatchQueue.global(qos: .userInitiated).async { [weak self] in
                self?.session.startRunning()
            }
        }
    }

    public override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        if session.isRunning { session.stopRunning() }
    }

    public override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        preview?.frame = view.layer.bounds
    }

    private func configureSession() {
        guard let device = AVCaptureDevice.default(for: .video) else { return }
        guard let input = try? AVCaptureDeviceInput(device: device) else { return }
        if session.canAddInput(input) { session.addInput(input) }

        let output = AVCaptureMetadataOutput()
        if session.canAddOutput(output) {
            session.addOutput(output)
            output.setMetadataObjectsDelegate(self, queue: .main)
            output.metadataObjectTypes = [.qr]
        }

        let preview = AVCaptureVideoPreviewLayer(session: session)
        preview.videoGravity = .resizeAspectFill
        preview.frame = view.layer.bounds
        view.layer.addSublayer(preview)
        self.preview = preview
    }

    public func metadataOutput(
        _ output: AVCaptureMetadataOutput,
        didOutput metadataObjects: [AVMetadataObject],
        from connection: AVCaptureConnection
    ) {
        guard !didFire else { return }
        for obj in metadataObjects {
            guard let machine = obj as? AVMetadataMachineReadableCodeObject,
                  machine.type == .qr,
                  let payload = machine.stringValue,
                  !payload.isEmpty else { continue }
            didFire = true
            session.stopRunning()
            onScan?(payload)
            return
        }
    }
}
#endif
