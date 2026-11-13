# Where-Is-It AI --- Specification v2

## 1. Problem Definition

University students who cannot remember where they last used or placed an everyday belonging may spend several minutes searching several places when they need it (one participant reported about 10 minutes; Log 10, Q8), causing stress and a risk of being late.

The supporting interview quotations and validation rules are maintained in `Problem.md`.

v1 could serve only one room with one camera. Because every participant described the problem in their own space, v2 extends the system so that several students can use one service at the same time, each with a separate room and separate records.


## 2. Target Users and Non-Target Users

### 2.1 Primary Target Users

The primary target users are **university students who repeatedly have difficulties in
finding everyday belongings inside their room**.

The supported key item classes, their canonical names and their aliases are defined only in `ontology.yaml` under `vocabulary.items` and `vocabulary.item_aliases`. This specification and the other project documents refer to that list instead of repeating it.

Each student will set up their own camera phone as a separate room and will see only that room's records.

The system is particularly relevant to users who:

-   Often forget where they placed an object.
-   Check the same usual locations repeatedly.
-   Need to find an object quickly before leaving home, going to class,
    or going to work.
-   Want more specific indoor location information than existing finder
    applications provide.
-   Want to know where and when an object was last detected.

### 2.2 Non-Target Users

This version does not primarily target:

-   Users trying to find belongings lost outside the camera-covered
    environment and trying to track stolen objects over long distances.
-   Large-scale public lost-and-found services.
-   Family users who need to manage the belongings of multiple people.
-   Roommates or households who want to share one camera or one set of records.
-   Business users who need to manage many objects or equipment in offices or facilities.


This project only focuses on **indoor object finding using available camera
evidence**. It is not intended to replace GPS/Bluetooth tracking devices
or public lost-and-found systems.


## 3. Evidence from User Interviews

The supporting interview quotations are maintained in `Problem.md`, Section 3. The supplied responses are recorded in `interview_answers.md`.

The following table connects the findings to proposed requirements.

| Finding | Interview evidence | Design implication |
|---|---|---|
| Participants mentioned several everyday item types. | Logs 3, 6, 7, and 10, Q2 | Use the bounded key-item set defined in `ontology.yaml`, under `vocabulary.items`. Also record other portable items so that users are not limited to seven classes. |
| Missing items were noticed when needed or before leaving. | Log 1 Q4; log 6 Q4; log 10 Q4 and Q8 | Provide simple item-search questions and evaluate whether the system reduces search effort. |
| Participants checked usual storage places first. | Logs 1, 6, and 10, Q5 | Derive frequently recorded places from confirmed camera records and offer them for "where should I look first" questions. |
| Finder services indicated nearby items without identifying their exact location. | Log 6 Q8; log 9 Q7 | Return the place and observation time supported by camera records, described relative to nearby furniture or objects. |
| Remembering the last-used place helped participants recover items. | Logs 1, 6, and 10, Q9 | Support last-seen retrieval and label every result as a recorded observation. |
| Some objects were covered or hidden. | Log 2 Q3; logs 6 and 10 Q9 | Handle limited visibility and avoid inventing a current location. |
| All participants described the problem in their own space. | Logs 1–10 | Give each user a separate room with records that no other user can access. |

Log 1 describes recovery at a copy shop. It supports the value of remembering a last-used place, but does not validate indoor camera coverage.

The interviews did not ask about privacy concerns with a room camera whose photos are analysed by a cloud service. This must be checked in the user test (AC-14).

These findings motivate the proposed design. Camera acceptance, detection reliability, and reductions in search time require separate evaluation.


## 4. Solution and MVP Scope

### 4.1 Core Function

**Where-Is-It AI** is a camera-based AI assistant that helps users
locate misplaced belongings. A phone placed in the room sends a photo at a
set interval. The system detects objects in each photo, stores their
location and time under that camera's room, and allows the owner to ask
where an object is using natural language in English or Korean.

The system follows a simple principle:

> **Detect → Save → Search → Explain** --- separately for each room

For a resolved item query, the system first checks the room's latest photo for a qualifying observation. If none exists, it searches the room's historical records. Every returned location is accompanied by its image capture time and confidence and must be described as a recorded observation rather than a guarantee of the current location.

### 4.2 MVP Features

