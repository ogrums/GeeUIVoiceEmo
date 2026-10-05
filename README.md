# GeeUIVoiceEmo

Emotion layer for the RUX robot. Separate from [GeeUIVoice](https://github.com/ogrums/GeeUIVoice). GeeUIVoice keeps the mic, the VAD and Lemonade. This repo decides the affect, holds a mood, and tells the body and the TTS what to do.

Nothing here calls AWS, Azure or iFlytek. The LAN box is a Ryzen AI 9 HX 470 with a Radeon 860M and 96 Go of system RAM. That is not 64 Go of VRAM. Bandwidth is dual-channel, about 90 Go/s. Kokoro stays the default. CosyVoice is the expressive path, with a timeout back to Kokoro.

## Decisions

| Choice | Taken |
|---|---|
| Repo | `ogrums/GeeUIVoiceEmo`, does not modify GeeUIVoice |
| Scope | voice + face + ears + LED + mood that decays |
| User affect | audio classifier and transcript, LLM breaks a tie |
| TTS | CosyVoice if the label is not neutral, the clause is short, and the sidecar is healthy. Else Kokoro |
| Boot | optional. Robot still walks and shows faces if this service is down |

## Loop

```text
WAV of the turn  ──▶  POST /affect/audio     (emotion2vec, parallel)
transcript       ──▶  POST /affect/text      (label from the chat JSON)
                         └─ Arbiter ──▶ Mood (half-life 45 s)
                                    ├─ BodyPose ──▶ EmotionService ──▶ ILetianpaiService
                                    └─ TtsRoute ──▶ CosyVoice :13306 or Lemonade Kokoro :13305
```

GeeUIVoice already posts the WAV to Lemonade `/audio/transcriptions` and streams `/chat/completions`. The chat system prompt asks for one JSON object before the spoken sentence:

```json
{"emotion":"sad","say":"D'accord, j'y vais doucement."}
```

Skills (`avance`, `recule`) stay in GeeUIVoice and do not update the mood.

## Labels

`neutral` `happy` `sad` `angry` `fear` `surprise`.

Faces are RobotSDK tags: happy `h0006`, angry `h0001`, surprise `h0046`, fear `h0134`, sad `h0211`, neutral `h0189`. Ears are angles for servos 5 (right) and 6 (left). LED is `controlAntennaLight` on / off / twinkle. The AIDL name has no color field.

## Android adapter

`app/` is `com.geeui.voiceemo`. It does not open the microphone. `EmotionWire` builds the calls, `EmotionBus` binds `ILetianpaiService` the same way as GeeUIVoice `AidlBus`.

| Call | Payload |
|---|---|
| `setExpression("controlFace", id)` | face tag |
| `setMcuCommand("ear", "AT+MOTORW,5,0,<angle>\r\n")` | right ear, type 0 = angle |
| `setMcuCommand("ear", "AT+MOTORW,6,0,<angle>\r\n")` | left ear |
| `setMcuCommand("controlAntennaLight", {antenna_light})` | off, on, or twinkle |

`ear` is not a name in the MCU vocab. If the service ignores it, the same AT string still has to be written on the serial path (`AT+MOTORW`). Face and antenna light use names already observed.

```text
adb shell am startservice -n com.geeui.voiceemo/.EmotionService -e emotion sad
adb shell am startservice -n com.geeui.voiceemo/.EmotionService -e sidecar http://<pc>:13306
```

The poll reads `GET /mood` every 400 ms and applies only when the label changes. Needs SDK 30 to build. Copy the Gradle wrapper from GeeUIVoice.

## Sidecar

`sidecar/emo_server.py` is stdlib only. It owns the mood and the route. Audio classification is a hook: `EMO_AUDIO_CMD` receives a wav path and prints `label confidence`. Empty hook returns neutral, so text still drives the mood.

```text
python3 sidecar/emo_server.py --port 13306
```

| Call | Body | Result |
|---|---|---|
| `POST /affect/text` | `{"label":"sad","confidence":0.8}` | blended mood |
| `POST /affect/audio` | wav bytes | hook, else neutral |
| `GET /mood` | | current label, intensity, age |
| `POST /route` | `{"text":"...","emotion":"sad"}` | `kokoro` or `cosyvoice` |

CosyVoice itself is not vendored. Point `COSYVOICE_URL` at a local OpenAI-shaped `/audio/speech`. On non-2xx or timeout, the caller uses Lemonade Kokoro (`ff_siwis` / `af_heart`).

## Kotlin core

`emotion-core` is plain Kotlin. `./gradlew :emotion-core:test`.
