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
adb shell am startservice -n com.geeui.voiceemo/.EmotionService -e sidecar http://nimbus:13306
```

## Sidecar

`python3 sidecar/emo_server.py`. Blank env falls back to the default.

| Variable | Default |
|---|---|
| `EMO_HOST` | `http://nimbus:13306` |
| `LEMONADE_HOST` | `http://nimbus:13305/api/v1` |
| `KOKORO_MODEL` | `kokoro-v1` |
| `KOKORO_VOICE_FR` | `ff_siwis` |
| `KOKORO_VOICE_EN` | `af_heart` |
| `COSYVOICE_HOST` | empty, so CosyVoice stays off |
| `COSYVOICE_MODEL` | `cosyvoice2` |
| `EMO_AUDIO_CMD` | empty, audio vote is neutral |
| `EMO_AUDIO_MODEL` | `emotion2vec` |
| `EMO_AUDIO_ONNX` | vide ; chemin du backbone ONNX emotion2vec+ |
| `EMO_AUDIO_HEAD` | vide ; chemin de la tête JSON `weight`/`bias`/`labels` |
| `EMO_ORT_PROVIDERS` | vide ; choix automatique, sinon liste séparée par des virgules |
| `EMO_AUDIO_LABELS` | non défini : labels du JSON, sinon ordre emotion2vec+ historique ; prioritaire si défini explicitement |
| `EMO_STT_MODEL` | `Whisper-Small` |
| `EMO_CHAT_MODEL` | `gemma4e-flash-e2b-FLM` |

`GET /config` returns the resolved values. `POST /route` returns `engine`, `host`, `model` and `voice`. CosyVoice is chosen only if `COSYVOICE_HOST` is set, the label is not neutral, and the clause is at most 180 characters. Otherwise Kokoro on Lemonade.

The Android service takes the same names as extras (`sidecar`, `lemonade`, `cosyvoice`, …). An empty extra uses the default.

## Core

`emotion-core` is plain Kotlin. `./gradlew :emotion-core:test`. Copy the Gradle wrapper from GeeUIVoice. SDK 30 to build `app/`.

## Emotion gateway

The unchanged stdlib server also exposes OpenAI-compatible routes on port 13306: `POST /v1/audio/transcriptions`, `POST /v1/chat/completions` (byte-preserving SSE), `POST /v1/audio/speech`, and `GET /v1/models`. They forward to `LEMONADE_HOST`. Transcription classifies the multipart WAV while Whisper runs and adds the audio-only `emotion` and `emotion_confidence` to its JSON. Fusion happens on the robot in `EmotionFusion` (emotion-core), the single source of truth: audio emotion 0.6 / LLM reply tag from `EmotionTagParser` 0.4, neutral below a best score of 0.45, and repeated non-neutral reactions suppressed for 4 s.

### Classifieur ONNX et diagnostic

Installation et téléchargement du modèle de référence (les fichiers restent hors du dépôt) :

```bash
python3 -m venv .venv
.venv/bin/pip install onnxruntime numpy
mkdir -p models
curl -fL -o models/emotion2vec_plus_base.onnx \
  https://huggingface.co/ziyu12345/emotion2vec_plus_base_onnx/resolve/main/emotion2vec_plus_base.onnx
curl -fL -o models/emotion2vec_head.json \
  https://huggingface.co/ziyu12345/emotion2vec_plus_base_onnx/resolve/main/emotion2vec_head.json
EMO_AUDIO_ONNX="$PWD/models/emotion2vec_plus_base.onnx" \
EMO_AUDIO_HEAD="$PWD/models/emotion2vec_head.json" \
.venv/bin/python sidecar/emo_server.py
```

Le WAV doit être PCM 16 kHz mono 16 bits ; en dessous d'une seconde, le vote reste `neutral`, confiance 0. Le backbone reçoit un tenseur `float32` de forme `[1, nombre_échantillons]`, plus éventuellement la fréquence d'échantillonnage en second argument. Les caractéristiques sont moyennées avec NumPy avant la couche linéaire. Les labels de `EMO_AUDIO_HEAD` sont normalisés (`快乐/happy` devient `happy`) et pris par défaut ; `EMO_AUDIO_LABELS` explicite est prioritaire, sinon l'ordre historique `angry, disgusted, fearful, happy, neutral, other, sad, surprised, unknown` est le dernier repli. Un modèle produisant directement les logits n'a pas besoin de tête.

`GET /v1/emotion/status` expose le chemin et l'existence du modèle, la version ONNX Runtime, les fournisseurs disponibles/sélectionnés, la tête et ses labels, la session, la dernière erreur et les compteurs `classifications`/`failures`. Le démarrage charge le modèle immédiatement et journalise `ONNX prêt` ou un traceback (une fois par erreur distincte). Les transcriptions ajoutent `emotion_source` : `onnx` pour une vraie classification, `fallback` pour un clip court, un modèle absent/en échec ou le hook `EMO_AUDIO_CMD`. Pour diagnostiquer :

```bash
curl -s http://127.0.0.1:13306/v1/emotion/status | python3 -m json.tool
```

Vérifier `session_loaded=true`, `head_loaded=true`, `last_error=null`, puis `emotion_source=onnx` dans une transcription d'au moins une seconde. Les paquets `onnxruntime` (CPU) et `onnxruntime-gpu` (CUDA) s'installent séparément selon la machine.

`FRENCH_EMOTION_SYSTEM_PROMPT` instructs a chat model to begin with one emotion tag. `EmotionTagParser` consumes that tag across streaming boundaries and removes it; `finish()` flushes an incomplete tag as ordinary text. Run Python checks with `python3 -m unittest discover -s sidecar -v`; Kotlin checks remain `./gradlew :emotion-core:test` when the wrapper is present.

### Campagne de test du sidecar

Le cahier de test et son automate couvrent les six émotions, les labels bruts, les erreurs audio/amont, les proxies et la latence. La campagne mock fonctionne entièrement hors ligne avec la bibliothèque standard Python :

```bash
python3 sidecar/tests/run_emotion_tests.py --mode mock
python3 sidecar/tests/run_emotion_tests.py --mode live --url http://nimbus:13306 --audio-dir sidecar/tests/samples/ravdess
```

Consulter [`sidecar/tests/CAHIER_DE_TEST.md`](sidecar/tests/CAHIER_DE_TEST.md) pour le détail, les rapports et le téléchargement sélectif d'échantillons RAVDESS sous CC BY-NC-SA 4.0.
