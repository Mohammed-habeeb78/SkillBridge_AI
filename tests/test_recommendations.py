"""
tests/test_recommendations.py — Unit tests for recommendation_engine.py
"""
import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from modules.recommendation_engine import (
    generate_roadmap,
    get_resources_for_skill,
    get_mini_project,
    estimate_duration,
    PREREQUISITES,
    _has_unmet_prerequisites,
    _assign_stage,
)


def _make_gap(mand_missing=None, pref_missing=None, mand_partial=None, pref_partial=None,
              role_id="test", role_title="Test Role"):
    def _s(sid, weight, mandatory=True):
        return {
            "skill_id": sid,
            "skill_label": sid.replace("_", " ").title(),
            "weight": weight,
            "mandatory": mandatory,
            "reason": f"Needed for {sid}",
            "match_type": "missing",
        }

    return {
        "role_id": role_id,
        "role_title": role_title,
        "mandatory_match": [],
        "mandatory_partial": mand_partial or [],
        "mandatory_missing": mand_missing or [],
        "preferred_match": [],
        "preferred_partial": pref_partial or [],
        "preferred_missing": pref_missing or [],
        "extra_skills": [],
        "summary": {"matched_count": 0, "missing_count": 0},
    }


class TestGenerateRoadmap:
    def test_empty_gap_returns_no_stages(self):
        gap = _make_gap()
        result = generate_roadmap(gap, [])
        assert result["total_tasks"] == 0

    def test_missing_skills_create_tasks(self):
        gap = _make_gap(
            mand_missing=[
                {"skill_id": "python", "skill_label": "Python", "weight": 0.9,
                 "mandatory": True, "reason": "Primary language", "match_type": "missing"},
            ]
        )
        result = generate_roadmap(gap, [])
        assert result["total_tasks"] >= 1

    def test_stage4_always_included_when_tasks_exist(self):
        """Stage 4 (projects + interview prep) should always appear."""
        gap = _make_gap(
            mand_missing=[
                {"skill_id": "python", "skill_label": "Python", "weight": 0.9,
                 "mandatory": True, "reason": "Primary language", "match_type": "missing"},
            ]
        )
        result = generate_roadmap(gap, [])
        stage_numbers = [s["stage"] for s in result["stages"]]
        assert 4 in stage_numbers

    def test_mandatory_missing_before_preferred_missing(self):
        """All mandatory missing tasks must appear before preferred missing tasks in the flat list."""
        gap = _make_gap(
            mand_missing=[
                {"skill_id": "python", "skill_label": "Python", "weight": 0.5,
                 "mandatory": True, "reason": "R1", "match_type": "missing"},
            ],
            pref_missing=[
                {"skill_id": "docker", "skill_label": "Docker", "weight": 0.9,
                 "mandatory": False, "reason": "R2", "match_type": "missing"},
            ],
        )
        result = generate_roadmap(gap, [])
        tasks = result.get("all_tasks", [])
        # Find first mandatory and first preferred task
        mandatory_tasks = [t for t in tasks if t["mandatory"]]
        preferred_tasks = [t for t in tasks if not t["mandatory"] and t["match_type"] != "stage4"]
        if mandatory_tasks and preferred_tasks:
            # Mandatory priority should be numerically lower (higher priority)
            assert min(t["priority"] for t in mandatory_tasks) < min(t["priority"] for t in preferred_tasks)

    def test_high_weight_mandatory_in_stage1(self):
        """A mandatory skill with weight >= 0.8 should be assigned to stage 1."""
        gap = _make_gap(
            mand_missing=[
                {"skill_id": "python", "skill_label": "Python", "weight": 0.9,
                 "mandatory": True, "reason": "", "match_type": "missing"},
            ]
        )
        result = generate_roadmap(gap, [])
        all_tasks = result.get("all_tasks", [])
        py_task = next((t for t in all_tasks if t["skill_id"] == "python"), None)
        assert py_task is not None
        assert py_task["stage"] == 1

    def test_low_weight_preferred_in_stage3(self):
        """A preferred skill should be assigned to stage 3."""
        gap = _make_gap(
            pref_missing=[
                {"skill_id": "docker", "skill_label": "Docker", "weight": 0.6,
                 "mandatory": False, "reason": "", "match_type": "missing"},
            ]
        )
        result = generate_roadmap(gap, [])
        all_tasks = result.get("all_tasks", [])
        docker_task = next((t for t in all_tasks if t["skill_id"] == "docker"), None)
        assert docker_task is not None
        assert docker_task["stage"] == 3

    def test_result_has_summary(self):
        gap = _make_gap(
            mand_missing=[
                {"skill_id": "python", "skill_label": "Python", "weight": 0.9,
                 "mandatory": True, "reason": "", "match_type": "missing"},
            ]
        )
        result = generate_roadmap(gap, [])
        assert "summary" in result
        assert len(result["summary"]) > 0

    def test_unmet_prerequisites_flagged(self):
        """scikit_learn requires python; if python not in candidate_skills, it should be flagged."""
        gap = _make_gap(
            mand_missing=[
                {"skill_id": "scikit_learn", "skill_label": "Scikit-learn", "weight": 0.85,
                 "mandatory": True, "reason": "", "match_type": "missing"},
            ]
        )
        # candidate does NOT have python
        result = generate_roadmap(gap, [])
        all_tasks = result.get("all_tasks", [])
        sklearn_task = next((t for t in all_tasks if t["skill_id"] == "scikit_learn"), None)
        assert sklearn_task is not None
        assert "python" in sklearn_task["unmet_prerequisites"]

    def test_unmet_prerequisites_empty_when_met(self):
        """If candidate already has python, scikit_learn prereq should not flag it."""
        gap = _make_gap(
            mand_missing=[
                {"skill_id": "scikit_learn", "skill_label": "Scikit-learn", "weight": 0.85,
                 "mandatory": True, "reason": "", "match_type": "missing"},
            ]
        )
        result = generate_roadmap(gap, candidate_skill_ids=["python", "pandas", "numpy", "statistics"])
        all_tasks = result.get("all_tasks", [])
        sklearn_task = next((t for t in all_tasks if t["skill_id"] == "scikit_learn"), None)
        assert sklearn_task is not None
        assert "python" not in sklearn_task["unmet_prerequisites"]


