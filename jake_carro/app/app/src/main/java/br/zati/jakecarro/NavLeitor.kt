package br.zati.jakecarro

import android.app.Notification
import android.content.ComponentName
import android.content.Context
import android.provider.Settings
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification

/**
 * Lê a notificação de navegação do Google Maps (e do Waze) pra mostrar a próxima curva no cockpit.
 * O Google não deixa ler a rota do app; a notificação ("Em 400 m vire à direita · Rua X") é o caminho.
 * Precisa da permissão "acesso a notificações" dada uma vez nas configurações do Android.
 */
class NavLeitor : NotificationListenerService() {

    companion object {
        private val APPS = setOf("com.google.android.apps.maps", "com.waze")

        /** Quem quer saber da navegação (o cockpit). Recebe null quando a navegação termina. */
        var ouvinte: ((Map<String, String>?) -> Unit)? = null
        var ultimo: Map<String, String>? = null
            private set

        fun permitido(ctx: Context): Boolean {
            val ativos = Settings.Secure.getString(ctx.contentResolver, "enabled_notification_listeners") ?: return false
            return ativos.contains(ComponentName(ctx, NavLeitor::class.java).flattenToString())
        }
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        if (sbn.packageName !in APPS || !sbn.isOngoing) return
        val e = sbn.notification.extras
        val dados = mapOf(
            "app" to sbn.packageName,
            "titulo" to (e.getCharSequence(Notification.EXTRA_TITLE)?.toString() ?: ""),
            "texto" to (e.getCharSequence(Notification.EXTRA_TEXT)?.toString() ?: ""),
            "sub" to (e.getCharSequence(Notification.EXTRA_SUB_TEXT)?.toString() ?: ""),
        )
        if (dados["titulo"].isNullOrBlank() && dados["texto"].isNullOrBlank()) return
        ultimo = dados
        ouvinte?.invoke(dados)
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification) {
        if (sbn.packageName !in APPS || !sbn.isOngoing) return
        ultimo = null
        ouvinte?.invoke(null)
    }
}
