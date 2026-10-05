package com.geeui.voiceemo

import android.content.Context
import com.leitianpai.robotsdk.RobotService
import com.leitianpai.robotsdk.commandlib.Light
import com.leitianpai.robotsdk.message.AntennaLightMessage
import com.leitianpai.robotsdk.message.AntennaMessage

/** RobotSDK only. Opens the servo rail once. Does not walk and does not take the mic. */
class EmotionBus(context: Context) {
    private val robot = RobotService.getInstance(context.applicationContext)
    private var motorOn = false
    private var expressionOn = false

    fun apply(emotion: Emotion) {
        val pose = SdkMap.pose(emotion)
        if (!motorOn) {
            robot.robotOpenMotor()
            motorOn = true
        }
        if (!expressionOn) {
            robot.robotStartExpression(pose.faceId)
            expressionOn = true
        } else {
            robot.robotChangeExpression(pose.faceId)
        }
        val ears = AntennaMessage()
        ears.set(pose.earCmd, pose.earStep, pose.earSpeedMs, pose.earAngle)
        robot.robotAntennaMotion(ears)
        val color = light(pose.light)
        if (color == null) {
            robot.robotCloseAntennaLight()
        } else {
            val lamp = AntennaLightMessage()
            lamp.set(color)
            robot.robotAntennaLight(lamp)
        }
    }

    fun close() {
        if (expressionOn) robot.robotStopExpression()
        robot.robotCloseAntennaLight()
        robot.unbindService()
        motorOn = false
        expressionOn = false
    }

    private fun light(name: String?): Int? = when (name) {
        "RED" -> Light.RED
        "BLUE" -> Light.BLUE
        "WHITE" -> Light.WHITE
        "YELLOW" -> Light.YELLOW
        else -> null
    }
}
