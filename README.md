# code-gen-agent

A Python **code-generation agent** built with [DeepAgents](https://docs.langchain.com/oss/python/deepagents/overview)
and packaged as a [LangGraph](https://docs.langchain.com/oss/python/langgraph) app.
It writes code, **executes it in an isolated LangSmith sandbox**, reads the real
output, and iterates until the code runs and is verified.

Following LangSmith agent-building best practices:

- **Prompt -> Prompt Hub.** The system prompt is pulled from LangSmith at
  construction, so you can edit it in the Playground without a redeploy.
- **Skill + memory -> Context Hub.** Skills are a simple list of Context Hub
  *skill repos* (`CODE_GEN_SKILLS`), pulled fresh at startup and served at
  `/skills/` with progressive disclosure. Durable long-term memory
  (`/memory/AGENTS.md`) lives in a Context Hub agent repo the agent rewrites at
  runtime.
- **Code -> LangSmith sandbox.** The agent's filesystem and `execute` tools run
  *inside* a shared, kept-warm LangSmith sandbox (the *sandbox-as-tool* pattern),
  connected once at startup.
- **Model -> LangSmith LLM gateway.** Model calls route through the gateway
  (`<gateway>/anthropic`) authenticated with the LangSmith API key, so there's no
  separate provider key to manage and usage shows up next to your traces. See
  `code_gen_agent/model.py`.

## Architecture

```
                create_deep_agent (LangGraph graph)
                          |
        +-----------------+----------------------+
   system_prompt        backend                 skills + memory
   (Prompt Hub)    CompositeBackend             (Context Hub repos,
                   |- "/"        -> LangSmithSandbox   surfaced via the
                   |              (code + execute)     backend routes)
                   |- "/skills/" -> FilesystemBackend (staged Context Hub skill repos)
                   +- "/memory/" -> ContextHubBackend
```

The agent's built-in `write_file` / `read_file` / `edit_file` / `execute` tools
all target the sandbox (the default route). `/skills/` (the skill repos staged at
startup) and `/memory/` are diverted off the sandbox. The sandbox is connected
inline in `code_gen_agent/agent.py` at construction.

## Layout

```
code_gen_agent/
  agent.py        # builds the compiled graph -> module-level `agent`; connects the sandbox
  prompt.py       # pulls the system prompt from the Prompt Hub (seed fallback)
  model.py        # builds the chat model, routed through the LangSmith gateway
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
| `CODE_GEN_USE_GATEWAY` | `true` | Route model calls through the LangSmith LLM gateway |
| `LANGSMITH_GATEWAY_URL` | `https://gateway.smith.langchain.com` | Gateway base URL (override for self-hosted) |
| `CODE_GEN_PROMPT_REPO` | `code-gen-agent` | Prompt Hub repo |
| `CODE_GEN_SKILLS` | `python-codegen,shared-workspace` | Comma-separated Context Hub skill repos to load |
| `CODE_GEN_MEMORY_REPO` | `code-gen-agent-memory` | Context Hub memory repo |
| `CODE_GEN_SANDBOX_NAME` | `code-gen-agent-sandbox` | Name of the shared, kept-warm sandbox to reuse-or-create |

### Sandbox connection

At startup the agent connects to the sandbox named `CODE_GEN_SANDBOX_NAME`: it
reuses it if it exists (starting it if it had idled) and creates it warm
(`idle_ttl_seconds=0`, never auto-stops) if not. The connection is a single
synchronous call at construction — `code_gen_agent/agent.py`. All runs share this
one sandbox.

Because the agent's `LANGSMITH_API_KEY` creates the sandbox, that key is its
*creator*, which is what grants run / file-op access. A different key can only
operate a sandbox it didn't create if its role has the `sandboxes:exec`
permission.

## Deploy

Push the repo and create a LangSmith Deployment from `langgraph.json`; the
platform builds the image and injects a workspace-scoped `LANGSMITH_API_KEY` plus
a checkpointer/store. With gateway routing on (the default) that key also covers
model calls, so no provider key is required; set any repo overrides in the
deployment config. Don't pass your own checkpointer/store in code -- the platform
provides them.

## Notes & safety

- Sandboxes isolate code execution, but the agent is still susceptible to prompt
  injection from untrusted input. Use human-in-the-loop approval and short-lived
  secrets for sensitive deployments.
- The shared sandbox is created warm (no idle auto-stop) and kept running until
  you delete it, so it stays ready across runs.
- Secrets live only in `.env` (gitignored). Never commit real keys.
- **Gateway PII redaction:** the LangSmith gateway may rewrite locations/PII in
  prompts (e.g. "US"/"China" -> placeholders), which can confuse a coding agent.
  If you hit this, disable the redaction policy for this workspace, or set
  `CODE_GEN_USE_GATEWAY=false` to call the provider directly. A gateway-enabled
  key may also 401 against the provider directly, and vice-versa.