class TestResourceLookup:
    def test_python_has_resources(self):
        resources = get_resources_for_skill("python")
        assert len(resources) > 0

    def test_resource_has_required_fields(self):
        resources = get_resources_for_skill("python")
        for r in resources:
            assert "title" in r
            assert "url" in r
            assert "platform" in r

    def test_unknown_skill_returns_empty_list(self):
        resources = get_resources_for_skill("this_skill_does_not_exist_xyz")
        assert resources == []

    def test_sql_has_resources(self):
        resources = get_resources_for_skill("sql")
        assert len(resources) > 0


class TestMiniProject:
    def test_python_has_mini_project(self):
        mp = get_mini_project("python")
        assert mp is not None
        assert len(mp) > 10

    def test_unknown_skill_returns_none(self):
        assert get_mini_project("nonexistent_xyz") is None


class TestEstimateDuration:
    def test_returns_positive_integer(self):
        hours = estimate_duration("python")
        assert isinstance(hours, int)
        assert hours > 0

    def test_unknown_skill_returns_positive(self):
        hours = estimate_duration("totally_made_up_skill")
        assert hours > 0


class TestStageAssignment:
    def test_high_weight_mandatory_is_stage1(self):
        assert _assign_stage("python", 0.9, mandatory=True) == 1

    def test_lower_weight_mandatory_is_stage2(self):
        assert _assign_stage("agile_scrum", 0.55, mandatory=True) == 2

    def test_preferred_is_stage3(self):
        assert _assign_stage("docker", 0.6, mandatory=False) == 3


class TestHasUnmetPrerequisites:
    def test_scikit_learn_needs_python(self):
        unmet = _has_unmet_prerequisites("scikit_learn", [])
        assert "python" in unmet

    def test_scikit_learn_met_when_python_present(self):
        unmet = _has_unmet_prerequisites("scikit_learn", ["python", "pandas", "numpy", "statistics"])
        assert "python" not in unmet

    def test_no_prerequisites_for_git(self):
        unmet = _has_unmet_prerequisites("git", [])
        assert unmet == []
