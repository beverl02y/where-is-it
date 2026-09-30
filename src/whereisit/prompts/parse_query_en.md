# Where-Is-It AI Parsing Prompt — parse_query.md

| Item | Value |
|---|---|
| prompt_version | 1 |
| Paired schema | `src/whereisit/schemas/query.schema.json` |
| Reading code | `src/whereisit/parser.py` — reads only the text between `<!-- prompt:start -->` and `<!-- prompt:end -->` and sends it as the system prompt |

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
Output: {"queries":[{"questionText":"Where's my black wallet?","objectName":"black wallet" "questionType":"current_location"}]}

Example 2
Input: Ugh, where did that thing go
Output: {"queries":[{"questionText":"Ugh, where did that thing go","objectName":null}]}

Example 3
Input: I'm late, where are my phone and black wallet? Not on the desk.
Output: {"queries":[{"questionText":"I'm late, where are my phone and black wallet? Not on the desk.","objectName":"phone","questionType":"current_location","urgency":"high","checkedPlaces":["desk"]},{"questionText":"I'm late, where are my phone and black wallet? Not on the desk.","objectName":"black wallet","questionType":"current_location","urgency":"high","checkedPlaces":["desk"]}]}
<!-- prompt:end -->

## Field → Function Argument (Hard/Soft)

Input: "I'm late for class, where's my black wallet? It's not on the desk. I think I left it on the bed last night"
Structure to extract as output: `questionText`, `objectName`, `questionType`, `urgency`, `checkedPlaces`, `lastUsedPlace`. If the user is looking for two or more items, create one Query per item and put them in the queries array (because `Query asksAbout Object` is `many:1`, one Query points to only one Object).

| Field | Which argument of which function it goes to | Hard/Soft |
|---|---|---|
| `objectName` | `Query asksAbout Object` — matched against the AI-registered `Object.name` and `Object.category` to confirm the target Object → `Object has Detection` fetches only that Object's detections → rule 1 (`confidence > 70%`) applied | **Hard**. Detections of any Object other than the confirmed Object cannot be the basis of a Response. Required to collect — if null, do not query detections; ask the user again |
| `questionText` | `Query produces Response` — used as the user's original question when generating `Response.answer` | Not used for ranking. For preserving the original text. Literal Input |
| `queries` | Each Query goes through `Query asksAbout Object` → `Query produces Response` separately — one Response per Query | Hard |
| `questionType` | Determines the starting step of rule 2. `current_location` → ① current sighting → `location_or_last_seen` / `last_seen`, `disappeared_when` → ② history (`Detection.timestamp`) → `location_or_last_seen` / `nearby_context` → ③ `Detection coOccursWith ContextEvent` → `possibility_suggestion` / `where_to_look` → ③ + rule 3 → `possibility_suggestion`. If omitted, follow rule 2 in its default order (①→②→③) | Soft. Only changes the order; does not remove detections |
| `urgency` | `Query produces Response` — length of `Response.answer`. If high, one line of `location_or_last_seen`; if low, all Response items. Either way, rule 3's `fact_vs_possibility_disclaimer` is never removed | Not used for ranking. Response format argument |
| `checkedPlaces` | rule 2 ①② — compared against the confirmed `Detection.location`. Even if it matches, the detection is not discarded; per rule 3, the answer states "detected location (fact) + possibility that it is hidden under another item" | Soft. Cases where items were found hidden in places already searched (logs 2, 6, 10) |
| `lastUsedPlace` | rule 2 ③ + rule 3 — since it is the user's memory, used only in `possibility_suggestion` and never in `location_or_last_seen`. Used only when no detection exceeds rule 1 (`confidence > 70%`) | Soft. Cases where the expected location and the actual location differed (logs 4, 9) |

## Schema Design Notes

