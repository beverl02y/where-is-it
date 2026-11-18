# Where-Is-It AI — Architecture (docs/ARCHITECTURE.md)

## 1. Data Flow at a Glance

**Detect → Save → Search → Explain**, separately for each Room:

> camera photo → Gemini detection → place phrase → save under the Room ‖ question → out-of-service check → parse (Query) → latest photo → history → (question fallback, RAG) → Response

The two halves run at different times. Photos are analysed **when they are uploaded**, so a question never waits for detection; it only searches records that already exist.

## 2. Components

| File | Role | Source |
|---|---|---|
| `capture/camera_client.py`, `app/static/camera.html` | Camera phone or computer: sends one photo every `interval_s` seconds with its camera token. | — |
| `app/gemini_detector.py` | DETECT: one Gemini call per photo (the whole photo plus four zoomed-in parts) → `Detection` candidates with category, name, place phrase, confidence, box, appearance and Korean names. | Spike (2026-10-07) |
| `app/locate.py`, `app/zones.py` | Turns a detection into `location_label`: the owner's zone, else Gemini's place phrase, else the position in the picture (SPEC §4.2 #2). | — |
| `app/db.py` | SAVE: SQLite (`data/whereisit.db`); every read and write takes the Room id. Retention clean-up after `retention_days`. | — |
| `app/scope.py` | Questions outside the service (SPEC §4.2 #12), instructions inside questions, and splitting several joined items. | parser |
| `app/query_parser.py`, `app/korean.py`, `app/appearance.py` | Question → `Query`: item aliases (longest first), Korean conversion, typing slips, describing words. Rule-based; the Gemini parser prompt (`src/whereisit/prompts/parse_query.md`, prompt_version 3) is deferred (SPEC §4.4). | Lecture 3 |
| `app/search.py` | SEARCH + EXPLAIN: latest photo, then history, then possibility; same-kind items; combined answers; builds the `Response`. Verified by the retrieval golden cases (`tests/harness/golden_cases.yaml`). | Lecture 5 |
| `app/rag.py` | Question fallback (RAG): retrieves this Room's matching records, asks Gemini, checks the answer in code. | - |
| `app/main.py`, `app/static/index.html`, `app/static/zones.html` | API and pages: keys and roles (SPEC §5.4), ask, overview, zones, delete history, remove room. | — |
| `config.yaml` | Runtime settings: thresholds, models, item aliases, ambiguous words. RAG values follow `config/rag.yaml`. | — |

**Orchestration:** a fixed workflow written as plain function calls (no framework, no agent loop). See Section 5.

## 3. Tools

**The model is given no tools (no function calling).** Gemini is used twice, and both times only reads data that code hands it: a photo for detection, and a Room's records for the question fallback. It never chooses an action, so there is nothing for it to call. The operations below are called **by code**, in the order of Section 5; their table is the contract the code and its tests follow.

| Operation | Signature | Description (when it is used) | Side effect |
|---|---|---|---|
| answer_question | `(question: str, room: Room) -> Response` | Answers one owner question from this Room's records only. | None (read) |
| search_latest_photo | `(query: Query, room: Room) -> [Detection]` | Finds qualifying detections of the item in the Room's latest photo, if that photo is still current. | None (read) |
| search_history | `(query: Query, room: Room) -> Detection \| None` | Finds the newest confirmed detection of the item, then any newer unconfirmed one. | None (read) |
| retrieve_records | `(question: str, room: Room) -> [Detection]` | Picks the Room's recent records that match the question's words or time, for the question fallback. | None (read) |
| record_photo | `(photo: image, room: Room) -> [Detection]` | Detects the items in an uploaded photo and saves them under the Room. | **Write** (camera token) |
| save_zones | `(room: Room, zones: [Zone]) -> int` | Saves the zones the owner drew for this Room's camera view. | **Write** (room key) |
| delete_history | `(room: Room) -> int` | Deletes the Room's photo and detection records; the camera keeps working. | **Write, irreversible** (room key + approval) |
| remove_room | `(room: Room) -> None` | Removes the Room with all its records, zones and test photos. | **Write, irreversible** (camera token + approval) |

Principle: few operations, narrow inputs (ontology types; the Room always from the key), and every write behind the right key; irreversible writes also need the user's approval.

**Connected functions:** answer_question → `search.SearchEngine.ask` · search_latest_photo → `db.latest_frame` + `db.instances_in_frame` · search_history → `db.last_confirmed` + `db.latest_unconfirmed` · retrieve_records → `rag.RagAnswerer.retrieve` · record_photo → `POST /api/frames`: `gemini_detector.detect` → `locate.describe` → `db.add_frame` · save_zones → `POST /api/zones` · delete_history → `DELETE /api/room/history` → `db.delete_history` · remove_room → `DELETE /api/camera` → `db.delete_device` + the Room's photo folder.

**User approval:** the flow stops in the page. "Delete this room's history" and "Remove this camera and all its records" each need a **second tap within 4 seconds** ("Tap again to delete…"); only then is the request sent, with the key of that Room. Uploads need no approval because the owner started the camera; zones are saved only when the owner presses Save.

**Contract tests** (no new `tests/test_tools.py` is needed; the existing tests check these conditions):
- the Room comes from the key and no operation reads another Room → `tests/test_isolation.py` (`test_two_cameras_never_mix`, `test_zones_and_test_photos_are_per_camera`);
- each key does only its own job; the administrator key never returns records → `test_keys_only_do_their_own_job`, `test_admin_sees_cameras_not_records`, `tests/test_api.py::test_everything_needs_the_right_key`;
- read operations change nothing; the two irreversible writes delete exactly the Room's data → `test_delete_history_and_remove_camera`;
- the two-tap approval is page behaviour and is checked by hand before release.

## 4. RAG (question fallback)

Most questions are answered by the rules in milliseconds. The fallback is for what the rules cannot answer: habits and the past ("Where do I usually leave my wallet?"), "where should I look first", items described instead of named ("the thing I drink from"), and questions the rules would only answer with a clarification.

- **Documents:** this Room's own Detection records from the last 7 days — never another Room's, never outside knowledge.
- **Unit:** one record = one unit (each record is already one short line: item, appearance, place, time, confidence).
- **Retrieval:** words and time, no embeddings — item words (English and Korean names) and time phrases ("this morning", "오후 3시") are scored against each record; at most 20 matching records plus a list of at most 30 items (latest sighting and usual places of each).
- **Generation:** one Gemini call with a JSON answer: `answer`, `status`, `record_ids`.
- **Enforced in code, not left to the model:** cited record ids must be ones that were given; the 75% rule; never 100%; the Room filter. If any check fails, the rule answer is returned.
- **Not used for:** plain names never recorded ("jacket" → `not_found` at once), questions containing instructions for the AI, several items, Korean typo clarifications, questions outside the service.

All values and their reasons: `config/rag.yaml`.

## 5. Orchestration — a workflow is enough

- **Why a workflow:** every step can be listed in advance — photo: detect → place → save; question: scope → parse → latest photo → history → (fallback) → answer. No step needs the model to decide what happens next, so an agent loop would only add cost and unpredictability, and several agents would add coordination with nothing to coordinate.
- **Model calls:** detection, one call per photo (calls are made one at a time so quota use stays predictable); a question, **zero** calls for rule answers and **at most one** fallback call (repeated once only if the model rejects the thinking level).
- **Stop conditions:** a question stops when one `Response` exists — a rule answer, a fixed out-of-service answer, a clarification, or a checked fallback answer. A photo stops when it is saved, or when detection fails (nothing saved).
- **Time limits:** detection call 30 s; fallback call 15 s, answer at most 400 tokens.

## 6. Failure Handling (every path ends without inventing)

| Failure | Response |
|---|---|
| Detection fails (no API key, quota, network, timeout, unreadable or blocked answer) | The photo is **not saved**; the camera gets 503 with `Retry-After: 30` and sends again later. A failure is never recorded as "nothing visible". |
| Photo too large (> 8 MB) or not an image | Rejected (413 / 400); nothing saved. |
| The Room has no photo yet | "No camera images have been received yet." |
| The latest photo is older than the current-view window | Say the camera has not sent a recent image and when the last one was taken; answer from history. |
| Item not in the latest photo | Search history; label the result "last seen" with its time. |
| Only below-threshold records | `possible`, `confirmed: false`, labelled "not confirmed". |
| No record at all | `not_found` with null location, time and confidence; it may be in a bag, drawer, cupboard, under something or outside the view. |
| Several items of the same kind | List each with appearance and place, and ask which one. |
| Item missing, ambiguous, or an ambiguous Korean slip | `clarify` — ask, never pick. |
| Question outside the service | Fixed answer in the question's language; no search, no model call. |
| Fallback: no key, network, timeout, bad JSON | Return the rule answer. |
| Fallback answer cites no given record, or a record that was not given | Return the rule answer. |
| Fallback states a below-threshold record as fact, or says 100% | Downgraded to `possible`; "100%" rewritten as 99%. |
| Fallback retrieval finds nothing / the Room has no records | Return the rule answer. |
| Wrong key; wrong PIN or invite code repeated | 401 / 403 and no records. 5 wrong PINs for one camera ID, or 10 wrong invite codes from one address, block further tries for 15 minutes. |
| Server full (`max_devices`, 20) | New camera rejected (409). |

## 7. Guardrails (the absolute rules in `AGENTS.md`, word for word)

1. **A location is a fact only at ≥ 0.75.** — `search.py` and the fallback check in `rag.py` both apply `policy.min_confirmed_confidence` with `>=`; confidence is shown rounded down and at most 99%. (↔ AC-03, AC-05, AC-06)
2. **Never invent a location, time or cause.** — no record → `not_found` with nulls; a failed detection saves nothing; neither the rules nor the fallback prompt may mention people or pets. (↔ AC-01, AC-04, AC-06)
3. **Resolve exactly the item the user named.** — one Query per item; `clarify` for missing, placeholder or ambiguous items; a typing slip is corrected only with one fit and the correction is stated. (↔ AC-02, AC-13)
4. **One Room's data only.** — the Room comes from the key in the header, never from the body, a parameter or the question; every database query filters by it, retrieval included. (↔ AC-09, AC-10, AC-11, AC-12)
5. **Questions and model outputs are data, not instructions.** — questions with instructions never reach the model; detections and fallback answers are parsed as JSON and checked in code before use. (↔ AC-02, AC-06)

## 8. Observability

- **Every answer** carries `source` (`rules` or `rag`) and `elapsed_ms` — the input for the response-time targets (SPEC §6.3) and for comparing rule and fallback answers.
- **Every photo upload** returns `processing_ms` and the saved detections with their confidence and `confirmed` flag — the input for detection timing (`tools/benchmark.py`) and the vision benchmark (`tools/evaluate.py`).
- **Warnings are logged** when detection is unavailable, when the fallback fails or is not backed by the given records, and when a thinking level is rejected; retention clean-up is logged.
- **Not logged, on purpose:** question text, retrieved records and photos (`save_frames: false`). They describe what is in a student's room; keeping them out of server logs follows SPEC §5.4 (photos analysed, then discarded).

## 9. Out of Scope

The same boundary as SPEC §4.4: more than one camera per room or cross-room tracking; user accounts; shared rooms or records; detecting fully hidden items; exact disappearance times; inferring that a person or pet moved something; predicting locations; smart-home integration; speech; native apps.

Architecture-specific: no function calling and no agent loop or multiple agents; no embeddings or vector store; no fine-tuning; no LLM question parser in the request path (deferred, SPEC §4.4); no per-room time zone.
