package com.geeui.voiceemo

/**
 * Face ids are RobotSDK expression tags.
 * Ears: servo 5 right, servo 6 left. 90 is rest. Higher is raised.
 */
data class BodyPose(
    val faceId: String,
    val earRight: Int,
    val earLeft: Int,
    val led: String,
)

object BodyMap {
    fun pose(emotion: Emotion): BodyPose = when (emotion) {
        Emotion.HAPPY -> BodyPose("h0006", 130, 130, "amber")
        Emotion.SAD -> BodyPose("h0211", 50, 50, "blue")
        Emotion.ANGRY -> BodyPose("h0001", 40, 140, "red")
        Emotion.FEAR -> BodyPose("h0134", 60, 60, "dim")
        Emotion.SURPRISE -> BodyPose("h0046", 150, 150, "white")
        Emotion.NEUTRAL -> BodyPose("h0189", 90, 90, "off")
    }
}
