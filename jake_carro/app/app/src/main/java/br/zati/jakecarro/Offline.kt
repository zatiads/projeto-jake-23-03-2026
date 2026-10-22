package br.zati.jakecarro

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import kotlinx.coroutines.suspendCancellableCoroutine
import org.json.JSONObject
import kotlin.coroutines.resume

/** Plano B sem internet: reconhecimento do próprio aparelho + regras simples. */
object Offline {

    fun disponivel(ctx: Context) = SpeechRecognizer.isRecognitionAvailable(ctx)

    /** Ouve pelo reconhecedor do Android (offline se o pacote pt-BR estiver baixado). */
    suspend fun ouvir(ctx: Context): String? = suspendCancellableCoroutine { cont ->
        val sr = SpeechRecognizer.createSpeechRecognizer(ctx)
        fun fim(texto: String?) {
            sr.destroy()
            if (cont.isActive) cont.resume(texto)
        }
        sr.setRecognitionListener(object : RecognitionListener {
            override fun onResults(r: Bundle?) =
                fim(r?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull())
            override fun onError(error: Int) = fim(null)
            override fun onReadyForSpeech(p: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rms: Float) {}
            override fun onBufferReceived(b: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onPartialResults(p: Bundle?) {}
            override fun onEvent(t: Int, p: Bundle?) {}
        })
        sr.startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "pt-BR")
            .putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true))
        cont.invokeOnCancellation { sr.destroy() }
    }

    private val navegar = Regex(
        """^(?:jake[, ]+)?(?:me leva|leva|vamos|vambora|bora|partiu|navega|rota|ir)\s+(?:pra|para|pro|até|ao|à|a|no|na)?\s*(.+)$""",
        RegexOption.IGNORE_CASE)
    private val tocar = Regex(
        """^(?:jake[, ]+)?(?:toca|toque|coloca|coloque|bota|põe|poe|play)\s+(?:uma?\s+|o\s+|a\s+)?(.+?)(?:\s+no spotify)?$""",
        RegexOption.IGNORE_CASE)

    /** Converte a frase em (fala, ação, parâmetros) no mesmo formato do servidor. */
    fun interpretar(frase: String): Triple<String, String, JSONObject> {
        val t = frase.trim().trimEnd('.', '!', '?')
        val baixo = t.lowercase()
        navegar.find(t)?.let {
            val destino = it.groupValues[1]
            return Triple("Bora, patrão. Rota pra $destino.", "navegar",
                JSONObject().put("destino", destino).put("app", if ("waze" in baixo) "waze" else "maps"))
        }
        tocar.find(t)?.let {
            val busca = it.groupValues[1]
            return Triple("Tocando $busca.", "tocar_musica",
                JSONObject().put("busca", busca).put("tipo", "artista").put("uri", ""))
        }
        val midia = when {
            Regex("""\b(pausa|para a música|pare)\b""").containsMatchIn(baixo) -> "pausar"
            Regex("""\b(próxima|proxima|pula|passa)\b""").containsMatchIn(baixo) -> "proxima"
            Regex("""\b(volta a música|anterior)\b""").containsMatchIn(baixo) -> "anterior"
            Regex("""\b(continua|despausa|solta o som)\b""").containsMatchIn(baixo) -> "continuar"
            else -> null
        }
        if (midia != null) return Triple("Feito.", "midia", JSONObject().put("comando", midia))
        return Triple("Sem internet eu só consigo rota e música, patrão.", "nada", JSONObject())
    }
}
