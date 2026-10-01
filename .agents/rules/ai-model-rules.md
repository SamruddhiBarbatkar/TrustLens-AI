# AI Model Rules

- Inspect supplied checkpoints and training/inference code before integrating either model.
- Do not retrain, replace, alter weights, infer class mappings, or invent preprocessing.
- Run models only in FastAPI backend inference mode; never expose weights to the client.
- Return explicit unavailable/error states, never placeholder predictions.
- Describe results as signals, not proof; do not claim unverified accuracy.
