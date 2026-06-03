"""Publish the agent's prompt, skills, and seed memory to LangSmith.

Run once (and again whenever you want to reset the seeds) to populate:
  - the **Prompt Hub** with the system prompt,
  - one **Context Hub skill repo** per skill under assets/skills/, and
  - a **Context Hub agent repo** with the seed memory.

After this, the agent pulls its prompt and skills from the Hub at construction
and reads `/memory/` from the Context Hub at runtime. Thereafter, edit the prompt
in the Playground and let the agent rewrite its own memory — no redeploy.

    uv run --env-file .env python -m scripts.bootstrap_hub  
    
Requires a workspace-scoped LANGSMITH_API_KEY.
"""

from __future__ import annotations

import os
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langsmith import Client
from langsmith.schemas import FileEntry

from code_gen_agent.prompt import PROMPT_REPO

# Read the memory repo name directly (same default as agent.py) so this script
# doesn't import the agent module, whose import connects to the sandbox.
MEMORY_REPO = os.environ.get("CODE_GEN_MEMORY_REPO", "code-gen-agent-memory")

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def _file_entry(path: Path) -> FileEntry:
    return FileEntry(type="file", content=path.read_text())


def main() -> None:
    client = Client()

    # 1. System prompt -> Prompt Hub. Stored as a ChatPromptTemplate; the agent
    #    pulls messages[0].prompt.template back out.
    system_text = (ASSETS / "system_prompt.md").read_text()
    template = ChatPromptTemplate.from_messages([("system", system_text)])
    url = client.push_prompt(
        PROMPT_REPO,
        object=template,
        description="System prompt for the Python code-generation sandbox agent.",
    )
    print(f"Pushed prompt   -> {PROMPT_REPO}\n  {url}")

    # 2. Skills -> Context Hub, one standalone skill repo per assets/skills/<name>.
    #    (Skills authored elsewhere in the hub, e.g. `shared-workspace`, are not
    #    seeded here — the agent just pulls them by name.)
    for skill_md in (ASSETS / "skills").rglob("SKILL.md"):
        name = skill_md.parent.name
        client.push_skill(
            name,
            files={"SKILL.md": _file_entry(skill_md)},
            description=f"{name} skill for the Python code-generation agent.",
        )
        print(f"Pushed skill    -> {name}")

    # 3. Seed memory -> Context Hub agent repo. The agent edits this at runtime.
    memory_files = {
        p.relative_to(ASSETS / "memory").as_posix(): _file_entry(p)
        for p in (ASSETS / "memory").rglob("*.md")
    }
    client.push_agent(
        MEMORY_REPO,
        files=memory_files,
        description="Long-term memory for the Python code-generation agent.",
    )
    print(f"Pushed memory   -> {MEMORY_REPO}: {sorted(memory_files)}")

    print("\nDone. Start the agent with: uv run langgraph dev")


if __name__ == "__main__":
    main()
