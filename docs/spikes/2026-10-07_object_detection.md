# Object Detection Technical Feasibility Spike

## 1. Riskiest Assumption

**"The system can detect supported everyday objects from indoor camera images
and determine their locations with sufficient accuracy for the Where-Is-It AI
MVP."**

- Failure impact:
  Where-Is-It AI depends on detecting objects from camera images and storing
  their detected locations. If object detection is not sufficiently accurate,
  incorrect location information may be stored, making later current-location
  and last-seen searches unreliable.

- Lack of evidence:
  User interviews confirmed that participants often have difficulty finding
  small everyday belongings. However, we have not yet verified whether an AI
  vision model can reliably detect these supported objects and determine their
  locations in realistic indoor images.

- Cost of alternatives:
  If automatic object detection is not sufficiently reliable, users may need
  to manually register object locations or use separate tracking devices.
  These alternatives require additional user effort or hardware and do not
  match the project's goal of passive camera-based object tracking.

- Comparison with other risks:
  Natural-language search and historical search are also important, but these
  functions depend on reliable detection records. Therefore, object detection
  feasibility should be tested first.


## 2. Time Limit

The spike will be limited to **one day, with a maximum of 6 hours**.

The experiment will stop when either of the following occurs:

- 6 hours have passed, or
- Evaluation of all 20 test images has been completed.

When either stopping condition is reached, the experiment will end regardless
of the result, and the available results will be used to make the decision.


## 3. Success Criteria (Defined Before Testing)

Testable statement:

**When the model is evaluated on 20 test images, at least 90% of all
photo-item pairs must match the human labels, and the false-certainty rate
must be 2% or lower.**

### Evaluation Unit

One supported item in one image is treated as one **photo-item pair**.

The evaluation dataset contains:

- 20 test images
- 6 supported object classes:
  - glasses
  - wallet
  - card
  - earphones
  - phone
  - hairtie

Therefore:

**20 images × 6 objects = 120 photo-item pairs**

The evaluation images must not be used to modify the prompt or adjust the
success criteria during the experiment.

### Per-Pair Judgment Rule

Only model detections with **confidence ≥ 0.75** are treated as reliable
detections.

A photo-item pair is counted as a **match** when:

1. The human label indicates that the object is visible in a specific area,
   and the model detects the same object in the same area with confidence
   ≥ 0.75.

OR

2. The human label indicates that the object is not visible, and the model
   does not report that object with confidence ≥ 0.75.

A photo-item pair is counted as a **mismatch** when:

1. **Missed detection**
   - The object is visible according to the human label, but the model does
     not detect it with confidence ≥ 0.75.

2. **Wrong area**
   - The model detects the correct object, but assigns a different area from
     the human label.

3. **False certainty**
   - The object is not visible according to the human label, but the model
     reports it with confidence ≥ 0.75.

### Passing Threshold

The spike passes only if both conditions are satisfied:

- **Match rate ≥ 90%**
- **False-certainty rate ≤ 2%**


## 4. Method

### 1. Create the Ground Truth

Prepare 20 indoor test images.

Two team members independently label each image without seeing the other
person's labels.

For every supported object, each person records:

- whether the object is visible
- the object's area if it is visible

The allowed areas are:

- table
- under_table
- sofa
- held_by_person

The first person's labels are stored in:

`spike/labels_A.csv`

The second person's labels are stored in:

`spike/labels_B.csv`

The two sets of labels are compared. If there is a disagreement, the two
labelers review the image together and agree on one final label.

The agreed human labels are stored in:

`spike/labels.csv`


### 2. Generate Model Outputs

Run the object-detection model on each of the 20 test images.

The following settings remain fixed throughout the experiment:

- Model: Gemini 3.8 Flash
- Thinking level: MEDIUM
- Runs per image: 1
- Confidence threshold: 0.75
- Supported objects:
  glasses, wallet, card, earphones, phone, hairtie
- Supported areas:
  table, under_table, sofa, held_by_person

For every detected supported object, the model returns structured information
containing:

- item
- area
- confidence

The model, prompt, settings, supported object list, supported area list, and
confidence threshold are not changed during the evaluation.


### 3. Compare the Results

Compare the model output for every image with the final human labels in
`labels.csv`.

Each of the 120 photo-item pairs is evaluated using the judgment rules defined
in Section 3.

Calculate:

- Match count
- Match rate
- Missed detection count
- Wrong-area count
- False-certainty count
- False-certainty rate

