# TrustLens external-domain validation gate

## Source and protocol

The pilot uses the authors' [So-Fake-Set dataset](https://huggingface.co/datasets/saberzl/So-Fake-Set), whose card describes `real`, `tampered`, and `full_synthetic` image labels and a CC-BY-4.0 license. The [dataset-viewer API](https://huggingface.co/docs/dataset-viewer/en/quick_start) supplied individual JPEG previews from its `validation` split. The script downloaded no full archive and kept the selected media below 8 MB. Viewer JPEG conversion can change compression traces, so this is a **transcoded-image domain-shift pilot**, not a pristine-source forensic benchmark.

`prepare_sofake_external_pack.py` assigned source filename groups deterministically to a validation and a reserved test partition, recorded row indices, generators, hashes, and the viewer revision, and excluded exact image hashes from earlier local packs. The selected groups do not cross partitions. Filename grouping and exact hashes cannot prove that visually related originals from an aggregated source dataset are absent from model training; that needs source-level provenance or independent collection.

Two initially reserved rows were opened during visual QA before any model test inference. They were excluded and replaced with unseen rows. Their indices remain in the provenance metadata's `excluded_inspected_rows` list so a later rebuild cannot silently put them back. The validation membership and its observations were unchanged.

The active HYBRID_V2 checkpoint pair was run **only on the validation partition**. The reserved test images have been downloaded but have no detector predictions. Existing temperatures and reliabilities were kept fixed. The gate thresholds were the ones already declared in `artifacts/active.json`: AUROC at least 0.70, expected calibration error at most 0.15, and reliability at least 0.20.

## Validation findings

| Detector | AUROC | Calibrated ECE | Reliability | Gate |
| --- | ---: | ---: | ---: | --- |
| AI-generation EfficientNet | 0.609 | 0.174 | 0.175 | Fail |
| Forensic multiview EfficientNet | 0.503 | 0.256 | 0.000 | Fail |

On the same validation images, the fixed active policy marked **no authentic image** low concern and marked **three suspicious images** low concern. The latter is an image-triage error, not an administrator approval. The sample is small; its rates are exploratory and should not be used as final deployment estimates.

The already trained alternatives were also compared on this validation partition without changing the runtime policy:

| Candidate tampering branch | Raw validation AUROC |
| --- | ---: |
| Active forensic multiview EfficientNet | 0.503 |
| ResNet-18 hard-negative shadow | 0.446 |
| Three-class EfficientNet, single view | 0.399 |

The shared three-class EfficientNet's AI-generation branch had raw AUROC 0.441; the specialist AI-generation branch had raw AUROC 0.609. None provides a defensible substitute on this source. Temperature scaling can change probability calibration but cannot repair these ranking results. The active policy and thresholds were **not** changed, and the reserved test partition remains unscored.

This source contains social-media content, including people, and does not establish performance on warranty product photos or insurance documents. Its JPEG previews introduce another domain difference. The next model iteration should collect labeled, source-disjoint claim-domain training and validation images, improve the detector checkpoints, and repeat this gate. Only after a candidate passes a predeclared validation gate should the reserved test partition be evaluated once. A journal-level evaluation needs a larger independent, original-format claim-domain cohort.

## Reproduce

From `backend`, with the Python environment in `requirements.txt` and `requirements-training.txt`:

```powershell
python scripts/prepare_sofake_external_pack.py --per-class-per-split 20 --max-storage-mb 100 --exclude-row 0 --exclude-row 7
python scripts/collect_calibration_observations.py calibration/sofake_external_manifest.csv --split validation --ai-model-path training_outputs/ai_detector_multigen_candidate.pth --multiclass-tampering-model-path training_outputs/evidence_authenticity_forensic_multiview_candidate.pth --tampering-inference multiview --output calibration/sofake_external_validation_observations.csv
python scripts/evaluate_external_validation.py
python scripts/compare_external_candidates.py
```

Machine-readable results: `artifacts/sofake-external-validation-gate.json` and `artifacts/sofake-validation-model-comparison.json`. The test partition has intentionally not been passed to `collect_calibration_observations.py`.

Dataset citation: Huang *et al.*, “So-Fake: Benchmarking and Explaining Social Media Image Forgery Detection,” arXiv:2505.18660, 2025. Follow the dataset card's attribution and source-use conditions when publishing results.
