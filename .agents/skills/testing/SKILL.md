# Testing Skill

## Test strategy

- Unit-test deterministic validation, scoring, quality/ELA helpers, schemas, and service errors.
- Use API integration tests for authentication, authorization, upload limits, traversal attempts, persistence, and reports.
- Add model contract tests only after verified artifacts are available; do not assert invented labels.
- Test frontend route guards and loading/error/empty/unavailable states.
- Use isolated test configuration and temporary artifacts; never use production secrets or user data.

## Completion rule

Run the smallest relevant test set first, fix failures, then run the task-level suite. Mark completion only with recorded passing evidence or a clearly documented external blocker.
