#!/usr/bin/env python3
"""Télécharge quelques WAV RAVDESS, sans récupérer l'archive complète de 199 Mio.

Licence RAVDESS : CC BY-NC-SA 4.0 (usage non commercial, attribution et partage
à l'identique). Source : Livingstone & Russo (2018), Zenodo 1188976.
Nécessite Python 3.9+ ; utilise zipfile et les requêtes HTTP de la stdlib.
"""
import argparse
import csv
import io
import array
import wave
import json
from pathlib import Path
import sys
from urllib.request import urlopen
import zipfile

# Un acteur, une phrase, une intensité forte, une prise par émotion disponible.
# RAVDESS ne contient pas surprise : les classes réellement disponibles sont
# neutral, happy, sad, angry, fear (calm/disgust sont laissées de côté).
FILES = {
    "neutral": "Actor_01/03-01-01-01-01-01-01.wav",
    "happy": "Actor_01/03-01-03-02-01-01-01.wav",
    "sad": "Actor_01/03-01-04-02-01-01-01.wav",
    "angry": "Actor_01/03-01-05-02-01-01-01.wav",
    "fear": "Actor_01/03-01-06-02-01-01-01.wav",
}
BASE = "https://zenodo.org/records/1188976/files/Audio_Speech_Actors_01-24.zip"


def wav_16k_mono(data):
    """Convertit les WAV RAVDESS 48 kHz vers le format exigé par le sidecar."""
    with wave.open(io.BytesIO(data), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError("Échantillon RAVDESS inattendu : mono PCM 16 bits requis")
        rate = source.getframerate()
        samples = array.array("h", source.readframes(source.getnframes()))
    if sys.byteorder != "little":
        samples.byteswap()
    output = array.array("h", (samples[min(len(samples) - 1, int(i * rate / 16000))]
                              for i in range(int(len(samples) * 16000 / rate))))
    if sys.byteorder != "little":
        output.byteswap()
    result = io.BytesIO()
    with wave.open(result, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(output.tobytes())
    return result.getvalue()



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("sidecar/tests/samples"))
    parser.add_argument("--start", type=int, default=0, help="Premier membre ZIP à extraire (ordre de la table centrale)")
    parser.add_argument("--count", type=int, default=5, help="Nombre de membres WAV à extraire")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Téléchargement par plages : seules la table centrale et les quelques WAV
    # choisis traversent le réseau ; le ZIP de ~199 Mio n'est jamais enregistré.
    import remotezip
    try:
        with remotezip.RemoteZip(BASE + "?download=1") as archive:
            selected = [(name, emotion) for emotion, name in FILES.items()]
            rows = []
            for name, emotion in selected:
                data = wav_16k_mono(archive.read(name))
                destination = args.output_dir / f"{emotion}_{Path(name).name}"
                destination.write_bytes(data)
                rows.append({"file": destination.name, "expected_emotion": emotion})
                print(f"{destination} : {len(data)} octets")
            with (args.output_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=("file", "expected_emotion"))
                writer.writeheader()
                writer.writerows(rows)
    except ImportError:
        parser.error("Installer le petit utilitaire remotezip : python3 -m pip install remotezip")
    print("Licence : CC BY-NC-SA 4.0 ; attribution : Livingstone & Russo, RAVDESS, Zenodo 1188976.")
    print("RAVDESS n'a pas de classe surprise : fournir ce WAV séparément si nécessaire.")


if __name__ == "__main__":
    main()
