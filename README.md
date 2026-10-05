# GeeUIVoiceEmo

Emotion layer for the RUX robot. Separate from [GeeUIVoice](https://github.com/ogrums/GeeUIVoice). GeeUIVoice keeps the mic, the VAD and Lemonade. This repo decides the affect, holds a mood, and tells the body and the TTS what to do.

Nothing here calls AWS, Azure or iFlytek. The LAN box is a Ryzen AI 9 HX 470 with a Radeon 860M and 96 Go of system RAM. That is not 64 Go of VRAM. Kokoro stays the default. CosyVoice is the expressive path.

## Decisions

| Choice | Taken |
|---|---|
| Repo | `ogrums/GeeUIVoiceEmo`, does not modify GeeUIVoice |
| Body | RobotSDK `RobotService`, not raw AT |
| Scope | voice + face + ears + antenna light + a small gesture + a built-in sound |
| User affect | audio classifier and transcript |
| TTS | CosyVoice if the label is not neutral, the clause is short, and the sidecar is healthy. Else Kokoro |
| Boot | optional |

## Body

One table, `SdkMap`. `EmotionBus` applies it. Faces come from the Feishu map. Lights are the 2.5 AAR constants. Actions and sounds are the published lists. Neutral does not move and does not play a sound.

| Emotion | Face | Ears | Light | Action | Sound |
|---|---|---|---|---|---|
| happy | `h0006` 大笑 | cmd 3, 2 steps, 250 ms, 60° | `YELLOW` | 77 yeah | `a0032` |
| sad | `h0119` 哭泣 | cmd 1, 1 step, 500 ms, 40° | `BLUE` | 20 rest | `a0086` |
| angry | `h0001` 愤怒 | cmd 2, 2 steps, 200 ms, 70° | `RED` | 15 stomp | `a0020` |
| fear | `h0133` 害怕 | cmd 1, 1 step, 400 ms, 30° | `CYAN` | 44 dodge | `a0037` |
| surprise | `h0046` 惊讶 | cmd 3, 1 step, 150 ms, 90° | `WHITE` | 76 nod | `a0095` |
| neutral | `h0059` 常规环 | cmd 1, angle 0 | off | none | none |

`robotOpenMotor()` once. `robotStartExpression` once, then `robotChangeExpression`. No `AT+MOTORW`. No `robotPlayTTs`.

Put `RobotSdk-release.2.5.aar` in `app/libs/` before building. It is not committed.

```text
adb shell am startservice -n com.geeui.voiceemo/.EmotionService -e emotion sad
adb shell am startservice -n com.geeui.voiceemo/.EmotionService -e sidecar http://<pc>:13306
```

## Sidecar

`python3 sidecar/emo_server.py`. Blank env falls back to the default.

| Variable | Default |
|---|---|
| `EMO_HOST` | `0.0.0.0` |
| `EMO_PORT` | `13306` |
| `LEMONADE_HOST` | `http://127.0.0.1:13305` |
| `KOKORO_MODEL` | `kokoro` |
| `KOKORO_VOICE_FR` | `ff_siwis` |
| `KOKORO_VOICE_EN` | `af_heart` |
| `COSYVOICE_HOST` | empty, so CosyVoice stays off |
| `COSYVOICE_MODEL` | `cosyvoice2` |
| `EMO_AUDIO_CMD` | empty, audio vote is neutral |
| `EMO_AUDIO_MODEL` | `emotion2vec` |
| `EMO_CHAT_MODEL` | `llama` |

`GET /config` returns the resolved values. `POST /route` returns `engine`, `host`, `model` and `voice`. CosyVoice is chosen only if `COSYVOICE_HOST` is set, the label is not neutral, and the clause is at most 180 characters. Otherwise Kokoro on Lemonade.

The Android service takes the same names as extras (`sidecar`, `lemonade`, `cosyvoice`, …). An empty extra uses the default.

## Core

`emotion-core` is plain Kotlin. `./gradlew :emotion-core:test`. Copy the Gradle wrapper from GeeUIVoice. SDK 30 to build `app/`.
