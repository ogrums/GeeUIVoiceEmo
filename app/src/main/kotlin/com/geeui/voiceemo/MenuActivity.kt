package com.geeui.voiceemo

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.util.TypedValue
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

/** Round 480 screen. Menu, then server, model, voice. Back leaves the app. */
class MenuActivity : Activity() {
    private val pool = Executors.newSingleThreadExecutor()
    private val prefs by lazy { getSharedPreferences("geeui.voiceemo", MODE_PRIVATE) }
    private var server = HostConfig.SIDECAR
    private var lemonade = HostConfig.LEMONADE
    private var model = HostConfig.KOKORO
    private var voice = HostConfig.VOICE_FR
    private var models = listOf(HostConfig.KOKORO)
    private var voices = listOf(HostConfig.VOICE_FR, HostConfig.VOICE_EN)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        load()
        showMenu()
    }

    override fun onDestroy() {
        pool.shutdownNow()
        super.onDestroy()
    }

    private fun load() {
        server = prefs.getString("sidecar", HostConfig.SIDECAR) ?: HostConfig.SIDECAR
        lemonade = prefs.getString("lemonade", HostConfig.LEMONADE) ?: HostConfig.LEMONADE
        model = prefs.getString("kokoro", HostConfig.KOKORO) ?: HostConfig.KOKORO
        voice = prefs.getString("voice_fr", HostConfig.VOICE_FR) ?: HostConfig.VOICE_FR
    }

    private fun save() {
        prefs.edit()
            .putString("sidecar", server)
            .putString("lemonade", lemonade)
            .putString("kokoro", model)
            .putString("voice_fr", voice)
            .apply()
    }

    private fun showMenu() {
        val root = column()
        root.addView(title("GeeUIVoiceEmo"))
        root.addView(button("Lancer") { launch() })
        root.addView(button("Paramètres") { showServer() })
        root.addView(button("Retour") { finish() })
        setContentView(scroll(root))
    }

    private fun launch() {
        save()
        val intent = Intent(this, EmotionService::class.java)
            .putExtra("sidecar", server)
            .putExtra("lemonade", lemonade)
            .putExtra("kokoro", model)
            .putExtra("voice_fr", voice)
        startForegroundService(intent)
        finish()
    }

    private fun showServer() {
        val root = column()
        root.addView(title("Serveur"))
        val field = edit(server)
        root.addView(field)
        val status = text("Non validé")
        root.addView(status)
        root.addView(button("Valider") {
            server = field.text.toString().trim().ifEmpty { HostConfig.SIDECAR }
            status.text = "Validation…"
            pool.execute {
                val result = validate(server)
                runOnUiThread {
                    if (result == null) {
                        status.text = "Serveur injoignable"
                        return@runOnUiThread
                    }
                    lemonade = result.lemonade
                    models = result.models
                    if (model !in models) model = models.first()
                    status.text = "OK ${result.lemonade}"
                    showModels()
                }
            }
        })
        root.addView(button("Retour") { showMenu() })
        setContentView(scroll(root))
    }

    private fun showModels() {
        val root = column()
        root.addView(title("Modèle"))
        root.addView(text(server))
        models.forEach { name ->
            root.addView(button(if (name == model) "• $name" else name) {
                model = name
                voices = voicesFor(name)
                if (voice !in voices) voice = voices.first()
                showVoices()
            })
        }
        root.addView(button("Retour") { showServer() })
        setContentView(scroll(root))
    }

    private fun showVoices() {
        val root = column()
        root.addView(title("Voix"))
        root.addView(text(model))
        voices.forEach { name ->
            root.addView(button(if (name == voice) "• $name" else name) {
                voice = name
                save()
                showMenu()
            })
        }
        root.addView(button("Retour") { showModels() })
        setContentView(scroll(root))
    }

    private fun voicesFor(modelName: String): List<String> {
        val key = modelName.lowercase()
        return when {
            "cosy" in key -> listOf("happy", "sad", "angry", "fear", "surprise")
            else -> listOf(HostConfig.VOICE_FR, HostConfig.VOICE_EN)
        }
    }

    private fun validate(raw: String): Probe? {
        val base = raw.trimEnd('/')
        val config = getJson("$base/config")
        if (config != null) {
            val lemon = config.optString("lemonade_host", HostConfig.LEMONADE)
            val found = mutableListOf(config.optString("kokoro_model", HostConfig.KOKORO))
            if (config.optBoolean("cosyvoice_enabled")) found += config.optString("cosyvoice_model", HostConfig.COSY)
            return Probe(lemon, found.distinct())
        }
        val models = getJson("$base/v1/models") ?: getJson("$base/api/v1/models") ?: return null
        val ids = mutableListOf<String>()
        val data = models.optJSONArray("data")
        if (data != null) {
            for (i in 0 until data.length()) ids += data.getJSONObject(i).optString("id")
        }
        if (ids.isEmpty()) ids += HostConfig.KOKORO
        return Probe(base, ids)
    }

    private fun getJson(url: String): JSONObject? {
        return try {
            val conn = URL(url).openConnection() as HttpURLConnection
            conn.connectTimeout = 2_000
            conn.readTimeout = 2_000
            conn.requestMethod = "GET"
            if (conn.responseCode !in 200..299) return null
            JSONObject(conn.inputStream.readBytes().toString(Charsets.UTF_8))
        } catch (_: Exception) {
            null
        }
    }

    private fun scroll(child: LinearLayout) = ScrollView(this).apply {
        setBackgroundColor(Color.BLACK)
        addView(child)
    }

    private fun column() = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(48, 96, 48, 48)
        setBackgroundColor(Color.BLACK)
    }

    private fun title(value: String) = TextView(this).apply {
        text = value
        setTextColor(Color.WHITE)
        setTextSize(TypedValue.COMPLEX_UNIT_PX, 36f)
        gravity = Gravity.CENTER
        setPadding(0, 0, 0, 24)
    }

    private fun edit(value: String) = EditText(this).apply {
        setText(value)
        setTextColor(Color.WHITE)
        setTextSize(TypedValue.COMPLEX_UNIT_PX, 22f)
        setSingleLine(true)
    }

    private fun text(value: String) = TextView(this).apply {
        text = value
        setTextColor(Color.LTGRAY)
        setTextSize(TypedValue.COMPLEX_UNIT_PX, 22f)
        setPadding(0, 8, 0, 8)
    }

    private fun button(label: String, onClick: () -> Unit) = Button(this).apply {
        text = label
        setTextSize(TypedValue.COMPLEX_UNIT_PX, 28f)
        setOnClickListener { onClick() }
    }

    private data class Probe(val lemonade: String, val models: List<String>)
}
