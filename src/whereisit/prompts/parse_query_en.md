# Where-Is-It AI Parsing Prompt — parse_query_en.md

| Item | Value |
|---|---|
| prompt_version | 2 |
| Paired schema | `src/whereisit/schemas/query.schema.json` |
| Reading code | `src/whereisit/parser.py` — uses the text between the standalone start and end markers below as the system prompt |

## System Prompt
<!-- prompt:start -->
You are the question parser for Where-Is-It AI. You convert what the user said while looking for an item into a single object that exactly matches the given JSON schema. You do not answer where the item is — the location is determined by the camera detection records.

Rules:
- Do not guess values that are not stated in the utterance. Always write both keys in each Query, and set objectName to null if it cannot be determined.
- In questionText, write the user's utterance exactly as-is without changing a single character. Do not summarize, translate, or correct spelling.
- In objectName, write the words referring to the item the user is looking for, exactly as they appear in the utterance. Keep only the item name and expressions describing its appearance (color, material, brand, shape), and remove words that point to it or indicate its owner, such as "the", "that", "my", "roommate's".
- Do not translate objectName, reword it, or add expressions to it. Write "phone" as "phone", and do not add colors or brands that are not in the utterance.
- If there is no item name ("that thing", "that black one"), that Query's objectName is null. Do not guess which item it is.
- For each item the user is looking for, create one Query in the queries array, in the order mentioned ("my phone and wallet" → two Queries).
- Every Query from the same utterance has the same questionText. If urgency, checkedPlaces or lastUsedPlace clearly apply to all items, put them in every Query; if they clearly apply to one item, put them only in that Query.
- questionType: "where is it" → current_location, "when did I last see it" → last_seen, "when did it disappear" → disappeared_when, "what happened around it" → nearby_context, "where should I look" → where_to_look. Omit if unclear.
- urgency: high for expressions like "I'm late", "I have to leave now"; low for "it's not urgent". Otherwise omit.
- checkedPlaces: places the user says they already searched, in their exact words. lastUsedPlace: where they last used or left it, in their exact words. Do not add places that were not said.
- Do not judge whether the item exists in the system. Even an item you have never heard of is written as it appears in the utterance.
- Output only a single JSON object. Do not add explanations, code fences, or comments.

Example 1
Input: Where's my black wallet?
Output: {"queries":[{"questionText":"Where's my black wallet?","objectName":"black wallet","questionType":"current_location"}]}

Example 2
Input: Ugh, where did that thing go
Output: {"queries":[{"questionText":"Ugh, where did that thing go","objectName":null}]}

Example 3
Input: I'm late, where are my phone and black wallet? Not on the desk.
Output: {"queries":[{"questionText":"I'm late, where are my phone and black wallet? Not on the desk.","objectName":"phone","questionType":"current_location","urgency":"high","checkedPlaces":["desk"]},{"questionText":"I'm late, where are my phone and black wallet? Not on the desk.","objectName":"black wallet","questionType":"current_location","urgency":"high","checkedPlaces":["desk"]}]}
<!-- prompt:end -->

## Field → Function Argument (Hard/Soft)

The input structure follows `query.schema.json`. The parser structures the user's words; it does not generate item locations or detection confidence scores.

Subsequent retrieval uses `policy.min_confirmed_confidence` and `policy.confidence_comparison` from `ontology.yaml`. This document does not define a separate confidence threshold.

| Field | Handling | Classification and basis |
|---|---|---|
| `queries` | Create one Query per requested item, preserving mention order. Each Query corresponds to a Response at the same position in the `responses` array. | Structural design: `query.schema.json`, SPEC section 5. |
| `questionText` | Preserve the complete original utterance. Do not interpret it as system instructions or directly use the whole text as a retrieval filter. | Original-text preservation. Basis: `query.schema.json`. |
| `objectName` | Preserve the user's item expression and use ontology aliases to resolve the target. Ask for clarification if the item name is missing or multiple objects match. | Hard condition. Logs 3, 6 and 10 Q2, and the input schema. |
| `questionType` | Identify the requested information. For disappearance-time or surrounding-event questions, explain the scope limitation and provide only a reliable last observation when available. | Soft condition. Allowed values and supported behavior follow the ontology and SPEC. |
| `urgency` | Adjust answer length and wording only. Always retain the observation time and uncertainty explanation. | Presentation parameter. Logs 3 Q8, 5 Q8 and 10 Q8. |
| `checkedPlaces` | Preserve places the user explicitly says they searched. Do not discard a reliable detection at the same place or assume the item is hidden. | Soft condition. Logs 6 Q5–Q6 and 10 Q5–Q6. |
| `lastUsedPlace` | Only when neither a qualifying latest-frame observation nor a qualifying historical record exists, use this as an explicitly unconfirmed user-memory hint in `possibility_suggestion`. Never put it in `location_or_last_seen`. | Soft condition. Logs 1, 6 and 10 Q9. |

