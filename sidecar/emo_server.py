#!/usr/bin/env python3
"""Mood, route, and host config for GeeUIVoiceEmo. Stdlib only.

Unset or blank variables fall back to the defaults below.
Lemonade stays the Kokoro path. CosyVoice is a second host, off unless set.
"""

import array
import concurrent.futures
import io
import re
import json
import math
import os
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

LABELS = {"neutral", "happy", "sad", "angry", "fear", "surprise"}
HALF_LIFE = 45.0
BLEND = 0.6
MAX_CHARS = 180
ONNX_LABELS = [
    "angry", "disgusted", "fearful", "happy", "neutral", "other", "sad",
    "surprised", "unknown",
]
PROVIDER_ORDER = [
    "CUDAExecutionProvider", "ROCMExecutionProvider", "MIGraphXExecutionProvider",
    "DmlExecutionProvider", "VitisAIExecutionProvider", "CPUExecutionProvider",
]

DEFAULTS = {
    "EMO_HOST": "http://nimbus:13306",
    "LEMONADE_HOST": "http://nimbus:13305/api/v1",
    "KOKORO_MODEL": "kokoro-v1",
    "KOKORO_VOICE_FR": "ff_siwis",
    "KOKORO_VOICE_EN": "af_heart",
    "COSYVOICE_HOST": "",
    "COSYVOICE_MODEL": "cosyvoice2",
    "EMO_AUDIO_CMD": "",
    "EMO_AUDIO_MODEL": "emotion2vec",
    "EMO_AUDIO_ONNX": "",
    "EMO_ORT_PROVIDERS": "",
    "EMO_AUDIO_LABELS": ",".join(ONNX_LABELS),
    "EMO_COOLDOWN_S": "4",
    "EMO_STT_MODEL": "whisper-small",
    "EMO_CHAT_MODEL": "gemma4e-flash-e2b-FLM",
}


def env(name):
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return DEFAULTS[name]
    return raw.strip()


def config():
    cosy = env("COSYVOICE_HOST")
    emo = env("EMO_HOST").rstrip("/")
    parsed = urlparse(emo if "://" in emo else "http://" + emo)
    return {
        "emo_host": emo,
        "bind_port": parsed.port or 13306,
        "lemonade_host": env("LEMONADE_HOST").rstrip("/"),
        "kokoro_model": env("KOKORO_MODEL"),
        "kokoro_voice_fr": env("KOKORO_VOICE_FR"),
        "kokoro_voice_en": env("KOKORO_VOICE_EN"),
        "cosyvoice_host": cosy.rstrip("/") if cosy else "",
        "cosyvoice_model": env("COSYVOICE_MODEL"),
        "cosyvoice_enabled": bool(cosy),
        "audio_cmd": env("EMO_AUDIO_CMD"),
        "audio_model": env("EMO_AUDIO_MODEL"),
        "audio_onnx": env("EMO_AUDIO_ONNX"),
        "ort_providers": env("EMO_ORT_PROVIDERS"),
        "audio_labels": env("EMO_AUDIO_LABELS"),
        "cooldown_s": env("EMO_COOLDOWN_S"),
        "stt_model": env("EMO_STT_MODEL"),
        "chat_model": env("EMO_CHAT_MODEL"),
    }


mood = {"emotion": "neutral", "intensity": 0.0, "at": time.time()}


def parse_label(raw):
    key = (raw or "").strip().lower()
    aliases = {"cheerful": "happy", "joy": "happy", "sadness": "sad",
               "anger": "angry", "afraid": "fear", "fearful": "fear",
               "surprised": "surprise"}
    key = aliases.get(key, key)
    return key if key in LABELS else "neutral"


def decay(now):
    elapsed = max(0.0, now - mood["at"])
    if elapsed and mood["intensity"]:
        mood["intensity"] *= 0.5 ** (elapsed / HALF_LIFE)
        if mood["intensity"] < 0.08:
            mood["emotion"] = "neutral"
            mood["intensity"] = 0.0
    mood["at"] = now