The second version includes the following core features:

1.  **Object Detection**\
    Detect portable objects in each camera photo with a multimodal model (Gemini API). For each object the model returns a category (one of the key items or `other`), a short name, the place in words, and a confidence score from 0 to 1. Where possible it also returns a bounding box, appearance (colour, size, shape) and Korean names. Furniture, people and pets are not recorded. To find small and distant items, the photo is sent together with zoomed-in parts of the same photo.

2.  **Location Recording**\
    Save the item name, location, capture time, confidence and appearance under the camera's room. Choose the location in this order:
    1. a zone the owner has drawn for this room;
    2. the model's own place description (e.g. "on the desk next to the laptop");
    3. the position in the camera picture (e.g. "in the bottom-left of the camera view").

    Zones are optional, so the system works in any room without setup. If detection fails, the photo must not be saved, so that a failure is never recorded as "nothing visible".

3.  **Natural-Language Search**\
    Allow the user to ask questions such as:

    -   "Where are my glasses?"
    -   "Where is my black wallet?"
    -   "지갑 어디 있어?"

    Resolve one item per question using the item aliases in `ontology.yaml` (`vocabulary.item_aliases`; the runtime configuration must contain the same aliases), preferring the longest matching phrase, and keep describing words such as colour and size.

4.  **Latest-Frame Search**\
    Search the room's latest photo for a qualifying observation of the requested item. A photo counts as current for 120 seconds, or longer when the camera's interval is longer (1.5 × the interval + 30 seconds).

5.  **Historical Search**\
    If no latest-frame observation qualifies, return the latest qualifying historical observation, explicitly labeled as last seen with its capture time.

6.  **Confidence-Based Response**\
    Clearly distinguish between confirmed detections and uncertain possibilities. A detection below the threshold that is newer than the last confirmed one is offered only as a labelled, unconfirmed possibility. Never show a confidence of 100%.

7.  **Safe Failure**

    Apply the confirmation threshold and comparison operator defined under `policy` in `ontology.yaml`.

    If the latest image has no qualifying detection, search historical records. If no reliable record exists, explain that the item could not be located from the available camera records and that it may be inside a bag, drawer or cupboard, under something, or outside the camera's view.

    Never invent a detected location. Never state that a person or pet moved an item.

8.  **Same-Kind Items**\
    When several items of the same kind are confirmed (for example, two wallets), list each with its appearance and place and ask which one is the user's. A describing word in the question ("black", "big") selects the matching item.

9.  **Question Fallback (RAG)**\
    When the rules cannot answer a question — questions about the past or habits, "where should I look first", vague names such as "the thing I drink from", or questions the rules would only answer with a clarification — generate an answer with the language model using only this room's recent records. The answer must cite the records it used. The confidence policy and the "never 100%" rule are then checked in code. If generation or any check fails, return the rule-based answer.

10. **Separate Rooms**\
    Each camera phone is one room. Photos, detections, zones and test photos belong to one room, and a user can never see, search or change another room's data.

11. **Own-Data Control**\
    The owner can delete the room's history, and can remove the room with all of its data. Records older than `policy.retention_days` in `ontology.yaml` are deleted automatically.

### 4.3 MVP Object Scope

The supported key item classes are defined in `ontology.yaml` under `vocabulary.items`. Canonical place names are defined under `vocabulary.places`; zone names should use them where possible.

Other portable items reported by the detector are also stored and can be searched. Different names for the same kind of item (for example, "mask" and "face mask") are saved under one name defined in `config.yaml`.

The historical spike's tested subset is recorded under `validation_scope.historical_spike` in the same file. Its results apply only to that subset and the evaluated images, and were obtained with an earlier detector.

The full vocabulary is a product scope definition, not a claim that every item and place has already passed detection testing.

### 4.4 Out of Scope for v2

The required v2 scope uses one camera per room, one room per camera phone, and a text-based search interface.

The following capabilities are outside the required scope:

- More than one camera per room, and cross-room tracking.
- User accounts with email and password. Access uses the camera ID with a PIN, or a private room link.
- Shared rooms, family groups, or sharing records between rooms.
- Detecting objects fully hidden inside closed bags, drawers, cupboards, or beneath opaque coverings.
- Determining the exact disappearance time from periodically captured images.
- Inferring that a person or pet moved an object, or explaining the cause of its disappearance.
- Predicting an object's future location.
- Smart-home integration.
- Speech interaction.
- Native mobile apps.

