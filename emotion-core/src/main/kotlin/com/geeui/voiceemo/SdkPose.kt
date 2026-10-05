package com.geeui.voiceemo

/**
 * What RobotSDK expects. Ears are a gesture, not a servo angle.
 * cmd: 1 both ears left, 2 both ears right, 3 both ears the other way (demo uses 3).
 * angle is clamped to 0..90 by the firmware.
 */
data class SdkPose(
    val faceId: String,
    val earCmd: Int,
    val earStep: Int,
    val earSpeedMs: Int,
    val earAngle: Int,
    val light: String?,
)

object SdkMap {
    fun pose(emotion: Emotion): SdkPose = when (emotion) {
        Emotion.HAPPY -> SdkPose("h0006", 3, 2, 250, 60, "YELLOW")
        Emotion.SAD -> SdkPose("h0119", 1, 1, 500, 40, "BLUE")
        Emotion.ANGRY -> SdkPose("h0001", 2, 2, 200, 70, "RED")
        Emotion.FEAR -> SdkPose("h0133", 1, 1, 400, 30, "WHITE")
        Emotion.SURPRISE -> SdkPose("h0046", 3, 1, 150, 90, "WHITE")
        Emotion.NEUTRAL -> SdkPose("h0059", 1, 1, 400, 0, null)
    }
}
