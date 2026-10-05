package com.geeui.voiceemo

import android.content.Context
import com.leitianpai.robotsdk.RobotService
import com.leitianpai.robotsdk.commandlib.Light
import com.leitianpai.robotsdk.message.ActionMessage
import com.leitianpai.robotsdk.message.AntennaLightMessage
import com.leitianpai.robotsdk.message.AntennaMessage

/** RobotSDK 2.5. Opens the servo rail once. Does not walk and does not take the mic. */
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
        if (pose.action != null) {
            val move = ActionMessage()
            move.set(pose.action, 3, 1)
            robot.robotActionCommand(move)
        }
        if (pose.sound != null) robot.robotControlSound(pose.sound)
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
        "GREEN" -> Light.GREEN
        "BLUE" -> Light.BLUE
        "ORANGE" -> Light.ORANGE
        "WHITE" -> Light.WHITE
        "YELLOW" -> Light.YELLOW
        "PURPLE" -> Light.PURPLE
        "CYAN" -> Light.CYAN
        "BLACK" -> Light.BLACK
        else -> null
    }
}
