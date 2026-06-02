"""LangSmith sandbox backend for the code-generation agent.

The agent runs the *sandbox-as-tool* pattern: the LangGraph loop runs wherever
the graph is hosted, but every filesystem and `execute` tool call is dispatched
into a remote LangSmith sandbox. We expose this through DeepAgents' native
``LangSmithSandbox`` backend, composed with the Context Hub so that ``/skills/``
and ``/memory/`` stay durable across sessions while code lives in the sandbox.

Layout of the agent's virtual filesystem:

    /                -> LangSmith sandbox (code, scratch, `execute` target)
    /skills/         -> Context Hub repo (read-only knowledge, progressive disclosure)
    /memory/         -> Context Hub repo (long-term memory the agent edits)
"""

from __future__ import annotations

import os
import threading

from deepagents.backends import (
    CompositeBackend,
    ContextHubBackend,
    LangSmithSandbox,
)
from deepagents.backends.protocol import BackendProtocol
from langsmith.sandbox import Sandbox, SandboxClient

# Context Hub agent repos that hold the agent's skills and long-term memory.
SKILLS_REPO = os.environ.get("CODE_GEN_SKILLS_REPO", "code-gen-agent-skills")
MEMORY_REPO = os.environ.get("CODE_GEN_MEMORY_REPO", "code-gen-agent-memory")

# How long a sandbox may sit idle before LangSmith stops it. Any file I/O or
# command execution resets the timer (see Sandbox lifetime and retention).
_IDLE_TTL = int(os.environ.get("CODE_GEN_SANDBOX_IDLE_TTL", "600"))
# Optionally boot from a prebuilt snapshot (e.g. one with deps preinstalled).
_SNAPSHOT = os.environ.get("CODE_GEN_SANDBOX_SNAPSHOT") or None

# One sandbox per conversation thread, reused across turns. The SandboxClient is
# created lazily so importing this module never requires credentials/network.
_client: SandboxClient | None = None
_sandboxes: dict[str, Sandbox] = {}
_lock = threading.Lock()


def _get_client() -> SandboxClient:
    global _client
    if _client is None:
        # Reads LANGSMITH_ENDPOINT / LANGSMITH_API_KEY from the environment.
        _client = SandboxClient()
    return _client


def _get_sandbox(thread_id: str) -> Sandbox:
    """Return the sandbox for this thread, creating it on first use."""
    with _lock:
        sandbox = _sandboxes.get(thread_id)
        if sandbox is None:
            sandbox = _get_client().create_sandbox(
                snapshot_name=_SNAPSHOT,
                idle_ttl_seconds=_IDLE_TTL,
            )
            _sandboxes[thread_id] = sandbox
        return sandbox


def make_backend(runtime: object) -> BackendProtocol:
    """Backend factory passed to ``create_deep_agent(backend=...)``.

    Invoked per run with a ``ToolRuntime``; we key the sandbox off the LangGraph
    ``thread_id`` so a multi-turn conversation keeps the same workspace.
    """
    config = getattr(runtime, "config", None) or {}
    thread_id = (config.get("configurable") or {}).get("thread_id") or "default"

    sandbox = _get_sandbox(thread_id)

    return CompositeBackend(
        default=LangSmithSandbox(sandbox),
        routes={
            "/skills/": ContextHubBackend(SKILLS_REPO),
            "/memory/": ContextHubBackend(MEMORY_REPO),
        },
    )
