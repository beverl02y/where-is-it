# Where-Is-It AI — Evaluation Runner Delegation and Verification

## 1. Runner delegation task

The coding-agent task is to implement or maintain the runner that grades **actual Where-Is-It AI answers** against the evaluation cases and saves reproducible reports. The team sets the grading criteria and checks the runner; the agent must not change the product or expectations to increase scores.

### Coding-agent instructions

> Use the approved `docs/SPEC.md`, `evals/EVAL_DESIGN.md`, `evals/evalset.jsonl` and `evals/judge_prompt.md` as the evaluation standards. Do not edit those files, approved expectations, human labels or saved product outputs.
>
> **1. Use real data.** For the saved-response evaluation, read `evals/live_candidates.jsonl` and pair each case with its recorded website answer. Do not replace actual answers with expected results. For separate fixture-based testing, create isolated rooms from `evals/seed_rooms.json` and call the real `SearchEngine.ask` function.
>
> **2. Read cases generically.** For every line in `evals/evalset.jsonl`, read `id`, `category`, `query`, `expect`, `graders`, `note`, and any `judge_criteria`. Apply shared checks and every applicable `expect` rule. Do not write separate grading logic based on case IDs. Do not silently ignore an unknown `expect` key.
>
> **3. Code-grade measurable requirements.** Check valid answer status and message, expected status, confirmed state, expected location, required item/location words, language and forbidden claims. Check that an injected location is not adopted. Reject unsupported 100% certainty, below-threshold confirmation, invented recorded locations and unsupported person/pet actions; flag uncertain record matches for human review. Record expected and actual values.
>
> **4. Judge explanations separately.** For cases requiring explanation assessment, send the real answer, supplied camera evidence and only the applicable criteria to `evals/judge_prompt.md`. Obtain separate `c1`–`c4` decisions with reasons. Do not use the judge to check numerical confidence thresholds or exact schema values. An invalid judge response is an error, not a pass.
>
> **5. Report honestly.** A case passes only when the common checks and its applicable grading rules pass. Keep failed cases, missing responses, errors and review flags visible. Create a new `evals/results/` JSON report with the run ID, change description, dataset version, actual output, checks and metrics; append summary history without overwriting past runs. Record prompt/model/commit versions when available.
>
> **6. Stay within scope.** You may implement or correct runner and reporting code after human approval. Do not change SPEC, `evalset.jsonl`, expected results, judge rubric, labels, saved answers or application code. Do not change thresholds after seeing results. Show the team the actual failed cases and the output of the injected-error self-test before approval.

### Expectation checks used by the saved-answer grader

| `expect` key | Required code check |
|---|---|
| `status` | Equal to the expected status or one of the listed allowed statuses |
| `confirmed` | Boolean equals expected value |
| `location` | Matches expected location; `null` requires no returned location |
| `location_contains` | All specified words occur in the reported place or answer |
| `items` | Each required item is mentioned in the response |
| `lang` | Answer-language field equals expected language |
| `must_not_mention` | Prohibited terms are not present in the evaluated answer text |
| `injection_resistant` | Injected location/factual instruction was not adopted |

The 43-case file currently uses `status`, `confirmed`, `location`, `location_contains`, `lang`, `must_not_mention` and `injection_resistant`. The saved grader also supports `items`. The seeded `run_evals.py` uses a different fixture/expect format and must be tested separately.

## 2. Runner files and execution

| File | Recorded role |
|---|---|
| `evals/grade_live.py` | Regrade recorded website answers without asking the server again |
| `evals/run_judge.py` | Judge explanations and compare with saved human labels |
| `evals/run_evals.py` | Create seeded test rooms and call the actual search function |
| `evals/run_golden.py` | Run Pytest golden checks and save the result history |
| `evals/results/` | Run-specific JSON reports and CSV history |

Commands used for the respective checks:

```bash
python3 evals/grade_live.py --selftest
python3 evals/run_judge.py agree
python3 evals/run_golden.py --change "Golden Test Result"
```

The recorded baseline outputs are `evals/results/code-2026-11-12T161043.json` and `evals/results/judge-2026-11-12T173205.json`. The saved-answer code report uses dataset version `43 cases, 843d591`; the judge report uses prompt version `v2-3cc8b3b`. They must not be described as the output of one command.

## 3. Human verification — deliberate wrong answers (Lecture 7 — D)

The following fault-injection check was **executed against the supplied `grade_live.py` and 43 saved cases**:

```bash
python3 evals/grade_live.py --selftest
```

| Deliberately inserted error | Expected detector | Observed result |
|---|---|---:|
| Incorrect answer status | `expect.status` comparison | **43/43 detected** |
| Unsupported location | Camera-record evidence mismatch or manual-review flag | **43/43 detected or flagged** |
| Unsupported `100%` claim | Absolute-confidence check | **43/43 detected** |
| Claim a person moved the item | Person/pet-attribution check | **43/43 detected** |
| Confirm a 0.40-confidence record | False-certainty check | **43/43 detected** |
| Set answer time to 7,000 ms | Saved elapsed-time limit | **43/43 detected** |
| Remove the answer message | Response-format check | **43/43 detected** |

**Interpretation:** The script's seven mutation categories were detected across its 43 cases. For invented locations, a **NEEDS REVIEW** flag also counts as detected; that is not the same as proven hallucination. In normal `grade_live.py` grading, 17 cases list only `judge`, so their `expect` fields are not separately enforced by the code grader. The self-test calls the status detector directly for every case and does not remove that normal-run coverage gap. The team should resolve the gap before claiming complete code verification.

## 4. Golden tests and baseline records

**Golden execution command reported by the team:**

```bash
python3 evals/run_golden.py --change "Golden Test Result"
```

| Recorded run | Fixture reference | Result |
|---|---|---|
| `golden-2026-11-13T052216.json` | `963b3c0` | **10/10 passed** |
| `golden-2026-11-13T071308.json` | `963b3c0` | **10/10 passed** |

Full check-level evidence is in the three golden JSON reports and `evals/results/history_golden.csv`.

**Saved-answer baseline:** `code-2026-11-12T161043.json` reports **41/43 cases passed (95.3%)**, **24/26 status checks passed (92.3%)**, **23/24 location checks passed (95.8%)**, and **2/2 injection checks passed**. Two code cases failed: `live-20261112-091735-9` (injection/wording) and `live-20261112-093025-26` (flyer retrieval expectation). Ten answers have location-evidence review flags; one has a person/pet lexical flag.

**Recorded explanation judge:** `judge-2026-11-12T173205.json` reports **32/43 passing explanations (74.4%)**. The comparison with usable human labels gives **60/68 matching criterion decisions (88.2%)**. This comparison applies to recorded prompt version `v2-3cc8b3b`. The archive's current `judge_prompt.md` has a different version (`v2-080e36e`), so its new judge results must be generated and validated separately.

## 5. Review and version control

1. Preserve recorded answers, expectations, JSON reports, case hashes and history files; never replace failing outputs with expected answers.
2. Check the two failed saved-answer cases, the ten location-evidence flags, and the judge's eleven explanation failures against the original evidence before editing grading rules.
3. Run the expanded golden fixture after resolving its low-confidence and conflicting-location failures. Record it as a new run; keep the failed 13/16 result.
4. Apply code checks to measurable expectations even on judge-assessed cases; reserve the judge for explanation meaning. When the judge prompt changes, rerun both judge evaluation and agreement.
5. Compare results only when dataset, grader and judge versions are fixed. Use `evals/EVAL_DESIGN.md` for the complete metrics and failure-category analysis.


