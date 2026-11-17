# Where-Is-It AI

A camera-based assistant that answers **"Where are my glasses?"** from camera evidence only.
It follows the SPEC principle **Detect → Save → Search → Explain**, using **Gemini 3.8 Flash**
to recognise objects. Every camera phone is its own private room.

```
 Camera phone (/camera)  ── photo every 15 min (10 s for demos) ──▶  Server (FastAPI on a Google Cloud VM)
   camera token                                                       DETECT  gemini_detector.py  Gemini 3.8 Flash:
                                                                              every object, confidence, place in words,
                                                                              colour / size / shape
 Your own phone (/)       ── "Where is my black laptop?" ──────────▶  SAVE    db.py               SQLite, one room per camera
   camera ID + PIN                                                    SEARCH  search.py           current view → history →
                                                                              possibility → safe "not found"
```

The step-by-step setup on Google Cloud (Cloud Shell, e2-micro VM, HTTPS, phone camera) is in the
**Where-Is-It AI — Build & Deploy Guide** document. This README describes the code.

## How the SPEC maps to the code

| SPEC | Where |
|---|---|
| §4.3 seven key objects | `config.yaml → objects` (`hint` for Gemini, `aliases` for questions) |
| AC-01 Object detection | `app/gemini_detector.py` — one Gemini request per photo |
| §4.2 #2 Location recording | `app/locate.py` (Gemini's place description, optional zones), `app/db.py` |
| AC-02 Natural-language search | `app/query_parser.py`, `POST /api/ask` |
| AC-03 Current detection ≥ 75 % | `search.py` step 1 (latest photo; window follows the camera interval) |
| AC-04 / AC-05 Last seen | `search.py` step 2 |
| AC-06 Possibility, labelled "not confirmed" | `search.py` step 3 |
| §6.2 ambiguous → clarify, no evidence → safe failure | `ambiguous_terms` in config; `search.py` step 4 |
| §6.2 never 100 %, never blame a person or pet | `pct()` caps at 99 %; Gemini prompt; tests |
| §6.3 targets | `tools/evaluate.py` (accuracy, false positives, false certainty), `tools/benchmark.py` (speed) |
| v2 separate records per user | `app/main.py` (camera token, room key, camera ID + PIN), `app/db.py` (`device_id` on every record) |

## Project layout

```
where-is-it-ai/
├── app/
│   ├── main.py             web server: pages, API, keys
│   ├── gemini_detector.py  DETECT: photo → Gemini 3.8 Flash → objects
│   ├── detector.py         Detection record; "none" detector for demos/tests
│   ├── locate.py           where an object is, in words
│   ├── zones.py            optional named zones (point-in-polygon)
│   ├── db.py               SQLite: cameras, records, zones, PIN sessions
│   ├── query_parser.py     question → object (+ describing words like "black", "big")
│   ├── appearance.py       matching describing words (big = large, circle = round …)
│   ├── search.py           SEARCH + EXPLAIN: the answer
│   └── static/             index.html (ask), camera.html (camera phone), zones.html
├── capture/camera_client.py  optional: use a laptop/USB webcam as the camera
├── tools/                  devices.py (admin), seed_demo.py, evaluate.py, make_label_template.py,
│                           benchmark.py, gcp_https.sh
├── tests/                  67 tests (SPEC rules, Gemini parsing, isolation, PIN, appearance)
├── config.yaml             thresholds, objects, Gemini settings
├── Dockerfile, docker-compose.yml, .env.example
└── requirements*.txt
```

## Who can do what

Every camera phone is its own **room** with its own records, zones and test photos. Two people can use
the server at the same time and never see each other's records.

| Who | Holds | Can do |
|---|---|---|
| Camera phone | **camera token** (made when it is set up on `/camera`, kept in that phone) | upload photos and test photos — nothing else |
| Owner's own phone | **camera ID + PIN** (entered on the main page) or the **room link** `https://<server>/#room=…` | ask, see the overview, draw zones, delete history — for that room only |
| Server operator | `WIIA_API_KEY` | list / remove cameras (`/api/admin/devices`, `tools/devices.py`) — never sees records |

Setting up a camera needs the **invite code** (`WIIA_INVITE_CODE`), so strangers can't use your Gemini quota.
Five wrong PINs lock that camera ID for 15 minutes. PINs and keys are stored only as hashes.

## What Gemini returns, and how answers use it

For every portable object in a photo Gemini returns: a category (one of the 7 key objects or "other"),
a name, a box, its own confidence (0–1), **where it is in words** ("on the desk next to the laptop"),
and **what it looks like** (appearance phrase, colour, size, shape).

- Below 75 % confidence an item is only ever a *possibility*, never a fact.
- If Gemini fails (quota, network, missing key) the photo is **not** saved, so a failure never looks like
  "nothing there"; the camera page shows the reason and retries with the next photo.
- **Same-name items:** "Where is my laptop?" with two laptops lists both; "Where is my black laptop?" /
  "my big one" answers about the matching one (big = large, tiny = small, circle = round, grey = gray).
- **Any item:** with `detect_all_objects: true` you can also ask about things beyond the 7 ("water bottle").

## Hybrid RAG fallback (`app/rag.py`)

Questions are answered in two steps:

1. **Rules first** (`app/search.py`): "Where is my wallet?" / "지갑 어디 있어?" are answered instantly
   from the database: no AI call, no cost, and they follow the SPEC rules exactly.
