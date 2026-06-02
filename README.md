# code-gen-agent

A Python **code-generation agent** built with [DeepAgents](https://docs.langchain.com/oss/python/deepagents/overview)
and packaged as a [LangGraph](https://docs.langchain.com/oss/python/langgraph) app.
It writes code, **executes it in an isolated LangSmith sandbox**, reads the real
output, and iterates until the code runs and is verified.

Following LangSmith agent-building best practices:

- **Prompt -> Prompt Hub.** The system prompt is pulled from LangSmith at
  construction, so you can edit it in the Playground without a redeploy.
- **Skill + memory -> Context Hub.** On-demand skills (`/skills/`) and durable
  long-term memory (`/memory/AGENTS.md`) live in Context Hub agent repos; the
  agent reads skills progressively and rewrites its own memory at runtime.
- **Code -> LangSmith sandbox.** The agent's filesystem and `execute` tools run
  *inside* a remote LangSmith sandbox (the *sandbox-as-tool* pattern), keyed per
  conversation thread.

## Architecture

```
                create_deep_agent (LangGraph graph)
                          |
        +-----------------+----------------------+
   system_prompt        backend                 skills + memory
   (Prompt Hub)    CompositeBackend             (Context Hub repos,
                   |- "/"        -> LangSmithSandbox   surfaced via the
                   |              (code + execute)     backend routes)
                   |- "/skills/" -> ContextHubBackend
                   +- "/memory/" -> ContextHubBackend
```

The agent's built-in `write_file` / `read_file` / `edit_file` / `execute` tools
all target the sandbox (the default route). Only `/skills/` and `/memory/` are
diverted to the Context Hub. See `code_gen_agent/sandbox.py`.

## Layout

```
code_gen_agent/
  agent.py        # builds the compiled graph -> module-level `agent`
  prompt.py       # pulls the system prompt from the Prompt Hub (seed fallback)
  sandbox.py      # LangSmith sandbox backend factory (per-thread sandbox)
assets/           # seed content published to LangSmith by the bootstrap script
  system_prompt.md
  skills/python-codegen/SKILL.md
  memory/AGENTS.md
scripts/bootstrap_hub.py   # publish prompt + skills + memory to LangSmith
langgraph.json    # graph registry + .env pointer
```

## Setup

1. Install dependencies (managed by [uv](https://docs.astral.sh/uv/)):

   ```bash
   uv sync
   ```

2. Configure secrets:

   ```bash
   cp .env.example .env
   # fill in LANGSMITH_API_KEY (workspace-scoped) and ANTHROPIC_API_KEY
   ```

3. Publish the prompt, skills, and seed memory to LangSmith (one time):

   ```bash
   uv run --env-file .env python scripts/bootstrap_hub.py
   ```

   > Until you run this, the agent falls back to the bundled seed prompt and the
   > Context Hub repos are treated as empty, so `langgraph dev` still starts.

## Run

```bash
uv run langgraph dev
```

Opens LangGraph Studio with hot reload. Ask it to "write and test a function
that ..."; watch the trace in LangSmith as it writes files and runs `execute`
inside the sandbox.

## Configuration

All optional, via environment variables (see `.env.example`):

| Variable | Default | Purpose |
| --- | --- | --- |
| `CODE_GEN_MODEL` | `anthropic:claude-sonnet-4-6` | Chat model |
| `CODE_GEN_PROMPT_REPO` | `code-gen-agent` | Prompt Hub repo |
| `CODE_GEN_SKILLS_REPO` | `code-gen-agent-skills` | Context Hub skills repo |
| `CODE_GEN_MEMORY_REPO` | `code-gen-agent-memory` | Context Hub memory repo |
| `CODE_GEN_SANDBOX_IDLE_TTL` | `600` | Idle seconds before the sandbox is stopped |
| `CODE_GEN_SANDBOX_SNAPSHOT` | (none) | Boot the sandbox from a prebuilt snapshot |

## Deploy

Push the repo and create a LangSmith Deployment from `langgraph.json`; the
platform builds the image and injects a workspace-scoped `LANGSMITH_API_KEY` plus
a checkpointer/store. Set `ANTHROPIC_API_KEY` (and any repo overrides) in the
deployment config. Don't pass your own checkpointer/store in code -- the platform
provides them.

## Notes & safety

- Sandboxes isolate code execution, but the agent is still susceptible to prompt
  injection from untrusted input. Use human-in-the-loop approval and short-lived
  secrets for sensitive deployments.
- Sandboxes auto-stop after `CODE_GEN_SANDBOX_IDLE_TTL` idle seconds and are
  deleted per LangSmith's retention policy; no manual cleanup needed for dev.
- Secrets live only in `.env` (gitignored). Never commit real keys.
