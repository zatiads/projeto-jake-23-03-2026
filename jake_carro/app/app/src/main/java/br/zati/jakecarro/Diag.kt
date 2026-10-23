package br.zati.jakecarro

import org.json.JSONObject
import java.util.concurrent.Executors

/**
 * Relatório do próprio app pro servidor (/carro/diag): versão do Android, permissões, GPS, Spotify.
 * Assim dá pra ver o que aconteceu na central sem depender da descrição de quem testou.
 */
object Diag {
    private var api: JakeApi? = null
    private val fila = Executors.newSingleThreadExecutor()
    private val vistos = HashMap<String, Long>()

    fun iniciar(a: JakeApi) { api = a }

    /** Manda em segundo plano; o mesmo tipo+mensagem no máximo 1x por minuto. */
    fun enviar(tipo: String, msg: String, vararg detalhe: Pair<String, Any?>) {
        val chave = tipo + msg
        val agora = System.currentTimeMillis()
        synchronized(vistos) {
            if ((vistos[chave] ?: 0L) > agora - 60_000) return
            vistos[chave] = agora
        }
        val json = JSONObject()
        detalhe.forEach { (k, v) -> json.put(k, v ?: JSONObject.NULL) }
        fila.execute { runCatching { api?.diag(tipo, msg, json) } }
    }
}
