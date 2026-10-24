package br.zati.jakecarro

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.location.LocationManager
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.WindowManager
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.content.FileProvider
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File

class MainActivity : Activity(), Cockpit.Ouvinte {

    companion object {
        const val EXTRA_OUVIR = "ouvir"
        const val EXTRA_PALAVRA = "palavra"   // chamado pela palavra "Jake" (não pela bolinha)
        private const val PEDIDO_PERMISSOES = 1
        private const val SAUDAR_DE_NOVO_MS = 2 * 60 * 1000L   // abertura com som de novo se ficou 2 min desligado
        private val CIANO = 0xFF22D3EE.toInt()
        private val FUNDO = 0xFF0B1220.toInt()
    }

    private val escopo = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private val api = JakeApi()
    private lateinit var voz: Voz
    private lateinit var ouvido: Ouvido
    private lateinit var acoes: Acoes

    private lateinit var botao: TextView
    private lateinit var status: TextView
    private lateinit var ouvidoTxt: TextView
    private lateinit var falaTxt: TextView
    private lateinit var detalhe: TextView
    private lateinit var btnBolha: Button
    private lateinit var btnAtualizar: Button
    private lateinit var btnMaps: Button
    private lateinit var btnApps: Button

    private lateinit var cockpit: Cockpit
    private lateinit var musica: Musica
    private lateinit var nativo: View

    private var conversa: Job? = null
    private var musicaSpotify: Map<String, Any>? = null
    private var naFrente = false

    override fun onResume() { super.onResume(); naFrente = true }
    override fun onPause() { super.onPause(); naFrente = false }