def observe(label, confidence, now):
    decay(now)
    confidence = max(0.0, min(1.0, float(confidence)))
    if confidence <= 0:
        return
    weight = BLEND * confidence
    if label == mood["emotion"] or mood["emotion"] == "neutral":
        mood["emotion"] = label
        mood["intensity"] = max(0.0, min(1.0, mood["intensity"] * (1 - weight) + weight))
    elif weight > mood["intensity"]:
        mood["emotion"] = label
        mood["intensity"] = weight
    else:
        mood["intensity"] *= 1 - weight
    if mood["intensity"] < 0.08:
        mood["emotion"] = "neutral"
        mood["intensity"] = 0.0
    mood["at"] = now


def select_providers(available, override=""):
    """Prefer an accelerator, but only when the installed runtime provides it."""
    chosen = [p.strip() for p in override.split(",") if p.strip()]
    return chosen or [p for p in PROVIDER_ORDER if p in available][:1]


def onnx_audio_vote(wav):
    """Classify PCM WAV with a lazily loaded ONNX session; failures stay neutral."""
    model = env("EMO_AUDIO_ONNX")
    if not model:
        return audio_command_vote(wav)
    try:
        import onnxruntime as ort
    except ImportError:
        log("onnxruntime is unavailable; falling back to EMO_AUDIO_CMD")
        return audio_command_vote(wav)
    try:
        with wave.open(io.BytesIO(wav), "rb") as pcm:
            rate = pcm.getframerate()
            if rate != 16000 or pcm.getnchannels() != 1 or pcm.getsampwidth() != 2:
                raise ValueError("expected 16 kHz, mono, 16-bit PCM WAV")
            frames = pcm.getnframes()
            if frames < rate:
                return "neutral", 0.0
            samples = array.array("h", pcm.readframes(frames))
        if sys.byteorder != "little":
            samples.byteswap()
        signal = [sample / 32768.0 for sample in samples]
        inputs = [signal, 16000]
        logits = _onnx_session(model).run(None, dict(zip(_onnx_input_names(), inputs)))[0][0]
        confidence, index = softmax(logits)
        return parse_label(_onnx_labels()[index]), confidence
    except Exception as exc:
        log(f"ONNX audio classification failed: {exc}")
        return audio_command_vote(wav)


_onnx = None
_onnx_names = None
_onnx_lock = threading.Lock()


def _onnx_session(model):
    global _onnx, _onnx_names
    with _onnx_lock:
        if _onnx is None:
            import onnxruntime as ort
            providers = select_providers(ort.get_available_providers(), env("EMO_ORT_PROVIDERS"))
            _onnx = ort.InferenceSession(model, providers=providers)
            _onnx_names = [value.name for value in _onnx.get_inputs()]
        return _onnx


def _onnx_input_names():
    return _onnx_names or ["input_values", "sampling_rate"]


def _onnx_labels():
    return [label.strip() for label in env("EMO_AUDIO_LABELS").split(",") if label.strip()]


def softmax(logits):
    top = max(logits)
    weights = [math.exp(value - top) for value in logits]
    index, score = max(enumerate(weights), key=lambda item: item[1])
    return score / sum(weights), index


def audio_command_vote(wav):
    cmd = env("EMO_AUDIO_CMD")
    if not cmd:
        return "neutral", 0.0
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(wav)
        path = tmp.name
    try:
        last = None
        for attempt in range(3):
            try:
                out = subprocess.check_output(cmd.split() + [path], timeout=3, text=True)
                parts = out.split()
                return parse_label(parts[0]), float(parts[1]) if len(parts) > 1 else 0.5
            except (subprocess.SubprocessError, ValueError, IndexError) as exc:
                last = exc
                log(f"audio hook try {attempt + 1} failed: {exc}")
                time.sleep(0.2 * (attempt + 1))
        log(f"audio hook gave up: {last}")
        return "neutral", 0.0
    finally:
        os.unlink(path)