- **Multiple items are resolved as multiple Queries.** In the ontology, `Query asksAbout Object` is many:1 and `Query produces Response` is 1:1. Turning `objectName` into an array would change these relationships, so one Query is created per item and placed in the top-level `queries` array. `queries` is an outer envelope, not an ontology attribute, and has `minItems: 1` — even an utterance that names no item produces one Query with `objectName: null`. All Queries from the same utterance have the same `questionText`.
- **The properties are the same as the six attributes of the ontology's `Query`.** `questionText`, `objectName`, `questionType`, `urgency`, `checkedPlaces`, `lastUsedPlace`. When the ontology changes, the schema is changed in the same commit. Owner distinction ("not my roommate's") is information the camera cannot know and would also require an attribute on `Object`, so it is deferred to v2.
- **required = `questionText`, `objectName`.** Without the original text and the item being searched for, a Query cannot exist. `questionText` always exists, so null is not allowed; `objectName` may be unknown, so it is opened as `["string", "null"]`. `{"questionText":"Ugh, where did that thing go","objectName":null}` must pass validation so that the application can ask the user again.
- **null vs. omission.** The two required keys are null when unknown; the other four keys (`questionType`, `urgency`, `checkedPlaces`, `lastUsedPlace`) are omitted entirely when not in the utterance. To treat empty arrays as omission as well, `minItems: 1` is set on `checkedPlaces`.
- **enum only for closed sets.** `questionType` is the five questions defined by the ontology's purpose (`current_location`, `last_seen`, `disappeared_when`, `nearby_context`, `where_to_look`), and `urgency` has two values, `high`/`low`, so enums are applied. If it cannot be determined, do not force a choice; omit it.
- **Why there is no enum on `objectName`.** `Object.name` is a descriptive name ("black wallet") that the AI assigns when detecting, so it is not a closed set. Putting an enum on an unclosed value makes the model cram the input into the closest value — the anxiety factor from the interviews ("it sees a different wallet and says the wallet is on the table") is exactly this kind of forced mapping. Instead, `objectName` is built only from words in the utterance to prevent hallucination, and matching against registered Objects happens in `Query asksAbout Object`.
- **Why there is no enum on the place fields.** `checkedPlaces` and `lastUsedPlace` are compared against `Detection.location`, but its list of values has not been decided yet. The user's expressions are taken as-is and matching happens at the rule 2 step. Once the list is finalized, injection + post-processing matching will be considered.
- **Why appearance expressions are kept and owner expressions are removed.** The names the AI assigns include appearance such as color and material, so "black" is used to tell apart multiple items of the same kind. "My" and "roommate's" are information the camera cannot know, so they do not help matching and actually get in the way.
- **`additionalProperties: false`.** Applied both at the top level and on `Query`. It prevents the parser from answering the location directly, like `"location": "bed"`, or pulling in `Object`'s attributes (`category`). If the model's guess replaces `Detection`, rule 3 (distinguishing confirmed facts from possibilities) breaks down.

## Failure Mode Checklist

