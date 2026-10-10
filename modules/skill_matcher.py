"""
modules/skill_matcher.py — Compare candidate skills against job requirements.

Matching approach:
  1. Exact match — candidate has the canonical skill_id in their profile.
  2. Partial match — candidate has a related skill that partially satisfies
     a requirement.  Partial matches are determined by explicit rules only
     (not text similarity) to avoid false equivalence between distinct
     technologies.
  3. No match — skill is absent from the candidate profile.

Partial-match rules are stored as a curated dict rather than computed by
embedding distance, because similar embedding cosine similarity does not
imply technological interchangeability.

Design notes:
  - Returns a MatchResult dataclass-like dict for easy serialization.
  - All weights used in scoring are sourced from the role's skill entries.
  - Explicitly separates absence-from-resume from absence-of-ability.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, Set

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PARTIAL_MATCH_THRESHOLD
from modules.skill_extractor import get_skill_label, get_skill_category


# ---------------------------------------------------------------------------
# Partial-match rules
# ---------------------------------------------------------------------------
# Format: {required_skill_id: [candidate_skill_ids_that_partially_satisfy_it]}
# These represent skills that provide partial but NOT full coverage.
# e.g. knowing pandas partially satisfies a numpy requirement (shared ecosystem)
# but does NOT mean numpy is known.

PARTIAL_MATCH_RULES: Dict[str, List[str]] = {
    # Data manipulation ecosystem
    "numpy": ["pandas", "scikit_learn"],
    "pandas": ["numpy"],
    # ML ecosystem
    "scikit_learn": ["machine_learning", "machine_learning_basics"],
    "machine_learning": ["scikit_learn", "machine_learning_basics", "deep_learning"],
    "deep_learning": ["machine_learning", "natural_language_processing"],
    "feature_engineering": ["pandas", "scikit_learn", "machine_learning"],
    "model_evaluation": ["scikit_learn", "machine_learning"],
    "machine_learning_basics": ["machine_learning", "scikit_learn"],
    # Web
    "rest_api": ["javascript", "python"],          # knowing a language → partial API awareness
    "responsive_design": ["css", "css_frameworks"],
    "css_frameworks": ["css", "responsive_design"],
    "typescript": ["javascript"],                   # JS → partial TS (same ecosystem)
    "authentication_authorization": ["rest_api", "python", "javascript"],
    # DevOps / cloud
    "ci_cd": ["git", "docker"],
    "infrastructure_as_code": ["cloud_basics", "linux_basics"],
    "monitoring_observability": ["cloud_basics", "linux_basics"],
    "kubernetes": ["docker"],
    # Security
    "vulnerability_assessment": ["security_fundamentals", "networking_fundamentals"],
    "incident_response": ["security_fundamentals", "siem_tools"],
    "ethical_hacking_basics": ["security_fundamentals", "linux_basics", "networking_fundamentals"],
    "firewall_configuration": ["networking_fundamentals", "security_fundamentals"],
    # General
    "linux_basics": ["cloud_basics"],              # cloud familiarity → partial Linux awareness
    "algorithms": ["data_structures"],
    "data_structures": ["algorithms"],
    "design_patterns": ["object_oriented_programming"],
    "probability": ["statistics"],
    "statistics": ["probability"],
    "data_cleaning": ["pandas", "feature_engineering"],
    "nosql": ["sql"],                              # SQL knowledge → partial NoSQL awareness
    "caching": ["nosql", "rest_api"],
}

# Skills that are essentially interchangeable for the purpose of satisfying
# a broad requirement (e.g. "a backend framework").
# These are NOT the same technology; a role specifically asking for Python
# is NOT satisfied by Java. Use this only for roles with explicit "OR" intent.
EQUIVALENT_GROUPS: List[Set[str]] = [
    # Any SQL flavour satisfies "sql"  — already handled via alias normalization
    # Any JS framework gives partial React credit
    # (full credit only if react is explicitly in candidate profile)
]


# ---------------------------------------------------------------------------
# Core matching function
# ---------------------------------------------------------------------------

def match_skills(
    candidate_skill_ids: List[str],
    required_skills: List[Dict],   # [{skill_id, weight, mandatory, reason, ...}]
) -> Dict:
    """
    Compare candidate skills against a list of required skills.

    Args:
        candidate_skill_ids: Canonical skill ids confirmed by the candidate.
        required_skills:     List of requirement dicts from job_analyzer.

    Returns:
        {
          matched:   [{skill_id, skill_label, weight, match_type, candidate_proficiency}]
          partial:   [{skill_id, skill_label, weight, matched_by: [skill_ids], explanation}]
          missing:   [{skill_id, skill_label, weight, mandatory, reason}]
          extra:     [{skill_id, skill_label}]   # candidate skills not in requirements
        }
    """
    candidate_set: Set[str] = set(candidate_skill_ids)
    required_ids = {r["skill_id"] for r in required_skills}

    matched = []
    partial = []
    missing = []

    for req in required_skills:
        sid = req["skill_id"]

        if sid in candidate_set:
            # Exact match
            matched.append({
                "skill_id": sid,
                "skill_label": get_skill_label(sid),
                "weight": req["weight"],
                "mandatory": req.get("mandatory", False),
                "match_type": "exact",
                "reason": req.get("reason", ""),
            })
        else:
            # Check partial match
            partial_sources = [
                s for s in PARTIAL_MATCH_RULES.get(sid, [])
                if s in candidate_set
            ]
            if partial_sources:
                explanation = (
                    f"You have {', '.join(get_skill_label(s) for s in partial_sources)}, "
                    f"which demonstrates related knowledge but does not fully satisfy "
                    f"the requirement for {get_skill_label(sid)}."
                )
                partial.append({
                    "skill_id": sid,
                    "skill_label": get_skill_label(sid),
                    "weight": req["weight"],
                    "mandatory": req.get("mandatory", False),
                    "match_type": "partial",
                    "matched_by": partial_sources,
                    "explanation": explanation,
                    "reason": req.get("reason", ""),
                })
            else:
                missing.append({
                    "skill_id": sid,
                    "skill_label": get_skill_label(sid),
                    "weight": req["weight"],
                    "mandatory": req.get("mandatory", False),
                    "match_type": "missing",
                    "reason": req.get("reason", ""),
                })

    # Extra skills the candidate has that are relevant but not in requirements
    extra_ids = candidate_set - required_ids
    extra = [
        {"skill_id": sid, "skill_label": get_skill_label(sid)}
        for sid in sorted(extra_ids)
    ]

    return {
        "matched": sorted(matched, key=lambda x: -x["weight"]),
        "partial": sorted(partial, key=lambda x: -x["weight"]),
        "missing": sorted(missing, key=lambda x: (-x["weight"], not x["mandatory"])),
        "extra": extra,
    }


# ---------------------------------------------------------------------------
# Full gap analysis
# ---------------------------------------------------------------------------

def analyze_skill_gap(
    candidate_skill_ids: List[str],
    role_requirements: Dict,
) -> Dict:
    """
    Perform a full skill-gap analysis for a single role.

    Args:
        candidate_skill_ids: Canonical skill ids from the candidate profile.
        role_requirements:   Dict from job_analyzer.get_role_requirements().

    Returns:
        {
          role_id, role_title,
          mandatory_match, mandatory_partial, mandatory_missing,
          preferred_match, preferred_partial, preferred_missing,
          extra_skills,
          summary: {
            total_required, matched_count, partial_count, missing_count,
            mandatory_matched_count, mandatory_missing_count,
          }
        }
    """
    mandatory_result = match_skills(
        candidate_skill_ids,
        role_requirements.get("mandatory_skills", [])
    )
    preferred_result = match_skills(
        candidate_skill_ids,
        role_requirements.get("preferred_skills", [])
    )

    all_required_ids = {
        s["skill_id"] for s in
        role_requirements.get("mandatory_skills", []) +
        role_requirements.get("preferred_skills", [])
    }
    extra = [
        {"skill_id": sid, "skill_label": get_skill_label(sid)}
        for sid in sorted(set(candidate_skill_ids) - all_required_ids)
    ]

    mand_match = len(mandatory_result["matched"])
    mand_partial = len(mandatory_result["partial"])
    mand_missing = len(mandatory_result["missing"])

    total_required = (
        len(role_requirements.get("mandatory_skills", []))
        + len(role_requirements.get("preferred_skills", []))
    )
    total_matched = (
        len(mandatory_result["matched"]) + len(preferred_result["matched"])
    )
    total_partial = (
        len(mandatory_result["partial"]) + len(preferred_result["partial"])
    )
    total_missing = (
        len(mandatory_result["missing"]) + len(preferred_result["missing"])
    )

    return {
        "role_id": role_requirements.get("role_id", ""),
        "role_title": role_requirements.get("title", ""),
        "mandatory_match": mandatory_result["matched"],
        "mandatory_partial": mandatory_result["partial"],
        "mandatory_missing": mandatory_result["missing"],
        "preferred_match": preferred_result["matched"],
        "preferred_partial": preferred_result["partial"],
        "preferred_missing": preferred_result["missing"],
        "extra_skills": extra,
        "summary": {
            "total_required": total_required,
            "matched_count": total_matched,
            "partial_count": total_partial,
            "missing_count": total_missing,
            "mandatory_matched_count": mand_match,
            "mandatory_partial_count": mand_partial,
            "mandatory_missing_count": mand_missing,
        },
    }


# ---------------------------------------------------------------------------
# Multi-role comparison matching
# ---------------------------------------------------------------------------

def compare_candidate_across_roles(
    candidate_skill_ids: List[str],
    role_requirements_list: List[Dict],
) -> List[Dict]:
    """
    Run analyze_skill_gap for multiple roles and return results sorted
    by total matched skills descending (best-fit roles first).
    """
    results = [
        analyze_skill_gap(candidate_skill_ids, req)
        for req in role_requirements_list
        if req
    ]
    results.sort(
        key=lambda r: -(
            r["summary"]["matched_count"] + 0.5 * r["summary"]["partial_count"]
        )
    )
    return results
