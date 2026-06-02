"""Publish the agent's prompt, skills, and seed memory to LangSmith.

Run once (and again whenever you want to reset the seeds) to populate:
  - the **Prompt Hub** with the system prompt, and
  - two **Context Hub** agent repos with the skills and the seed memory.

After this, the agent pulls its prompt from the Hub at construction and reads
`/skills/` + `/memory/` from the Context Hub at runtime. Thereafter, edit the
prompt in the Playground and let the agent rewrite its own memory — no redeploy.

    uv run --env-file .env python scripts/bootstrap_hub.py

Requires a workspace-scoped LANGSMITH_API_KEY.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langsmith import Client
from langsmith.schemas import FileEntry

from code_gen_agent.prompt import PROMPT_REPO
from code_gen_agent.sandbox import MEMORY_REPO, SKILLS_REPO

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

    # 2. Skills -> Context Hub agent repo, laid out as <skill>/SKILL.md.
    skill_files: dict[str, FileEntry] = {}
    for skill_md in (ASSETS / "skills").rglob("SKILL.md"):
        rel = skill_md.relative_to(ASSETS / "skills").as_posix()
        skill_files[rel] = _file_entry(skill_md)
    client.push_agent(
        SKILLS_REPO,
        files=skill_files,
        description="Skills for the Python code-generation agent.",
    )
    print(f"Pushed skills   -> {SKILLS_REPO}: {sorted(skill_files)}")

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
