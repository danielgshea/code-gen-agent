"""Code-generation DeepAgent that writes and runs Python in a LangSmith sandbox.

Exposes a compiled LangGraph graph as the module-level ``agent`` (referenced by
``langgraph.json``). The agent's filesystem and shell tools execute inside a
remote LangSmith sandbox; its prompt comes from the Prompt Hub and its skills +
long-term memory come from the Context Hub.
"""

from __future__ import annotations

import os

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model

from code_gen_agent.prompt import get_system_prompt
from code_gen_agent.sandbox import make_backend

_MODEL = os.environ.get("CODE_GEN_MODEL", "anthropic:claude-sonnet-4-6")

agent = create_deep_agent(
    model=init_chat_model(_MODEL),
    system_prompt=get_system_prompt(),
    # Per-thread LangSmith sandbox as the default backend; /skills/ and /memory/
    # are routed to the Context Hub inside the factory.
    backend=make_backend,
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
