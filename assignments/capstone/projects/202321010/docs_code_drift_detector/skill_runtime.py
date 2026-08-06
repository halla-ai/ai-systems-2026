"""L5 Markdown-SSOT Skill Runtime — load role instructions, rubrics, tool scope."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"


@dataclass
class SkillDefinition:
    name: str
    role: str
    instructions: str
    rubric: dict[str, str] = field(default_factory=dict)
    allowed_tools: list[str] = field(default_factory=list)
    forbidden_actions: list[str] = field(default_factory=list)
    raw_markdown: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "instructions": self.instructions,
            "rubric": self.rubric,
            "allowed_tools": self.allowed_tools,
            "forbidden_actions": self.forbidden_actions,
        }


def _parse_section(content: str, heading: str) -> str:
    pattern = rf"##\s*{re.escape(heading)}\s*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _parse_list_section(content: str, heading: str) -> list[str]:
    section = _parse_section(content, heading)
    return [
        line.lstrip("- ").strip()
        for line in section.splitlines()
        if line.strip().startswith("-")
    ]


def _parse_rubric(content: str) -> dict[str, str]:
    section = _parse_section(content, "Rubric")
    rubric = {}
    for line in section.splitlines():
        if ":" in line and line.strip().startswith("-"):
            key, val = line.lstrip("- ").split(":", 1)
            rubric[key.strip()] = val.strip()
    return rubric


def load_skill(skill_name: str, skills_root: Path | None = None) -> SkillDefinition:
    root = skills_root or SKILLS_ROOT
    skill_path = root / skill_name / "SKILL.md"
    if not skill_path.exists():
        return SkillDefinition(
            name=skill_name,
            role="worker",
            instructions=f"No SKILL.md found for {skill_name}.",
        )
    content = skill_path.read_text(encoding="utf-8")
    title_match = re.search(r"^#\s+(.+)$", content, re.M)
    role_match = re.search(r"\*\*Role:\*\*\s*(\w+)", content)
    return SkillDefinition(
        name=skill_name,
        role=role_match.group(1) if role_match else "worker",
        instructions=_parse_section(content, "Instructions"),
        rubric=_parse_rubric(content),
        allowed_tools=_parse_list_section(content, "Allowed Tools"),
        forbidden_actions=_parse_list_section(content, "Forbidden Actions"),
        raw_markdown=content,
    )


def load_all_skills(skills_root: Path | None = None) -> dict[str, SkillDefinition]:
    root = skills_root or SKILLS_ROOT
    if not root.exists():
        return {}
    skills = {}
    for skill_dir in sorted(root.iterdir()):
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            skills[skill_dir.name] = load_skill(skill_dir.name, root)
    return skills


def get_instruction_for_agent(agent_name: str, skills_root: Path | None = None) -> str:
    skill = load_skill(agent_name, skills_root)
    return skill.instructions or skill.raw_markdown
