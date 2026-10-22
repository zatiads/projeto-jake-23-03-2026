package br.zati.jakecarro

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.IBinder
import android.provider.Settings
import android.view.Gravity
import android.view.MotionEvent
import android.view.WindowManager
import android.widget.ImageView
import kotlin.math.abs

/**
 * Bolinha flutuante por cima do Maps/Spotify: um toque chama o Jake já ouvindo.
 * Some quando o Jake está na tela (MainActivity manda MOSTRAR/ESCONDER).
 */
class BolhaService : Service() {

    companion object {
        const val MOSTRAR = "mostrar"
        const val ESCONDER = "esconder"

        fun enviar(ctx: Context, acao: String) {
            if (!Settings.canDrawOverlays(ctx)) return
            val i = Intent(ctx, BolhaService::class.java).setAction(acao)
            try { ctx.startForegroundService(i) } catch (_: Exception) {}
        }
    }

    private lateinit var janela: WindowManager
    private var bolha: ImageView? = null
    private lateinit var params: WindowManager.LayoutParams

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        janela = getSystemService(WINDOW_SERVICE) as WindowManager
        val canal = NotificationChannel("bolha", "Jake no carro", NotificationManager.IMPORTANCE_MIN)
        getSystemService(NotificationManager::class.java).createNotificationChannel(canal)
        val aviso = Notification.Builder(this, "bolha")
            .setSmallIcon(R.drawable.ic_jake)
            .setContentTitle("Jake pronto")
            .build()
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(1, aviso, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(1, aviso)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            MOSTRAR -> mostrar()
            ESCONDER -> esconder()
        }
        return START_STICKY
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun mostrar() {
        if (bolha != null || !Settings.canDrawOverlays(this)) return
        val tam = (resources.displayMetrics.density * 84).toInt()
        val v = ImageView(this).apply {
            setImageResource(R.drawable.ic_jake)
            background = GradientDrawable().apply {
                shape = GradientDrawable.OVAL
                setColor(0xFF0B1220.toInt())
                setStroke((resources.displayMetrics.density * 3).toInt(), 0xFF22D3EE.toInt())
            }
            elevation = 12f
        }
        params = WindowManager.LayoutParams(
            tam, tam,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            val prefs = getSharedPreferences("jake", MODE_PRIVATE)
            x = prefs.getInt("bolha_x", 24)
            y = prefs.getInt("bolha_y", resources.displayMetrics.heightPixels / 2)
        }

        // Arrastar move a bolinha; toque curto chama o Jake.
        var x0 = 0; var y0 = 0; var tx = 0f; var ty = 0f; var moveu = false
        v.setOnTouchListener { _, e ->
            when (e.action) {
                MotionEvent.ACTION_DOWN -> {
                    x0 = params.x; y0 = params.y; tx = e.rawX; ty = e.rawY; moveu = false
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = e.rawX - tx; val dy = e.rawY - ty
                    if (abs(dx) > 12 || abs(dy) > 12) moveu = true
                    if (moveu) {
                        params.x = x0 + dx.toInt(); params.y = y0 + dy.toInt()
                        janela.updateViewLayout(v, params)
                    }
                }
                MotionEvent.ACTION_UP -> {
                    if (moveu) {
                        getSharedPreferences("jake", MODE_PRIVATE).edit()
                            .putInt("bolha_x", params.x).putInt("bolha_y", params.y).apply()
                    } else {
                        startActivity(Intent(this, MainActivity::class.java)
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                            .putExtra(MainActivity.EXTRA_OUVIR, true))
                    }
                }
            }
            true
        }
        janela.addView(v, params)
        bolha = v
    }

    private fun esconder() {
        bolha?.let { try { janela.removeView(it) } catch (_: Exception) {} }
        bolha = null
    }

    override fun onDestroy() {
        esconder()
        super.onDestroy()
    }
}