def audio_vote(wav):
    # Kept as a small seam for callers and tests of the original audio hook.
    return onnx_audio_vote(wav)


def fuse_votes(audio, text):
    """Weighted 0.6/0.4 vote, ignoring missing labels and low-confidence results."""
    merged = max(((parse_label(label), max(0.0, min(1.0, float(confidence))) * weight)
                  for (label, confidence), weight in ((audio, 0.6), (text, 0.4))),
                 key=lambda vote: vote[1])
    return merged if merged[1] >= 0.5 else ("neutral", merged[1])


class ReactionFusion:
    """Suppress repeated non-neutral reactions during a monotonic-time cooldown."""

    def __init__(self, cooldown_s=4.0, min_confidence=0.5):
        self.cooldown_s = cooldown_s
        self.min_confidence = min_confidence
        self.last_reaction = None
        self.lock = threading.Lock()

    def fuse(self, audio, text, now=None):
        label, confidence = fuse_votes(audio, text)
        if confidence < self.min_confidence:
            label = "neutral"
        if label != "neutral":
            with self.lock:
                now = time.monotonic() if now is None else now
                if self.last_reaction is not None and now - self.last_reaction < self.cooldown_s:
                    return "neutral", confidence
                self.last_reaction = now
        return label, confidence


def text_vote(text):
    """A transcript contributes only an explicit leading tag, not keyword guesses."""
    match = re.match(r"\s*\[([a-zA-Z]+)\]", text or "")
    return (parse_label(match.group(1)), 1.0) if match else ("neutral", 0.0)


fusion = ReactionFusion()


def fuse(audio, text, now=None):
    fusion.cooldown_s = float(env("EMO_COOLDOWN_S"))
    return fusion.fuse(audio, text, now)


def audio_command_name():
    return env("EMO_AUDIO_CMD")

