"""System prompt loading.

The prompt is the source of truth in the LangSmith **Prompt Hub** so it can be
edited in the Playground and committed without a redeploy. It is pulled fresh at
graph construction. If the Hub repo doesn't exist yet (e.g. before you run the
bootstrap script, or offline), we fall back to the bundled seed so `langgraph
dev` still starts.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from langsmith import Client

logger = logging.getLogger(__name__)

PROMPT_REPO = os.environ.get("CODE_GEN_PROMPT_REPO", "code-gen-agent")
_SEED_PROMPT = Path(__file__).resolve().parent.parent / "assets" / "system_prompt.md"


def get_system_prompt() -> str:
    """Pull the system prompt from the Prompt Hub, falling back to the seed file."""
    try:
        prompt = Client().pull_prompt(PROMPT_REPO)
        # A ChatPromptTemplate: the system message text is the caller-layer prompt.
        return prompt.messages[0].prompt.template
    except Exception as exc:  # noqa: BLE001 - degrade gracefully to the seed
        logger.warning(
            "Could not pull prompt %r from the Prompt Hub (%s); using bundled seed. "
            "Run `uv run python scripts/bootstrap_hub.py` to publish it.",
            PROMPT_REPO,
            exc,
        )
        return _SEED_PROMPT.read_text()
