"""Code-generation DeepAgent that writes and runs Python in a LangSmith sandbox.

Exposes a compiled LangGraph graph as the module-level ``agent`` (referenced by
``langgraph.json``). The agent's filesystem and shell tools execute *inside* a
shared, kept-warm LangSmith sandbox; its prompt comes from the Prompt Hub and
its skills + long-term memory come from the Context Hub.

The sandbox is connected once here at construction (server startup), not per
request, so a plain synchronous ``get_sandbox`` is fine — no event loop to block.
"""

from __future__ import annotations

import os
import pathlib
import tempfile

from deepagents import create_deep_agent
from deepagents.backends import (
    CompositeBackend,
    ContextHubBackend,
    FilesystemBackend,
    LangSmithSandbox,
)
from langsmith import Client
from langsmith.sandbox import ResourceNotFoundError, SandboxClient

from code_gen_agent.model import build_model
from code_gen_agent.prompt import get_system_prompt

# Context Hub skill repos, pulled at construction and served at /skills/.
SKILLS = [
    h.strip()
    for h in os.environ.get(
        "CODE_GEN_SKILLS", "python-codegen,shared-workspace"
    ).split(",")
    if h.strip()
]
# Context Hub agent repo holding the agent's long-term memory.
MEMORY_REPO = os.environ.get("CODE_GEN_MEMORY_REPO", "code-gen-agent-memory")

# Shared, kept-warm sandbox the agent writes and executes code in.
SANDBOX_NAME = os.environ.get("CODE_GEN_SANDBOX_NAME", "code-gen-agent-sandbox")

# Connect by name: reuse it if present (starting it if it was idled), or create
# it warm (no idle auto-stop) if absent. Creating it with this key makes the key
# the sandbox's creator, which is what grants run / file-op access.
_client = SandboxClient()
try:
    sandbox = _client.get_sandbox(SANDBOX_NAME)
    if sandbox.status != "ready":
        sandbox = _client.start_sandbox(SANDBOX_NAME)
except ResourceNotFoundError:
    sandbox = _client.create_sandbox(name=SANDBOX_NAME, idle_ttl_seconds=0)

# Pull each Context Hub skill repo and stage it as <name>/SKILL.md, then root a
# FilesystemBackend there. virtual_mode=True is required for routing under a
# CompositeBackend. Skills are curated, stable config — refreshed on restart.
_staged = pathlib.Path(tempfile.mkdtemp(prefix="code_gen_skills_"))
_hub = Client()
for handle in SKILLS:
    skill_md = _staged / handle / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text(_hub.pull_skill(handle).files["SKILL.md"].content)
skills_backend = FilesystemBackend(root_dir=str(_staged), virtual_mode=True)

# The sandbox is the agent's default filesystem + `execute` target; /skills/
# serves the staged skill repos and /memory/ is the Context Hub memory repo.
backend = CompositeBackend(
    default=LangSmithSandbox(sandbox),
    routes={
        "/skills/": skills_backend,
        "/memory/": ContextHubBackend(MEMORY_REPO),
    },
)

agent = create_deep_agent(
    # Routed through the LangSmith LLM gateway by default (see model.py).
    model=build_model(),
    system_prompt=get_system_prompt(),
    backend=backend,
    # On-demand expertise (progressive disclosure): only descriptions are in
    # context until the agent reads a SKILL.md.
    skills=["/skills/"],
    # Always-loaded memory the agent updates at runtime via its file tools.
    memory=["/memory/AGENTS.md"],
).with_config(
    # DeepAgents defaults recursion_limit to 9999; cap it so a non-converging
    # run can't loop effectively forever.
    {"recursion_limit": 75}
)
