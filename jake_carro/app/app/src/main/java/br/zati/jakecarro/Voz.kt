package br.zati.jakecarro

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Base64
import kotlinx.coroutines.suspendCancellableCoroutine
import java.io.File
import java.util.Locale
import kotlin.coroutines.resume

/** Fala do Jake: toca o mp3 que veio da VPS; sem ele, usa a voz do próprio Android. */
class Voz(private val ctx: Context) {
    private val audio = ctx.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private var tts: TextToSpeech? = null
    private var ttsPronto = false
    private var player: MediaPlayer? = null

    private val atributos = AudioAttributes.Builder()
        .setUsage(AudioAttributes.USAGE_ASSISTANT)
        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
        .build()

    private var foco: AudioFocusRequest? = null

    init {
        tts = TextToSpeech(ctx) { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts?.language = Locale("pt", "BR")
                tts?.setAudioAttributes(atributos)
                ttsPronto = true
            }
        }
    }

    /** Pede silêncio pro Spotify enquanto o Jake ouve ([exclusivo]) ou fala (abaixa o volume). */
    fun pegarFoco(exclusivo: Boolean) {
        soltarFoco()
        val tipo = if (exclusivo) AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE
        else AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK
        foco = AudioFocusRequest.Builder(tipo).setAudioAttributes(atributos).build().also {
            audio.requestAudioFocus(it)
        }
    }

    fun soltarFoco() {
        foco?.let { audio.abandonAudioFocusRequest(it) }
        foco = null
    }

    suspend fun falar(texto: String, mp3B64: String = "") {
        if (mp3B64.isNotEmpty() && tocarMp3(mp3B64)) return
        falarLocal(texto)
    }

    private suspend fun tocarMp3(b64: String): Boolean {
        val arquivo = File(ctx.cacheDir, "fala.mp3")
        return try {
            arquivo.writeBytes(Base64.decode(b64, Base64.DEFAULT))
            suspendCancellableCoroutine { cont ->
                val mp = MediaPlayer()
                player = mp
                mp.setAudioAttributes(atributos)
                mp.setDataSource(arquivo.absolutePath)
                mp.setOnCompletionListener { it.release(); player = null; if (cont.isActive) cont.resume(true) }
                mp.setOnErrorListener { p, _, _ -> p.release(); player = null; if (cont.isActive) cont.resume(false); true }
                mp.setOnPreparedListener { it.start() }
                mp.prepareAsync()
                cont.invokeOnCancellation { try { mp.release() } catch (_: Exception) {} }
            }
        } catch (e: Exception) {
            false
        }
    }

    suspend fun falarLocal(texto: String) {
        val t = tts ?: return
        if (!ttsPronto || texto.isBlank()) return
        suspendCancellableCoroutine { cont ->
            val id = System.nanoTime().toString()
            t.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {}
                override fun onDone(utteranceId: String?) { if (cont.isActive) cont.resume(Unit) }
                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) { if (cont.isActive) cont.resume(Unit) }
            })
            t.speak(texto, TextToSpeech.QUEUE_FLUSH, null, id)
            cont.invokeOnCancellation { t.stop() }
        }
    }

    fun calar() {
        try { player?.stop(); player?.release() } catch (_: Exception) {}
        player = null
        tts?.stop()
    }

    fun encerrar() {
        calar()
        soltarFoco()
        tts?.shutdown()
    }
}
