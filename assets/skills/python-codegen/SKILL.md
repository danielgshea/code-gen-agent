---
name: python-codegen
description: Workflow and conventions for writing, running, and verifying Python code inside the LangSmith sandbox. Read this before any non-trivial coding task.
---

# Writing and running Python in the sandbox

The sandbox is a fresh Linux environment. Working directory is `/root`. `python3`
and `pip` are available. State persists across `execute` calls within a session,
so files you write and packages you install stay until the sandbox is recycled.

## Standard loop

1. **Scaffold to a file.** Put real code in files under `/root` (e.g.
   `/root/solution.py`, `/root/test_solution.py`). The model's `write_file`/
   `edit_file` tools write into the sandbox.
2. **Install dependencies** before importing them:
   `pip install --quiet <pkg>`. Check the exit status — a non-zero exit means the
   install failed; read stderr.
3. **Run and read output:** `python3 /root/solution.py`. Inspect `stdout` and
   `stderr`. A traceback is data — fix the specific line it points to.
4. **Re-run after every fix.** Never assume an edit worked; confirm with `execute`.

## Verifying behavior

"Runs without error" is not "correct". Demonstrate correctness:
- Add a `if __name__ == "__main__":` block, or a separate test file, that exercises
  the code with representative inputs and prints/asserts expected results.
- For functions, a few `assert` statements are the fastest proof:
  `python3 -c "from solution import f; assert f(2) == 4"`.
- If `pytest` is appropriate, `pip install pytest` and run `pytest -q`.

## Conventions

- Prefer the standard library. Justify any third-party dependency.
- Use type hints and docstrings on public functions; keep functions small.
- Pin nothing the user didn't ask to pin; report the versions you installed.
- Clean up large temporary outputs; keep the final deliverable in one obvious file.

## Common gotchas

- Long-running or interactive programs will hang `execute`. Pass a timeout, or
  make scripts non-interactive (read args/stdin, not `input()` prompts you can't answer).
- Relative imports depend on the working directory — run from `/root` or set
  `PYTHONPATH`.
- Network access may be restricted; prefer offline approaches and fail loudly if a
  needed resource is unavailable.
