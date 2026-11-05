# Cahier de test — passerelle émotion du sidecar

## Objet et périmètre

Cette campagne valide `sidecar/emo_server.py` et ses routes OpenAI compatibles. Le mode **mock** teste le serveur HTTP réel, lancé dans le processus de test, avec un serveur Lemonade local simulé et un classifieur déterministe. Il ne requiert ni réseau, ni ONNX Runtime, ni modèle. Le mode **live** envoie de vrais WAV à un sidecar déjà démarré.

La réponse de transcription attendue conserve le JSON Whisper et ajoute `emotion` (une des six émotions robot) et `emotion_confidence` (nombre entre 0 et 1). Les labels ONNX sont, dans l'ordre : `angry, disgusted, fearful, happy, neutral, other, sad, surprised, unknown`. `fearful` devient `fear`, `surprised` devient `surprise` ; `disgusted`, `other` et `unknown` deviennent `neutral`. Un WAV de moins d'une seconde renvoie `neutral` avec une confiance de 0.

## Préparation

- Python 3.9 ou supérieur ; **aucune dépendance Python supplémentaire** pour le script de campagne (bibliothèque standard).
- En live : sidecar accessible, Lemonade et modèles configurés ; WAV PCM 16 kHz, mono, 16 bits.
- Le petit corpus RAVDESS attribué est versionné ; les autres téléchargements et rapports restent exclus de Git.

## Cas de test

| ID | Objectif | Entrée / simulation | Résultat attendu |
|---|---|---|---|
| EMO-01 | Joie | WAV ≥ 1 s ; label forcé `happy` | HTTP 200 ; `emotion=happy`, confiance numérique ; champs Whisper conservés |
| EMO-02 | Tristesse | WAV ≥ 1 s ; label forcé `sad` | HTTP 200 ; `emotion=sad` |
| EMO-03 | Colère | WAV ≥ 1 s ; label forcé `angry` | HTTP 200 ; `emotion=angry` |
| EMO-04 | Peur | WAV ≥ 1 s ; label forcé `fear` (alias de `fearful`) | HTTP 200 ; `emotion=fear` |
| EMO-05 | Surprise | WAV ≥ 1 s ; label forcé `surprise` (alias de `surprised`) | HTTP 200 ; `emotion=surprise` |
| EMO-06 | Neutralité | WAV ≥ 1 s ; label forcé `neutral` | HTTP 200 ; `emotion=neutral` |
| EMO-07 | Calme RAVDESS | Label brut `calm` | `emotion=neutral` |
| EMO-08 | Repli du dégoût | Label brut `disgusted` (code 07) | `emotion=neutral` |
| EMO-09 | Surprise RAVDESS | Label brut `surprised` (code 08) | `emotion=surprise` |
| EMO-10 | Repli d'inconnu | Label brut `unknown` | `emotion=neutral` |

