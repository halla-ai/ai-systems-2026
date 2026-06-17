"""Tests for L5 skill runtime."""

from pathlib import Path

from docs_code_drift_detector.skill_runtime import load_all_skills, load_skill

SKILLS_ROOT = Path(__file__).parent.parent / "skills"


def test_load_all_skills():
    skills = load_all_skills(SKILLS_ROOT)
    assert "doc_analyzer" in skills
    assert "drift_detector" in skills
    assert "reviewer" in skills


def test_load_skill_has_instructions_and_tools():
    skill = load_skill("doc_analyzer", SKILLS_ROOT)
    assert skill.role == "worker"
    assert "doc_spec" in skill.instructions or "README" in skill.instructions
    assert "filesystem.read" in skill.allowed_tools
    assert any("semantic" in a.lower() for a in skill.forbidden_actions)


def test_reviewer_skill_role():
    skill = load_skill("reviewer", SKILLS_ROOT)
    assert skill.role == "reviewer"
    combined = skill.raw_markdown.lower()
    assert "hotl" in combined or "human_review" in combined