2. **RAG fallback**, only when the rules can't help:
   - questions about the past or habits: "What was on my desk this morning?", "Where do I usually leave my keys?",
     "어디부터 찾아봐야 해?", "어제 지갑 어디 있었어?"
   - vague names: "the thing I drink water from", "물 마시는 거"
   - questions the rules couldn't understand (clarify / unsupported / never-seen name)

   **Retrieve** this camera's records from the last `rag.lookback_days` (matching words, Korean names and times,
   plus every item's latest sighting and usual places) → **augment** a Gemini prompt with them (ids like `R12`)
   → **generate** the answer in the user's language → **check** it in code: it must cite records it was given,
   anything under 75% becomes "possibility", and 100% is never shown. If Gemini fails or the check fails,
   the rule answer is used.

Answers carry `"source": "rules"` or `"source": "rag"`; the page labels RAG answers "AI answer from camera
records". Turn it off with `rag: enabled: false` in `config.yaml`. Cost: about $0.002–0.005 per RAG answer
(text only); normal "where is X" questions stay free.

## Run it locally (no camera, no Gemini)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && pytest -q          # 67 passed
pip install "uvicorn[standard]" opencv-python-headless
export WIIA_MODEL_TYPE=none WIIA_API_KEY=demo
python tools/seed_demo.py                                   # prints two demo room links
uvicorn app.main:create_app --factory --port 8080
```

Open http://localhost:8080, open **Room settings**, paste a demo room link and ask "Where are my glasses?".

## Run it for real

1. Copy `.env.example` to `.env` and fill in `WIIA_API_KEY` (admin), `GEMINI_API_KEY`
   ([Google AI Studio](https://aistudio.google.com/apikey)) and `WIIA_INVITE_CODE`.
2. `docker compose up -d --build` (about 2 minutes), then serve it over HTTPS (`tools/gcp_https.sh` on a
   Google Cloud VM — phones only allow the camera on HTTPS pages).
3. On the camera phone open `https://<server>/camera`: room name, invite code, PIN → **Set up** → **Start camera**.
4. On your own phone open `https://<server>/`, **Room settings** → camera ID + PIN → **Connect**.

Full cloud instructions, costs and troubleshooting: see the Build & Deploy Guide.

## Configuration (`config.yaml`)

| Setting | Default | Meaning |
|---|---|---|
| `detection.model_type` | `gemini` | `none` = no detection (demo/tests) |
| `detection.confirm_threshold` | `0.75` | SPEC: a fact only at ≥ 75 % |
| `detection.store_threshold` | `0.15` | weaker detections are kept as possibilities |
| `detection.detect_all_objects` | `true` | also find items beyond the 7 key objects |
| `gemini.thinking_level` | `low` | `medium` = more careful, slower, costs more |
| `gemini.media_resolution` | `high` | helps with small items |
| `objects.<key>.hint` | — | what Gemini should look for |
| `location.mode` | `auto` | `zones` = only named zones |
| `server.retention_days` | `30` | older records are deleted |

## Admin

```bash
docker compose exec api python tools/devices.py list                 # cameras, photo counts
docker compose exec api python tools/devices.py remove CAMERA_ID     # camera + all its records
docker compose exec api python tools/devices.py pin CAMERA_ID 2580   # reset a forgotten PIN
```

## Measuring the SPEC targets

1. Press **Save test photo** on the camera page for 100–200 varied photos (saved in `data/devices/<id>/eval/images`).
2. `python tools/make_label_template.py --images data/devices/<id>/eval/images --out data/devices/<id>/eval/labels.csv`,
   then mark `present` = 1 where each object is visible.
3. `python tools/evaluate.py --csv … --images …` → accuracy, false positive rate, false-certainty rate, time per photo.
4. `python tools/benchmark.py --server https://… --room-key "<room link>"` → answer time.

## API reference

| Method | Path | Key | Purpose |
|---|---|---|---|
| POST | `/api/devices/register` | invite code (or admin key) | `{"name","invite_code","pin"}` → camera token + room key |
| GET / DELETE | `/api/camera` | camera token | camera info / remove camera and all its data |
| POST | `/api/camera/pin` | camera token | set / change the PIN (disconnects phones that used the old PIN) |
| POST | `/api/camera/room-key` | camera token | new room link (old one stops working) |
| POST | `/api/frames` | camera token | detect + save one photo (`file`, optional `captured_at`, `interval_s`) |
| POST | `/api/test-photos` | camera token | save a photo to `data/devices/<id>/eval/images` |
| POST | `/api/room/connect` | none | `{"camera_id","pin"}` → a private key for this phone |
| GET | `/api/room` | room key | room name, photo count, last photo time |
| POST | `/api/ask` | room key | `{"question": "Where are my glasses?"}` |
| GET | `/api/objects` | room key | last confirmed location of every object in this room |
| DELETE | `/api/room/history` | room key | delete this room's records |
| GET / POST / DELETE | `/api/zones` | room key | this room's optional zones |
| GET | `/api/test-photos/latest` | room key | this room's latest test photo |
| GET / DELETE | `/api/admin/devices[/{id}]` | admin key | list / remove cameras |
| GET | `/api/health` | none | status and detector only |

Headers: `X-Camera-Token`, `X-Room-Key`, `X-API-Key`.