Les scénarios mock couvrent donc les huit codes RAVDESS, `other` et `unknown` en plus des six émotions robot.
| EDGE-01 | Clip trop court | WAV tonal de 0,5 s ; vrai classifieur, sans modèle | HTTP 200 ; `neutral`, confiance 0 ; aucun appel ONNX nécessaire |
| EDGE-02 | Silence | WAV de silence de 1,2 s ; label `neutral` simulé | Réponse valide ; `neutral` |
| EDGE-03 | Bruit | WAV de bruit pseudo-aléatoire de 1,2 s ; label `neutral` simulé | Réponse valide ; `neutral` |
| EDGE-04 | Fichier corrompu | Octets non audio nommés `corrompu.wav` | HTTP 400 de l'amont conservé ; pas d'émotion ajoutée |
| EDGE-05 | Champ manquant | Multipart sans partie `file` | HTTP 400 ; `{"error":"missing audio file"}` |
| EDGE-06 | Fichier volumineux | WAV d'environ 2 Mio + données supplémentaires | Pas de troncature/crash ; HTTP 200 et émotion simulée |
| UP-01 | Lemonade arrêté | URL amont pointant vers un port local fermé | Comportement actuel : HTTP 500 contrôlé `{"error":"URLError"}`, pas de crash du serveur |
| UP-02 | Lemonade trop lent | Amont différé et timeout du stub | Comportement actuel : HTTP 500 contrôlé `TimeoutError` |
| CONF-01 | Modèle absent | `EMO_AUDIO_ONNX` et `EMO_AUDIO_CMD` vides | Repli sans erreur : `neutral`, confiance 0 |
| CONF-02 | Modèle mal configuré | `EMO_AUDIO_ONNX=/chemin/inexistant.onnx` | Erreur ONNX interceptée ; repli `neutral`, transcription conservée |
| PROXY-01 | Chat en streaming | POST chat `stream=true`, trois événements SSE du stub | HTTP 200, `text/event-stream`, fragments `Bon`, `jour`, puis `[DONE]`, sans altération |
| PROXY-02 | Synthèse vocale | POST `/v1/audio/speech` | HTTP 200, `Content-Type: audio/wav`, contenu RIFF transmis |
| PROXY-03 | Modèles | GET `/v1/models` | HTTP 200 ; JSON de l'amont inchangé |
| PERF-01 | Latence | Cinq transcriptions mock successives ; toutes requêtes live | Durée par cas, moyenne et p95 dans Markdown/JSON ; seuil non imposé en mock |

## Exécution

Depuis la racine du dépôt :

```bash
# Tout simuler, hors ligne ; sortie non nulle si au moins un cas échoue
python3 sidecar/tests/run_emotion_tests.py --mode mock

# Vrais fichiers ; le nom doit contenir happy, sad, angry, fear, surprise ou neutral
python3 sidecar/tests/run_emotion_tests.py --mode live \
  --url http://nimbus:13306

# Dossier explicite équivalent (valeur par défaut) :
# --audio-dir sidecar/tests/samples/ravdess
```

Un `manifest.csv` facultatif dans le dossier prioritaire sur les noms contient `file,expected_emotion`, par exemple :

```csv
file,ravdess_label,expected_emotion
03-01-03-02-01-01-01.wav,happy,happy
03-01-08-02-01-01-01.wav,surprised,surprise
```

RAVDESS contient huit codes : neutral, calm, happy, sad, angry, fearful, disgusted et surprised. Le manifeste conserve le label brut ; calm et disgusted sont attendus comme neutral. Le rapport live fournit l'exactitude par label brut et par émotion robot, ainsi que la matrice de confusion robot. Le mode live ajoute les cas court, silence et bruit. Les autres erreurs sont validées en mock.

Les rapports `RAPPORT.md`, `resultats.json` et `rapport.html` sont créés dans `sidecar/tests/reports/<horodatage>/`. Le JSON contient les réponses détaillées, l'exactitude par émotion, la matrice de confusion et les latences. Le HTML est autonome.

## Jeu d'échantillons réels

RAVDESS (Livingstone & Russo, 2018, PLoS ONE 13(5): e0196391), Zenodo **10.5281/zenodo.1188976**, est sous **CC BY-NC-SA 4.0**. Voir `samples/ravdess/SOURCE.md` pour l'attribution complète, la liste et les modifications. Les 24 WAV convertis, trois par expression, sont commités et totalisent moins de 3 Mio.

```bash
# Téléchargement sélectif par défaut (24 WAV, nécessite remotezip)
python3 -m pip install remotezip
python3 sidecar/tests/fetch_samples.py --output-dir sidecar/tests/samples/ravdess

# Alternative : archive complète (199 Mio), extraction des 1440 WAV
python3 sidecar/tests/fetch_samples.py --full --output-dir sidecar/tests/samples/ravdess-full
```

L'option `--full` télécharge exactement `https://zenodo.org/records/1188976/files/Audio_Speech_Actors_01-24.zip?download=1`. Aucune dépendance externe n'est requise dans ce mode. Le ZIP et les fichiers hors du petit corpus commité restent ignorés par Git.

## Tests unitaires existants

```bash
python3 -m unittest discover -s sidecar -v
```
