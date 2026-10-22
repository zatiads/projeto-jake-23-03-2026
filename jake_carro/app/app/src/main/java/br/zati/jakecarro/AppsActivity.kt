package br.zati.jakecarro

import android.app.Activity
import android.content.Intent
import android.content.pm.ResolveInfo
import android.graphics.Typeface
import android.os.Bundle
import android.text.TextUtils
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.BaseAdapter
import android.widget.FrameLayout
import android.widget.GridView
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView

/** Gaveta com todos os apps da central (o Jake é o launcher, então tudo tem que ser alcançável daqui). */
class AppsActivity : Activity() {

    private data class App(val nome: String, val info: ResolveInfo)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val d = resources.displayMetrics.density
        fun dp(v: Int) = (v * d).toInt()

        val apps = packageManager.queryIntentActivities(
            Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER), 0)
            .filter { it.activityInfo.packageName != packageName }
            .map { App(it.loadLabel(packageManager).toString(), it) }
            .sortedBy { it.nome.lowercase() }

        val raiz = FrameLayout(this).apply { setBackgroundColor(0xF2040A12.toInt()) }
        val coluna = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(32), dp(20), dp(32), dp(12))
        }
        val titulo = TextView(this).apply {
            text = "APPS"
            textSize = 18f
            letterSpacing = 0.25f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(0xFF22D3EE.toInt())
        }
        coluna.addView(titulo)

        val grade = GridView(this).apply {
            numColumns = GridView.AUTO_FIT
            columnWidth = dp(112)
            verticalSpacing = dp(14)
            stretchMode = GridView.STRETCH_COLUMN_WIDTH
            setPadding(0, dp(16), 0, 0)
            clipToPadding = false
            adapter = object : BaseAdapter() {
                override fun getCount() = apps.size
                override fun getItem(p: Int) = apps[p]
                override fun getItemId(p: Int) = p.toLong()
                override fun getView(p: Int, reuso: View?, pai: ViewGroup?): View {
                    val item = (reuso as? LinearLayout) ?: LinearLayout(this@AppsActivity).apply {
                        orientation = LinearLayout.VERTICAL
                        gravity = Gravity.CENTER_HORIZONTAL
                        minimumHeight = dp(104)
                        addView(ImageView(context), LinearLayout.LayoutParams(dp(64), dp(64)))
                        addView(TextView(context).apply {
                            textSize = 14f
                            setTextColor(0xFFE6F1F8.toInt())
                            gravity = Gravity.CENTER
                            maxLines = 1
                            ellipsize = TextUtils.TruncateAt.END
                            setPadding(dp(4), dp(8), dp(4), 0)
                        })
                    }
                    (item.getChildAt(0) as ImageView).setImageDrawable(apps[p].info.loadIcon(packageManager))
                    (item.getChildAt(1) as TextView).text = apps[p].nome
                    return item
                }
            }
            setOnItemClickListener { _, _, p, _ ->
                val a = apps[p].info.activityInfo
                startActivity(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
                    .setClassName(a.packageName, a.name)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED))
                finish()
            }
        }
        coluna.addView(grade, LinearLayout.LayoutParams(-1, 0, 1f))
        raiz.addView(coluna, FrameLayout.LayoutParams(-1, -1))

        val fechar = TextView(this).apply {
            text = "✕"
            textSize = 26f
            gravity = Gravity.CENTER
            setTextColor(0xFFCFF8FD.toInt())
            contentDescription = "Fechar"
            setOnClickListener { finish() }
        }
        raiz.addView(fechar, FrameLayout.LayoutParams(dp(64), dp(64), Gravity.TOP or Gravity.END))
        setContentView(raiz)
    }
}
