#!/usr/bin/env python3
"""Mood and TTS route for GeeUIVoice. Stdlib only.

Audio hook: set EMO_AUDIO_CMD to a program that reads a wav path and
prints "label confidence". No hook means audio votes neutral.
"""

import json
import os
import subprocess
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LABELS = {"neutral", "happy", "sad", "angry", "fear", "surprise"}
HALF_LIFE = 45.0
BLEND = 0.6
MAX_CHARS = 180

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
    cmd = os.environ.get("EMO_AUDIO_CMD", "").strip()
    if not cmd:
        return "neutral", 0.0
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(wav)
        path = tmp.name
    try:
        out = subprocess.check_output(cmd.split() + [path], timeout=3, text=True)
        parts = out.split()
        return parse_label(parts[0]), float(parts[1]) if len(parts) > 1 else 0.5
    except (subprocess.SubprocessError, ValueError, IndexError):
        return "neutral", 0.0
    finally:
        os.unlink(path)


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        raw = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.split("?")[0] != "/mood":
            self._json(404, {"error": "not found"})
            return
        now = time.time()
        decay(now)
        self._json(200, {"emotion": mood["emotion"], "intensity": round(mood["intensity"], 3)})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        path = self.path.split("?")[0]
        now = time.time()
        if path == "/affect/audio":
            label, conf = audio_vote(body)
            observe(label, conf, now)
            self._json(200, {"audio": label, "confidence": conf, "mood": mood["emotion"]})
            return
        try:
            data = json.loads(body.decode() or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "bad json"})
            return
        if path == "/affect/text":
            label = parse_label(data.get("label") or data.get("emotion"))
            observe(label, data.get("confidence", 0.7), now)
            self._json(200, {"mood": mood["emotion"], "intensity": round(mood["intensity"], 3)})
            return
        if path == "/route":
            text = data.get("text") or ""
            emotion = parse_label(data.get("emotion") or mood["emotion"])
            engine = "kokoro"
            if emotion != "neutral" and 0 < len(text.strip()) <= MAX_CHARS:
                engine = "cosyvoice"
            self._json(200, {"engine": engine, "voice_hint": emotion})
            return
        self._json(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=13306)
    args = parser.parse_args()
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()
