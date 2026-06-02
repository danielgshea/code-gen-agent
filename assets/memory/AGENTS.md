# Agent memory

Durable notes the code-generation agent carries across sessions. Read this at the
start of a task; append concise, generally-useful lessons as you learn them. Keep
it short and high-signal — this file is loaded into context on every run.

## Environment facts
- Code executes in a LangSmith sandbox; working directory is `/root`.
- Use `python3` and `pip`. Installed packages persist for the life of the sandbox.

## Conventions
- Always write code to a file and run it before reporting success.
- Verify behavior with a test/assertion, not just absence of errors.

## Learned lessons
<!-- Append dated, concrete lessons below. Example:
- 2026-06-02: `pandas` is not preinstalled; `pip install pandas` first.
-->
