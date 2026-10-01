# AI Inference Skill

## Preconditions

Do not implement model inference until checkpoint files and corresponding training/inference code are available for inspection. Record verified architecture, state-dict handling, class mapping, preprocessing, output interpretation, and required package versions.

## Implementation standards

- Load weights from an ignored server-only directory and verify file integrity/load errors.
- Recreate only the verified architecture and preprocessing contract.
- Use `eval()` and inference/no-grad execution; select CPU/CUDA safely.
- Normalize and expose confidence only when its meaning is verified.
- Keep models process-local/backend-only and protect initialization with clear health/error states.
- Keep OCR, quality, and ELA as separate measured services with explicit limitations.
- Fusion must be transparent deterministic application logic, not a claimed trained model.

## Verification

Use known, authorized fixtures or training-provided examples. Test valid/invalid images, missing weights, device fallback, output schema, and no fabricated fallback prediction.
