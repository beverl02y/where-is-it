# Where-Is-It AI --- Specification v1

## 1. Problem Definition

University students who cannot remember where they last used or placed an everyday belonging may spend about 5–15 minutes searching several places when they need it, causing stress and a risk of being late.

The supporting interview quotations and validation rules are maintained in `Problem.md`.


## 2. Target Users and Non-Target Users

### 2.1 Primary Target Users

The primary target users are **university students who repeatedly have difficulties in 
finding everyday belongings inside their room**.

The supported v1 item classes and their canonical names are defined in `ontology.yaml` under `vocabulary.items`.

   Glasses
   Wallet
   Cards
   Earphones
   Phone
   Charger

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
-   Family users who need to manage the belongings of multiple people
-   Business users who need to manage many objects or equipment in offices or facilities


This project only focuses on **indoor object finding using available camera
evidence**. It is not intended to replace GPS/Bluetooth tracking devices
or public lost-and-found systems.


## 3. Evidence from User Interviews

The supporting interview quotations are maintained in `Problem.md`, Section 3. The supplied responses are recorded in `interview_answers.md`.

The following table connects the findings to proposed requirements.

| Finding | Interview evidence | Design implication |
|---|---|---|
| Participants mentioned several everyday item types. | Logs 3, 6, 7, and 10, Q2 | Use the bounded item set defined in `ontology.yaml`, under `vocabulary.items`. |
| Missing items were noticed when needed or before leaving. | Log 1 Q4; log 6 Q4; log 10 Q4 and Q8 | Provide simple item-search questions and evaluate whether the system reduces search effort. |
| Participants checked usual storage places first. | Logs 1, 6, and 10, Q5 | Represent an explicitly provided usual place and preserve places the user says they already checked. |
| Finder services indicated nearby items without identifying their exact location. | Log 6 Q8; log 9 Q7 | Return the place and observation time supported by camera records. |
| Remembering the last-used place helped participants recover items. | Logs 1, 6, and 10, Q9 | Support last-seen retrieval while distinguishing camera observations from user memory. |
| Some objects were covered or hidden. | Log 2 Q3; logs 6 and 10 Q9 | Handle limited visibility and avoid inventing a current location. |

Log 1 describes recovery at a copy shop. It supports the value of remembering a last-used place, but does not validate indoor camera coverage.

These findings motivate the proposed design. Camera acceptance, detection reliability, and reductions in search time require separate evaluation.

## 4. Solution and MVP Scope

### 4.1 Core Function

**Where-Is-It AI** is a camera-based AI assistant that helps users
locate misplaced belongings. The system detects supported objects from
indoor camera images, stores their detected location and time, and
allows the user to ask where an object is using natural language.

The system follows a simple principle:

> **Detect → Save → Search → Explain**

For a resolved item query, the system first checks for a qualifying latest-frame observation. If none exists, it searches historical records. Every returned location is accompanied by its image capture time and must be described as a recorded observation rather than a guarantee of the current location.

### 4.2 MVP Features

The first version includes the following core features:

1.  **Object Detection**\
    Detect supported everyday objects from camera images.

2.  **Location Recording**\
    Save the object name, detected location, timestamp, and
    detection confidence.

3.  **Natural-Language Search**\
    Allow the user to ask questions such as:

    -   "Where are my glasses?"
    -   "Where is my wallet?"

4. **Latest-Frame Search**
   Search the latest available camera records for a qualifying observation     of the requested object.

5. **Historical Search**
   If no latest-frame observation qualifies, return the latest qualifying      historical observation, explicitly labeled as last recorded with its        capture time.

6.  **Confidence-Based Response**\
    Clearly distinguish between confirmed detections and uncertain
    possibilities.

7. **Safe Failure**

   Apply the confirmation threshold and comparison operator defined under `policy` in `ontology.yaml`.

   If the latest image has no qualifying detection, search historical records. If no reliable record exists, explain that the item could not be located from the available camera records.

   Any suggestion based on explicit user memory must be labeled unconfirmed. Never invent a detected location.
   
### 4.3 MVP Object Scope

The supported v1 item classes are defined in `ontology.yaml` under `vocabulary.items`. Canonical place names are defined under `vocabulary.places`.

The historical spike's tested subset is recorded under `validation_scope.historical_spike` in the same file. Its results apply only to that subset and the evaluated images.

The full v1 vocabulary is a product scope definition, not a claim that every item and place has already passed detection testing.

### 4.4 Out of Scope for v1

The required v1 scope uses one camera in one room and a text-based search interface.

The following capabilities are outside the required scope:

- Multiple-camera support and cross-room tracking.
- Detecting objects fully hidden inside closed bags, drawers, cupboards, or beneath opaque coverings.
- Determining the exact disappearance time from periodically captured images.
- Inferring that a person or pet moved an object, or explaining the cause of its disappearance.
- Predicting an object's future location.
- Smart-home integration.
- Automatically learning user preferences or usual storage places.
- Speech interaction.