def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        raw = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
        shown = raw.decode()
        if len(shown) > 300:
            shown = shown[:300] + "…"
        log(f"{self.command} {self.path} {code} {shown}")

    def _proxy(self, path, body=None, content_type=None):
        """Forward one OpenAI-shaped request without changing its body."""
        request = Request(
            config()["lemonade_host"] + path.removeprefix("/v1"),
            data=body,
            headers={"Content-Type": content_type} if content_type else {},
            method=self.command,
        )
        try:
            return urlopen(request, timeout=600)
        except HTTPError as exc:
            return exc

    def _stream(self, response):
        self.send_response(response.status)
        for name in ("Content-Type", "Cache-Control"):
            if response.headers.get(name):
                self.send_header(name, response.headers[name])
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        try:
            while True:
                chunk = response.read(4096)
                if not chunk:
                    break
                self.wfile.write(f"{len(chunk):X}\r\n".encode() + chunk + b"\r\n")
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
        except (BrokenPipeError, ConnectionResetError):
            log(f"{self.command} {self.path} client disconnected")
        finally:
            response.close()

    def _transcribe(self, body):
        parts = {}
        other_fields = {}
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("multipart/form-data"):
            self._json(400, {"error": "expected multipart WAV"})
            return
        from email.parser import BytesParser
        from email.policy import default
        envelope = b"Content-Type: " + content_type.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
        for part in BytesParser(policy=default).parsebytes(envelope).iter_parts():
            if part.get_filename():
                parts[part.get_param("name", header="content-disposition")] = (
                    part.get_filename(), part.get_payload(decode=True),
                    part.get_content_type(),
                )
        if not parts.get("file"):
            self._json(400, {"error": "missing audio file"})
            return
        audio = parts["file"][1]
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        try:
            upstream = executor.submit(self._proxy, self.path.split("?")[0], body, content_type)
            classified = executor.submit(onnx_audio_vote, audio)
            response = upstream.result()
            with response:
                raw = response.read()
            if not 200 <= response.status < 300:
                self._raw(response.status, raw, response.headers.get("Content-Type"))
                return
            label, confidence = classified.result()
            text = json.loads(raw.decode()).get("text", "")
            text_label = text_vote(text)
            reacted, fused_confidence = fuse((label, confidence), text_label)
            observe(reacted, fused_confidence, time.time())
            payload = json.loads(raw.decode())
            payload["emotion"] = reacted
            payload["emotion_confidence"] = fused_confidence
            self._json(response.status, payload)
        finally:
            executor.shutdown(wait=True)

    def _raw(self, code, raw, content_type=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        try:
            self._get()
        except Exception as exc:
            log(f"GET {self.path} crash {exc}")
            traceback.print_exc()
            self._json(500, {"error": type(exc).__name__})

    def _get(self):
        path = self.path.split("?")[0]
        if path == "/v1/models":
            with self._proxy(path) as response:
                self._raw(response.status, response.read(), response.headers.get("Content-Type"))
            return
        if path == "/config":
            self._json(200, config())
            return
        if path != "/mood":
            self._json(404, {"error": "not found"})
            return
        now = time.time()
        decay(now)
        self._json(200, {"emotion": mood["emotion"], "intensity": round(mood["intensity"], 3)})

    def do_POST(self):
        try:
            self._post()
        except Exception as exc:
            log(f"POST {self.path} crash {exc}")
            traceback.print_exc()
            self._json(500, {"error": type(exc).__name__})

    def _post(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        path = self.path.split("?")[0]
        preview = body[:200].decode(errors="replace")
        log(f"POST {path} from {self.client_address[0]} {length}b {preview!r}")
        now = time.time()
        cfg = config()
        if path == "/v1/audio/transcriptions":
            self._transcribe(body)
            return
        if path in ("/v1/chat/completions", "/v1/audio/speech"):
            self._stream(self._proxy(path, body, self.headers.get("Content-Type")))
            return
        if path == "/affect/audio":
            label, conf = audio_vote(body)
            observe(label, conf, now)
            self._json(200, {"audio": label, "confidence": conf, "mood": mood["emotion"],
                             "audio_model": cfg["audio_model"]})
            return
        try:
            data = json.loads(body.decode() or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "bad json", "body": body.decode(errors="replace")[:200]})
            return
        if path == "/affect/text":
            label = parse_label(data.get("label") or data.get("emotion"))
            observe(label, data.get("confidence", 0.7), now)
            self._json(200, {"mood": mood["emotion"], "intensity": round(mood["intensity"], 3)})
            return
        if path == "/route":
            text = data.get("text") or ""
            emotion = parse_label(data.get("emotion") or mood["emotion"])
            lang = (data.get("lang") or "fr").lower()
            voice = cfg["kokoro_voice_en"] if lang.startswith("en") else cfg["kokoro_voice_fr"]
            engine = "kokoro"
            host = cfg["lemonade_host"]
            model = cfg["kokoro_model"]
            if cfg["cosyvoice_enabled"] and emotion != "neutral" and 0 < len(text.strip()) <= MAX_CHARS:
                engine = "cosyvoice"
                host = cfg["cosyvoice_host"]
                model = cfg["cosyvoice_model"]
                voice = emotion
            self._json(200, {
                "engine": engine,
                "host": host,
                "model": model,
                "voice": voice,
                "chat_model": cfg["chat_model"],
                "lemonade_host": cfg["lemonade_host"],
            })
            return
        self._json(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        log(f"{self.address_string()} {fmt % args}")


if __name__ == "__main__":
    cfg = config()
    log(f"listen 0.0.0.0:{cfg['bind_port']} advertised {cfg['emo_host']}")
    log(json.dumps(cfg))
    server = ThreadingHTTPServer(("0.0.0.0", cfg["bind_port"]), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("stopped")
    finally:
        server.server_close()
