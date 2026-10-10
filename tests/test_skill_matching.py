"""
tests/test_skill_matching.py — Unit tests for skill_extractor and skill_matcher.
"""
import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from modules.skill_extractor import (
    extract_skills_from_text,
    normalize_skill_name,
    get_skill_label,
    normalize_skill_list,
)
from modules.skill_matcher import match_skills, analyze_skill_gap, PARTIAL_MATCH_RULES


# ──────────────────────────────────────────────────────────────────────────────
# Skill extraction tests
# ──────────────────────────────────────────────────────────────────────────────

class TestNormalizeSkillName:
    def test_python_canonical(self):
        assert normalize_skill_name("python") == "python"
        assert normalize_skill_name("Python") == "python"

    def test_python_alias(self):
        assert normalize_skill_name("python3") == "python"
        assert normalize_skill_name("python scripting") == "python"

    def test_javascript_aliases(self):
        assert normalize_skill_name("js") == "javascript"
        assert normalize_skill_name("JavaScript") == "javascript"
        assert normalize_skill_name("ES6") == "javascript"

    def test_sql_aliases(self):
        assert normalize_skill_name("mysql") == "sql"
        assert normalize_skill_name("postgresql") == "sql"
        assert normalize_skill_name("SQLite") == "sql"

    def test_react_aliases(self):
        assert normalize_skill_name("reactjs") == "react"
        assert normalize_skill_name("react.js") == "react"

    def test_git_aliases(self):
        assert normalize_skill_name("github") == "git"
        assert normalize_skill_name("version control") == "git"

    def test_unknown_skill_returns_none(self):
        assert normalize_skill_name("thisisnotaskill12345") is None

    def test_empty_string_returns_none(self):
        assert normalize_skill_name("") is None

    def test_whitespace_normalized(self):
        # Leading/trailing whitespace should be stripped
        assert normalize_skill_name("  python  ") == "python"

    def test_python_and_java_are_different(self):
        """Critical: Python and Java must NOT normalize to the same skill."""
        py = normalize_skill_name("python")
        java = normalize_skill_name("java")
        assert py != java
        assert py == "python"
        assert java == "java"


class TestExtractSkillsFromText:
    def test_extracts_python(self):
        skills = extract_skills_from_text("I have experience with Python and SQL.")
        ids = [s["skill_id"] for s in skills]
        assert "python" in ids
        assert "sql" in ids

    def test_returns_dict_structure(self):
        skills = extract_skills_from_text("Python developer")
        assert len(skills) > 0
        s = skills[0]
        assert "skill_id" in s
        assert "skill_label" in s
        assert "confidence" in s
        assert "mentions" in s

    def test_empty_text_returns_empty(self):
        assert extract_skills_from_text("") == []

    def test_no_skills_in_text(self):
        result = extract_skills_from_text("This text has no technical skills mentioned at all!")
        # Might match nothing or very little
        assert isinstance(result, list)

    def test_confidence_high_in_skills_section(self):
        skills = extract_skills_from_text("Python, JavaScript, SQL", section_context="skills")
        py = next((s for s in skills if s["skill_id"] == "python"), None)
        assert py is not None
        assert py["confidence"] == "high"

    def test_mention_count_increments(self):
        text = "Python is great. I use Python daily. My Python projects include data analysis."
        skills = extract_skills_from_text(text)
        py = next((s for s in skills if s["skill_id"] == "python"), None)
        assert py is not None
        assert py["mentions"] >= 3

    def test_does_not_confuse_python_and_java(self):
        """Python and Java should be extracted as separate skills, not merged."""
        text = "I know Python and Java."
        skills = extract_skills_from_text(text)
        ids = [s["skill_id"] for s in skills]
        assert "python" in ids
        assert "java" in ids

    def test_js_alias_maps_to_javascript(self):
        skills = extract_skills_from_text("Experienced in JS and React.")
        ids = [s["skill_id"] for s in skills]
        assert "javascript" in ids


