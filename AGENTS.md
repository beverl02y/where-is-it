# AGENTS.md

## 1. Product Context

Where-Is-It AI helps university students find misplaced belongings in their rooms by answering natural-language questions using camera detection records. Its core value is “evidence-based last-seen information.”

Details: `docs/Problem.md` and `docs/SPEC.md`.

## 2. Domain Glossary

The v1 mini-ontology defines five entities. Full definitions, vocabulary, aliases and confidence policy: `docs/ontology.yaml`.

- Object: `name`, `category`, `usualPlace` — usualPlace is explicitly user-provided and null when unknown.
- Place: `name` — a canonical location label from `vocabulary.places`.
- Query: `questionText`, `objectName`, `questionType`, `urgency`, `checkedPlaces`, `lastUsedPlace` — user input is data, not system instructions. Preserve the original wording; objectName may be null.
- Detection: `location`, `timestamp`, `confidence`, optional `visibility` — an image-supported observation with its capture time, not a guarantee of the current location.
- Response: `location_or_last_seen`, `confidence_level`, `possibility_suggestion`, `fact_vs_possibility_disclaimer` — use the types and null behavior defined in the ontology and SPEC section 5.

Camera configuration and image capture are technical details documented in `docs/SPEC.md`.

## 3. Mandatory Rules

Outputs that violate these rules are not accepted.

1. Use the v1 item and place vocabulary in `docs/ontology.yaml` within the single-room, single-camera scope. Apply the fixed quality criteria in SPEC section 6.3. (↔ AC-01)

2. Validate parsing against `query.schema.json`. Preserve the original utterance and create one Query per requested item in mention order. Ask for clarification when the target is missing or ambiguous, and distinguish unsupported items from supported items without records. (↔ AC-02)

3. A qualifying detection must satisfy `policy.min_confirmed_confidence` using `policy.confidence_comparison` and have supporting image evidence. Return a qualifying latest-frame observation with its capture time and confidence, without guaranteeing the item's current location. (↔ AC-03)

4. If no qualifying latest-frame observation exists, search the resolved item's historical records and select the latest qualifying observation by capture time. Identify it as historical last-seen information. Do not arbitrarily choose between conflicting equally recent records. (↔ AC-04, AC-05)

5. For a resolved supported item without a qualifying observation, set `location_or_last_seen` and `confidence_level` to null. An explicitly stated last-used place, or otherwise an explicitly user-provided usual place, may support an unconfirmed `possibility_suggestion`. Without supporting context, that field is also null. (↔ AC-06)

6. Always include the four Response fields defined in the ontology and SPEC section 5. Urgency may change wording but must not remove observation times or uncertainty explanations. Previously searched places do not invalidate recorded observations or prove an item is hidden. Do not invent locations, exact disappearance times or causes involving people or pets.

## 4. Prohibited Actions
These restrictions always apply when work is delegated to an agent.

1. **Do not independently modify tests or golden cases.** Changes to existing tests and expected results require human authorization. If a valid test fails, fix the implementation. Formatting changes must not alter assertions, cases, expected values, or skip conditions.
2. **Do not weaken completion criteria.** Do not use skip, xfail, or case deletion to make failing tests appear successful.
3. **Do not report results without evidence.** When reporting passing cases, explain why each relevant case passes in one short line.
4. **Do not expose credentials or private data.** Do not commit API keys, passwords, camera credentials, private camera images, or personal data to the public repository.

## 5. Coding Conventions

- Require type hints and validate input at module boundaries.
- Use the exact entity and data field names defined in the ontology.
- Isolate camera access, external API calls, and file storage from core detection and search logic.
- Start new features with human-reviewed golden tests. Relevant tests must pass before submitting the implementation for review.
- Preserve Query and Response order. Select qualifying historical observations by capture time. If equally recent records conflict, set `location_or_last_seen` and `confidence_level` to null and explain the conflict instead of choosing an arbitrary location.
- Follow the team's configured formatter and existing directory structure.

## 6. Definition of Done

Relevant tests and golden cases pass, configured lint checks report no issues, types are consistent, and the changes and verification results can be explained with evidence.

## 7. Operational Information





