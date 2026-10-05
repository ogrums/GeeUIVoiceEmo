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
                                    ├─ BodyPose ──▶ setExpression + EARW + LED
                                    └─ TtsRoute ──▶ CosyVoice :13306 or Lemonade Kokoro :13305
```

GeeUIVoice already posts the WAV to Lemonade `/audio/transcriptions` and streams `/chat/completions`. The chat system prompt asks for one JSON object before the spoken sentence:

```json
{"emotion":"sad","say":"D'accord, j'y vais doucement."}
```

Skills (`avance`, `recule`) stay in GeeUIVoice and do not update the mood.

## Labels

`neutral` `happy` `sad` `angry` `fear` `surprise`.

Faces are RobotSDK tags, not invented ids: happy `h0006`, angry `h0001`, surprise `h0046`, fear `h0134`, sad `h0211`, neutral `h0189`. Ears are angles for servos 5 (right) and 6 (left), sent later as `AT+EARW`. LED is a color name; the AIDL payload is filled by the app adapter.

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

## Kotlin

`emotion-core` is plain Kotlin, same idea as `voice-core`. Copy the Gradle wrapper from GeeUIVoice, then `./gradlew :emotion-core:test`.

The Android adapter is intentionally not in this commit. It binds `ILetianpaiService` the way `AidlBus` does, and adds ear and LED. Face ids already go through `setExpression("controlFace", faceId)`.
