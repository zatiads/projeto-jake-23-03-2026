package br.zati.jakecarro

import android.content.ComponentName
import android.content.Context
import android.graphics.Bitmap
import android.media.MediaMetadata
import android.media.session.MediaController
import android.media.session.MediaSessionManager
import android.media.session.PlaybackState
import android.util.Base64
import java.io.ByteArrayOutputStream

/**
 * O que está tocando (Spotify ou qualquer player) pro mini player do cockpit, e os botões dele.
 * Usa a mesma permissão de "acesso a notificações" do NavLeitor.
 */
class Musica(private val ctx: Context, private val aoMudar: (Map<String, Any>?) -> Unit) {

    private val SPOTIFY = "com.spotify.music"
    private val gerente = ctx.getSystemService(Context.MEDIA_SESSION_SERVICE) as MediaSessionManager
    private val componente = ComponentName(ctx, NavLeitor::class.java)
    private var atual: MediaController? = null
    private var capaChave = ""
    private var capaB64 = ""

    private val callback = object : MediaController.Callback() {
        override fun onMetadataChanged(m: MediaMetadata?) = avisar()
        override fun onPlaybackStateChanged(s: PlaybackState?) = avisar()
        override fun onSessionDestroyed() { escolher(gerente.getActiveSessions(componente)) }
    }

    private val sessoes = MediaSessionManager.OnActiveSessionsChangedListener { escolher(it ?: emptyList()) }

    fun ligar() {
        if (!NavLeitor.permitido(ctx)) {
            Diag.enviar("musica", "sem acesso a notificações: não dá pra ler o player")
            return
        }
        try {
            gerente.addOnActiveSessionsChangedListener(sessoes, componente)
            val lista = gerente.getActiveSessions(componente)
            Diag.enviar("musica", "players abertos: ${lista.size}",
                "apps" to lista.joinToString { "${it.packageName}:${it.playbackState?.state}" })
            escolher(lista)
        } catch (e: SecurityException) {
            Diag.enviar("musica", "recusado ao ler players: ${e.message}")
        }
    }

    fun desligar() {
        runCatching { gerente.removeOnActiveSessionsChangedListener(sessoes) }
        atual?.unregisterCallback(callback)
        atual = null
    }

    /**
     * Ordem: o que está tocando > Spotify > outros players > Bluetooth da central (que fica sempre aberto e
     * vazio; antes ele era escolhido e o mini player mostrava "nada tocando").
     */
    private fun escolher(lista: List<MediaController>) {
        fun nota(c: MediaController) = (if (c.playbackState?.state == PlaybackState.STATE_PLAYING) 100 else 0) +
            (if (c.packageName == SPOTIFY) 10 else 0) + (if (c.packageName.contains("bluetooth")) -50 else 0)
        val novo = lista.maxByOrNull { nota(it) }
        if (novo?.sessionToken == atual?.sessionToken) { avisar(); return }
        atual?.unregisterCallback(callback)
        atual = novo
        novo?.registerCallback(callback)
        avisar()
    }

    private fun avisar() {
        val c = atual
        val m = c?.metadata
        if (c == null || m == null) { aoMudar(null); return }
        val titulo = m.getString(MediaMetadata.METADATA_KEY_TITLE) ?: ""
        val artista = m.getString(MediaMetadata.METADATA_KEY_ARTIST) ?: m.getString(MediaMetadata.METADATA_KEY_ALBUM_ARTIST) ?: ""
        val chave = "$titulo|$artista"
        if (chave != capaChave) {  // só reprocessa a capa quando a música muda
            capaChave = chave
            capaB64 = (m.getBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART) ?: m.getBitmap(MediaMetadata.METADATA_KEY_ART))
                ?.let { dataUri(it) } ?: ""
        }
        aoMudar(mapOf("titulo" to titulo, "artista" to artista, "capa" to capaB64,
            "tocando" to (c.playbackState?.state == PlaybackState.STATE_PLAYING), "app" to c.packageName))
    }

    private fun dataUri(b: Bitmap): String {
        val pequeno = Bitmap.createScaledBitmap(b, 128, 128, true)
        val out = ByteArrayOutputStream()
        pequeno.compress(Bitmap.CompressFormat.JPEG, 80, out)
        return "data:image/jpeg;base64," + Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP)
    }

    /** anterior | alternar | proxima. Devolve false se não tem player de música de verdade aberto. */
    fun comando(cmd: String): Boolean {
        val c = atual?.takeUnless { it.packageName.contains("bluetooth") } ?: return false
        val t = c.transportControls
        when (cmd) {
            "anterior" -> t.skipToPrevious()
            "proxima" -> t.skipToNext()
            "alternar" -> if (atual?.playbackState?.state == PlaybackState.STATE_PLAYING) t.pause() else t.play()
        }
        return true
    }
}
