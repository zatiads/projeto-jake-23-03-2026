package br.zati.jakecarro

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.pm.PackageManager
import android.graphics.Color
import android.location.GnssStatus
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.webkit.JavascriptInterface
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
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
        fun aoAcao(acao: String, parametros: JSONObject)
        fun aoFoco(ativo: Boolean)
        fun aoFalarAudio(texto: String, mp3B64: String)
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
        // conversa em tempo real: a página precisa do microfone (o app já tem a permissão)
        web.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(req: PermissionRequest) {
                tela.runOnUiThread {
                    val pode = tela.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
                    if (pode && PermissionRequest.RESOURCE_AUDIO_CAPTURE in req.resources)
                        req.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE))
                    else req.deny()
                }
            }
        }
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

    /** Abre a conversa em tempo real pela página (mesmo que tocar na bolinha). */
    fun conversar() = js("jake.conversar()")
    val carregado get() = pronto

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
    // Ouve o satélite E a rede. Satélite manda velocidade; sem ele (antena sem sinal), calcula pela
    // distância entre dois pontos. Fix de satélite recente tem prioridade sobre o da rede.
    private val anteriores = HashMap<String, Location>()
    private var ultimoSatelite = 0L
    private val primeiros = HashSet<String>()
    private val gps = object : LocationListener {
        override fun onLocationChanged(l: Location) {
            val prov = l.provider ?: "?"
            if (prov != LocationManager.GPS_PROVIDER && System.currentTimeMillis() - ultimoSatelite < 5000) return
            if (prov == LocationManager.GPS_PROVIDER) ultimoSatelite = System.currentTimeMillis()
            val antes = anteriores[prov]
            anteriores[prov] = l
            val kmh = when {
                l.hasSpeed() -> l.speed * 3.6f
                antes != null && l.accuracy < 80 && antes.accuracy < 80 && l.time - antes.time >= 3000 ->
                    l.distanceTo(antes) / ((l.time - antes.time) / 1000f) * 3.6f
                else -> 0f
            }
            if (primeiros.add(prov)) Diag.enviar("gps", "primeira posição: $prov",
                "precisao_m" to l.accuracy, "tem_velocidade" to l.hasSpeed(), "kmh" to kmh)
            js("jake.gps($kmh, ${l.latitude}, ${l.longitude})")
        }
        @Deprecated("Deprecated in Java")
        override fun onStatusChanged(p: String?, s: Int, e: Bundle?) {}
        override fun onProviderEnabled(p: String) {}
        override fun onProviderDisabled(p: String) {}
    }

    // satélites: diz se a antena de GPS está pegando (relatório 1x por minuto no máximo)
    private val satelites = object : GnssStatus.Callback() {
        override fun onSatelliteStatusChanged(s: GnssStatus) {
            var usados = 0
            var forca = 0f
            var fortes = 0
            for (i in 0 until s.satelliteCount) {
                if (s.usedInFix(i)) usados++
                val cn0 = s.getCn0DbHz(i)
                forca += cn0
                if (cn0 >= 25) fortes++          // abaixo de ~25 dB-Hz o satélite não serve pra posição
            }
            // força média: < 20 = antena escondida/sem céu; 25–35 = ok; > 35 = ótima
            Diag.enviar("gps", "satélites", "vistos" to s.satelliteCount, "usados" to usados,
                "fortes" to fortes, "forca_media" to if (s.satelliteCount > 0) Math.round(forca / s.satelliteCount) else 0)
        }
    }

    @SuppressLint("MissingPermission")
    fun ligarGps() {
        val lm = tela.getSystemService(Activity.LOCATION_SERVICE) as LocationManager
        val permitido = tela.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val ativos = lm.getProviders(true)
        Diag.enviar("gps", "ligando", "permissao" to permitido, "provedores" to ativos.joinToString())
        if (!permitido) return
        lm.removeUpdates(gps)
        for (p in listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)) {
            if (p in ativos) runCatching { lm.requestLocationUpdates(p, 1000L, 0f, gps) }
        }
        runCatching { lm.registerGnssStatusCallback(satelites) }
    }

    fun desligarGps() {
        val lm = tela.getSystemService(Activity.LOCATION_SERVICE) as LocationManager
        lm.removeUpdates(gps)
        runCatching { lm.unregisterGnssStatusCallback(satelites) }
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
        /** Ação pedida pela IA em tempo real: {"acao": "navegar|tocar_musica|midia", "parametros": {...}} */
        @JavascriptInterface fun acao(json: String) = tela.runOnUiThread {
            runCatching { JSONObject(json) }.getOrNull()?.let {
                ouvinte?.aoAcao(it.optString("acao"), it.optJSONObject("parametros") ?: JSONObject())
            }
        }
        /** Aviso falado: o app toca (abaixa a música e devolve), em vez da página (que pausava o Spotify). */
        @JavascriptInterface fun falarAudio(texto: String, mp3: String) = tela.runOnUiThread { ouvinte?.aoFalarAudio(texto, mp3) }
        /** true = conversa começou (abaixa/pausa a música); false = terminou */
        @JavascriptInterface fun foco(ativo: Boolean) = tela.runOnUiThread { ouvinte?.aoFoco(ativo) }
    }
}
