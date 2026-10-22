package br.zati.jakecarro

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import kotlinx.coroutines.delay
import java.io.File

/**
 * Grava um comando e para sozinho quando a pessoa termina de falar.
 * Mede o barulho de fundo nos primeiros 400 ms (ronco do motor, estrada) e só
 * considera fala o que passa bem acima dele.
 */
class Ouvido(private val ctx: Context) {

    var limiarMinimo = 1800        // amplitude (0..32767) mínima pra contar como fala
    var silencioFimMs = 1200L      // quanto silêncio depois da fala encerra a gravação
    var esperaInicioMs = 6000L     // se ninguém falar nesse tempo, desiste
    var maximoMs = 10000L

    private var gravador: MediaRecorder? = null

    /** Grava e devolve o arquivo, ou null se não ouviu fala. [nivel] recebe 0..1 pra animar a tela. */
    suspend fun gravar(nivel: (Float) -> Unit = {}): File? {
        val arquivo = File(ctx.cacheDir, "fala.m4a")
        arquivo.delete()
        val rec = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(ctx) else @Suppress("DEPRECATION") MediaRecorder()
        gravador = rec
        try {
            rec.setAudioSource(MediaRecorder.AudioSource.VOICE_RECOGNITION)
            rec.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            rec.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            rec.setAudioSamplingRate(16000)
            rec.setAudioEncodingBitRate(32000)
            rec.setAudioChannels(1)
            rec.setOutputFile(arquivo.absolutePath)
            rec.prepare()
            rec.start()
            rec.maxAmplitude // zera a leitura

            val inicio = System.currentTimeMillis()
            var fundo = 0.0
            var amostrasFundo = 0
            var falou = false
            var ultimoSom = 0L

            while (true) {
                delay(100)
                val agora = System.currentTimeMillis()
                val dt = agora - inicio
                val amp = rec.maxAmplitude
                nivel((amp / 12000f).coerceIn(0f, 1f))

                if (dt < 400) {
                    fundo += amp; amostrasFundo++
                    continue
                }
                val limiar = maxOf(limiarMinimo.toDouble(), (fundo / maxOf(1, amostrasFundo)) * 2.2)
                if (amp > limiar) {
                    falou = true
                    ultimoSom = agora
                }
                if (!falou && dt > esperaInicioMs) break
                if (falou && agora - ultimoSom > silencioFimMs) break
                if (dt > maximoMs) break
            }
            parar()
            return if (falou && arquivo.length() > 1000) arquivo else null
        } catch (e: Exception) {
            parar()
            throw e
        }
    }

    fun parar() {
        gravador?.let {
            try { it.stop() } catch (_: Exception) {}
            it.release()
        }
        gravador = null
    }
}