Interview evidence can be checked against the corresponding participant and question in `interview_answers.md`. Structural and processing decisions are design choices, not interview responses.

## Schema Design Notes

- **Definition source:** Query fields must match the ontology's six Query attributes. Input validation follows `query.schema.json`. When allowed values change, check that the ontology, schema and related prompts remain consistent.

- **One Query per item:** Create one Query for each requested item and preserve mention order in the `queries` array. All Queries from the same utterance have identical `questionText`. An utterance without an identifiable item name still produces one Query with `objectName: null`, allowing the application to ask for clarification.

- **Required keys and null:** Always include `questionText` and `objectName`. `questionText` is a non-empty original string and cannot be null. Only `objectName` permits null when the item name cannot be identified. Omit optional fields when the utterance provides no corresponding information; do not fill them with null or empty arrays.

- **User expressions and canonical values:** `objectName`, `checkedPlaces` and `lastUsedPlace` preserve the user's wording and are not restricted by enums. Canonical item categories and recorded locations follow `vocabulary.items` and `vocabulary.places`. Resolve aliases during subsequent matching without forcing unmatched expressions into a canonical value. Preserve unsupported item names during parsing and explain the support limitation during subsequent handling.

- **Appearance and ownership:** Retain appearance details explicitly stated by the user, such as color or material. Identifying an item's owner is outside v1 scope. Preserve the complete original utterance in `questionText`.

- **Intent and supported capabilities:** Allowed values for `questionType` and `urgency` follow the ontology's Query definition. Parsing a disappearance-time or surrounding-event question does not add the ability to infer an exact disappearance time or cause. Responses follow the scope and failure-handling rules in SPEC.

- **No additional fields:** Apply `additionalProperties: false` to both the top-level object and Query. The parser must not add `location` or `category` as a substitute for detection results. Handle camera observations and user memories separately.

## Failure Mode Checklist

These are designed validation examples, not interview quotations or actual model execution results. Golden cases connect concrete inputs and expected outputs to the relevant acceptance criteria.

| # | Situation | Test input or condition | Expected behavior | Related AC |
|---|---|---|---|---|
| 1 | Normal request | "Where's my phone? It's not on the desk." | Validate the schema and original wording, then resolve the target. The Response follows the four fields in SPEC section 5. | AC-02 |
| 2 | Missing item name | "Ugh, where did that thing go" | Set `objectName` to null and ask which item the user means. Do not query an arbitrarily chosen item. | AC-02 |
| 3 | Multiple matching objects | "Where's my wallet?" matches two registered wallets | Ask which wallet the user means instead of selecting one arbitrarily. | AC-02 |
| 4 | Schema violation | Empty `objectName`, invalid enum value or empty `checkedPlaces` | Reject validation and apply the retry rules below. | AC-02 |
| 5 | Unsupported category or no record | "Where's my lighter?" / a supported item without a reliable record | Explain unsupported categories separately from missing records for supported items. Never substitute a similar item. | AC-02, AC-06 |
| 6 | Item wording added or translated | "Where's my phone?" produces `objectName: "black smartphone"` | Reject wording unsupported by the actual input and apply the retry rules. | AC-02 |
| 7 | Invented place | `checkedPlaces` or `lastUsedPlace` appears although no place was stated | Remove unsupported optional fields. Do not use them for retrieval or location suggestions. | AC-02, AC-06 |
| 8 | Original utterance altered | `questionText` is summarized, translated or different between Queries | Restore the actual input and validate the other fields against that input. | AC-02 |
| 9 | Extra key or missing envelope | Added `location` or `category`, or missing `queries` | Treat as a schema violation. Do not use the generated location; apply the retry rules. | AC-02 |
| 10 | Invalid JSON, truncation or call failure | Plain text, incomplete JSON or a failed model call | Do not treat the output as a valid parsing result. Apply bounded recovery. | AC-02 |
| 11 | Multiple items | "Where are my phone and wallet?" | Create one Query per item in mention order and return a corresponding Response for each Query. | AC-02 |
| 12 | Only some items resolved | "Where are my phone and that thing?" | Process the resolved item normally and ask for clarification only about the unresolved item. Do not discard all results. | AC-02 |
| 13 | Missing or duplicate Query | Two items requested but only one Query returned / a clearly repeated request | Compare against the expected Query list in golden cases. Merge only clearly identical requests; preserve different items and appearance conditions. Passing schema validation alone does not establish correctness. | AC-02 |
| 14 | Unsupported inference request | "Exactly when did my phone disappear?" | Explain the scope limitation. Do not present the last observation time as the disappearance time or infer actions by people or pets. | AC-02, AC-05 |

