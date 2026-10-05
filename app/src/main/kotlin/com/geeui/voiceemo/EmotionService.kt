package com.geeui.voiceemo

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.IBinder
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Applies the sidecar mood to the body.
 *
 * adb shell am startservice -n com.geeui.voiceemo/.EmotionService \
 *   -e sidecar http://192.168.1.20:13306
 *
 * One-shot, no poll: -e emotion sad
 */
class EmotionService : Service() {
    private val running = AtomicBoolean(false)
    private val pool = Executors.newSingleThreadExecutor()
    private var bus: EmotionBus? = null
    private var last = ""

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(42, note())
        if (bus == null) bus = EmotionBus(this)
        val once = intent?.getStringExtra("emotion")
        if (!once.isNullOrBlank()) {
            show(Emotion.parse(once))
            return START_STICKY
        }
        val sidecar = intent?.getStringExtra("sidecar") ?: return START_STICKY
        if (running.compareAndSet(false, true)) {
            pool.execute { poll(sidecar.trimEnd('/')) }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        running.set(false)
        bus?.close(this)
        pool.shutdownNow()
        super.onDestroy()
    }

    private fun poll(base: String) {
        while (running.get()) {
            val label = readMood(base)
            if (label != null && label != last) {
                last = label
                show(Emotion.parse(label))
            }
            Thread.sleep(400)
        }
    }

    private fun show(emotion: Emotion) {
        bus?.apply(BodyMap.pose(emotion), emotion)
    }

    private fun readMood(base: String): String? {
        return try {
            val conn = URL("$base/mood").openConnection() as HttpURLConnection
            conn.connectTimeout = 1_000
            conn.readTimeout = 1_000
            conn.requestMethod = "GET"
            if (conn.responseCode !in 200..299) return null
            val raw = conn.inputStream.readBytes().toString(Charsets.UTF_8)
            val key = "\"emotion\":"
            val at = raw.indexOf(key)
            if (at < 0) null else unquote(raw.substring(at + key.length).trimStart())
        } catch (_: Exception) {
            null
        }
    }

    private fun unquote(raw: String): String {
        if (raw.isEmpty() || raw[0] != '"') return ""
        val end = raw.indexOf('"', 1)
        return if (end < 0) "" else raw.substring(1, end)
    }

    private fun note(): Notification {
        val mgr = getSystemService(NotificationManager::class.java)
        mgr.createNotificationChannel(
            NotificationChannel("emo", "GeeUIVoiceEmo", NotificationManager.IMPORTANCE_LOW),
        )
        return Notification.Builder(this, "emo")
            .setContentTitle("GeeUIVoiceEmo")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .build()
    }
}
