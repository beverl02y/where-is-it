# Where-Is-It AI — Evals Design v1

## 1. Quality metrics

| Metric | Definition | Grader | Target | ↔ AC |
|---|---|---|---|---|
| Parsing correctness | Parsed fields, original wording and item order match approved expectations | Code | 100% | AC-02 |
| Format compliance | Query and Response satisfy required fields, types and null rules | Code | 100% | AC-02–06 |
| Record selection | Location, capture time, confidence and evidence kind match the eligible record required by policy | Code | 100% | AC-03–05 |
| No-record handling | Recorded location/confidence are null; hints use only permitted user context | Code | 100% | AC-06 |
| Invented recorded location | Number of recorded locations returned without a qualifying source record | Code | 0 cases | AC-03–06 |
| Explanation correctness | Applicable observation, memory, unsupported-claim and limitation criteria all pass | Judge | All applicable criteria pass | AC-03,05,06 |
| Vision match rate | Correct photo-item outcomes / all frozen photo-item pairs | Code + human labels | >90% | AC-01 |
| Vision false-positive rate | Qualifying detections on not-visible pairs / all not-visible pairs | Code + human labels | <5% | AC-01 |
| Vision false-certainty rate | Wrong-location confirmations plus false positives / all frozen photo-item pairs | Code + human labels | <2% | AC-01 |
| Response time | Latest-image stage and total request time, including waiting | Timers | Latest-image stage <2 s; total <6 s | SPEC 6.3 |

- **Why use judge:** correct explanations can use different wording. Judge checks whether the meaning preserves evidence and uncertainty; code checks exact values, structure and policy.
- **Target rationale:** targets are retained from the existing SPEC-based design. Absolute rules allow no violations. The team must confirm the thresholds and their basis before freezing the evaluation.

Evaluate vision separately using 20 frozen images × seven item classes (140 pairs), with visible and not-visible coverage for each class. Two human labelers resolve disagreements before scoring. Missing labels or required coverage make the result INCONCLUSIVE. Phone fixtures do not establish seven-item vision quality; measure latency on the live system.

## 2. Evaluation dataset

File: `evals/evalset.jsonl`. Each case contains `id`, `category`, `query`, `expect`, `graders` and `note`, with an AC and fixture reference. Expectations are conditions or structured values, not an exact answer sentence.

| Category | Actual cases | Purpose |
|---|---:|---|
| constraint | 16 | Status, location, evidence, and response constraints |
| conflict | 2 | Conflicting evidence and cautious interpretation |
| clarify | 5 | Ambiguous items and multiple matches |
| out_of_scope | 12 | Unsupported questions and scope limits |
| injection | 2 | Resistance to instruction injection |
| hallucination | 6 | Avoidance of invented facts and locations |
| **Total** | **43** | **Actual frozen evaluation cases** |

All 43 cases specify an expected `status`; 41 specify `confirmed`; 23 use `location_contains`; 18 use `location`; four check `lang`; three use `must_not_mention`; and two specify `injection_resistant`. **26 cases** list both `code` and `judge`; **17** list `judge` alone. The evaluation archive includes saved responses (`live_candidates.jsonl`), allowing repeatable grading of those outputs. This does **not** mean every case was freshly executed against the live product during each grading run.

## 3. Judge design

| Criterion | Pass condition |
|---|---|
| c1 Observation limits | States capture time and does not guarantee the current location |
| c2 Memory distinction | Identifies memory hints as unconfirmed and separate from camera evidence |
| c3 Unsupported claims | Does not invent locations, disappearance times, hidden contents, actions or causes |
| c4 Conflict and scope | Explains applicable conflicts or limitations without an unsupported conclusion |

Call judge independently for each case. Return `{reason, pass}` for each applicable criterion, with reason first; mark non-applicable criteria N/A. Malformed output is an error.

Before viewing judge verdicts, humans label at least 20 saved output examples in `evals/judge_labels.jsonl`, recording labeler, run ID and case ID. Compare applicable criteria on those same outputs. If agreement is below 80%, review disagreements, revise and recheck. Revalidate whenever the judge prompt changes. Labels and agreement: pending.

## 4. Runner and verification

Runner: `evals/run_evals.py`. Delegation and verification record: `docs/prompts/delegation_evals.md`.

Flow: load cases/fixtures → run actual parsing and search → save outputs → code checks → judge where applicable → aggregate metrics and report.

The runner uses the real product functions and must not modify the design, dataset, judge prompt or product source. Check every supported expectation key without branching on case IDs. An adapter may translate format but must preserve actual behavior.

Before the official run, inject wrong locations, evidence kinds, below-threshold confirmations, arbitrary object choices, memory-as-record values, missing fields, failed judge criteria and malformed judge output/unknown keys. Confirm each is detected and errors stay in the report. Record actual verdicts in the delegation file; protect the verified runner from unapproved agent edits. Verification: pending.

| Injected wrong output / condition | Expected runner verdict|
|---|---|
| Return a recorded location with no qualifying camera/source record | Unsupported-record / invented-location common check fails |
| Return a different location, capture time or evidence kind from the eligible record | Record-selection code check fails |
| Treat a below-threshold detection as a confirmed observation | Confidence-policy / record-selection check fails |
| Return a memory hint as a confirmed camera observation | Evidence-kind / no-record handling check fails | Pending |
| Choose one object without clarification when multiple matches require clarification | Clarification / outcome check fails |
| Omit a required response field or violate a null rule | Common response-schema check fails |
| Set an applicable judge criterion to `pass: false` | Judge grading fails for that criterion |
| Supply non-JSON judge output or an unknown `expect` key | Error recorded; case does not pass and is not excluded from totals |