The following are deferred to a later version:

- A language-model parser producing structured Queries (`query.schema.json`), including several items in one question, `questionType`, `urgency`, `checkedPlaces` and `lastUsedPlace`.
- Explicitly user-provided `usualPlace` and `lastUsedPlace` hints. When added, they must be distinguished from camera observations.
- Per-detection visibility labels.
- A separate time zone for each room.


## 5. Input and Output Interface

### 5.1 User Input and Parsing

The user enters a natural-language question. The page sends it to the search endpoint.

| Request part | Name | Type | Rule |
|---|---|---|---|
| Endpoint | `POST /api/ask` | — | One question per request. |
| Header | `X-Room-Key` | string | Required. The room key from Section 5.4. Missing or invalid → rejected (401), no records shown. |
| Body field | `question` | string | Required. 1–300 characters. Empty or longer → rejected (422) before parsing. |

```json
{"question": "Where is my phone?"}
```

The parser turns the question into one parsed Query, defined under `entities.Query` in `ontology.yaml`:

| Query field | Type | Rule |
|---|---|---|
| questionText | string | Required. The original question, unchanged. |
| objectName | string or null | Required key. The item phrase the user wrote; null when no item is identifiable. |
| descriptors | array of strings | Optional. Colour, size and shape words from the question. |
| lang | enum: `en`, `ko` | Required. `ko` when the question contains Hangul. |
| limitationRequest | boolean | Optional. True when the question asks for an exact disappearance time or who or what moved the item. |

The parser resolves the question as follows.

