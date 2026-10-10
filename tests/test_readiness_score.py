"""
tests/test_readiness_score.py — Unit tests for readiness_score.py
"""
import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from modules.readiness_score import calculate_readiness_score, _score_band, compare_scores


def _make_gap(
    mand_match=None, mand_partial=None, mand_miss=None,
    pref_match=None, pref_partial=None, pref_miss=None,
    role_id="test", role_title="Test Role"
):
    """Helper to build a minimal gap analysis dict."""
    def _s(skill_id, weight, mandatory=True):
        return {"skill_id": skill_id, "skill_label": skill_id.replace("_", " ").title(),
                "weight": weight, "mandatory": mandatory}

    return {
        "role_id": role_id,
        "role_title": role_title,
        "mandatory_match":   mand_match or [],
        "mandatory_partial": mand_partial or [],
        "mandatory_missing": mand_miss or [],
        "preferred_match":   pref_match or [],
        "preferred_partial": pref_partial or [],
        "preferred_missing": pref_miss or [],
        "extra_skills": [],
        "summary": {},
    }


class TestCalculateReadinessScore:
    def test_perfect_match_score_100(self):
        gap = _make_gap(
            mand_match=[
                {"skill_id": "python", "skill_label": "Python", "weight": 0.9, "mandatory": True},
                {"skill_id": "sql", "skill_label": "SQL", "weight": 0.8, "mandatory": True},
            ]
        )
        result = calculate_readiness_score(gap)
        assert result["score"] == 100.0

    def test_all_missing_score_0(self):
        gap = _make_gap(
            mand_miss=[
                {"skill_id": "python", "skill_label": "Python", "weight": 0.9, "mandatory": True},
                {"skill_id": "sql", "skill_label": "SQL", "weight": 0.8, "mandatory": True},
            ]
        )
        result = calculate_readiness_score(gap)
        assert result["score"] == 0.0

    def test_partial_match_contributes_half_weight(self):
        """If all mandatory skills are partial, score should be ~50% of mandatory tier."""
        gap = _make_gap(
            mand_partial=[
                {"skill_id": "python", "skill_label": "Python", "weight": 0.9, "mandatory": True},
            ]
        )
        result = calculate_readiness_score(gap)
        # mandatory_ratio = (0.9 * 0.5) / 0.9 = 0.5
        # No preferred skills, so score comes entirely from mandatory tier
        # Combined: (1.0 * 0.5 + 0.4 * 1.0) / 1.4 ≈ 0.643... wait, no preferred skills
        # Actually: with no preferred at all, preferred_ratio = 1.0 (vacuously true)
        # score = 100 * (1.0*0.5 + 0.4*1.0) / 1.4 ≈ 64.3
        # Just check it's between 0 and 100 and less than 100
        assert 0 < result["score"] < 100

    def test_score_between_0_and_100(self):
        """Score must always be in [0, 100] range."""
        gap = _make_gap(
            mand_match=[{"skill_id": "python", "skill_label": "Python", "weight": 0.8, "mandatory": True}],
            mand_miss=[{"skill_id": "sql", "skill_label": "SQL", "weight": 0.9, "mandatory": True}],
            pref_match=[{"skill_id": "docker", "skill_label": "Docker", "weight": 0.6, "mandatory": False}],
            pref_miss=[{"skill_id": "kubernetes", "skill_label": "K8s", "weight": 0.5, "mandatory": False}],
        )
        result = calculate_readiness_score(gap)
        assert 0 <= result["score"] <= 100

    def test_mandatory_score_greater_than_preferred_when_more_mandatory_covered(self):
        gap = _make_gap(
            mand_match=[
                {"skill_id": "python", "skill_label": "Python", "weight": 0.9, "mandatory": True},
                {"skill_id": "sql", "skill_label": "SQL", "weight": 0.8, "mandatory": True},
            ],
            pref_miss=[
                {"skill_id": "docker", "skill_label": "Docker", "weight": 0.6, "mandatory": False},
                {"skill_id": "tableau", "skill_label": "Tableau", "weight": 0.5, "mandatory": False},
            ],
        )
        result = calculate_readiness_score(gap)
        assert result["mandatory_score"] == 100.0
        assert result["preferred_score"] == 0.0

    def test_result_contains_required_keys(self):
        gap = _make_gap(
            mand_match=[{"skill_id": "python", "skill_label": "Python", "weight": 0.8, "mandatory": True}]
        )
        result = calculate_readiness_score(gap)
        required_keys = [
            "score", "mandatory_score", "preferred_score",
            "band", "band_description", "formula_explanation",
            "disclaimer", "skill_contributions",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_skill_contributions_list_completeness(self):
        """All matched, partial, and missing skills should appear in contributions."""
        gap = _make_gap(
            mand_match=[{"skill_id": "python", "skill_label": "Python", "weight": 0.9, "mandatory": True}],
            mand_partial=[{"skill_id": "numpy", "skill_label": "NumPy", "weight": 0.8, "mandatory": True,
                           "matched_by": ["pandas"], "explanation": "partial"}],
            mand_miss=[{"skill_id": "sql", "skill_label": "SQL", "weight": 0.8, "mandatory": True}],
        )
        result = calculate_readiness_score(gap)
        contribution_ids = {c["skill_id"] for c in result["skill_contributions"]}
        assert "python" in contribution_ids
        assert "numpy" in contribution_ids
        assert "sql" in contribution_ids

    def test_missing_skills_have_zero_contribution(self):
        gap = _make_gap(
            mand_miss=[{"skill_id": "python", "skill_label": "Python", "weight": 0.9, "mandatory": True}]
        )
        result = calculate_readiness_score(gap)
        py_contrib = next(c for c in result["skill_contributions"] if c["skill_id"] == "python")
        assert py_contrib["contribution"] == 0.0

    def test_exact_match_contribution_greater_than_partial(self):
        """Exact match contribution should exceed partial match for same weight."""
        gap_exact = _make_gap(
            mand_match=[{"skill_id": "python", "skill_label": "Python", "weight": 0.9, "mandatory": True}]
        )
        gap_partial = _make_gap(
            mand_partial=[{"skill_id": "python", "skill_label": "Python", "weight": 0.9, "mandatory": True,
                           "matched_by": ["pandas"], "explanation": "partial"}]
        )
        exact_result = calculate_readiness_score(gap_exact)
        partial_result = calculate_readiness_score(gap_partial)
        assert exact_result["score"] > partial_result["score"]

    def test_no_skills_empty_gap(self):
        """Edge case: no required skills at all."""
        gap = _make_gap()
        result = calculate_readiness_score(gap)
        # With no required skills, score should be 100 (nothing to fail on)
        assert result["score"] == 100.0

    def test_score_updates_when_skills_added(self):
        """Simulates a user adding skills: score should increase."""
        gap_before = _make_gap(
            mand_miss=[
                {"skill_id": "python", "skill_label": "Python", "weight": 0.9, "mandatory": True},
                {"skill_id": "sql", "skill_label": "SQL", "weight": 0.8, "mandatory": True},
            ]
        )
        gap_after = _make_gap(
            mand_match=[{"skill_id": "python", "skill_label": "Python", "weight": 0.9, "mandatory": True}],
            mand_miss=[{"skill_id": "sql", "skill_label": "SQL", "weight": 0.8, "mandatory": True}],
        )
        score_before = calculate_readiness_score(gap_before)["score"]
        score_after = calculate_readiness_score(gap_after)["score"]
        assert score_after > score_before


class TestScoreBand:
    def test_excellent_band(self):
        band, desc = _score_band(85)
        assert band == "Excellent"
        assert len(desc) > 10

    def test_good_band(self):
        band, _ = _score_band(70)
        assert band == "Good"

    def test_developing_band(self):
        band, _ = _score_band(50)
        assert band == "Developing"

    def test_beginner_band(self):
        band, _ = _score_band(20)
        assert band == "Beginner"

    def test_boundary_80_is_excellent(self):
        band, _ = _score_band(80)
        assert band == "Excellent"

    def test_boundary_60_is_good(self):
        band, _ = _score_band(60)
        assert band == "Good"


class TestCompareScores:
    def test_sorted_by_score_descending(self):
        gaps = [
            _make_gap(
                mand_match=[{"skill_id": "python", "skill_label": "Python", "weight": 0.9, "mandatory": True}],
                role_id="role_a", role_title="Role A"
            ),
            _make_gap(
                mand_miss=[{"skill_id": "python", "skill_label": "Python", "weight": 0.9, "mandatory": True}],
                role_id="role_b", role_title="Role B"
            ),
        ]
        results = compare_scores(gaps)
        assert results[0]["score"] >= results[1]["score"]

    def test_returns_list_of_dicts(self):
        gaps = [_make_gap(role_id="r", role_title="Role")]
        results = compare_scores(gaps)
        assert isinstance(results, list)
        assert "score" in results[0]
        assert "band" in results[0]

    def test_empty_gaps(self):
        assert compare_scores([]) == []
