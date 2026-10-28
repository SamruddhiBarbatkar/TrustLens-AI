# TrustLens calibration workflow

TrustLens does not treat raw neural-network confidence as a calibrated trust
probability. Calibration observations must use this CSV schema:

`detector,sample_id,group_id,split,detector_label,claim_label,raw_probability,quality_status`

- `detector`: `TAMPERING_DETECTION` or `AI_GENERATION`
- `detector_label`: detector-specific target. A tampered but non-synthetic
  image is `1` for `TAMPERING_DETECTION` and `0` for `AI_GENERATION`.
- `claim_label`: overall target, where `1` means the submission contains any
  validated manipulation, synthetic-generation, or inconsistency condition.
- `split`: `calibration`, `validation`, or `test`
- `group_id`: original-source identifier used to detect partition leakage
- `quality_status`: `GOOD`, `WARNING`, `POOR`, or `UNKNOWN`

Images derived from the same source must share a `group_id` and remain in one
split. The fitting command rejects sample or group leakage.

## Conditional ELA and OCR branches

The runtime supports two additional branches without allowing unvalidated
heuristics to silently change a Trust Score:

- `ELA_SUPPORT` is folded into `VISUAL_MANIPULATION_BRANCH` with a capped
  support weight. It is not treated as independent evidence because ELA and
  the tampering model can respond to the same compression artifacts.
- `OCR_CONSISTENCY` becomes a separate document-consistency source only when
  at least one OCR field comparison is genuinely comparable. No-text and
  unrelated-image cases are `NOT_APPLICABLE`, not suspicious.

Each branch requires `enabled: true`, `validated: true`, calibrated reliability
values, and inclusion in `thresholds.calibrated_branches` inside the activated
artifact. The last requirement proves that approval/review thresholds were
re-fitted with the new branch present. Until all conditions are satisfied, the
branch is reported to reviewers but cannot alter the numerical score.

ELA artifacts must also record the versioned recompression feature transform
(`LOGISTIC` center and scale). OCR calibration data must be claim-level and
contain real matching, conflicting, and non-applicable document combinations;
the image-only detector pack is not valid OCR-consistency calibration data.

## Compact public evaluation pack

If local storage is limited, build a 270-image research evaluation pack
(90 authentic, 90 tampered, and 90 fully synthetic images) without downloading
the multi-gigabyte source archives:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_compact_calibration_dataset.py
```

The builder downloads labeled rows individually from Tiny-GenImage and the
Tampered Images Combined Dataset, normalizes natural and fully synthetic images
to at most 512 px, preserves original tampering bytes so subtle edits are not
recompressed away, rejects duplicate tampered files, keeps every source group
in one partition, records SHA-256 checksums and provenance, and enforces a
250 MB storage cap. Authentic and fully synthetic samples come from
Tiny-GenImage; tampered samples come from manipulated-only SAGI-D/OpenSDID rows
so a source original cannot leak across partitions. Downloaded media are
research-evaluation data and are ignored by Git; do not redistribute them.

Then collect model outputs:

```powershell
.\.venv\Scripts\python.exe scripts\collect_calibration_observations.py `
  calibration\compact_image_manifest.csv `
  --output calibration\compact_detector_observations.csv
```

This compact pack is useful for pilot cross-dataset calibration. It has lower
statistical power and narrower coverage than a production-scale validation
study, so its limitations must be reported with any resulting artifact.

## Evaluate a retrained AI checkpoint safely

The multi-generator Colab workflow writes a separate candidate under
`training_outputs/`. Evaluate it without overwriting the deployed CIFAKE model:

```powershell
.\.venv\Scripts\python.exe scripts\collect_calibration_observations.py `
  calibration\compact_image_manifest.csv `
  --ai-model-path training_outputs\ai_detector_multigen_candidate.pth `
  --output calibration\multigen_candidate_observations.csv
```

Then run `calibrate_fusion.py` against those observations. Observation files
and calibration artifacts record the exact model version and SHA-256 checkpoint
hash, preventing metrics from being attributed to a different weight file.

## Retrain and evaluate the tampering detector safely

Use `training/tampering_detector_multisource_retraining.ipynb` on a Colab GPU.
The notebook streams the combined public dataset plus fully synthetic hard
negatives from Tiny-GenImage's separate training split. It requires
`compact_provenance.csv`, excludes every source group reserved by the compact
evaluation pack, and keeps original/manipulated pairs in the same deterministic
partition. It writes a separate candidate and never replaces the deployed
CASIA2 checkpoint.

Evaluate both candidates together without changing production files:

```powershell
.\.venv\Scripts\python.exe scripts\collect_calibration_observations.py `
  calibration\compact_image_manifest.csv `
  --ai-model-path training_outputs\ai_detector_multigen_candidate.pth `
  --tampering-model-path training_outputs\tampering_multisource_hardnegative_candidate.pth `
  --output calibration\multimodel_candidate_observations.csv
```

Run `calibrate_fusion.py` on the resulting observations. Promotion still
requires both detectors and the combined policy to clear all activation gates.

