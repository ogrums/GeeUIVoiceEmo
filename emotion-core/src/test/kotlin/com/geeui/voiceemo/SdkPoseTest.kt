package com.geeui.voiceemo

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class SdkPoseTest {
    @Test
    fun angry_uses_red_and_a_right_ear_gesture() {
        val pose = SdkMap.pose(Emotion.ANGRY)
        assertEquals("h0001", pose.faceId)
        assertEquals(2, pose.earCmd)
        assertEquals("RED", pose.light)
        assertTrue(pose.earAngle in 0..90)
    }

    @Test
    fun neutral_closes_the_light() {
        val pose = SdkMap.pose(Emotion.NEUTRAL)
        assertEquals("h0189", pose.faceId)
        assertNull(pose.light)
    }
}
