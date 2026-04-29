/*
 * Single-screen Activity hosting the L1 pairing flow.
 *
 * No DI yet — the host base URL is read from BuildConfig (set by
 * Gradle) so a debug build can point at `http://10.0.2.2:8765`
 * (Android emulator → host loopback) without rebuilding the world.
 */

package world.meeet.tars

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.lifecycle.viewmodel.initializer
import world.meeet.tars.net.PairingClient
import world.meeet.tars.ui.PairingScreen

class PairingActivity : ComponentActivity() {
    private val pairingViewModel: PairingViewModel by viewModels {
        viewModelFactory {
            initializer {
                val baseURL = TARSCompanion.DEFAULT_LAN_URL
                PairingViewModel(client = PairingClient(baseURL = baseURL))
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { PairingScreen(viewModel = pairingViewModel) }
    }
}
