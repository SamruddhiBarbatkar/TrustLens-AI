# /checkpoint Workflow

1. Inspect `git status` and the diff; identify changes outside the active task.
2. Check tracked/untracked files for likely secrets and confirm `.gitignore` covers generated/private artifacts.
3. Run relevant existing tests without starting new implementation tasks.
4. Summarize completed, active, blocked, and unverified work from `PLAN.md` and `TASKS.md`.
5. Suggest a concise Git commit message.
6. Do not commit or push automatically.
