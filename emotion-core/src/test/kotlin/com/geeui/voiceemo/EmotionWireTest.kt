package com.geeui.voiceemo

import kotlin.test.Test
import kotlin.test.assertEquals

class EmotionWireTest {
    @Test
    fun sad_pose_is_cry_face_low_ears_and_led_on() {
        val calls = EmotionWire.calls(BodyMap.pose(Emotion.SAD), Emotion.SAD)
        assertEquals("setExpression", calls[0].method)
        assertEquals("h0211", calls[0].data)
        assertEquals("AT+MOTORW,5,0,50\r\n", calls[1].data)
        assertEquals("AT+MOTORW,6,0,50\r\n", calls[2].data)
        assertEquals("""{"antenna_light":"on"}""", calls[3].data)
    }

    @Test
    fun neutral_turns_the_antenna_light_off() {
        val calls = EmotionWire.calls(BodyMap.pose(Emotion.NEUTRAL), Emotion.NEUTRAL)
        assertEquals("h0189", calls[0].data)
        assertEquals("""{"antenna_light":"off"}""", calls[3].data)
    }
}