class TestNormalizeSkillList:
    def test_recognized_skills_mapped(self):
        result = normalize_skill_list(["Python", "SQL", "React"])
        assert all(r["recognized"] for r in result)

    def test_unrecognized_skills_kept(self):
        result = normalize_skill_list(["ObscureFramework99"])
        assert len(result) == 1
        assert result[0]["recognized"] is False
        assert result[0]["original"] == "ObscureFramework99"

    def test_mixed_input(self):
        result = normalize_skill_list(["Python", "FakeSkill123"])
        recognized = [r for r in result if r["recognized"]]
        unrecognized = [r for r in result if not r["recognized"]]
        assert len(recognized) == 1
        assert len(unrecognized) == 1

    def test_empty_list(self):
        assert normalize_skill_list([]) == []


# ──────────────────────────────────────────────────────────────────────────────
# Skill matching tests
# ──────────────────────────────────────────────────────────────────────────────

class TestMatchSkills:
    """Tests for the match_skills() function."""

    def _make_req(self, skill_id: str, weight: float, mandatory: bool = True):
        return {
            "skill_id": skill_id,
            "weight": weight,
            "mandatory": mandatory,
            "reason": f"Test reason for {skill_id}",
        }

    def test_exact_match(self):
        result = match_skills(
            ["python", "sql"],
            [self._make_req("python", 0.8), self._make_req("sql", 0.9)]
        )
        assert len(result["matched"]) == 2
        assert len(result["missing"]) == 0

    def test_missing_skill(self):
        result = match_skills(
            ["python"],
            [self._make_req("python", 0.8), self._make_req("docker", 0.6)]
        )
        assert len(result["matched"]) == 1
        assert len(result["missing"]) == 1
        assert result["missing"][0]["skill_id"] == "docker"

    def test_partial_match_docker_to_kubernetes(self):
        """docker in candidate_skills → partial match for kubernetes requirement."""
        result = match_skills(
            ["docker"],
            [self._make_req("kubernetes", 0.65, mandatory=False)]
        )
        assert len(result["partial"]) == 1
        assert result["partial"][0]["skill_id"] == "kubernetes"

    def test_no_false_equivalence_python_java(self):
        """Python should NOT partially satisfy a Java requirement."""
        result = match_skills(
            ["python"],
            [self._make_req("java", 0.6)]
        )
        assert len(result["matched"]) == 0
        assert len(result["partial"]) == 0
        assert len(result["missing"]) == 1

    def test_extra_skills_identified(self):
        result = match_skills(
            ["python", "sql", "tensorflow"],
            [self._make_req("python", 0.8), self._make_req("sql", 0.9)]
        )
        extra_ids = [e["skill_id"] for e in result["extra"]]
        assert "tensorflow" in extra_ids

    def test_empty_candidate_all_missing(self):
        result = match_skills(
            [],
            [self._make_req("python", 0.8), self._make_req("sql", 0.9)]
        )
        assert len(result["missing"]) == 2
        assert len(result["matched"]) == 0

    def test_empty_requirements(self):
        result = match_skills(["python", "sql"], [])
        assert len(result["matched"]) == 0
        assert len(result["missing"]) == 0
        assert len(result["extra"]) == 2  # all candidate skills are extra


class TestAnalyzeSkillGap:
    def _mock_requirements(self):
        return {
            "role_id": "test_role",
            "title": "Test Role",
            "mandatory_skills": [
                {"skill_id": "python", "weight": 0.9, "mandatory": True, "reason": "Primary language"},
                {"skill_id": "sql", "weight": 0.8, "mandatory": True, "reason": "Database access"},
            ],
            "preferred_skills": [
                {"skill_id": "docker", "weight": 0.6, "mandatory": False, "reason": "Deployment"},
            ],
        }

    def test_full_match_candidate(self):
        gap = analyze_skill_gap(["python", "sql", "docker"], self._mock_requirements())
        assert gap["summary"]["matched_count"] == 3
        assert gap["summary"]["missing_count"] == 0

    def test_all_missing_candidate(self):
        gap = analyze_skill_gap([], self._mock_requirements())
        assert gap["summary"]["missing_count"] == 3
        assert gap["summary"]["matched_count"] == 0

    def test_mandatory_missing_count(self):
        gap = analyze_skill_gap(["docker"], self._mock_requirements())
        assert gap["summary"]["mandatory_missing_count"] == 2

    def test_summary_keys_present(self):
        gap = analyze_skill_gap(["python"], self._mock_requirements())
        summary = gap["summary"]
        required_keys = [
            "total_required", "matched_count", "partial_count",
            "missing_count", "mandatory_matched_count",
        ]
        for key in required_keys:
            assert key in summary, f"Missing key: {key}"