After a development pack has informed a model revision, generate a fresh audit
pack from unused selection windows rather than reusing its test split:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_compact_calibration_dataset.py `
  --output-dir calibration\final_audit_data `
  --manifest calibration\final_audit_image_manifest.csv `
  --provenance calibration\final_audit_provenance.csv `
  --genimage-start-offset 1000 --tamper-block-shift 300
```

## Three-class evidence authenticity candidate

When separate binary detectors confuse fully synthetic images with localized
tampering, use `training/evidence_authenticity_three_class_retraining.ipynb`.
It trains one EfficientNet-B0 with the stable class mapping `AUTHENTIC=0`,
`TAMPERED=1`, and `SYNTHETIC=2`. Both previous audit provenance files are
required and their combined source groups are excluded from training.

The candidate still feeds two independent signals into the existing
methodology: the `TAMPERED` softmax probability becomes
`TAMPERING_DETECTION`, and the `SYNTHETIC` probability becomes
`AI_GENERATION`. Each is independently temperature-scaled and reliability
weighted before Dempster-Shafer fusion.

Evaluate the candidate without replacing deployed checkpoints:

```powershell
.\.venv\Scripts\python.exe scripts\collect_calibration_observations.py `
  calibration\new_audit_image_manifest.csv `
  --multiclass-model-path training_outputs\evidence_authenticity_three_class_candidate.pth `
  --output calibration\three_class_candidate_observations.csv
```

Evaluate the locked hybrid candidate in one reproducible run. This uses the
specialist EfficientNet for `AI_GENERATION` and the three-class EfficientNet
for `TAMPERING_DETECTION`; the ResNet result remains a separately reported
shadow/ablation signal:

```powershell
.\.venv\Scripts\python.exe scripts\collect_calibration_observations.py `
  calibration\confirmation_image_manifest.csv `
  --ai-model-path training_outputs\ai_detector_multigen_candidate.pth `
  --multiclass-tampering-model-path training_outputs\evidence_authenticity_three_class_candidate.pth `
  --output calibration\hybrid_confirmation_observations.csv
```

The API keeps `DETECTOR_POLICY_MODE=LEGACY` by default. Change it to
`HYBRID_V1` only after the locked hybrid passes final confirmation and
its validated calibration artifact has been activated.

## Validated hybrid 1.0

The locked hybrid was confirmed on a fourth 270-image pack generated with
`--genimage-start-offset 3200 --tamper-block-shift 500`. The pack has 90
authentic, 90 tampered, and 90 synthetic images; its hashes and source groups
have zero overlap with all three earlier evaluation packs.

The held-out test results recorded in `artifacts/ds-fusion-hybrid-1.0.json`
are:

- `AI_GENERATION` (specialist EfficientNet-B0): AUROC 0.787222, ECE 0.128962.
- `TAMPERING_DETECTION` (three-class EfficientNet-B0): AUROC 0.807778,
  ECE 0.141654.

Both branches passed the configured AUROC, ECE, and reliability gates. The
activated artifact is copied to `artifacts/active.json`, and the local runtime
uses `DETECTOR_POLICY_MODE=HYBRID_V1`.

The ResNet-18 tampering candidate remains enabled as a shadow-only research
signal. On the same confirmation pack it achieved AUROC 0.760556 but failed
the calibration/reliability gates (ECE 0.215233, reliability 0.05), so its
output is stored as `TAMPERING_RESNET_SHADOW` and excluded from the Trust
Score. Its comparison artifact is `artifacts/resnet-shadow-confirmation.json`.

## Validated forensic multi-view 2.0

`HYBRID_V2` promotes the forensic EfficientNet checkpoint and deterministic
global-plus-five-patch inference to the primary `TAMPERING_DETECTION` branch.
The specialist multi-generator EfficientNet remains the primary
`AI_GENERATION` branch.

The locked policy was calibrated and tested on a fresh 270-image external pack
selected from unused dataset rows and source groups. The pack occupies 11.77 MB
and contains 90 authentic, 90 tampered, and 90 synthetic samples. Automated
checks found zero dataset-row, source-group, or SHA-256 overlap with all four
earlier packs.

Held-out test results in
`artifacts/ds-fusion-forensic-multiview-2.0.json` are:

- `AI_GENERATION`: AUROC 0.898333, calibrated ECE 0.134800, reliability 0.533333.
- `TAMPERING_DETECTION`: AUROC 0.870000, calibrated ECE 0.079439, reliability 0.383333.

Both detectors passed the locked AUROC, ECE, and reliability gates. Operational
threshold selection met the maximum false-acceptance rate of 0.05 and maximum
false-rejection rate of 0.05. The validated artifact is activated as
`artifacts/active.json`, and the local runtime uses `DETECTOR_POLICY_MODE=HYBRID_V2`.

## Global-and-patch accuracy stage

The next tampering candidate evaluates the full image plus deterministic
top-left, top-right, bottom-left, bottom-right, and center crops. It averages
the six three-class probability vectors. This preserves small local editing
traces that can disappear when the entire image is resized to 224 x 224.

