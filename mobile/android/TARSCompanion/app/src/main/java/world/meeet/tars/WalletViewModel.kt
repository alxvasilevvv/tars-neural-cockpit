/*
 * WalletViewModel — pure state machine for the read-only wallet
 * surface on Android. Mirrors the iOS WalletViewModel one-for-one.
 *
 * Three operations:
 *   - load()                → list wallets from /api/wallet
 *   - refreshBalance(id)    → live JSON-RPC balance via host
 *   - proveOwnership(id)    → POST /api/wallet/{id}/sign with a
 *                             timestamped proof message
 *
 * The host signs; this side never touches a private key.
 */

package world.meeet.tars

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import world.meeet.tars.net.CompanionBalance
import world.meeet.tars.net.CompanionWallet
import world.meeet.tars.net.WalletClient

data class WalletState(
    val wallets: List<CompanionWallet> = emptyList(),
    val balances: Map<String, CompanionBalance> = emptyMap(),
    val balanceErrors: Map<String, String> = emptyMap(),
    val proofs: Map<String, String> = emptyMap(),
    val busyBalance: Set<String> = emptySet(),
    val busyProof: Set<String> = emptySet(),
    val isLoading: Boolean = false,
    val error: String? = null,
)

class WalletViewModel(
    private val client: WalletClient,
) : ViewModel() {
    private val _state = MutableStateFlow(WalletState())
    val state: StateFlow<WalletState> = _state

    fun load() {
        _state.value = _state.value.copy(isLoading = true, error = null)
        viewModelScope.launch {
            try {
                val items = withContext(Dispatchers.IO) { client.listWallets() }
                // Stable sort so the UI doesn't flicker on re-fetch.
                val sorted = items.sortedWith(
                    compareBy<CompanionWallet> { it.chain }.thenBy { it.createdAt }
                )
                _state.value = _state.value.copy(wallets = sorted, isLoading = false)
            } catch (t: Throwable) {
                _state.value = _state.value.copy(
                    isLoading = false,
                    error = "${t.message ?: t}",
                )
            }
        }
    }

    fun refreshBalance(walletID: String) {
        _state.value = _state.value.copy(
            busyBalance = _state.value.busyBalance + walletID
        )
        viewModelScope.launch {
            try {
                val bal = withContext(Dispatchers.IO) { client.fetchBalance(walletID) }
                val current = _state.value
                val newBalances = if (bal != null) current.balances + (walletID to bal) else current.balances
                val newErrors = if (bal == null)
                    current.balanceErrors + (walletID to "rpc_unavailable")
                else
                    current.balanceErrors - walletID
                _state.value = current.copy(
                    balances = newBalances,
                    balanceErrors = newErrors,
                    busyBalance = current.busyBalance - walletID,
                )
            } catch (t: Throwable) {
                val current = _state.value
                _state.value = current.copy(
                    balanceErrors = current.balanceErrors + (walletID to "${t.message ?: t}"),
                    busyBalance = current.busyBalance - walletID,
                )
            }
        }
    }

    fun proveOwnership(walletID: String) {
        _state.value = _state.value.copy(
            busyProof = _state.value.busyProof + walletID
        )
        viewModelScope.launch {
            try {
                val sig = withContext(Dispatchers.IO) { client.signOwnershipProof(walletID) }
                val current = _state.value
                _state.value = current.copy(
                    proofs = current.proofs + (walletID to sig),
                    busyProof = current.busyProof - walletID,
                )
            } catch (t: Throwable) {
                val current = _state.value
                _state.value = current.copy(
                    error = "${t.message ?: t}",
                    busyProof = current.busyProof - walletID,
                )
            }
        }
    }
}