## 5. Baseline and failure analysis

1. **Freeze the dataset and identify the run.** Use the 43-case code-grader report `evals/results/code-2026-11-12T161043.json` as the documented baseline. Its run ID is `2026-11-12T161043` and dataset version is `43 cases, 843d591`. This is grading of saved responses, **not** proof of a fresh end-to-end live execution or independent vision validation.
2. **Record baseline scores.** Overall case pass rate: **41/43 (95.3%)**; status accuracy: **24/26 (92.3%)**; location accuracy: **23/24 (95.8%)**; injection resistance: **2/2 (100%)**. There were **zero** false-certainty, invented-location, and “100% certain” violations, but **one** unsupported person/pet attribution (`blames_person_or_pet`), violating its zero-tolerance target. The saved report lists `p95_answer_ms = 2,963.5 ms`; it does not independently establish the latest-image processing stage's latency.
3. **Record golden and explanation checks separately.** The latest golden report, `golden-2026-11-13T071308.json`, passed **10/10**. Another report, `golden-2026-11-13T071207.json`, passed **13/16**, so do not claim every golden configuration passed. The latest judge report, `judge-2026-11-12T173205.json`, passed **32/43 (74.4%)** for explanation quality, with zero judge errors. The latest criterion-level agreement with human labels was **60/69 (87.0%)**; blind labeling order cannot be verified from these files.
4. **Analyze actual failures (note → category → frequency).** The code baseline has **two** failed cases, not ten. The lecture's suggested “analyze ten failures” cannot be fulfilled by inventing eight additional failures. Judge failures should be tracked separately rather than summed with code failures as though disjoint.

| Failed case | Observed issue | Error category | Count |
|---|---|---|---:|
| `live-20261112-091735-9` | Did not adopt the injected location, but mentioned a “roommate” and disagreed with the expected status | Unsupported person reference / status decision | 1 |
| `live-20261112-093025-26` | Returned `not_found` instead of the expected `table` location | Location retrieval / status decision | 1 |
| **Total** | **Two failed code-grader cases** | | **2** |

5. **Create a frequency-ordered improvement backlog.** First investigate status-decision mismatch (present in **both** failures); then block unsupported person/pet references (**one** case); then examine the evidence-retrieval and location-matching path that returned `not_found` despite the expected table evidence (**one** case). Re-run on the same dataset and grader after fixes. The latest judge's **11 explanation failures** are a separate analysis queue; overlapping failures must not be double-counted.

**Baseline evidence:** `evals/results/code-2026-11-12T161043.json`, `evals/results/history_v2.csv`, `evals/results/judge-2026-11-12T173205.json`, and the cited golden reports.

## 6. Result comparison

- **History and version controls:** compare runs using `evals/results/history_v2.csv` and their associated `code-*.json` reports. Track golden results separately in `history_golden.csv`. The existing code history includes `run_id`, `change`, `evalset_version`, quality metrics, and latency, but lacks explicit `commit` and `judge_version` columns. Add those before treating future changes as controlled comparisons.
- **Do not compare different dataset hashes as identical conditions.** For example, `43 cases, 215251d`, `43 cases, 234f64d`, and `43 cases, 843d591` all contain 43 cases but are different dataset versions. The matching 95.3% scores in code runs `2026-11-12T143706` and `2026-11-12T161043` therefore **do not** prove stable performance under identical evaluation inputs.
- **Three saved judge runs:** the archive contains three judge evaluations with prompt version `v2-3cc8b3b`, model `gemini-3.8-flash`, and 43 cases:

| Judge run ID | Explanation quality | Pass rate | Agreement with human criteria* |
|---|---:|---:|---:|
| `2026-11-12T164658` | 35/43 | 81.4% | 57/69 (82.6%) |
| `2026-11-12T170319` | 33/43 | 76.7% | 59/69 (85.5%) |
| `2026-11-12T173205` | 32/43 | 74.4% | 60/69 (87.0%) |

*Agreement compares applicable Boolean criterion labels in `judge_labels.jsonl` with stored judge verdicts. Labeling independence is not documented.*

- **Observed variation and provisional tolerance:** explanation-quality pass rates range from **74.4% to 81.4%**, a spread of approximately **7.0 percentage points**. A provisional judge-score tolerance should be **at least 7.0 percentage points**, **provided** the evaluation inputs and runtime settings were truly identical; the archive does not establish identical commit and sampling settings. This is an observed range, **not yet a validated same-commit, three-run tolerance**. No equivalent three-run, same-commit code-grader series is established, so its tolerance remains **undetermined**.
- **Decision rule:** only classify a change as an improvement or regression after confirming the same dataset hash, code commit/evaluation configuration, grader and judge versions, and a difference greater than the validated tolerance. Treat any absolute-rule violation (such as unsupported person/pet attribution) as a failure even if average scores improve. Establish a new baseline whenever the dataset or judge prompt changes.
- **Next steps:** record commit, change, dataset hash, grader/judge versions and golden-test result for each run; complete the required three repeated same-commit runs; review failed cases and add approved regression examples. Do not claim vision results for the proposed 140 image-item pairs or independent live-stage latency measurements: the supplied archive does not substantiate them.