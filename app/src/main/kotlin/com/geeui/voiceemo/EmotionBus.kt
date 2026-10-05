package com.geeui.voiceemo

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.IBinder
import com.renhejia.robot.letianpaiservice.ILetianpaiService

/** Sends a BodyPose. Does not open the mic and does not walk. */
class EmotionBus(context: Context) : ServiceConnection {
    private var api: ILetianpaiService? = null
    private var pending: List<WireCall> = emptyList()

    init {
        val intent = Intent("android.intent.action.LETIANPAI")
            .setPackage("com.renhejia.robot.letianpaiservice")
        context.bindService(intent, this, Context.BIND_AUTO_CREATE)
    }

    override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
        api = ILetianpaiService.Stub.asInterface(service)
        pending.forEach { send(it) }
        pending = emptyList()
    }

    override fun onServiceDisconnected(name: ComponentName?) {
        api = null
    }

    fun apply(pose: BodyPose, emotion: Emotion) {
        EmotionWire.calls(pose, emotion).forEach { call ->
            if (api == null) pending = pending + call else send(call)
        }
    }

    fun close(context: Context) {
        runCatching { context.unbindService(this) }
        api = null
    }

    private fun send(call: WireCall) {
        val svc = api ?: return
        when (call.method) {
            "setExpression" -> svc.setExpression(call.command, call.data)
            else -> svc.setMcuCommand(call.command, call.data)
        }
    }
}
