package br.zati.jakecarro

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.pm.PackageManager
import android.graphics.Color
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.webkit.JavascriptInterface
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import org.json.JSONObject

/**
 * Cockpit animado: página servida pela VPS (/carro/cockpit/) aberta em tela cheia.
 * O app manda pra ela o estado da bolinha, o volume da voz, a velocidade do GPS e o destino;
 * ela chama de volta o app quando o patrão toca na bolinha ou nos botões.
 */
class Cockpit(private val tela: Activity) {

    interface Ouvinte {
        fun aoTocarJake()
        fun aoPerguntar(texto: String)
        fun aoOuvirCom(frase: String)
        fun aoFalharCockpit()
        fun aoAbrirApp(chave: String)
        fun aoMidia(cmd: String)
    }

    var ouvinte: Ouvinte? = null
    val web = WebView(tela)
    private var pronto = false
    var ultimaMusica: Map<String, Any>? = null
    private val fila = mutableListOf<String>()   // chamadas feitas antes da página carregar

    @SuppressLint("SetJavaScriptEnabled")
    fun montar() {
        web.setBackgroundColor(Color.parseColor("#04070D"))
        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true
        web.settings.mediaPlaybackRequiresUserGesture = false
        web.isVerticalScrollBarEnabled = false
        web.isHorizontalScrollBarEnabled = false
        web.overScrollMode = WebView.OVER_SCROLL_NEVER
        web.addJavascriptInterface(Ponte(), "Android")
        web.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                pronto = true
                fila.forEach { web.evaluateJavascript("window.jake && $it", null) }
                fila.clear()
                NavLeitor.ultimo?.let { navegacao(it) }
                ultimaMusica?.let { musica(it) }
            }
            override fun onReceivedError(view: WebView?, req: WebResourceRequest?, erro: WebResourceError?) {
                if (req?.isForMainFrame == true) ouvinte?.aoFalharCockpit()
            }
        }
        web.loadUrl(BuildConfig.SERVIDOR + "/carro/cockpit/")
    }

    fun recarregar() = web.reload()
    fun recarregarDados() = js("jake.painel()")

    private fun js(codigo: String) {
        if (pronto) web.post { web.evaluateJavascript("window.jake && $codigo", null) }
        else if (codigo.startsWith("jake.acordar") || codigo.startsWith("jake.estado")) fila.add(codigo)
    }

    private fun texto(s: String?) = if (s == null) "null" else JSONObject.quote(s)

    /** pronto | ouvindo | pensando | falando | feito | offline */
    fun estado(nome: String, frase: String? = null) = js("jake.estado(${texto(nome)}, ${texto(frase)})")
    fun nivel(v: Float) = js("jake.nivel($v)")

    /** Som da nave + clarão. O impacto do som cai em ~1,5 s: é aí que o Jake começa a falar. */
    fun acordar() = js("jake.acordar()")
    fun destino(nome: String?, chegada: String? = null) = js("jake.destino(${texto(nome)}, ${texto(chegada)})")

    /** O que está tocando (null = nada). */
    fun musica(m: Map<String, Any>?) = js("jake.musica(${if (m == null) "null" else JSONObject(m).toString()})")

    /** Próxima curva lida do Maps (null = navegação terminou). */
    fun navegacao(d: Map<String, String>?) =
        js("jake.navegacao(${if (d == null) "null" else JSONObject(d).toString()})")

    // ── GPS: velocidade e posição pro painel ──
    private val gps = object : LocationListener {
        override fun onLocationChanged(l: Location) {
            val kmh = if (l.hasSpeed()) l.speed * 3.6f else 0f
            js("jake.gps($kmh, ${l.latitude}, ${l.longitude})")
        }
        @Deprecated("Deprecated in Java")
        override fun onStatusChanged(p: String?, s: Int, e: Bundle?) {}
        override fun onProviderEnabled(p: String) {}
        override fun onProviderDisabled(p: String) {}
    }

    @SuppressLint("MissingPermission")
    fun ligarGps() {
        if (tela.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) return
        val lm = tela.getSystemService(Activity.LOCATION_SERVICE) as LocationManager
        if (lm.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
            lm.requestLocationUpdates(LocationManager.GPS_PROVIDER, 1000L, 0f, gps)
        }
    }

    fun desligarGps() {
        (tela.getSystemService(Activity.LOCATION_SERVICE) as LocationManager).removeUpdates(gps)
    }

    /** O que a página pode pedir pro app. Chega fora da main thread: devolve pra ela. */
    private inner class Ponte {
        @JavascriptInterface fun token(): String = BuildConfig.TOKEN
        @JavascriptInterface fun falar() = tela.runOnUiThread { ouvinte?.aoTocarJake() }
        @JavascriptInterface fun perguntar(t: String) = tela.runOnUiThread { ouvinte?.aoPerguntar(t) }
        @JavascriptInterface fun ouvirCom(f: String) = tela.runOnUiThread { ouvinte?.aoOuvirCom(f) }
        /** mapa | musica | waze | apps */
        @JavascriptInterface fun abrirApp(chave: String) = tela.runOnUiThread { ouvinte?.aoAbrirApp(chave) }
        /** anterior | alternar | proxima */
        @JavascriptInterface fun midia(cmd: String) = tela.runOnUiThread { ouvinte?.aoMidia(cmd) }
    }
}
