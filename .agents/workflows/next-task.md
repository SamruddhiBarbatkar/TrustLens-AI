# /next-task Workflow

1. Read `PLAN.md` and `TASKS.md`.
2. Select the first unchecked task whose dependencies are complete and which is not externally blocked.
3. Read applicable files in `.agents/rules/` and the relevant `.agents/skills/*/SKILL.md`.
4. Implement only that task; do not start dependents.
5. Run task-appropriate checks and fix failures.
6. Mark the task complete only when verification passes.
7. Update `PLAN.md` Status with material progress and report what changed.
8. Stop.