| # | Failure mode | Test input | Where it is caught | What happens next |
|---|---|---|---|---|
| 1 | (Normal) | "I'm late for class, where's my black wallet? It's not on the desk. I think I left it on the bed last night" | 1 Query. Passes schema, passes post-processing, matches exactly one, `"black wallet"`, in `Query asksAbout Object` | `Object has Detection` → rules 1–3 → `Query produces Response`. Since urgency is high, one line of `locationOrLastSeen` + `factVsPossibilityDisclaimer` |
| 2 | Insufficient information | "Ugh, where did that thing go" | Passes schema (null allowed). In the required-condition check, `objectName` is null | Without calling the model again, ask back: "Which item are you looking for?" |
| 3 | Ambiguous value (multiple matching Objects) | "Where's my wallet?" | Passes parser, schema, and post-processing. Matches two, `"black wallet"` and `"brown leather wallet"`, in `Query asksAbout Object` | Do not pick one and answer. Show the candidates by their registered names and ask back, e.g., "Is it the black wallet or the brown leather wallet?" |
| 4 | Range violation | Output contains `"objectName": ""`, `"questionText": null`, `"questionType": "where"`, `"urgency": "medium"`, `"checkedPlaces": []` | Schema `minLength` / type / `enum` / `minItems` violation → validation fails | Re-request with the error message attached (max 2 times) |
| 5 | Unregistered item | "Where did I put my lighter" | The parser outputs `"lighter"` as per the rules and passes schema and post-processing. 0 matching Objects in `Query asksAbout Object` | Tell the user "The camera hasn't detected and registered a lighter yet." Do not give the location of a similar item instead |
| 6 | objectName altered (translation/additions) | "Where's my phone" → output `"objectName": "black smartphone"` | Post-processing checks whether every word in objectName appears in `questionText` → "black", "smartphone" are not there | Re-request (max 2 times). If the re-request limit is exceeded, ask back as in #2 — matching with the model's invented "black" could confirm the wrong Object |
| 7 | Place hallucination | "Where's my phone" → output `"checkedPlaces": ["desk"]` or `"lastUsedPlace": "bag"` | Post-processing checks whether the place expression appears in `questionText` → it does not | Do not re-request; delete that key. Both fields are optional soft fields, so deleting them does not stop processing — better than letting an invented place get into `possibilitySuggestion` |
| 8 | Original text altered | The output's `questionText` is a summarized or translated sentence, or `questionText` differs between Queries from the same utterance | Post-processing string-compares against the actual input → mismatch | Do not re-request; overwrite every Query's `questionText` with the actual input (because the code already knows the value) |
| 9 | Key not in schema / envelope missing | Output contains `"location": "bed"`, `"category": "wallet"` / a single Query is output without `queries` | `additionalProperties: false`, top-level `required: ["queries"]` → validation fails | Re-request with the error message attached (max 2 times). The location the model wrote is not used anywhere |
| 10 | Not JSON or truncated | The model answers with a sentence like "Wallets are usually on the desk" / `stop_reason` is `max_tokens` | Response status check and JSON parsing fail | Re-request (max 2 times) |
| 11 | Two or more items (normal) | "Where are my phone and black wallet?" | 2 Queries. Passes schema and post-processing | Each Query separately goes through `Query asksAbout Object` → `Query produces Response`. The answers are split per item and shown together at once |
| 12 | Only one of two items resolved | "Where are my phone and that thing?" / "Where are my phone and lighter?" | One of the 2 Queries has `objectName` null (required-condition check) or 0 matches in `Query asksAbout Object` | Answer the resolved item right away, and only ask back about the other (#2) or report that it is not registered (#5). Do not stop everything because one is blocked |
| 13 | Query missing / duplicated | "My phone and wallet" → only 1 Query / 2 Queries with the same objectName | Post-processing: duplicate check on objectName → merged into one. A missing Query cannot be caught from the parser output alone | The code merges duplicates. To guard against missing Queries, the first line of the answer echoes the list of items searched ("Found your phone") so the user can notice a missing item |

- **Error types that trigger a re-request**: Format errors (4 range violation, 9 key not in schema / envelope missing, 10 not JSON / truncated) and 6 objectName altered. Insufficient information and ambiguity (2, 3, 5, 12) are not re-requested; the user is asked back. Original-text alteration (8) and duplication (13) are fixed by the code, and place hallucination (7) is handled by deleting the key 

- **Number of re-requests**: 2

- **Fallback when exceeded**: After 3 consecutive failures, give up parsing and ask the user back: "Please just tell me the name of the item you're looking for." Do not proceed with a detection query using guessed values.


## Test Run Log

Record the results of running the test inputs on the actual model. Record the model ID, `prompt_version`, and schema commit for each row.

| # | Model ID | prompt_version | Schema commit | Actual output | Caught as expected? |
|---|---|---|---|---|---|
| 1 |  | 1 |  |  |  |
| 2 |  | 1 |  |  |  |
| 3 |  | 1 |  |  |  |
| 5 |  | 1 |  |  |  |
| 10 |  | 1 |  |  |  |

(4, 6, 7, 8, 9 are verified not with model output but by feeding the corresponding outputs directly into the validator and post-processing. 3, 5, 12 can only be verified by running through the *Query asksAbout Object* matching.)

## Change History

- 
