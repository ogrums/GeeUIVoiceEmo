#!/usr/bin/env python3
"""Mood, route, and host config for GeeUIVoiceEmo. Stdlib only.

Unset or blank variables fall back to the defaults below.
Lemonade stays the Kokoro path. CosyVoice is a second host, off unless set.
"""

import json
import os
import subprocess
import sys
import traceback
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

LABELS = {"neutral", "happy", "sad", "angry", "fear", "surprise"}
HALF_LIFE = 45.0
BLEND = 0.6
MAX_CHARS = 180

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


def audio_vote(wav):
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

    def do_GET(self):
        try:
            self._get()
        except Exception as exc:
            log(f"GET {self.path} crash {exc}")
            traceback.print_exc()
            self._json(500, {"error": type(exc).__name__})

    def _get(self):
        path = self.path.split("?")[0]
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
    ThreadingHTTPServer(("0.0.0.0", cfg["bind_port"]), Handler).serve_forever()