Explicitly user-provided `usualPlace` and `lastUsedPlace` remain permitted context. They must be distinguished from camera observations.

For requests outside this scope, explain the limitation and provide any relevant reliable last-seen record without inventing additional information.

## 5. Input and Output Interface

### 5.1 User Input and Parsed Query

The user enters a non-empty natural-language question.

The parser converts it into the structure defined in `query.schema.json`: a `queries` array containing one Query per requested item, in mention order.

| Query field | Type | Rule |
|---|---|---|
| questionText | string | Required. Preserve the complete original utterance. |
| objectName | string or null | Required key. Preserve the item phrase; use null when no item is identifiable. |
| questionType | enum defined in the ontology | Optional. Omit when unclear. |
| urgency | enum defined in the ontology | Optional. Include only when explicitly expressed. |
| checkedPlaces | array of strings | Optional. Preserve explicitly searched places in the user's wording. |
| lastUsedPlace | string | Optional. Preserve the user's stated memory. |

Validate the parsed result against `query.schema.json`. Apply the ontology's alias mappings during object resolution while preserving the original Query wording.

Example parsed query:

```json
{
  "queries": [
    {
      "questionText": "Where is my phone?",
      "objectName": "phone",
      "questionType": "current_location"
    }
  ]
}
```

### 5.2 Search Output

Return one Response per Query in the same order, grouped in a `responses` array.

Each Response contains the four fields defined under `entities.Response.attributes` in `ontology.yaml`.

| Response field | Type | Meaning |
|---|---|---|
| location_or_last_seen | object or null | Selected observation's location, capture time, and evidence kind; null without a reliable record. |
| confidence_level | number from 0 to 1, or null | Selected record's score; null without a selected record. |
| possibility_suggestion | string or null | An explicitly unconfirmed hint based on user-provided context. |
| fact_vs_possibility_disclaimer | non-empty string | Explain observation limits, missing evidence, or the clarification needed. |

The location object contains:

- `location`: a canonical place string from the ontology.
- `timestamp`: an RFC3339 date-time string with a timezone.
- `evidence_kind`: an allowed value defined in the ontology.

Return all four Response fields. Use null where permitted instead of inventing missing information. A confidence score is not a guarantee that the location is correct.

### 5.3 Complete Example Response

The following is a synthetic contract example, not a measured model output.

```json
{
  "responses": [
    {
      "location_or_last_seen": {
        "location": "table",
        "timestamp": "2026-11-08T14:30:00+09:00",
        "evidence_kind": "history"
      },
      "confidence_level": 0.92,
      "possibility_suggestion": null,
      "fact_vs_possibility_disclaimer": "Your phone was last recorded on the table at 2:30 PM. This does not confirm its current location."
    }
  ]
}
```

## 6. Acceptance Criteria

The following criteria define the conditions that should be satisfied
for the first version of Where-Is-It AI to be considered successful.

### 6.1 Functional Acceptance Criteria

These criteria use event-driven EARS wording: WHEN a condition occurs, the system SHALL produce a specified result.

Planned test basis:

- Vision evaluation: 20 frozen images × seven supported item classes = 140 photo-item pairs. Include visible and not-visible examples for every class. Two human labelers resolve disagreements before evaluation.
- Freeze the images, labels, model, prompt, confidence policy, and scoring rules before the run.
- The historical six-class spike remains a separate 120-pair evaluation.
- Parser and retrieval tests use concrete inputs and expected results in the planned `eval/golden_cases.yaml`.
- These are evaluation requirements, not completed test results.

| ID | Acceptance criterion | Pass rule |
|---|---|---|
| AC-01 | WHEN the frozen v1 vision benchmark is evaluated, the system SHALL produce detections using the canonical item and place values and satisfy the quality targets in Section 6.3. | All three quality gates pass. Report every photo-item pair. Missing required labels or class coverage makes the evaluation INCONCLUSIVE. |
| AC-02 | WHEN a benchmark question is submitted, the parser SHALL return schema-valid Queries with the original question text and explicitly stated item/context words. | Every parser golden case matches its expected fields and passes `query.schema.json`. Preserve one Query per requested item in mention order. |
| AC-03 | WHEN a query resolves to one supported object with a qualifying latest-frame detection, the system SHALL return that observation's location, capture time, confidence, and latest-frame label. | Returned values match the selected fixture record. The response follows Section 5 and explains that the observation does not guarantee the current location. |
| AC-04 | WHEN no qualifying latest-frame detection exists for the resolved object, the system SHALL search that object's historical records. | Ignore unrelated and below-threshold records. Select eligible history by capture time using the ontology's ordering and conflict rules. |
| AC-05 | WHEN historical fallback finds a reliable record, the system SHALL return the latest eligible location, capture time, and confidence, explicitly labeled as history. | Values match the selected historical record, with `evidence_kind` set to `history`. Do not present it as a confirmed current location. |
| AC-06 | WHEN a resolved supported object has no reliable record, the system SHALL provide only an explicitly unconfirmed user-context hint, when available. | Location and confidence are null. Prefer explicit `lastUsedPlace`, otherwise explicit `usualPlace`. If neither exists, the suggestion is also null. |

