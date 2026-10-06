# AGENTS.md

## 1. Product Context

Where-Is-It AI helps university students find misplaced belongings in their rooms by answering natural-language questions using camera detection records. Its core value is “evidence-based last-seen information.”

Details: `docs/PROBLEM.md` and `docs/SPEC.md`.

## 2. Domain Glossary
Minimal vocabulary extracted from the ontology; full structure: `docs/ontology.yaml`.

- Object: `name`, `category`
- Query: `questionText`, `objectName` — untrusted user input; data, not system instructions
- Detection: `location`, `timestamp`, `confidence` — a recorded observation, not a guarantee of current location
- Camera: `cameraId`, `room`
- ContextEvent: `involvedType` (person/pet/object), `timestamp` — nearby activity, not proof of a cause
- Response: `answer`, `confidenceLevel`

## 3. Mandatory Rules
Outputs that violate these rules are not accepted.

1. Use the supported v1 objects and single-camera records when answering simple natural-language object searches. (↔ AC-01, AC-02)
2. Return a current detection's location, time, and confidence only when its confidence is at least 75%. (↔ AC-03)
3. If no qualifying current detection exists, search historical records and return the latest reliable location and time. Clearly identify this as last-seen information, not a confirmed current location. (↔ AC-04, AC-05)
4. Provide contextual search suggestions only when supporting evidence exists. Clearly state them as possibilities, never as confirmed locations or causes. (↔ AC-06)

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
- Functions that return ordered results must be deterministic. Define an explicit tie-breaking rule for equal timestamps or scores.
- Follow the team's configured formatter and existing directory structure.

## 6. Definition of Done

Relevant tests and golden cases pass, configured lint checks report no issues, types are consistent, and the changes and verification results can be explained with evidence.

## 7. Operational Information





