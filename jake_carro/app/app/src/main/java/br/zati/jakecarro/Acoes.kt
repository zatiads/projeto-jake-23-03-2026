package br.zati.jakecarro

import android.app.SearchManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.net.Uri
import android.provider.MediaStore
import android.view.KeyEvent
import com.spotify.android.appremote.api.ConnectionParams
import com.spotify.android.appremote.api.Connector
import com.spotify.android.appremote.api.SpotifyAppRemote
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONObject
import kotlin.coroutines.resume

/** Executa no Android o que o Jake decidiu. Devolve true se abriu outro app na frente. */
class Acoes(private val ctx: Context) {

    var spotifyClientId = ""
    private var spotify: SpotifyAppRemote? = null

    suspend fun executar(acao: String, p: JSONObject): Boolean = when (acao) {
        "navegar" -> navegar(p.optString("destino"), p.optString("app"))
        "tocar_musica" -> { tocar(p.optString("busca"), p.optString("tipo"), p.optString("uri")); false }
        "midia" -> { midia(p.optString("comando")); false }
        else -> false
    }

    private fun instalado(pacote: String) = try {
        ctx.packageManager.getPackageInfo(pacote, 0); true
    } catch (_: PackageManager.NameNotFoundException) { false }

    private fun abrir(intent: Intent): Boolean = try {
        ctx.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); true
    } catch (_: Exception) { false }

    fun navegar(destino: String, app: String): Boolean {
        if (destino.isBlank()) return false
        val q = Uri.encode(destino)
        if (app == "waze" && instalado("com.waze")) {
            return abrir(Intent(Intent.ACTION_VIEW, Uri.parse("https://waze.com/ul?q=$q&navigate=yes")).setPackage("com.waze"))
        }
        val maps = Intent(Intent.ACTION_VIEW, Uri.parse("google.navigation:q=$q&mode=d"))
        if (instalado("com.google.android.apps.maps")) maps.setPackage("com.google.android.apps.maps")
        return abrir(maps) || abrir(Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0?q=$q")))
    }

    // ── Spotify ──────────────────────────────────────────────────────────────

    /** Conecta no Spotify (App Remote). Na 1ª vez o Spotify pede pra autorizar o Jake. */
    suspend fun conectarSpotify(): SpotifyAppRemote? {
        spotify?.takeIf { it.isConnected }?.let { return it }
        if (spotifyClientId.isBlank() || !instalado("com.spotify.music")) return null
        val params = ConnectionParams.Builder(spotifyClientId)
            .setRedirectUri("jakecarro://callback")
            .showAuthView(true)
            .build()
        return withTimeoutOrNull(8000) {
            suspendCancellableCoroutine { cont ->
                SpotifyAppRemote.connect(ctx, params, object : Connector.ConnectionListener {
                    override fun onConnected(remote: SpotifyAppRemote) {
                        spotify = remote
                        if (cont.isActive) cont.resume(remote)
                    }
                    override fun onFailure(erro: Throwable) {
                        android.util.Log.w("Jake", "Spotify não conectou: $erro")
                        if (cont.isActive) cont.resume(null)
                    }
                })
            }
        }
    }

    suspend fun tocar(busca: String, tipo: String, uri: String) {
        if (uri.isNotBlank()) {
            val remote = conectarSpotify()
            if (remote != null) {
                remote.playerApi.play(uri)
                return
            }
        }
        // Sem App Remote: pede pro Spotify buscar e tocar (mesmo caminho do Google Assistente).
        val foco = when (tipo) {
            "artista" -> MediaStore.Audio.Artists.ENTRY_CONTENT_TYPE
            "album" -> MediaStore.Audio.Albums.ENTRY_CONTENT_TYPE
            "playlist" -> MediaStore.Audio.Playlists.ENTRY_CONTENT_TYPE
            else -> "vnd.android.cursor.item/audio"
        }
        val pedido = Intent(MediaStore.INTENT_ACTION_MEDIA_PLAY_FROM_SEARCH)
            .setPackage("com.spotify.music")
            .putExtra(SearchManager.QUERY, busca)
            .putExtra(MediaStore.EXTRA_MEDIA_FOCUS, foco)
        if (tipo == "artista") pedido.putExtra(MediaStore.EXTRA_MEDIA_ARTIST, busca)
        if (!abrir(pedido) && uri.isNotBlank()) {
            abrir(Intent(Intent.ACTION_VIEW, Uri.parse(uri)).setPackage("com.spotify.music"))
        }
    }

    fun midia(comando: String) {
        val remote = spotify?.takeIf { it.isConnected }
        if (remote != null) {
            when (comando) {
                "pausar" -> remote.playerApi.pause()
                "continuar" -> remote.playerApi.resume()
                "proxima" -> remote.playerApi.skipNext()
                "anterior" -> remote.playerApi.skipPrevious()
            }
            return
        }
        val tecla = when (comando) {
            "pausar" -> KeyEvent.KEYCODE_MEDIA_PAUSE
            "continuar" -> KeyEvent.KEYCODE_MEDIA_PLAY
            "proxima" -> KeyEvent.KEYCODE_MEDIA_NEXT
            "anterior" -> KeyEvent.KEYCODE_MEDIA_PREVIOUS
            else -> return
        }
        val audio = ctx.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        audio.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, tecla))
        audio.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, tecla))
    }

    fun desconectar() {
        spotify?.let { SpotifyAppRemote.disconnect(it) }
        spotify = null
    }
}
