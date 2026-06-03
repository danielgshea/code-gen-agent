"""Chat model construction, routed through the LangSmith LLM gateway.

Routing through the gateway means all model calls go to
``<gateway>/<provider>`` authenticated with your **LangSmith** API key (not the
raw provider key). The gateway centralizes provider keys, usage, and policy, and
the calls show up alongside your traces.

    chat completion  ->  https://gateway.smith.langchain.com/anthropic
                         (x-api-key: $LANGSMITH_API_KEY)

Set ``CODE_GEN_USE_GATEWAY=false`` to call the provider directly instead (then a
provider key such as ``ANTHROPIC_API_KEY`` must be set).

Caveats (see the langsmith-agent-builder skill):
- The gateway's PII-redaction policy can rewrite locations/PII in prompts
  (e.g. "US"/"China" -> placeholders), which can confuse a coding agent. Disable
  that policy for this agent's workspace if it trips you up.
- A *gateway* LangSmith key may 401 if used directly against the provider, and
  vice-versa. Use a workspace-scoped key that's enabled for the gateway.
"""

from __future__ import annotations

import os

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

_MODEL = os.environ.get("CODE_GEN_MODEL", "anthropic:claude-sonnet-4-6")
_USE_GATEWAY = os.environ.get("CODE_GEN_USE_GATEWAY", "true").lower() not in (
    "0",
    "false",
    "no",
)
# Base gateway URL; the provider is appended as a path segment. For self-hosted
# LangSmith, point this at your deployment's gateway.
_GATEWAY_URL = os.environ.get(
    "LANGSMITH_GATEWAY_URL", "https://gateway.smith.langchain.com"
).rstrip("/")


def _provider_of(model: str) -> str:
    """Provider prefix of a "provider:model" string (defaults to anthropic)."""
    return model.split(":", 1)[0] if ":" in model else "anthropic"


def build_model() -> BaseChatModel:
    """Build the chat model, routing through the LangSmith gateway by default."""
    if not _USE_GATEWAY:
        return init_chat_model(_MODEL)

    # The gateway can require a key distinct from the one used for the rest of
    # the LangSmith API (Hub/sandbox/tracing). Prefer the gateway-specific key.
    api_key = os.environ.get("LANGSMITH_API_KEY_GATEWAY") or os.environ.get(
        "LANGSMITH_API_KEY"
    )
    if not api_key:
        msg = (
            "CODE_GEN_USE_GATEWAY is on but no gateway key is set "
            "(LANGSMITH_API_KEY_GATEWAY or LANGSMITH_API_KEY). Set one, or set "
            "CODE_GEN_USE_GATEWAY=false to call the provider directly."
        )
        raise RuntimeError(msg)

    provider = _provider_of(_MODEL)
    return init_chat_model(
        _MODEL,
        base_url=f"{_GATEWAY_URL}/{provider}",
        api_key=api_key,
    )
