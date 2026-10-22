package br.zati.jakecarro

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

/** Resposta do Jake na VPS: o que falar e qual ação executar. */
data class Resposta(
    val ouvido: String,
    val fala: String,
    val audioB64: String,
    val acao: String,
    val parametros: JSONObject,
    val ms: String,
)

/** Conversa com o servidor (https://carro.amiartejoias.com.br). Tudo bloqueante: chamar fora da main. */
class JakeApi {
    private val http = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(25, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .build()

    private val base = BuildConfig.SERVIDOR
    private val sessao = java.util.UUID.randomUUID().toString()

    private fun pedido(caminho: String) = Request.Builder()
        .url(base + caminho)
        .header("Authorization", "Bearer ${BuildConfig.TOKEN}")

    private fun json(req: Request): JSONObject {
        http.newCall(req).execute().use { r ->
            if (!r.isSuccessful) throw IOException("HTTP ${r.code}")
            return JSONObject(r.body!!.string())
        }
    }

    fun config(): JSONObject = json(pedido("/carro/config").build())

    fun saudacao(lat: Double?, lon: Double?): Pair<String, String> {
        val q = if (lat != null && lon != null) "?lat=$lat&lon=$lon" else ""
        val d = json(pedido("/carro/saudacao$q").build())
        return d.optString("fala") to d.optString("audio_b64")
    }

    fun comando(audio: File? = null, texto: String? = null): Resposta {
        val corpo = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("sessao", sessao)
        if (texto != null) corpo.addFormDataPart("texto", texto)
        if (audio != null) corpo.addFormDataPart(
            "audio", "fala.m4a", audio.asRequestBody("audio/mp4".toMediaType()))
        val d = json(pedido("/carro/comando").post(corpo.build()).build())
        return Resposta(
            ouvido = d.optString("ouvido"),
            fala = d.optString("fala"),
            audioB64 = d.optString("audio_b64"),
            acao = d.optString("acao", "nada"),
            parametros = d.optJSONObject("parametros") ?: JSONObject(),
            ms = d.optJSONObject("ms")?.let { "ouvir ${it.optInt("ouvir")} · pensar ${it.optInt("pensar")} · voz ${it.optInt("voz")} ms" } ?: "",
        )
    }

    private val httpLento = http.newBuilder().readTimeout(45, TimeUnit.SECONDS).build()

    /** 2ª etapa de "consultar" (pesquisa, Meta, agenda): devolve (fala, mp3). */
    fun consulta(parametros: JSONObject): Pair<String, String> {
        val corpo = JSONObject(parametros.toString()).put("sessao", sessao).toString()
            .toRequestBody("application/json".toMediaType())
        httpLento.newCall(pedido("/carro/consulta").post(corpo).build()).execute().use { r ->
            if (!r.isSuccessful) throw IOException("HTTP ${r.code}")
            val d = JSONObject(r.body!!.string())
            return d.optString("fala") to d.optString("audio_b64")
        }
    }

    /** Baixa o APK novo pro arquivo dado. */
    fun baixarApk(destino: File) {
        http.newCall(pedido("/carro/apk").build()).execute().use { r ->
            if (!r.isSuccessful) throw IOException("HTTP ${r.code}")
            destino.outputStream().use { r.body!!.byteStream().copyTo(it) }
        }
    }
}