    private fun ligarEscuta() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) EscutaService.ligar(this)
    }

    private fun mostrarMusica(m: Map<String, Any>?) {
        cockpit.ultimaMusica = m
        cockpit.musica(m)
    }

    private fun relatarAmbiente() {
        val wv = runCatching { android.webkit.WebView.getCurrentWebViewPackage()?.versionName }.getOrNull()
        Diag.enviar("app", "abriu v${BuildConfig.VERSION_CODE}",
            "android" to android.os.Build.VERSION.RELEASE, "sdk" to android.os.Build.VERSION.SDK_INT,
            "sistema" to android.os.Build.DISPLAY, "modelo" to android.os.Build.MODEL, "webview" to wv,
            "microfone" to (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED),
            "localizacao" to (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED),
            "bolinha" to Settings.canDrawOverlays(this), "notificacoes" to NavLeitor.permitido(this),
            "spotify_instalado" to runCatching { packageManager.getPackageInfo("com.spotify.music", 0) }.isSuccess,
            "maps_instalado" to runCatching { packageManager.getPackageInfo("com.google.android.apps.maps", 0) }.isSuccess)
    }

    override fun onRequestPermissionsResult(codigo: Int, permissoes: Array<out String>, resultados: IntArray) {
        super.onRequestPermissionsResult(codigo, permissoes, resultados)
        // antes o GPS só ligava ao fechar e abrir o app depois de aceitar a permissão
        cockpit.ligarGps()
        musica.ligar()
        relatarAmbiente()
        ligarEscuta()
    }
    private var veioDaBolha = false
    private var versaoNova = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        voz = Voz(this)
        ouvido = Ouvido(this)
        acoes = Acoes(this)
        Diag.iniciar(api)
        cockpit = Cockpit(this).also { it.ouvinte = this }
        NavLeitor.ouvinte = { d -> runOnUiThread { cockpit.navegacao(d) } }
        // duas fontes pro mini player: os players do Android (precisa do acesso a notificações) e o Spotify direto
        musica = Musica(this) { m -> runOnUiThread { if (m != null || musicaSpotify == null) mostrarMusica(m) } }
        acoes.aoTocar = { m -> runOnUiThread { musicaSpotify = m; if (m != null) mostrarMusica(m) } }
        montarTela()
        telaCheia()
        registerReceiver(acordou, android.content.IntentFilter(Intent.ACTION_SCREEN_ON))
        pedirPermissoes()
        carregarConfig()
        if (intent?.getBooleanExtra(EXTRA_OUVIR, false) == true) chamarDaBolha() else saudar()
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        if (intent?.getBooleanExtra(EXTRA_OUVIR, false) == true) {
            // pela palavra "Jake" com o Jake já na tela: só escuta; vindo de outro app: escuta e devolve o app
            if (intent.getBooleanExtra(EXTRA_PALAVRA, false) && naFrente) { veioDaBolha = false; ouvir() }
            else chamarDaBolha()
        }
    }

    override fun onStart() {
        super.onStart()
        BolhaService.enviar(this, BolhaService.ESCONDER)
        cockpit.ligarGps()
        musica.ligar()
        relatarAmbiente()
        ligarEscuta()
        btnApps.visibility = if (nativo.visibility == View.VISIBLE) View.VISIBLE else View.GONE
        btnBolha.visibility = if (Settings.canDrawOverlays(this)) View.GONE else View.VISIBLE
        btnMaps.visibility = if (NavLeitor.permitido(this)) View.GONE else View.VISIBLE
    }

    override fun onStop() {
        super.onStop()
        BolhaService.enviar(this, BolhaService.MOSTRAR)
        // GPS continua ligado com o Maps na frente: desligar e religar fazia ele recomeçar do zero (minutos sem posição)
        musica.desligar()
    }

    override fun onDestroy() {
        escopo.cancel()
        ouvido.parar()
        voz.encerrar()
        acoes.desconectar()
        cockpit.desligarGps()
        runCatching { unregisterReceiver(acordou) }
        cockpit.web.destroy()
        super.onDestroy()
    }

    // ── Tela ─────────────────────────────────────────────────────────────────

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private fun texto(tam: Float, cor: Int, negrito: Boolean = false) = TextView(this).apply {
        textSize = tam
        setTextColor(cor)
        if (negrito) typeface = Typeface.DEFAULT_BOLD
    }

    private fun montarTela() {
        val raiz = FrameLayout(this).apply { setBackgroundColor(FUNDO) }

        val linha = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(32), dp(24), dp(32), dp(24))
        }

        botao = TextView(this).apply {
            text = "FALAR"
            textSize = 30f
            typeface = Typeface.DEFAULT_BOLD
            gravity = Gravity.CENTER
            setTextColor(FUNDO)
            background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(CIANO) }
            setOnClickListener { aoTocarBotao() }
        }
        linha.addView(botao, LinearLayout.LayoutParams(dp(240), dp(240)))

        val coluna = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(40), 0, 0, 0)
        }
        status = texto(34f, CIANO, true).apply { text = "Jake" }
        ouvidoTxt = texto(20f, 0xFF94A3B8.toInt())
        falaTxt = texto(24f, 0xFFF1F5F9.toInt())
        detalhe = texto(13f, 0xFF475569.toInt())
        coluna.addView(status)
        coluna.addView(ouvidoTxt, margem(top = 18))
        coluna.addView(falaTxt, margem(top = 10))
        coluna.addView(detalhe, margem(top = 18))
        linha.addView(coluna, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        raiz.addView(linha, FrameLayout.LayoutParams(-1, -1))
        nativo = linha
        nativo.visibility = View.INVISIBLE
        cockpit.montar()
        raiz.addView(cockpit.web, FrameLayout.LayoutParams(-1, -1))

        val topo = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        btnBolha = Button(this).apply {
            text = "Ativar bolinha"
            setOnClickListener {
                startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
            }
        }
        btnAtualizar = Button(this).apply {
            text = "Atualizar app"
            visibility = View.GONE
            setOnClickListener { atualizar() }
        }
        btnMaps = Button(this).apply {
            text = "Ler curvas do Maps"
            setOnClickListener { startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)) }
        }
        btnApps = Button(this).apply {
            text = "Apps"
            visibility = View.GONE
            setOnClickListener { startActivity(Intent(this@MainActivity, AppsActivity::class.java)) }
        }
        topo.addView(btnApps)
        topo.addView(btnAtualizar)
        topo.addView(btnMaps)
        topo.addView(btnBolha)
        // botões de configuração: canto de cima à direita, abaixo do clima; somem quando não precisam mais
        raiz.addView(topo, FrameLayout.LayoutParams(-2, -2, Gravity.TOP or Gravity.END).apply {
            setMargins(0, dp(52), dp(12), 0)
        })

        setContentView(raiz)
    }

    /** Esconde as barras do Android (volta deslizando da borda). */
    private fun telaCheia() {
        if (android.os.Build.VERSION.SDK_INT >= 30) {
            window.setDecorFitsSystemWindows(false)
            window.insetsController?.let {
                it.hide(WindowInsets.Type.systemBars())
                it.systemBarsBehavior = WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            }
        } else {
            // Android 8 a 10 (centrais "Android 14" que na verdade são versões antigas)
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility = (View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                or View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_LAYOUT_STABLE or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION)
        }
    }

    override fun onWindowFocusChanged(temFoco: Boolean) {
        super.onWindowFocusChanged(temFoco)
        if (temFoco) telaCheia()
    }

    // ── Cockpit chamando o app ──
    override fun aoTocarJake() = aoTocarBotao()

    override fun aoPerguntar(texto: String) {
        veioDaBolha = false
        conversa?.cancel()
        conversa = escopo.launch { perguntarTexto(texto) }
    }

    override fun aoOuvirCom(frase: String) {
        veioDaBolha = false
        conversa?.cancel()
        conversa = escopo.launch {
            estado("Falando…", painel = "falando", frase = frase)
            voz.pegarFoco(exclusivo = false)
            voz.falarLocal(frase)
            voz.soltarFoco()
            ouvir()
        }
    }

    override fun aoAbrirApp(chave: String) {
        val pacote = mapOf("mapa" to "com.google.android.apps.maps", "musica" to "com.spotify.music",
            "waze" to "com.waze")[chave]
        val abrir = pacote?.let { packageManager.getLaunchIntentForPackage(it) }
        if (abrir != null) startActivity(abrir.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        else startActivity(Intent(this, AppsActivity::class.java))
    }

    override fun aoAcao(acao: String, parametros: JSONObject) {
        escopo.launch { acoes.executar(acao, parametros) }
    }

    override fun aoFoco(ativo: Boolean) {
        if (ativo) {
            Escuta.pausar()
            conversa?.cancel(); ouvido.parar(); voz.calar()
            voz.pegarFoco(exclusivo = true)
        } else { voz.soltarFoco(); Escuta.retomar() }
    }

    override fun aoMidia(cmd: String) {
        if (musica.comando(cmd)) return
        // sem player aberto (ou só o Bluetooth): manda a tecla de mídia, que o Android entrega ao Spotify
        acoes.midia(when (cmd) { "alternar" -> "continuar"; else -> cmd })
    }

    override fun aoFalarAudio(texto: String, mp3B64: String) {
        if (conversa?.isActive == true) return
        conversa = escopo.launch {
            estado("Falando…", painel = "falando", frase = texto)
            voz.pegarFoco(exclusivo = false)
            voz.falar(texto, mp3B64)
            voz.soltarFoco()
            estado("Pronto, patrão", frase = texto)
        }
    }

    // Como launcher, "voltar" não sai do Jake: só para o que ele estiver fazendo.
    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (conversa?.isActive == true) aoTocarBotao()
    }

    /** A central "acorda" quando liga o carro (a tela acende): cumprimenta, respeitando a regra de 30 min. */
    private val acordou = object : android.content.BroadcastReceiver() {
        override fun onReceive(c: android.content.Context?, i: Intent?) {
            cockpit.recarregarDados()
            if (conversa?.isActive != true) saudar()
        }
    }

    override fun aoFalharCockpit() {
        // sem a página (sem internet ao abrir): mostra a tela simples do app
        nativo.visibility = View.VISIBLE
        cockpit.web.visibility = View.GONE
        btnApps.visibility = View.VISIBLE
    }

    private fun margem(top: Int) = LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(top) }

    /** Atualiza a tela simples e o cockpit ([painel] = estado da bolinha, [frase] = legenda). */
    private fun estado(t: String, corBotao: Int = CIANO, rotulo: String = "FALAR",
                       painel: String = "pronto", frase: String? = null) {
        status.text = t
        botao.text = rotulo
        (botao.background as GradientDrawable).setColor(corBotao)
        cockpit.estado(painel, frase)
        // microfone é de um só: a escuta do "Jake" pausa enquanto ele ouve/fala e volta quando termina
        if (painel in setOf("pronto", "feito", "offline") && rotulo != "PARAR") Escuta.retomar() else Escuta.pausar()
    }

    // ── Permissões / config ──────────────────────────────────────────────────

    private fun pedirPermissoes() {
        val faltando = listOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.ACCESS_COARSE_LOCATION,
            Manifest.permission.ACCESS_FINE_LOCATION,
        ).let { if (android.os.Build.VERSION.SDK_INT >= 33) it + Manifest.permission.POST_NOTIFICATIONS else it }
        .filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (faltando.isNotEmpty()) requestPermissions(faltando.toTypedArray(), PEDIDO_PERMISSOES)
    }

    private fun carregarConfig() = escopo.launch {
        try {
            val cfg = withContext(Dispatchers.IO) { api.config() }
            acoes.spotifyClientId = cfg.optString("spotify_client_id")
            acoes.conectarSpotify(pedirAutorizacao = false)   // se já autorizou, o mini player mostra o que toca
            versaoNova = cfg.optJSONObject("app")?.optInt("versao") ?: 0
            btnAtualizar.visibility = if (versaoNova > BuildConfig.VERSION_CODE) View.VISIBLE else View.GONE
        } catch (_: Exception) {}
    }

    @Suppress("MissingPermission")
    private fun localizacao(): Pair<Double, Double>? {
        if (checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED) return null
        val lm = getSystemService(LOCATION_SERVICE) as LocationManager
        val loc = lm.getProviders(true).mapNotNull { runCatching { lm.getLastKnownLocation(it) }.getOrNull() }
            .maxByOrNull { it.time } ?: return null
        return loc.latitude to loc.longitude
    }

    // ── Conversa ─────────────────────────────────────────────────────────────

    private fun saudar() {
        val prefs = getSharedPreferences("jake", MODE_PRIVATE)
        val agora = System.currentTimeMillis()
        if (agora - prefs.getLong("ultima_saudacao", 0) < SAUDAR_DE_NOVO_MS) {
            estado("Pronto, patrão", frase = "Toque em mim pra falar.")
            return
        }
        prefs.edit().putLong("ultima_saudacao", agora).apply()
        conversa = escopo.launch {
            estado("Acordando…")
            val inicio = System.currentTimeMillis()
            cockpit.acordar()
            voz.tocarSom(R.raw.abertura)   // pelo app: a música só abaixa (pela página, o Spotify pausava)
            val (fala, mp3) = try {
                val loc = localizacao()
                withContext(Dispatchers.IO) { api.saudacao(loc?.first, loc?.second) }
            } catch (_: Exception) {
                "Fala, patrão! Tô sem internet agora, mas rota e música eu ainda consigo." to ""
            }
            // espera o impacto do som da nave (~1,7 s) antes de falar; se a internet demorou, fala na hora
            val falta = 1700 - (System.currentTimeMillis() - inicio)
            if (falta > 0) kotlinx.coroutines.delay(falta)
            falaTxt.text = fala
            estado("Falando…", painel = "falando", frase = fala)
            voz.pegarFoco(exclusivo = false)
            voz.falar(fala, mp3)
            voz.soltarFoco()
            estado("Pronto, patrão", frase = fala)
        }
    }

    private fun chamarDaBolha() {
        veioDaBolha = true
        ouvir()
    }

    private fun aoTocarBotao() {
        if (conversa?.isActive == true) {
            conversa?.cancel()
            ouvido.parar()
            voz.calar()
            voz.soltarFoco()
            estado("Pronto, patrão", frase = "")
            return
        }
        veioDaBolha = false
        ouvir()
    }

    private fun ouvir() {
        conversa?.cancel()
        voz.calar()
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            pedirPermissoes()
            return
        }
        Escuta.pausar()   // solta o microfone ANTES de gravar
        conversa = escopo.launch {
            ouvidoTxt.text = ""
            falaTxt.text = ""
            detalhe.text = ""
            voz.pegarFoco(exclusivo = true)
            estado("Ouvindo…", 0xFFF43F5E.toInt(), "PARAR", painel = "ouvindo", frase = "")
            val audio = try {
                ouvido.gravar { n -> botao.scaleX = 1f + n * 0.12f; botao.scaleY = 1f + n * 0.12f; cockpit.nivel(n) }
            } catch (e: Exception) {
                null
            } finally {
                botao.scaleX = 1f; botao.scaleY = 1f
            }
            if (audio == null) {
                voz.soltarFoco()
                estado("Não ouvi nada. Toca de novo.", frase = "Não ouvi nada. Toca de novo.")
                voltarSeVeioDaBolha()
                return@launch
            }

            estado("Pensando…", 0xFFFBBF24.toInt(), "…", painel = "pensando")
            val r = try {
                withContext(Dispatchers.IO) { api.comando(audio = audio) }
            } catch (e: Exception) {
                null
            }
            if (r == null) {
                modoOffline()
                return@launch
            }
            mostrarResposta(r)
        }
    }

    private suspend fun perguntarTexto(texto: String) {
        estado("Pensando…", 0xFFFBBF24.toInt(), "…", painel = "pensando", frase = "“$texto”")
        val r = try {
            withContext(Dispatchers.IO) { api.comando(texto = texto) }
        } catch (e: Exception) {
            null
        }
        if (r == null) {
            estado("Sem internet", painel = "offline", frase = "Tô sem internet, patrão.")
            voz.falarLocal("Tô sem internet, patrão.")
            return
        }
        mostrarResposta(r)
    }

    private suspend fun mostrarResposta(r: Resposta) {
        ouvidoTxt.text = if (r.ouvido.isNotBlank()) "“${r.ouvido}”" else ""
        if (r.ouvido.isNotBlank()) cockpit.estado("pensando", "“${r.ouvido}”")
        responder(r.fala, r.audioB64, r.acao, r.parametros)
        detalhe.text = r.ms
    }

    private suspend fun responder(fala: String, mp3: String, acao: String, params: JSONObject) {
        if (acao == "consultar") return consultar(fala, mp3, params)
        falaTxt.text = fala
        estado("Falando…", painel = "falando", frase = fala)
        voz.pegarFoco(exclusivo = false)
        voz.falar(fala, mp3)
        voz.soltarFoco()
        if (acao == "navegar") cockpit.destino(params.optString("destino").substringBefore(","))
        val abriuOutroApp = acoes.executar(acao, params)
        estado("Pronto, patrão", painel = if (acao in setOf("navegar", "tocar_musica", "midia")) "feito" else "pronto",
            frase = fala)
        if (!abriuOutroApp) voltarSeVeioDaBolha()
    }

    /** Fala a frase de espera enquanto o servidor busca (internet, Meta, agenda) em paralelo. */
    private suspend fun consultar(espera: String, mp3: String, params: JSONObject) {
        val busca = escopo.async(Dispatchers.IO) { runCatching { api.consulta(params) }.getOrNull() }
        falaTxt.text = espera
        estado("Buscando…", 0xFFFBBF24.toInt(), "…", painel = "pensando", frase = espera)
        voz.pegarFoco(exclusivo = false)
        voz.falar(espera, mp3)
        val r = busca.await()
        val (fala, audio) = r ?: ("Não consegui puxar isso agora, patrão." to "")
        falaTxt.text = fala
        estado("Falando…", painel = "falando", frase = fala)
        voz.falar(fala, audio)
        voz.soltarFoco()
        estado("Pronto, patrão", frase = fala)
        voltarSeVeioDaBolha()
    }

    private suspend fun modoOffline() {
        estado("Sem internet", painel = "offline", frase = "Tô sem internet, patrão.")
        voz.pegarFoco(exclusivo = false)
        if (!Offline.disponivel(this)) {
            voz.falarLocal("Tô sem internet, patrão. Assim que voltar eu te respondo.")
            voz.soltarFoco()
            estado("Sem internet", painel = "offline", frase = "Tô sem internet, patrão.")
            voltarSeVeioDaBolha()
            return
        }
        voz.falarLocal("Tô sem internet, patrão. Fala de novo que eu tento aqui mesmo.")
        voz.soltarFoco()
        estado("Ouvindo (offline)…", 0xFFF43F5E.toInt(), "PARAR", painel = "offline", frase = "Ouvindo sem internet…")
        val frase = Offline.ouvir(this)
        if (frase.isNullOrBlank()) {
            estado("Não entendi offline")
            voltarSeVeioDaBolha()
            return
        }
        ouvidoTxt.text = "“$frase”"
        val (fala, acao, params) = Offline.interpretar(frase)
        responder(fala, "", acao, params)
        detalhe.text = "modo offline"
    }

    private fun voltarSeVeioDaBolha() {
        if (veioDaBolha) {
            veioDaBolha = false
            moveTaskToBack(true)
        }
    }

    // ── Atualização ──────────────────────────────────────────────────────────

    private fun atualizar() = escopo.launch {
        btnAtualizar.text = "Baixando…"
        try {
            val pasta = File(cacheDir, "atualizacao").apply { mkdirs() }
            val apk = File(pasta, "jake-carro.apk")
            withContext(Dispatchers.IO) { api.baixarApk(apk) }
            if (!packageManager.canRequestPackageInstalls()) {
                startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:$packageName")))
                btnAtualizar.text = "Libere e toque de novo"
                return@launch
            }
            val uri = FileProvider.getUriForFile(this@MainActivity, "br.zati.jakecarro.arquivos", apk)
            startActivity(Intent(Intent.ACTION_VIEW)
                .setDataAndType(uri, "application/vnd.android.package-archive")
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK))
            btnAtualizar.text = "Atualizar app"
        } catch (e: Exception) {
            btnAtualizar.text = "Falhou, tenta de novo"
        }
    }
}
