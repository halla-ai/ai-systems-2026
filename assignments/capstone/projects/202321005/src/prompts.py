"""에이전트 시스템 프롬프트 로더.

SOCRATES.md(공유 헌법) + .claude/agents/*.md(역할별 지침)를 읽어
각 에이전트의 최종 시스템 프롬프트를 조립한다 (docs/artifacts.md D-5).

Tier 3 주의: dialogue / qcritic 는 SOCRATES.md 를 상속하지만,
어느 프롬프트에도 정답 문자열이 들어있지 않다(SOCRATES.md 가 추상 원칙만 담음).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / ".claude" / "agents"
SOCRATES = ROOT / "SOCRATES.md"

# SOCRATES.md 를 상속하는 역할 (Dialogue·Q-Critic)
_INHERIT_SOCRATES = {"dialogue", "qcritic"}


def _strip_frontmatter(text: str) -> str:
    """`---` YAML frontmatter 제거 후 본문만 반환."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].lstrip("\n")
    return text


def load_system_prompt(role: str) -> str:
    """role 에 해당하는 에이전트의 최종 시스템 프롬프트를 조립한다.

    role ∈ {analysis, dialogue, qcritic, logging}
    """
    agent_file = AGENTS_DIR / f"{role}.md"
    if not agent_file.exists():
        raise FileNotFoundError(f"에이전트 지침 없음: {agent_file}")
    body = _strip_frontmatter(agent_file.read_text(encoding="utf-8"))

    if role in _INHERIT_SOCRATES:
        constitution = SOCRATES.read_text(encoding="utf-8")
        return f"{constitution}\n\n---\n\n{body}"
    return body
