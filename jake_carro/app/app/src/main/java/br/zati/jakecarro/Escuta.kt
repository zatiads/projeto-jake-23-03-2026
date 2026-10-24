package br.zati.jakecarro

import ai.picovoice.porcupine.PorcupineManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.IBinder
import org.json.JSONObject
import java.io.File

/**
 * Fica ouvindo a palavra "Jake" o tempo todo, dentro da central e sem internet (Porcupine, ~1% de CPU).
 * Ouviu: bipe curto e o Jake abre já escutando o pedido.
 * Enquanto o Jake está ouvindo ou falando, a escuta pausa (o microfone é de um só por vez).
 * A chave e a palavra vêm do servidor (/carro/config → palavra): trocar não exige reinstalar.
 */
object Escuta {
    private var gerente: PorcupineManager? = null
    @Volatile private var pausada = false
    @Volatile private var rodando = false

    /** Monta o detector com a chave e os arquivos baixados. Chamado pelo serviço. */
    fun montar(ctx: Context, cfg: JSONObject, ppn: File, modelo: File?) {
        desmontar()
        gerente = PorcupineManager.Builder()
            .setAccessKey(cfg.getString("chave"))
            .setKeywordPath(ppn.absolutePath)
            .apply { if (modelo != null) setModelPath(modelo.absolutePath) }
            .setSensitivity(cfg.optDouble("sensibilidade", 0.6).toFloat())
            .setErrorCallback { e -> Diag.enviar("palavra", "erro na escuta: ${e.message}") }
            .build(ctx.applicationContext) { aoOuvir(ctx.applicationContext) }
        if (!pausada) iniciar()
        Diag.enviar("palavra", "ouvindo \"Jake\"", "idioma" to cfg.optString("idioma"))
    }

    private fun iniciar() {
        if (rodando) return
        runCatching { gerente?.start(); rodando = gerente != null }
            .onFailure { Diag.enviar("palavra", "não conseguiu o microfone: ${it.message}") }
    }

    /** Solta o microfone pro Jake gravar (chamar ANTES de gravar). */
    fun pausar() {
        pausada = true
        if (rodando) runCatching { gerente?.stop() }
        rodando = false
    }

    fun retomar() {
        pausada = false
        iniciar()
    }

    fun desmontar() {
        runCatching { gerente?.stop(); gerente?.delete() }
        gerente = null
        rodando = false
    }

    private fun aoOuvir(ctx: Context) {
        pausar()
        runCatching { ToneGenerator(AudioManager.STREAM_MUSIC, 70).startTone(ToneGenerator.TONE_PROP_BEEP2, 140) }
        ctx.startActivity(Intent(ctx, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            .putExtra(MainActivity.EXTRA_OUVIR, true)
            .putExtra(MainActivity.EXTRA_PALAVRA, true))
    }
}

/** Mantém o app vivo em segundo plano (com o Maps na frente) pra continuar ouvindo "Jake". */
class EscutaService : Service() {

    companion object {
        fun ligar(ctx: Context) {
            runCatching { ctx.startForegroundService(Intent(ctx, EscutaService::class.java)) }
        }
    }

    private val api = JakeApi()

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        val canal = NotificationChannel("escuta", "Jake ouvindo", NotificationManager.IMPORTANCE_MIN)
        getSystemService(NotificationManager::class.java).createNotificationChannel(canal)
        val aviso = Notification.Builder(this, "escuta")
            .setSmallIcon(R.drawable.ic_jake)
            .setContentTitle("Diga \"Jake\"")
            .build()
        if (Build.VERSION.SDK_INT >= 30) {
            startForeground(2, aviso, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        } else {
            startForeground(2, aviso)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Thread { preparar() }.start()
        return START_STICKY
    }

    /** Baixa chave/palavra/modelo do servidor se mudaram e monta o detector. */
    private fun preparar() {
        try {
            val cfg = api.config().optJSONObject("palavra")
            if (cfg == null) {
                Diag.enviar("palavra", "servidor ainda sem a palavra \"Jake\" configurada")
                return
            }
            val pasta = File(filesDir, "palavra").apply { mkdirs() }
            val ppn = File(pasta, "jake.ppn")
            val modelo = if (cfg.optString("idioma") == "pt") File(pasta, "modelo_pt.pv") else null
            val versao = cfg.optLong("versao")
            val prefs = getSharedPreferences("jake", MODE_PRIVATE)
            if (!ppn.exists() || prefs.getLong("palavra_versao", 0) != versao) {
                api.baixar("/carro/palavra/jake.ppn", ppn)
                prefs.edit().putLong("palavra_versao", versao).apply()
            }
            if (modelo != null && !modelo.exists()) api.baixar("/carro/palavra/modelo.pv", modelo)
            Escuta.montar(this, cfg, ppn, modelo)
        } catch (e: Exception) {
            Diag.enviar("palavra", "não montou a escuta: ${e.javaClass.simpleName} ${e.message}")
        }
    }

    override fun onDestroy() {
        Escuta.desmontar()
        super.onDestroy()
    }
}
