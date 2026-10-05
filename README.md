# GeeUIVoiceEmo

Emotion layer for the RUX robot. Separate from [GeeUIVoice](https://github.com/ogrums/GeeUIVoice). GeeUIVoice keeps the mic, the VAD and Lemonade. This repo decides the affect, holds a mood, and tells the body and the TTS what to do.

Nothing here calls AWS, Azure or iFlytek. The LAN box is a Ryzen AI 9 HX 470 with a Radeon 860M and 96 Go of system RAM. That is not 64 Go of VRAM. Kokoro stays the default. CosyVoice is the expressive path.

## Decisions

| Choice | Taken |
|---|---|
| Repo | `ogrums/GeeUIVoiceEmo`, does not modify GeeUIVoice |
| Body | RobotSDK `RobotService`, not raw AT |
| Scope | voice + face + ears + antenna light + mood that decays |
| User affect | audio classifier and transcript |
| TTS | CosyVoice if the label is not neutral, the clause is short, and the sidecar is healthy. Else Kokoro |
| Boot | optional |

## Body

`EmotionBus` uses the same entry as DemoForRobotSDK.

| Emotion | Face | Ears `robotAntennaMotion` | Light |
|---|---|---|---|
| happy | `h0006` | cmd 3, step 2, 250 ms, 60° | `Light.YELLOW` |
| sad | `h0211` | cmd 1, step 1, 500 ms, 40° | `Light.BLUE` |
| angry | `h0001` | cmd 2, step 2, 200 ms, 70° | `Light.RED` |
| fear | `h0134` | cmd 1, step 1, 400 ms, 30° | `Light.WHITE` |
| surprise | `h0046` | cmd 3, step 1, 150 ms, 90° | `Light.WHITE` |
| neutral | `h0189` | cmd 1, angle 0 | `robotCloseAntennaLight` |

`robotOpenMotor()` once. `robotStartExpression` once, then `robotChangeExpression`. Ear cmd is the SDK gesture (1 left, 2 right, 3 the demo gesture), angle clamped 0–90. No `AT+MOTORW`.

Put `RobotSdk-release.2.5.aar` in `app/libs/` before building. It is not committed.

```text
adb shell am startservice -n com.geeui.voiceemo/.EmotionService -e emotion sad
adb shell am startservice -n com.geeui.voiceemo/.EmotionService -e sidecar http://<pc>:13306
```

## Sidecar

`python3 sidecar/emo_server.py --port 13306`

| Call | Body |
|---|---|
| `POST /affect/text` | `{"label":"sad","confidence":0.8}` |
| `POST /affect/audio` | wav bytes, or neutral if `EMO_AUDIO_CMD` is unset |
| `GET /mood` | label + intensity |
| `POST /route` | `kokoro` or `cosyvoice` |

## Core

`emotion-core` is plain Kotlin. `./gradlew :emotion-core:test`. Copy the Gradle wrapper from GeeUIVoice. SDK 30 to build `app/`.