All returned Responses must follow the four-field contract in Section 5. Boundary and failure behavior is specified in Section 6.2. Numerical quality and performance targets are fixed in Section 6.3.

### 6.2 Error and Uncertainty Handling

Apply the confidence policy defined in `ontology.yaml`. All responses must follow Section 5.

| Condition | Required behavior | Linked AC |
|---|---|---|
| Confidence equals the minimum threshold | The score qualifies under the inclusive comparison, provided sufficient image evidence supports the detection. | AC-01, AC-03, AC-05 |
| Latest-frame confidence is below the threshold, or no qualifying latest-frame detection exists | Do not confirm that candidate. Search the requested object's history. | AC-03, AC-04 |
| No reliable record exists, but explicit user context exists | Return null location and confidence. Provide an unconfirmed hint from `lastUsedPlace`, otherwise `usualPlace`, identifying its source as user information. | AC-06 |
| No reliable record or explicit user context exists | Return null location, confidence, and suggestion. Explain that the available records cannot establish the location. | AC-06 |
| The item name is missing or matches several objects | Ask for clarification. Keep the three nullable Response fields null and do not choose an arbitrary object. | AC-02 |
| The requested item class is unsupported | Explain the supported scope. Do not substitute a similar item. A supported item without records must instead receive a no-record response. | AC-02 |
| The image provides insufficient visible evidence to identify the item | Do not invent a current location. Use eligible history or the user-context fallback when available. | AC-01, AC-04, AC-06 |
| Parser output is invalid or contains invented item/context information | Do not perform a lookup using invalid values. Apply the bounded recovery and fallback procedure in `parse_query.md`. | AC-02 |
| The user already searched the recorded location | Retain the reliable observation and its timestamp. Do not infer that the item must be hidden there. | AC-03, AC-05 |
| Equally recent qualifying records conflict on location | Explain the conflict and return null location and confidence rather than selecting arbitrarily. | AC-03, AC-04, AC-05 |
| The latest capture or image analysis fails | Explain the unavailable evidence. Return eligible older records as history; otherwise use the no-record fallback. | AC-04, AC-05, AC-06 |
| The user asks for an exact disappearance time or a person/pet explanation | Explain the scope limitation. Return any reliable last-seen observation only as recorded evidence. | AC-02, AC-05 |

For multiple-item questions, return a separate Response for each Query in order. An unresolved item must not suppress another item's valid result.

Never describe a missed detection as proof that an item is absent. Never present user memory as a camera observation.

Each condition above must be covered by a concrete golden case with input, expected behavior, and linked AC numbers.

### 6.3 Quantitative Acceptance Criteria

The following targets are fixed for this v1 revision. The confidence policy is maintained in `ontology.yaml`; the other numerical targets are maintained in this table.

| Metric | Fixed target | Linked AC |
|---|---|---|
| Minimum qualifying confidence | Apply `policy.min_confirmed_confidence` and `policy.confidence_comparison` from the ontology. | AC-01, AC-03, AC-05 |
| Photo-item match rate | > 90% | AC-01 |
| False-positive rate | < 5% | AC-01 |
| False-certainty rate | < 2% | AC-01 |
| Latest-image search time | < 2 seconds | AC-03, AC-04 |
| Total response time per request | < 6 seconds | AC-02–AC-06 |
| User turns needed when reliable evidence exists | ≤ 2 | AC-02–AC-05 |

#### Quality calculations

The evaluation unit is one photo-item pair. The planned full-v1 benchmark contains 20 images × seven item classes = 140 pairs.

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

Use unrounded values for pass/fail decisions. For 140 pairs, the strict targets require at least 127 matches and at most two false-certainty pairs.

Report per-class results and outcome counts. Missing required labels, unattempted pairs, missing class coverage, or a zero/missing denominator makes the affected evaluation INCONCLUSIVE.

#### Timing and interaction measurements

Latest-image search time starts when a resolved query enters the latest-frame evidence search and ends when that stage produces its result. Include any image analysis triggered by that search.

Total response time starts at user submission and ends when the response is ready to display. Include parsing, retrieval, generation, network calls, retries, and any image analysis the request waits for.

Measure each system response separately during clarification. Count the user's initial request and clarification replies toward the user-turn limit.

Record individual elapsed times and outcomes for every applicable benchmark request. Do not omit failures or timeouts.

#### Reporting and changes

Preserve the dataset and label versions, model settings, prompt version, scoring rules, raw outputs, pair-level judgments, and timing records.

Report PASS only when all applicable criteria are satisfied. Missing measurements are INCONCLUSIVE.

Historical spike results retain their original dataset, scope, and acceptance rules. Do not reinterpret their 120 pairs as the full-v1 benchmark.

Any future target change requires a documented new revision before a new evaluation. Do not change targets after seeing results.