| Element | Rule |
|---|---|
| Original question | Required. Never change, summarize, or translate it. |
| Item | Exactly one item, matched against the item aliases (Section 4.2 #3), longest phrase first. A Korean question is first converted using a Korean word list and the Korean item names saved for this room. |
| Describing words | Keep colour, size and shape words. Treat equivalent words as the same ("big" = "large", "grey" = "gray"). |
| Ambiguous item | A word defined as ambiguous (e.g. "cable") or two different items in one question → ask which item. |
| No item | Placeholder words ("thing", "stuff", "it") are not items. Ask which item, or use the question fallback. |
| Other item | Match against items this room's camera has recorded. An unmatched item receives a no-record response. |
| Limitation request | Flag questions asking when an item disappeared or who or what moved it, so the answer can explain the scope limitation. |

Apply the ontology's alias mappings during item resolution while preserving the original question wording.

### 5.2 Search Output

Return one Answer per question. The fields are defined under `entities.Response.attributes` in `ontology.yaml`.

| Response field | Type | Meaning |
|---|---|---|
| status | enum | `current`, `last_seen`, `possible`, `not_found`, `clarify`, or `unsupported`. |
| message | non-empty string | The answer shown to the user. States place, time and confidence, explains observation limits or missing evidence, or asks for clarification. |
| object | string or null | The item the answer is about. |
| location | string or null | Place of the selected record; null without a selected record. |
| seen_at | string or null | Capture time of the selected record: an RFC3339 date-time string with a time zone. |
| confidence | number from 0 to 1, or null | Selected record's score; null without a selected record. |
| confirmed | boolean | True only when the selected record satisfies the confidence policy. |
| suggestion | string or null | An explicitly unconfirmed possibility based on a low-confidence detection. |
| source | enum | `rules` or `rag`: whether the rule search or the question fallback produced the answer. |
| lang | enum | `en` or `ko`, following the language of the question. |

Return all fields. Use null where permitted instead of inventing missing information. A confidence score is not a guarantee that the location is correct.

### 5.3 Complete Example Response

The following is a synthetic contract example, not a measured model output.

```json
{
  "status": "last_seen",
  "message": "Your phone is not visible in the current camera view. It was last seen on the bed at 1:51 PM today (80% confidence). If it isn't there now, it may have been moved, covered, or put somewhere the camera can't see, such as a bag or drawer.",
  "object": "phone",
  "location": "on the bed",
  "seen_at": "2026-11-09T13:51:00+09:00",
  "confidence": 0.8,
  "confirmed": true,
  "suggestion": null,
  "source": "rules",
  "lang": "en"
}
```

### 5.4 Rooms and Access

Three kinds of key give three different roles.

| Role | Key | Permitted actions |
|---|---|---|
| Camera phone | Camera token, issued when the phone is set up as a camera | Upload photos and test photos; set or change the room's PIN; issue a new room link; remove the room. It cannot ask questions or read records. |
| Owner's phone | Room key, obtained with the camera ID and PIN (4–6 digits) or with the room link | Ask questions, view the room's item overview, draw zones, view the latest test photo, delete history — for that room only. |
| Server operator | Administrator key | List and remove cameras. The operator cannot read any room's questions, records, zones or photos through the system. |

Rules:

- Setting up a new camera requires an invite code, so that strangers cannot use the service's detection quota. Repeated wrong codes from one address are blocked for 15 minutes.
- Repeated wrong PINs for one camera ID are blocked for 15 minutes. The error message must not reveal whether the camera ID exists.
- Tokens and keys are stored only as hashes. PINs are stored with a salted, slow hash.
- Changing the PIN disconnects phones that used the old PIN. Issuing a new room link disables the old one.
- The room that owns a photo is always taken from the camera token, never from a value in the request.
- The public health check reveals nothing about any room or its records.
- Photos are analysed and then discarded by default. Only the detection fields are kept. Users must be told that photos are sent to a cloud AI service for analysis.


## 6. Acceptance Criteria

The following criteria define the conditions that must be satisfied
for the second version of Where-Is-It AI to be considered successful.

### 6.1 Functional Acceptance Criteria

These criteria use event-driven EARS wording: WHEN a condition occurs, the system SHALL produce a specified result. Every criterion is evaluated for one room, using only that room's records.

Planned test basis:

- Vision evaluation: 20 frozen images × six key item classes = 120 photo-item pairs, taken with the test camera. Include visible and not-visible examples for every class. Two human labelers resolve disagreements before evaluation.
- Freeze the images, labels, model and its settings, prompt, confidence policy, and scoring rules before the run.
- The historical six-class spike remains a separate 120-pair evaluation.
- Parser, retrieval and isolation tests use concrete inputs and expected results in the planned `eval/golden_cases.yaml` and automated tests.
- These are evaluation requirements, not completed test results.

| ID | Acceptance criterion | Pass rule |
|---|---|---|
| AC-01 | WHEN the v2 vision benchmark is evaluated, the system SHALL produce detections using the canonical item values and satisfy the quality targets in Section 6.3. | All three quality gates pass. Report every photo-item pair. Missing required labels or class coverage makes the evaluation INCONCLUSIVE. |
| AC-02 | WHEN a benchmark question is submitted, the system SHALL resolve exactly the item the user named, keep its describing words, and ask for clarification instead of guessing when the item is missing or ambiguous. | Every parser golden case P-01 to P-17 in `parse_query_en.md` returns its expected parse and answer status. The original question is unchanged. |
| AC-03 | WHEN a query resolves to one item with a qualifying detection in a current latest photo, the system SHALL return that observation's location, capture time, and confidence with status `current`. | Returned values match the selected fixture record. The response follows Section 5 and states that the item is visible in the current camera view. |
| AC-04 | WHEN no qualifying latest-frame detection exists for the resolved item, the system SHALL search that item's historical records in the same room. | Ignore other rooms', unrelated and below-threshold records. Select eligible history by capture time. |
| AC-05 | WHEN historical search finds a reliable record, the system SHALL return the latest eligible location, capture time, and confidence with status `last_seen`. | Values match the selected historical record. Do not present it as a confirmed current location. |
| AC-06 | WHEN only below-threshold detections exist, or one is newer than the last confirmed record, the system SHALL offer it only as an explicitly unconfirmed possibility; WHEN no record exists, the system SHALL return a no-record response. | For status `possible`, `confirmed` is false and the suggestion is labelled "not confirmed". For `not_found`, location and confidence are null. |
| AC-07 | WHEN a phone is set up as a camera with the correct invite code, the system SHALL create a separate room and issue a camera token and room key. | Wrong invite codes are rejected and repeated attempts are blocked. |
| AC-08 | WHEN the owner enters the correct camera ID and PIN, the system SHALL issue a room key for that room only. | Wrong PINs are rejected without revealing whether the ID exists, and repeated failures are blocked. |
| AC-09 | WHEN two rooms record the same kind of item, the system SHALL answer each room only from its own records. | Answers, item overview, zones and test photos never include another room's data. |
| AC-10 | WHEN a room's zones change, the system SHALL apply them only to that room's later photos. | Another room's answers are unchanged. |
| AC-11 | WHEN a key is used for an action outside its role (Section 5.4), the system SHALL reject the request. | Missing or wrong keys are rejected and no records are shown. The administrator key never returns records. |
| AC-12 | WHEN the owner deletes history, or the room is removed, the system SHALL delete that room's photos and detections, and on removal also its zones, sessions and test photos. | Other rooms are not affected. |
| AC-13 | WHEN a question is asked in Korean, the system SHALL answer in Korean using the same search rules, including Korean place names. | Korean golden cases (P-09, P-10 in `parse_query_en.md`) return the same status, place and time as their English equivalents, with Korean wording and Korean place names. |
| AC-14 | WHEN the user test is run, participants SHALL be asked whether they are comfortable with a room camera whose photos are analysed by a cloud AI service and stored on a shared server. | Answers are recorded for every participant (`Problem.md` Section 5). |

All returned Answers must follow the contract in Section 5. Boundary and failure behavior is specified in Section 6.2. Numerical quality and performance targets are fixed in Section 6.3.

### 6.2 Error and Uncertainty Handling

Apply the confidence policy defined in `ontology.yaml`. All responses must follow Section 5.

| Condition | Example input | Required behavior | Linked AC |
|---|---|---|---|
| Confidence equals the minimum threshold | Record: phone, 0.75. Ask "Where is my phone?" | The score qualifies under the inclusive comparison, provided sufficient image evidence supports the detection. | AC-01, AC-03, AC-05  |
| Latest-frame confidence is below the threshold, or no qualifying latest-frame detection exists | Current photo has no wallet; record 2 h earlier: wallet on the bed, 0.90 | Do not confirm that candidate. State that the item is not visible in the current view and search the room's history. | AC-03, AC-04  |
| Only below-threshold records exist | Only record: glasses on the sofa, 0.749 | Return status `possible` with `confirmed: false` and a suggestion labelled as not confirmed. | AC-06  |
| No record exists | No earphones records. Ask "Where are my earphones?" | Return `not_found` with null location and confidence. Explain that the available records cannot establish the location. | AC-06  |
| The room has not received any photo | New room, no photo. Ask "Where is my wallet?" | State that no camera images have been received yet. | AC-04  |
| The latest photo is older than the current-view window | Latest photo 2 h old; it shows the wallet on the bed, 0.90 | State that the camera has not sent a recent image and when the last one was taken. Answer from history. | AC-04, AC-05  |
| The item name is missing or matches several item kinds | "Ugh, where did that thing go" · "Where is my cable?" | Ask for clarification. Do not choose an arbitrary item. | AC-02  |
| Several items of the same kind are confirmed | Black wallet on the desk (0.90), brown wallet on the bed (0.88). Ask "Where is my wallet?" | List each with appearance and place and ask which one is the user's. | AC-02, AC-03, AC-05  |
| The requested item has never been recorded in this room | No lighter records. Ask "Where's my lighter?" | Return `not_found`. Do not substitute a similar item. | AC-02, AC-06  |
| The image provides insufficient visible evidence to identify the item | Benchmark photo: wallet mostly hidden under clothes | Do not invent a current location. Use eligible history or the possibility fallback when available. | AC-01, AC-04, AC-06  |
| Detection fails (service unavailable, quota, network) | Detection service returns an error for an uploaded photo | Do not save the photo. Tell the camera to retry later. | AC-01  |
| The question fallback fails, cites no supplied record, or states a below-threshold record as fact | Fallback answer names a place but cites no supplied record | Return the rule-based answer, or downgrade the status to `possible`. | AC-02, AC-06  |
| The request has a missing or invalid key | Ask with a wrong room key | Reject the request and show no records. | AC-11  |
| The user asks for an exact disappearance time or a person/pet explanation | "Exactly when did my phone disappear?" · "Did my cat move my glasses?" | Explain the scope limitation. Return any reliable last-seen observation only as recorded evidence. | AC-02, AC-05  |

Never describe a missed detection as proof that an item is absent. Never show a confidence of 100%. Never present an unconfirmed possibility as a camera fact.

Each condition above must be covered by a concrete golden case or automated test that uses the example input (or an equivalent one) and checks the required behavior, with its linked AC numbers.

### 6.3 Quantitative Acceptance Criteria

The following targets are fixed for this v2 revision. The confidence policy is maintained in `ontology.yaml`; the other numerical targets are maintained in this table. All targets are measured per room.

| Metric | Fixed target | Linked AC |
|---|---|---|
| Minimum qualifying confidence | Apply `policy.min_confirmed_confidence` and `policy.confidence_comparison` from the ontology. | AC-01, AC-03, AC-05 |
| Photo-item match rate | > 90% | AC-01 |
| False-positive rate | < 5% | AC-01 |
| False-certainty rate | < 2% | AC-01 |
| Latest-image search time | < 2 seconds | AC-03, AC-04 |
| Total response time per request | < 6 seconds | AC-02–AC-06 |
| User turns needed when reliable evidence exists | ≤ 2 | AC-02–AC-05 |
| Cross-room data leaks in isolation tests | 0 (any leak fails) | AC-09–AC-12 |

#### Quality calculations

The evaluation unit is one photo-item pair. The planned v2 benchmark contains 20 images × seven item classes = 140 pairs.

Use the agreed human labels and frozen confidence policy. Assign each pair one outcome:

- Match, visible item: a valid output returns a qualifying prediction in the labeled area with no conflicting confirmed location.
- Match, not-visible item: a valid output returns no qualifying prediction for an item labeled not visible.
- Miss: a visible item has no qualifying prediction.
- Wrong area (W): a visible item has a qualifying prediction outside the labeled area or conflicting returned locations.
- False positive (FP): an item labeled not visible has any qualifying prediction.
- Processing failure: no valid output is available. Count this as a mismatch and report it separately.

Let T be all frozen pairs, M the matched pairs, and N the pairs labeled not visible:

- Match rate = M / T.
- False-positive rate = FP / N.
- False-certainty rate = (W + FP) / T.

W and FP are mutually exclusive because they apply to visible and not-visible items respectively. Count each pair once; do not shrink T when processing fails.

When several items of the same kind appear in one photo, judge the pair using the most confident qualifying prediction for that item class.

The labeled area is a zone name when zones are drawn; otherwise it is a canonical place from `vocabulary.places`, and labelers judge whether the model's place description matches it.

Use unrounded values for pass/fail decisions. For 140 pairs, the strict targets require at least 127 matches and at most two false-certainty pairs.

Report per-class results and outcome counts. Missing required labels, unattempted pairs, missing class coverage, or a zero/missing denominator makes the affected evaluation INCONCLUSIVE.

#### Timing and interaction measurements

Latest-image search time starts when a resolved query enters the latest-frame evidence search and ends when that stage produces its result. Photos are analysed when they are uploaded rather than when a question is asked, so detection time per photo is measured and reported separately.

Total response time starts at user submission and ends when the response is ready to display. Include parsing, retrieval, any question-fallback generation, network calls, and retries. Report rule-based and fallback answers separately.

Measure each system response separately during clarification. Count the user's initial request and clarification replies toward the user-turn limit.

Record individual elapsed times and outcomes for every applicable benchmark request. Do not omit failures or timeouts.

#### Reporting and changes

Preserve the dataset and label versions, model settings, prompt version, scoring rules, raw outputs, pair-level judgments, and timing records.

Report PASS only when all applicable criteria are satisfied. Missing measurements are INCONCLUSIVE.

Historical spike results retain their original dataset, scope, and acceptance rules. Do not reinterpret their 120 pairs as the full v2 benchmark.

Any future target change requires a documented new revision before a new evaluation. Do not change targets after seeing results.


## Version History

| Version | Summary |
|---|---|
| v1 | One room, one camera, text questions. |
| v2 draft | Account-based design (email and password). Not implemented. |
| v2 | One private room per camera phone, Gemini detection, search for any item, Korean questions, and a question fallback. Updated after the v1 review. |