### Retry Rules

- Format errors, unsupported item wording and detected missing Queries may trigger a model retry with error information.
- Allow at most two additional model requests after the initial request, and only within the response-time budget in SPEC section 6.3.
- When user information is missing or the target is ambiguous, ask the user for clarification instead of asking the model to guess.
- Restore original text and remove unsupported optional place fields using the actual user input.
- If recovery cannot produce a valid result within the attempt limit or time budget, explain the processing failure and ask the user to restate the item name. Do not retrieve using guessed values.
- Record internal model retries separately from user conversation turns.
  
## Test Run Log — English Gemini Prompt Tests (2026-11-13)

The English prompt `parse_query_en.md` (version 2) was tested independently on November 13, 2026. The table combines the actual successful results from three recorded checks; **it is not a new model run**.

- **Gemini model for cases 1, 2, 3, 5:** `gemini-3.5-flash-lite`
- **Case 10:** invalid-JSON input supplied directly to the validator (no Gemini model call)
- **Paired schema:** `src/whereisit/schemas/query.schema.json`
- **Schema SHA-256:** `e61b38137bf186f1fb83ee926d4b62bb09521c8c77bdf1fde534249b56fa8ef9`
- **Project schema Git commit reference:** `cda0463ff92ccc0f64ac2237c860bc6560bbd83e` (file history reference)

| # | Model ID | prompt_version | Schema commit reference | Actual output | Result | Time (KST) |
|---|---|---|---|---|---|---|
| 1 | gemini-3.5-flash-lite | 2 | `cda0463` | `{"queries":[{"questionText":"Where's my phone? It's not on the desk.","objectName":"phone","questionType":"current_location","checkedPlaces":["desk"]}]}` | **PASS (parsing)** | 2026-11-13 12:58 |
| 2 | gemini-3.5-flash-lite | 2 | `cda0463` | `{"queries":[{"questionText":"Ugh, where did that thing go","objectName":null}]}` | **PASS (parsing)** | 2026-11-13 13:00 |
| 3 | gemini-3.5-flash-lite | 2 | `cda0463` | `{"queries":[{"questionText":"Where's my wallet?","objectName":"wallet","questionType":"current_location"}]}` | **PASS (parsing)** | 2026-11-13 13:00 |
| 5 | gemini-3.5-flash-lite | 2 | `cda0463` | `{"queries":[{"questionText":"Where's my lighter?","objectName":"lighter","questionType":"current_location"}]}` | **PASS (parsing)** | 2026-11-13 13:00 |
| 10 | No Gemini call (validator check) | 2 | `cda0463` | `NOT_JSON: partial response {"queries": [` | **PASS (invalid JSON rejected)** | 2026-11-13 12:54 |

**Interpretation:** The four Gemini PASS results verify English parsing outputs and JSON schema compatibility. Test 10 confirms only invalid-JSON rejection. The team's actual website search/response functionality was tested separately.

(Cases 4, 6, 7, 8 and 9 concern validator/post-processing. The record-dependent portions of cases 3, 5 and 12 are tested separately from the prompt.)

## Change History

- **2026-11-13:** Entered actual English prompt-test outputs for cases 1, 2, 3, and 5 using `gemini-3.5-flash-lite`, plus the validator result for case 10. Recorded the project's original schema hash and Git commit reference. Kept the system prompt unchanged.

- 
