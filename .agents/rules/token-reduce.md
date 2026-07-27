---
trigger: always_on
---

MINIMAL OUTPUT MODE

Work autonomously and keep communication extremely concise.

Rules:
- Do not narrate routine actions.
- Do not explain commands before running them.
- Do not provide progress updates unless necessary.
- Do not summarize files you just read.
- Do not repeat the task or requirements.
- Do not explain obvious code changes.
- Use tools directly instead of describing what you are about to do.
- Keep terminal output/logs minimal; use quiet/silent flags when safe.
- Do not print full build/install logs unless an error occurs.
- If a command succeeds, continue silently.
- On errors, report only the relevant error and fix it.
- Ask questions only when blocked by missing information or a consequential ambiguity.
- After completing the task, respond with at most:
  1. What changed
  2. Files changed
  3. Any important issue
- Keep the final response under 5 lines unless I request an explanation.

Priority: execute > verify > concise result. Avoid narration.