The API records this as `TAMPERING_MULTIVIEW_CANDIDATE`. It has a distinct
model version ending in `-multiview-v1` and is always excluded from the active
Trust Score. Set `ENABLE_MULTIVIEW_CANDIDATE=true` to collect the research
signal during admin verification runs.

Compare single-view and multi-view inference on a genuinely held-out manifest:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_multiview_candidate.py `
  calibration\final_audit_image_manifest.csv `
  --model-path training_outputs\evidence_authenticity_three_class_candidate.pth `
  --split test `
  --output training_outputs\multiview_comparison_report.json
```

If the comparison improves the pre-declared tampering metrics, collect a full
three-way split for calibration while keeping the specialist AI branch:

```powershell
.\.venv\Scripts\python.exe scripts\collect_calibration_observations.py `
  calibration\new_external_audit_manifest.csv `
  --ai-model-path training_outputs\ai_detector_multigen_candidate.pth `
  --multiclass-tampering-model-path training_outputs\evidence_authenticity_three_class_candidate.pth `
  --tampering-inference multiview `
  --output calibration\multiview_candidate_observations.csv
```

Do not reuse a test pack that influenced the candidate design for final
promotion. Run `calibrate_fusion.py` on fresh external observations and only
activate the artifact when every calibration, discrimination, reliability,
false-acceptance, and false-rejection gate passes.

For a retrained checkpoint, the streaming trainer now defaults to
`--augmentation-profile forensic`. That profile mixes global and local crops
with realistic JPEG compression, resize degradation, mild blur, sharpening,
and color changes. It still streams the source datasets and stores only the
checkpoint and JSON report, so it does not require a large local dataset.

To generate detector observations directly from labeled images, prepare a
manifest matching `image_manifest.example.csv`, then run:

```powershell
.\.venv\Scripts\python.exe scripts\collect_calibration_observations.py `
  calibration\image_manifest.csv `
  --output calibration\detector_observations.csv
```

Generate an unvalidated artifact first:

```powershell
.\.venv\Scripts\python.exe scripts\calibrate_fusion.py calibration\detector_observations.csv `
  --output calibration/artifacts/candidate.json `
  --policy-version ds-fusion-1.0-candidate
```

After the research owner has reviewed data provenance, sample counts,
calibration metrics, reliability diagrams, operational constraints, and final
test results, activate a validated version:

```powershell
.\.venv\Scripts\python.exe scripts\calibrate_fusion.py calibration\detector_observations.csv `
  --output calibration/artifacts/ds-fusion-1.0.json `
  --policy-version ds-fusion-1.0 `
  --maximum-far 0.05 --maximum-frr 0.05 `
  --mark-validated --activate
```

Validation also requires every detector to pass the default activation gates:
test AUROC at least 0.70, test expected calibration error at most 0.15, and
overall held-out reliability at least 0.20. The CLI refuses `--mark-validated`
when any detector fails; the limits can be made stricter with the corresponding
command options.

Activation writes `calibration/artifacts/active.json`. Restart the API after
activation. The artifact records temperatures, reliability by quality group,
raw and calibrated Brier/ECE/log-loss metrics, threshold constraints, and data
counts.

The example CSV is only a format demonstration. It must never be activated as
a real calibration artifact.

## Reproduce the active policy's held-out triage audit

From `backend`, run:

```powershell
python scripts/audit_active_calibration.py
```

The command writes `calibration/artifacts/heldout-score-audit.json`. It verifies
the observation file and deployed checkpoint hashes, recomputes detector test
metrics, reconstructs the approval and low-score thresholds from the validation
split, and checks the current pack against earlier packs by source group,
dataset row, and image hash. It then applies the fixed policy to the held-out
test split and reports the image-level low-concern/review split with Wilson 95%
intervals.

The audit shows that the active policy is conservative: 3 of 60 suspicious
images were marked low concern (5.0%; Wilson interval 1.7%-13.7%), while 27 of
30 authentic images were sent to human review (90.0%; Wilson interval
74.4%-96.5%). Fusion uncertainty triggered 26 of those 27 authentic reviews.
These are triage outcomes, not administrator approvals or a claim-level accuracy
estimate. The test split informed the policy's promotion readiness, so this
reproduction is not a new independent external replication. The test images
cannot be used to retune the active thresholds.
Improving review coverage requires a new validation set, then a separate
untouched evaluation set, preferably from genuinely different claim sources.

The subsequent [So-Fake-Set external-domain pilot](SOFAKE_EXTERNAL_VALIDATION.md)
uses a new public source with a reserved test partition. The active detectors
failed the predeclared validation gate on its viewer-transcoded images, so the
runtime policy is unchanged and test predictions remain uncollected.

The [document-domain training pilot](DOCUMENT_DOMAIN_PILOT.md) trains a separate,
research-only head on a small Indian document set. Its validation AUROC improved
relative to the active model on that source but missed the readiness gates;
source-count and pairing limitations prevent promotion.
