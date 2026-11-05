package com.geeui.voiceemo

import kotlin.test.Test
import kotlin.test.assertEquals

class EmotionFusionTest {
    @Test
    fun agreeing_votes_add_up() {
        val r = EmotionFusion(clock = { 0L }).fuse(Emotion.HAPPY, 0.5, Emotion.HAPPY, true)
        assertEquals(Emotion.HAPPY, r.emotion)
        assertEquals(0.7, r.score, 1e-9)
    }

    @Test
    fun below_threshold_is_neutral() {
        val f = EmotionFusion(clock = { 0L })
        assertEquals(Emotion.NEUTRAL, f.fuse(Emotion.ANGRY, 0.8, Emotion.HAPPY, true).emotion)
        assertEquals(Emotion.NEUTRAL, f.fuse(Emotion.SAD, 0.5, Emotion.NEUTRAL, false).emotion)
        assertEquals(Emotion.SAD, f.fuse(Emotion.SAD, 0.9, Emotion.HAPPY, true).emotion)
    }

    @Test
    fun threshold_is_0_45() {
        // audio-only SAD at 0.75 -> 0.6 * 0.75 = 0.45, exactly on threshold
        val f = EmotionFusion(clock = { 0L })
        // Just below: 0.74 * 0.6 = 0.444
        assertEquals(Emotion.NEUTRAL, f.fuse(Emotion.SAD, 0.74, Emotion.NEUTRAL, false).emotion)
        // At threshold: 0.75 * 0.6 = 0.45
        assertEquals(Emotion.SAD, f.fuse(Emotion.SAD, 0.75, Emotion.NEUTRAL, false).emotion)
    }

    @Test
    fun cooldown_applies_to_non_neutral_only() {
        var now = 10_000L
        val f = EmotionFusion(clock = { now })
        assertEquals(Emotion.HAPPY, f.fuse(Emotion.HAPPY, 1.0, Emotion.HAPPY, true).emotion)
        now += 1_000
        assertEquals(Emotion.NEUTRAL, f.fuse(Emotion.SAD, 1.0, Emotion.SAD, true).emotion)
        now += 1_000
        assertEquals(Emotion.NEUTRAL, f.fuse(Emotion.NEUTRAL, 1.0, Emotion.NEUTRAL, true).emotion)
        now += 2_000
        assertEquals(Emotion.SAD, f.fuse(Emotion.SAD, 1.0, Emotion.SAD, true).emotion)
    }
}
