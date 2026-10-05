package com.geeui.voiceemo

/** One spoken reply after the arbiter and the mood. Skills do not call this. */
data class EmotionTurn(
    val say: String,
    val user: Affect,
    val mood: Affect,
    val pose: BodyPose,
    val engine: TtsEngine,
)

object EmotionPipeline {
    fun turn(
        say: String,
        audio: Affect,
        text: Affect,
        mood: Mood,
        now: Long,
        sidecarOkAt: Long,
    ): EmotionTurn {
        val user = Arbiter.merge(audio, text)
        mood.observe(user, now)
        val felt = mood.snapshot(now)
        val shown = if (felt.intensity >= 0.25f) felt.emotion else Emotion.NEUTRAL
        return EmotionTurn(
            say = say,
            user = user,
            mood = felt,
            pose = BodyMap.pose(shown),
            engine = TtsRoute.choose(say, shown, sidecarOkAt, now),
        )
    }
}
