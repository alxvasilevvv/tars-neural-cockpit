/*
 * WalletScreen — Compose mirror of the iOS WalletView.
 *
 * Renders the host's wallet list, lets the operator hit "Balance" to
 * pull a live RPC reading, and "Prove" to sign a timestamped
 * ownership-proof message. Every mutating action stays on the host.
 */

package world.meeet.tars.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import world.meeet.tars.WalletViewModel
import world.meeet.tars.net.CompanionWallet

@Composable
fun WalletScreen(viewModel: WalletViewModel) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(Unit) { viewModel.load() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Header(
            count = state.wallets.size,
            isLoading = state.isLoading,
            onRefresh = { viewModel.load() },
        )

        when {
            state.isLoading && state.wallets.isEmpty() ->
                CircularProgressIndicator(modifier = Modifier.padding(24.dp))

            state.wallets.isEmpty() && state.error != null ->
                EmptyState(
                    title = "Couldn't reach the host",
                    description = state.error ?: "",
                )

            state.wallets.isEmpty() ->
                EmptyState(
                    title = "No wallets yet",
                    description = "Mint one from the cockpit to see it here.",
                )

            else -> LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(vertical = 4.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                items(state.wallets, key = { it.id }) { w ->
                    WalletRow(
                        wallet = w,
                        balanceDisplay = state.balances[w.id]?.let { "${it.display} ${it.symbol}" },
                        balanceError = state.balanceErrors[w.id],
                        proof = state.proofs[w.id],
                        balanceBusy = w.id in state.busyBalance,
                        proofBusy = w.id in state.busyProof,
                        onBalance = { viewModel.refreshBalance(w.id) },
                        onProve = { viewModel.proveOwnership(w.id) },
                    )
                }
            }
        }
    }
}

@Composable
private fun Header(count: Int, isLoading: Boolean, onRefresh: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column {
            Text("Wallets", style = MaterialTheme.typography.titleLarge)
            Text(
                "$count on host · self-custodial",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        OutlinedButton(onClick = onRefresh, enabled = !isLoading) {
            Text("Refresh")
        }
    }
}

@Composable
private fun WalletRow(
    wallet: CompanionWallet,
    balanceDisplay: String?,
    balanceError: String?,
    proof: String?,
    balanceBusy: Boolean,
    proofBusy: Boolean,
    onBalance: () -> Unit,
    onProve: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(
                MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f),
                RoundedCornerShape(12.dp),
            )
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top,
        ) {
            Column {
                Text(wallet.label, style = MaterialTheme.typography.bodyLarge)
                Text(
                    wallet.shortenedAddress,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            ChainBadge(chain = wallet.chain)
        }

        when {
            balanceDisplay != null -> Text(
                balanceDisplay,
                style = MaterialTheme.typography.titleMedium,
            )
            balanceError != null -> Text(
                "balance unavailable",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
            )
            else -> { /* no-op */ }
        }

        if (proof != null) {
            Text(
                "signed · ${proof.take(20)}…",
                style = MaterialTheme.typography.bodySmall,
                color = Color(0xFF22c55e),
            )
        }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(
                onClick = onBalance,
                enabled = !balanceBusy,
            ) {
                Text(if (balanceBusy) "…" else "Balance")
            }
            if (wallet.signingSupported) {
                Button(
                    onClick = onProve,
                    enabled = !proofBusy,
                ) {
                    Text(if (proofBusy) "…" else "Prove")
                }
            }
        }
    }
}

@Composable
private fun ChainBadge(chain: String) {
    val color = when (chain.lowercase()) {
        "solana" -> Color(0xFF8B5CF6)
        "evm" -> Color(0xFF3B82F6)
        "ton" -> Color(0xFF06B6D4)
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Box(
        modifier = Modifier
            .background(color.copy(alpha = 0.15f), RoundedCornerShape(999.dp))
            .padding(horizontal = 10.dp, vertical = 3.dp),
    ) {
        Text(
            chain.uppercase(),
            style = MaterialTheme.typography.labelSmall,
            color = color,
        )
    }
}

@Composable
private fun EmptyState(title: String, description: String) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 200.dp)
            .padding(top = 40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Text(
            description,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
