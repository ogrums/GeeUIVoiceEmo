package com.geeui.voiceemo

/** One call on ILetianpaiService. Built here so the Android module only sends. */
data class WireCall(val method: String, val command: String, val data: String)

/**
 * Face goes through setExpression, same as GeeUIVoice AidlBus.
 * Ears are AT+MOTORW type 0 (angle) on servos 5 and 6.
 * LED uses the AIDL name controlAntennaLight. Color is not in that API:
 * off/dim -> off, anything else -> on, surprise twinkles.
 */
object EmotionWire {
    fun calls(pose: BodyPose, emotion: Emotion): List<WireCall> {
        val light = when {
            pose.led == "off" || pose.led == "dim" -> "off"
            emotion == Emotion.SURPRISE -> "twinkle"
            else -> "on"
        }
        return listOf(
            WireCall("setExpression", "controlFace", pose.faceId),
            WireCall("setMcuCommand", "ear", "AT+MOTORW,5,0,${pose.earRight}\r\n"),
            WireCall("setMcuCommand", "ear", "AT+MOTORW,6,0,${pose.earLeft}\r\n"),
            WireCall("setMcuCommand", "controlAntennaLight", """{"antenna_light":"$light"}"""),
        )
    }
}
