# Document-domain training pilot

## Purpose and source

This is an **academic, research-only** experiment on document imagery closer to
TrustLens invoice/insurance evidence than the general social-media benchmark.
It uses [Kriyam TamperFlow](https://huggingface.co/datasets/kriyam-ai/kriyam-tamperflow)
at pinned revision `923669c2a7af148da9e1f62ea56ac5f0308af322` under
CC-BY-NC-4.0. It does **not** cover product photos and does not establish
real-claim performance. No candidate was activated in the API or Trust Score.

The pinned `metadata.jsonl` contains 700 tampered and **69 authentic** source
documents, each with three compression tiers. The source card describes 350
authentic documents; that differs from the 69 available in the pinned files.
The authentic and tampered source IDs are disjoint (`0701`-`0769` versus
`0001`-`0700`), with no matched authentic/tampered pair. Document type or capture
differences may therefore influence classification. This is a pilot, not a
defensible tampering benchmark.

## Method

`prepare_document_domain_pack.py` selected the C2 compression tier, fixed one
image per source ID, and assigned source-disjoint balanced partitions:

| Partition | Authentic | Tampered | Role |
| --- | ---: | ---: | --- |
| Train | 40 | 40 | 64 head fitting, 16 development/temperature fitting |
| Validation | 14 | 14 | Candidate and baseline comparison |
| Reserved test | 15 | 15 | Unscored |

The builder downloaded individual originals but persisted only 768-pixel JPEG
derivatives, totaling **9.7 MB**, plus source IDs, row positions, and original
and stored SHA-256 values. This respects the local storage limit but changes
fine forensic traces. The original-format dataset must be evaluated before
any forensic deployment claim.

`train_document_domain_head.py` froze the currently active forensic
EfficientNet-B0 and trained only a binary linear head. A source-disjoint
development carve-out from the training partition selected the epoch and
temperature. Validation was loaded after those choices were fixed. The
reserved test images were **never passed to inference**.

## Validation result

| Model / inference | AUROC | ECE | Balanced accuracy |
| --- | ---: | ---: | ---: |
| Active three-class, global resize | 0.510 | 0.435 | 0.500 |
| Active three-class, deployed multiview path | 0.485 | 0.410 | 0.500 |
| Frozen backbone + document head, global resize | 0.684 | 0.313 | 0.750 |

The research head improved this small validation comparison, but missed the
predeclared **0.70 AUROC** and **0.15 ECE** gates. Its 28-image validation set
is too small for a deployment claim, and the unmatched source classes may
create shortcuts. The checkpoint is intentionally **not loaded by the app**.
Temperature calibration used only the development carve-out; it did not
repair the validation ECE.

The So-Fake-Set validation failure remains unresolved. The document head is
specialized to a different input domain and must not be substituted into the
general product-photo or social-media detector. Both the 30-image document
test partition and the 60-image So-Fake-Set test partition remain unscored.

## Reproduce

From `backend` with PyTorch and Pillow installed:

```powershell
python scripts/prepare_document_domain_pack.py
python scripts/train_document_domain_head.py
python -m unittest tests.test_document_domain_training -v
```

Machine-readable output: `training_outputs/document_tampering_head_report.json`.
The 7.7 KB head artifact is
`training_outputs/document_tampering_head_candidate.pth` and records the exact
base-checkpoint SHA-256. The media directory is Git-ignored; the manifest,
source metadata, and provenance remain available locally.

## What would permit another iteration

Collect **source-matched, labeled originals and edits** for claim documents
and product photos, with permission to use them. Separate source documents,
devices, and manipulation methods across train, development, validation, and
test; keep original encoded files for forensic evaluation. Admin approval or
rejection of an entire claim is not an image-tampering label. Any revised
checkpoint must first pass a new, larger, predeclared validation gate before
the reserved test partition is scored once.
