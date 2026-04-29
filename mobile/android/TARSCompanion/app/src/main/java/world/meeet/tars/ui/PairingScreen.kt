/*
 * PairingScreen — Compose mirror of the iOS PairingView.
 *
 * Renders idle / scanning / awaitingHostAccept / linked / failed exactly
 * the same way and exposes the same "paste-or-scan" textbox so unit
 * tests on either platform stay symmetric.
 */

package world.meeet.tars.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import world.meeet.tars.PairingPhase
import world.meeet.tars.PairingViewModel
import world.meeet.tars.crypto.PairingCrypto

@Composable
fun PairingScreen(viewModel: PairingViewModel) {
    val phase by viewModel.phase.collectAsState()
    val log by viewModel.statusLog.collectAsState()
    var raw by remember { mutableStateOf("") }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(20.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Header(phaseSummary = phaseSummary(phase))

        when (val p = phase) {
            is PairingPhase.Idle, is PairingPhase.Failed -> {
                Text("Paste host envelope", style = MaterialTheme.typography.titleMedium)
                OutlinedTextField(
                    value = raw,
                    onValueChange = { raw = it },
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 120.dp),
                    keyboardOptions = KeyboardOptions.Default,
                    placeholder = { Text("JSON envelope or tars-pair:// link") },
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = { viewModel.handleScannedEnvelope(raw) },
                        enabled = raw.trim().isNotEmpty(),
                    ) {
                        Text("Begin pairing")
                    }
                    OutlinedButton(onClick = {
                        viewModel.reset()
                        raw = ""
                    }) {
                        Text("Reset")
                    }
                }
                if (p is PairingPhase.Failed) {
                    Text(
                        p.message,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
            is PairingPhase.Scanning -> {
                Row(
                    verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    CircularProgressIndicator(modifier = Modifier.height(20.dp))
                    Text("Beginning handshake…")
                }
            }
            is PairingPhase.AwaitingHostAccept -> {
                FingerprintBlock(
                    title = "Host fingerprint",
                    fingerprint = p.begin.hostFingerprint,
                )
                Text(
                    "Open Cockpit on the host, paste this token, confirm the fingerprint matches.",
                    style = MaterialTheme.typography.bodySmall,
                )
                Text(
                    p.begin.acceptToken,
                    style = MaterialTheme.typography.bodyLarge,
                )
            }
            is PairingPhase.Linked -> {
                Text(
                    "Paired ✓",
                    style = MaterialTheme.typography.titleLarge,
                    color = Color(0xFF22c55e),
                )
                FingerprintBlock(title = "Verified host", fingerprint = p.fingerprint)
                p.status.deviceID?.let { deviceID ->
                    Text("device_id · $deviceID", style = MaterialTheme.typography.bodySmall)
                }
                val ctx = androidx.compose.ui.platform.LocalContext.current
                Button(
                    onClick = {
                        ctx.startActivity(
                            android.content.Intent(ctx, world.meeet.tars.WalletActivity::class.java)
                        )
                    },
                ) {
                    Text("open wallets")
                }
            }
        }

        Spacer(Modifier.height(8.dp))
        Text("Trace", style = MaterialTheme.typography.labelMedium)
        LazyColumn(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 80.dp, max = 200.dp),
            contentPadding = PaddingValues(0.dp),
        ) {
            items(log) { line ->
                Text(
                    line,
                    style = MaterialTheme.typography.bodySmall,
                    textAlign = TextAlign.Start,
                )
            }
        }
    }
}

@Composable
private fun Header(phaseSummary: String) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text("TARS · Pair this device", style = MaterialTheme.typography.headlineSmall)
        Text(phaseSummary, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun FingerprintBlock(title: String, fingerprint: String) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(title.uppercase(), style = MaterialTheme.typography.labelSmall)
        Text(
            PairingCrypto.formatFingerprint(fingerprint),
            style = MaterialTheme.typography.titleMedium,
        )
    }
}

private fun phaseSummary(phase: PairingPhase): String = when (phase) {
    is PairingPhase.Idle -> "idle"
    is PairingPhase.Scanning -> "begin → host"
    is PairingPhase.AwaitingHostAccept -> "awaiting host accept"
    is PairingPhase.Linked -> "linked"
    is PairingPhase.Failed -> "failed"
}