Finally, compare the measured results with the success criteria defined before
the experiment.


## 5. Results

**Not tested yet.**

After the experiment, record the results using the following format:

| Item | Result |
|---|---|
| Test images | 20 |
| Photo-item pairs | 120 |
| Matches | To be measured |
| Match rate | To be measured |
| False certainty | To be measured |
| False-certainty rate | To be measured |
| Passing threshold | Match ≥ 90%, False certainty ≤ 2% |
| Verdict | PASS / FAIL / INCONCLUSIVE |

Mismatches will also be categorized by error type:

| Error Type | Count | Example |
|---|---:|---|
| Missed detection | To be measured | To be recorded |
| Wrong area | To be measured | To be recorded |
| False certainty | To be measured | To be recorded |

The actual human labels and model outputs will be stored in:

- `spike/labels_A.csv`
- `spike/labels_B.csv`
- `spike/labels.csv`
- `spike/outputs.jsonl`
- `spike/results.csv`

## 5. Results-after-testing

### 5.1 Evaluation-round history

The preserved CSV files show multiple evaluation rounds. Their results are reported separately to avoid representing iterative prompt tuning as a single untouched test.

| Available results file | Matches / 120 | Match rate | False-certainty cases / 120 | False-certainty rate | Verdict |
|---|---:|---:|---:|---:|---|
| `results.csv` | 105 | 87.5% | 7 | 5.8% | FAIL |
| `results (2).csv` | 107 | 89.2% | 3 | 2.5% | FAIL |
| `results (4).csv` | 110 | 91.7% | 4 | 3.3% | FAIL |
| `results (5).csv` | **109** | **90.8%** | **2** | **1.7%** | **PASS** |

*File names distinguish available exports; they do not independently establish the chronological order of all runs.*

### 5.2 Passing-round result

The passing evaluation (`results (5).csv`) contains:

| Metric | Observed result | Required condition | Status |
|---|---:|---:|---|
| Photos | 20 | 20 | Completed |
| Photo-item pairs | 120 | 120 | Completed |
| Matches | 109 | ≥108 | PASS |
| Match rate | **90.8%** | ≥90% | PASS |
| Missed detections | 9 | Diagnostic | — |
| False certainty: wrong area | 2 | Diagnostic | — |
| False certainty: item not there | 0 | Diagnostic | — |
| Total false certainty | **2** | ≤2 | PASS |
| False-certainty rate | **1.7%** | ≤2% | PASS |

**Overall verdict for this evaluation round: PASS.** Both predefined numerical criteria are satisfied.

The remaining 11 mismatches consist of nine misses and two wrong-area false-certainty cases. The results demonstrate feasibility for the six supported items and four predefined areas in this 20-image evaluation, not universal reliability across rooms, cameras, or unseen conditions.

### 5.3 Evidence

- Human annotations: `labels_A.csv`, `labels_B.csv`, and `labels.csv`
- Scored per-pair output for the passing round: `results (5).csv`
- Scoring program and model configuration: preserve the versions corresponding to that run
- Raw output and prompt hash: attach the corresponding archived `outputs.jsonl` and console log if available

## 6. Decision and Retry Conditions

### Decision

**PASS for the recorded evaluation round.** Gemini-based image analysis met both numerical feasibility thresholds: **90.8% match rate** and **1.7% false-certainty rate**. This supports continuing with camera-based object detection as an MVP component for the tested scope.

Because several prompt/evaluation rounds were performed on the same collection of images, the passing score should be described as an **iterative development-set result**, not as an unbiased estimate of performance on previously unseen photos.

### Specification and Ontology implications

- Retain **Object Detection** as a core MVP function in the **Detect → Save → Search → Explain** flow.
- Use detections with confidence **≥ 0.75** for confirmed location records under the project's current policy.
- If an object is not reliably visible, do not invent a current location; use an available last-seen record or state that the camera evidence is insufficient.
- Keep the initial spike scope limited to six classes and four areas. Other objects or locations require separate validation.

### Retry Conditions

Before claiming generalizable performance, freeze the final model, prompt, threshold, and scoring procedure, then evaluate them **once on a fresh, independently labeled set of photos**. If the fresh set fails either threshold, inspect missed small/occluded objects and wrong-area classifications, revise the method, and test on another unused set. Do not change the original acceptance thresholds after seeing results.

**Final conclusion:** The spike demonstrates promising technical feasibility and passes the stated criteria on the recorded evaluation data. Independent validation remains the next step before relying on these rates in deployment.
