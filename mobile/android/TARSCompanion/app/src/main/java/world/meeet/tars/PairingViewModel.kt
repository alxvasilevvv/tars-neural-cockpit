/*
 * PairingViewModel — phase machine for the L1 pairing flow on Android.
 *
 * Mirrors `mobile/ios/.../PairingViewModel.swift`: idle → scanning →
 * awaitingHostAccept → linked|failed. Only this class talks to the
 * network; the Compose screen renders `phase` and `statusLog`.
 */

package world.meeet.tars

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import world.meeet.tars.crypto.PairingCrypto
import world.meeet.tars.net.PairingClient
import world.meeet.tars.net.PairingHostBegin
import world.meeet.tars.net.PairingState
import world.meeet.tars.net.PairingStatus
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

sealed interface PairingPhase {
    data object Idle : PairingPhase
    data object Scanning : PairingPhase
    data class AwaitingHostAccept(val begin: PairingHostBegin) : PairingPhase
    data class Linked(val status: PairingStatus, val fingerprint: String) : PairingPhase
    data class Failed(val message: String) : PairingPhase
}

class PairingViewModel(
    private val client: PairingClient,
) : ViewModel() {
    private val _phase = MutableStateFlow<PairingPhase>(PairingPhase.Idle)
    val phase: StateFlow<PairingPhase> = _phase

    private val _statusLog = MutableStateFlow<List<String>>(emptyList())
    val statusLog: StateFlow<List<String>> = _statusLog

    private var pollJob: Job? = null

    fun reset() {
        pollJob?.cancel()
        pollJob = null
        _phase.value = PairingPhase.Idle
        _statusLog.value = emptyList()
    }

    fun handleScannedEnvelope(raw: String) {
        try {
            PairingEnvelopeParser.parse(raw)
        } catch (e: Throwable) {
            log("Bad QR · ${e.message ?: e}")
            _phase.value = PairingPhase.Failed("Bad QR · ${e.message ?: e}")
            return
        }
        beginPairing()
    }

    fun beginPairing() {
        _phase.value = PairingPhase.Scanning
        log("Generating ephemeral key…")
        viewModelScope.launch {
            try {
                val eph = withContext(Dispatchers.Default) {
                    PairingCrypto.generateEphemeral()
                }
                log("POST /api/pairing/begin")
                val begin = withContext(Dispatchers.IO) {
                    client.begin(clientEphemeralKeyBase64 = eph.publicKeyBase64)
                }
                _phase.value = PairingPhase.AwaitingHostAccept(begin)
                log("Host fingerprint · ${PairingCrypto.formatFingerprint(begin.hostFingerprint)}")
                startPolling(begin.pairID, begin.hostFingerprint)
            } catch (t: Throwable) {
                log("Begin failed · ${t.message ?: t}")
                _phase.value = PairingPhase.Failed("begin failed: ${t.message ?: t}")
            }
        }
    }

    private fun startPolling(pairID: String, fingerprint: String) {
        pollJob?.cancel()
        val backoffsMs = longArrayOf(500, 750, 1000, 1500, 2000, 3000)
        pollJob = viewModelScope.launch {
            var attempt = 0
            while (true) {
                val delayMs = backoffsMs[minOf(attempt, backoffsMs.size - 1)]
                delay(delayMs)
                attempt++
                try {
                    val status = withContext(Dispatchers.IO) { client.pollStatus(pairID) }
                    log("status · ${status.state.raw}")
                    when (status.state) {
                        PairingState.LINKED -> {
                            _phase.value = PairingPhase.Linked(status, fingerprint)
                            return@launch
                        }
                        PairingState.EXPIRED, PairingState.REJECTED -> {
                            _phase.value = PairingPhase.Failed(status.state.raw)
                            return@launch
                        }
                        PairingState.PENDING, PairingState.UNKNOWN -> {
                            // keep polling
                        }
                    }
                } catch (t: Throwable) {
                    log("poll error · ${t.message ?: t}")
                }
            }
        }
    }

    private fun log(message: String) {
        val now = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())
        val current = _statusLog.value
        val next = (listOf("$now · $message") + current).take(12)
        _statusLog.value = next
    }
}
