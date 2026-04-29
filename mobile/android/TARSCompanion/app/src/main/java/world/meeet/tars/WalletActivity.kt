/*
 * WalletActivity — host for the read-only wallet surface.
 *
 * Reached from PairingActivity once the device is linked; on a fresh
 * install the operator should never see this screen unwrapped.
 *
 * Same DI shape as PairingActivity: BaseURL pulled from
 * `TARSCompanion.DEFAULT_LAN_URL` (debug builds patch this through
 * BuildConfig to point at the emulator/host loopback).
 */

package world.meeet.tars

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import world.meeet.tars.net.WalletClient
import world.meeet.tars.ui.WalletScreen

class WalletActivity : ComponentActivity() {
    private val walletViewModel: WalletViewModel by viewModels {
        viewModelFactory {
            initializer {
                WalletViewModel(
                    client = WalletClient(baseURL = TARSCompanion.DEFAULT_LAN_URL)
                )
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { WalletScreen(viewModel = walletViewModel) }
    }
}
