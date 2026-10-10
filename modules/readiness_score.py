"""
modules/readiness_score.py — Calculate and explain the career readiness score.

Scoring formula (transparent, explainable):
  For mandatory skills:
    mandatory_covered = sum(weight for matched) + 0.5 * sum(weight for partial)
    mandatory_total   = sum(weight for all mandatory skills)
    mandatory_ratio   = mandatory_covered / mandatory_total   (if total > 0 else 1.0)

  For preferred skills:
    preferred_covered = sum(weight for matched) + 0.5 * sum(weight for partial)
    preferred_total   = sum(weight for all preferred skills)
    preferred_ratio   = preferred_covered / preferred_total   (if total > 0 else 1.0)

  Combined score (0–100):
    raw = (MANDATORY_TIER_WEIGHT * mandatory_ratio
           + PREFERRED_TIER_WEIGHT * preferred_ratio)
          / (MANDATORY_TIER_WEIGHT + PREFERRED_TIER_WEIGHT)
    score = round(raw * 100, 1)

Rationale:
  - Mandatory skills carry more weight (default weight 1.0 vs 0.4 for preferred).
  - Partial matches contribute 50% of the skill's weight — they indicate
    related knowledge but not confirmed proficiency.
  - The score is explicitly labelled as indicative; it is NOT a hiring predictor.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MANDATORY_TIER_WEIGHT, PREFERRED_TIER_WEIGHT, DISCLAIMER


# ---------------------------------------------------------------------------
# Score calculation
# ---------------------------------------------------------------------------

PARTIAL_WEIGHT_FACTOR = 0.5  # partial matches contribute 50% of skill weight


def calculate_readiness_score(gap_analysis: Dict) -> Dict:
    """
    Calculate the career readiness score from a gap analysis result.

    Args:
        gap_analysis: Output of skill_matcher.analyze_skill_gap().

    Returns:
        {
          score: float,                   # 0–100
          mandatory_score: float,         # 0–100
          preferred_score: float,         # 0–100
          mandatory_covered_weight: float,
          mandatory_total_weight: float,
          preferred_covered_weight: float,
          preferred_total_weight: float,
          skill_contributions: [
            {skill_id, skill_label, weight, match_type, contribution, mandatory}
          ],
          band: str,                      # "Excellent" | "Good" | "Developing" | "Beginner"
          band_description: str,
          formula_explanation: str,
          disclaimer: str,
        }
    """
    # ── Mandatory tier ───────────────────────────────────────────────────────
    mand_match  = gap_analysis.get("mandatory_match", [])
    mand_partial= gap_analysis.get("mandatory_partial", [])
    mand_miss   = gap_analysis.get("mandatory_missing", [])

    mand_total  = (
        sum(s["weight"] for s in mand_match)
        + sum(s["weight"] for s in mand_partial)
        + sum(s["weight"] for s in mand_miss)
    )
    mand_covered = (
        sum(s["weight"] for s in mand_match)
        + PARTIAL_WEIGHT_FACTOR * sum(s["weight"] for s in mand_partial)
    )
    mand_ratio = mand_covered / mand_total if mand_total > 0 else 1.0

    # ── Preferred tier ───────────────────────────────────────────────────────
    pref_match  = gap_analysis.get("preferred_match", [])
    pref_partial= gap_analysis.get("preferred_partial", [])
    pref_miss   = gap_analysis.get("preferred_missing", [])

    pref_total  = (
        sum(s["weight"] for s in pref_match)
        + sum(s["weight"] for s in pref_partial)
        + sum(s["weight"] for s in pref_miss)
    )
    pref_covered = (
        sum(s["weight"] for s in pref_match)
        + PARTIAL_WEIGHT_FACTOR * sum(s["weight"] for s in pref_partial)
    )
    pref_ratio = pref_covered / pref_total if pref_total > 0 else 1.0

    # ── Combined ─────────────────────────────────────────────────────────────
    tier_denom = MANDATORY_TIER_WEIGHT + PREFERRED_TIER_WEIGHT
    raw_ratio = (
        MANDATORY_TIER_WEIGHT * mand_ratio
        + PREFERRED_TIER_WEIGHT * pref_ratio
    ) / tier_denom

    score = round(raw_ratio * 100, 1)
    mand_score = round(mand_ratio * 100, 1)
    pref_score = round(pref_ratio * 100, 1)

    # ── Per-skill contributions ───────────────────────────────────────────────
    contributions = []
    for s in mand_match:
        contributions.append(_contribution_record(s, "exact", True, mand_total, tier_denom))
    for s in mand_partial:
        contributions.append(_contribution_record(s, "partial", True, mand_total, tier_denom))
    for s in mand_miss:
        contributions.append(_contribution_record(s, "missing", True, mand_total, tier_denom))
    for s in pref_match:
        contributions.append(_contribution_record(s, "exact", False, pref_total, tier_denom))
    for s in pref_partial:
        contributions.append(_contribution_record(s, "partial", False, pref_total, tier_denom))
    for s in pref_miss:
        contributions.append(_contribution_record(s, "missing", False, pref_total, tier_denom))

    # ── Band ─────────────────────────────────────────────────────────────────
    band, band_desc = _score_band(score)

    formula_explanation = (
        "Score = 100 × [ "
        f"{MANDATORY_TIER_WEIGHT}×(mandatory_covered_weight / mandatory_total_weight) "
        f"+ {PREFERRED_TIER_WEIGHT}×(preferred_covered_weight / preferred_total_weight) "
        f"] / {tier_denom:.1f}. "
        "Partial matches count as 50% of the skill's weight. "
        "Mandatory skills receive a higher tier weight than preferred skills."
    )

    return {
        "score": score,
        "mandatory_score": mand_score,
        "preferred_score": pref_score,
        "mandatory_covered_weight": round(mand_covered, 4),
        "mandatory_total_weight": round(mand_total, 4),
        "preferred_covered_weight": round(pref_covered, 4),
        "preferred_total_weight": round(pref_total, 4),
        "skill_contributions": sorted(contributions, key=lambda x: (-x["mandatory"], -x["weight"])),
        "band": band,
        "band_description": band_desc,
        "formula_explanation": formula_explanation,
        "disclaimer": DISCLAIMER,
    }


def _contribution_record(
    skill: Dict,
    match_type: str,
    mandatory: bool,
    tier_total: float,
    tier_denom: float
) -> Dict:
    if match_type == "exact":
        effective_weight = skill["weight"]
    elif match_type == "partial":
        effective_weight = skill["weight"] * PARTIAL_WEIGHT_FACTOR
    else:
        effective_weight = 0.0

    tier_weight = MANDATORY_TIER_WEIGHT if mandatory else PREFERRED_TIER_WEIGHT
    # Contribution to the final score (as a 0–100 point value)
    if tier_total > 0:
        contribution = round(
            (effective_weight / tier_total) * tier_weight / (MANDATORY_TIER_WEIGHT + PREFERRED_TIER_WEIGHT) * 100,
            2
        )
    else:
        contribution = 0.0

    return {
        "skill_id": skill["skill_id"],
        "skill_label": skill.get("skill_label", skill["skill_id"]),
        "weight": skill["weight"],
        "match_type": match_type,
        "mandatory": mandatory,
        "contribution": contribution,
    }


def _score_band(score: float):
    if score >= 80:
        return "Excellent", (
            "Your skills profile covers the large majority of requirements for this role. "
            "Focus on any remaining gaps and strengthen practical project experience."
        )
    elif score >= 60:
        return "Good", (
            "You have a solid foundation. Address the missing mandatory skills "
            "to significantly improve your readiness."
        )
    elif score >= 40:
        return "Developing", (
            "You have relevant skills but notable gaps exist. "
            "Following the recommended learning roadmap will substantially improve your profile."
        )
    else:
        return "Beginner", (
            "This role requires skills you are still building. "
            "The learning roadmap provides a structured path from your current level."
        )


# ---------------------------------------------------------------------------
# Score comparison across roles
# ---------------------------------------------------------------------------

def compare_scores(gap_analyses: List[Dict]) -> List[Dict]:
    """
    Calculate readiness scores for multiple roles.

    Returns list of {role_id, role_title, score, band, mandatory_score, preferred_score}
    sorted by score descending.
    """
    results = []
    for gap in gap_analyses:
        score_result = calculate_readiness_score(gap)
        results.append({
            "role_id": gap.get("role_id", ""),
            "role_title": gap.get("role_title", ""),
            "score": score_result["score"],
            "band": score_result["band"],
            "band_description": score_result["band_description"],
            "mandatory_score": score_result["mandatory_score"],
            "preferred_score": score_result["preferred_score"],
        })
    results.sort(key=lambda r: -r["score"])
    return results
