# frozen_string_literal: true
#
# Homebrew formula for TARS — drop into a tap repo as Formula/tars.rb.
#
# Tap install:   brew tap meeet/tap
# Then:          brew install tars
#
# Each release of TARS pushes a fresh stable URL + sha256 — bump them in CI.
class Tars < Formula
  desc "Local-first AI agent — your machine, your second brain"
  homepage "https://meeet.world"
  version "9.0.0"
  license "MIT"

  on_macos do
    on_arm do
      url "https://github.com/meeet-world/tars/releases/download/v#{version}/tars-v#{version}-macos-arm64.tar.gz"
      sha256 "0000000000000000000000000000000000000000000000000000000000000000"
    end
    on_intel do
      url "https://github.com/meeet-world/tars/releases/download/v#{version}/tars-v#{version}-macos-x64.tar.gz"
      sha256 "0000000000000000000000000000000000000000000000000000000000000000"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/meeet-world/tars/releases/download/v#{version}/tars-v#{version}-linux-arm64.tar.gz"
      sha256 "0000000000000000000000000000000000000000000000000000000000000000"
    end
    on_intel do
      url "https://github.com/meeet-world/tars/releases/download/v#{version}/tars-v#{version}-linux-x64.tar.gz"
      sha256 "0000000000000000000000000000000000000000000000000000000000000000"
    end
  end

  depends_on "python@3.12"

  def install
    libexec.install Dir["*"]
    (bin/"tars").write <<~SHIM
      #!/usr/bin/env bash
      exec "#{libexec}/bin/tars" "$@"
    SHIM
    chmod 0755, bin/"tars"
  end

  service do
    run [opt_bin/"tars", "daemon"]
    keep_alive true
    log_path var/"log/tars/daemon.log"
    error_log_path var/"log/tars/daemon.err"
  end

  def caveats
    <<~CAVEATS
      TARS runs locally on http://127.0.0.1:8765
      Open the cockpit:    tars cockpit
      Sign in (optional):  https://meeet.world/auth

      Start the daemon at login:
          brew services start tars
    CAVEATS
  end

  test do
    assert_match "tars", shell_output("#{bin}/tars --version")
  end
end
