"""
modules/job_analyzer.py — Load and analyze job role requirements.

Responsibilities:
  - Load job role definitions from data/job_roles.json.
  - Return structured requirement sets for a given role.
  - Extract requirements from a user-pasted job description using
    skill_extractor.extract_skills_from_jd().
  - Distinguish mandatory skills from preferred skills.
  - Provide role comparison data.

Design notes:
  - Job descriptions in the dataset are labeled as representative examples,
    NOT current verified vacancies.
  - User-pasted JD parsing is a best-effort NLP extraction and may miss
    skills stated in non-standard phrasing.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional, Set, Tuple

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import JOB_ROLES_FILE
from modules.skill_extractor import (
    extract_skills_from_jd,
    get_skill_label,
    normalize_skill_name,
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

_roles_cache: Optional[Dict[str, Dict]] = None   # role_id → role dict


def _load_roles() -> None:
    global _roles_cache
    if _roles_cache is not None:
        return
    with open(JOB_ROLES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    _roles_cache = {r["id"]: r for r in data["roles"]}


def get_all_roles() -> List[Dict]:
    """Return all roles as a list, sorted by title."""
    _load_roles()
    return sorted(_roles_cache.values(), key=lambda r: r["title"])


def get_role(role_id: str) -> Optional[Dict]:
    """Return a single role dict or None if not found."""
    _load_roles()
    return _roles_cache.get(role_id)


def get_role_titles() -> List[Tuple[str, str]]:
    """Return [(role_id, title)] sorted by title."""
    return [(r["id"], r["title"]) for r in get_all_roles()]


# ---------------------------------------------------------------------------
# Role requirement extraction
# ---------------------------------------------------------------------------

def get_role_requirements(role_id: str) -> Dict:
    """
    Return the full requirement set for a role.

    Structure:
      {
        role_id: str,
        title: str,
        description: str,
        mandatory_skills: [
          {skill_id, skill_label, weight, reason}
        ],
        preferred_skills: [
          {skill_id, skill_label, weight, reason}
        ],
        soft_skills: [str],
        tools: [str],
        experience_note: str,
        total_mandatory_weight: float,
        total_preferred_weight: float,
      }
    """
    role = get_role(role_id)
    if not role:
        return {}

    mandatory = []
    preferred = []

    for skill_entry in role.get("required_skills", []):
        record = {
            "skill_id": skill_entry["skill"],
            "skill_label": get_skill_label(skill_entry["skill"]),
            "weight": skill_entry["weight"],
            "reason": skill_entry.get("reason", ""),
        }
        if skill_entry.get("mandatory", False):
            mandatory.append(record)
        else:
            preferred.append(record)

    # Sort by weight descending (highest importance first)
    mandatory.sort(key=lambda s: -s["weight"])
    preferred.sort(key=lambda s: -s["weight"])

    return {
        "role_id": role_id,
        "title": role["title"],
        "description": role.get("description", ""),
        "mandatory_skills": mandatory,
        "preferred_skills": preferred,
        "soft_skills": role.get("soft_skills", []),
        "tools": role.get("tools", []),
        "experience_note": role.get("experience_note", ""),
        "total_mandatory_weight": round(sum(s["weight"] for s in mandatory), 4),
        "total_preferred_weight": round(sum(s["weight"] for s in preferred), 4),
    }


def get_all_required_skill_ids(role_id: str) -> List[str]:
    """Return a flat list of all skill_ids (mandatory + preferred) for a role."""
    req = get_role_requirements(role_id)
    if not req:
        return []
    return (
        [s["skill_id"] for s in req["mandatory_skills"]]
        + [s["skill_id"] for s in req["preferred_skills"]]
    )


# ---------------------------------------------------------------------------
# Job description parsing (user-pasted text)
# ---------------------------------------------------------------------------

# Keywords that suggest a skill is required vs. preferred
_REQUIRED_SIGNALS = re.compile(
    r"\b(required|must have|essential|mandatory|must know|you will need|you must)\b",
    re.IGNORECASE,
)
_PREFERRED_SIGNALS = re.compile(
    r"\b(preferred|nice to have|bonus|a plus|desirable|advantage|ideally|good to have)\b",
    re.IGNORECASE,
)


def analyze_job_description(jd_text: str) -> Dict:
    """
    Extract skills and classify them as mandatory or preferred from
    a user-pasted job description.

    Returns:
      {
        extracted_skills: [
          {skill_id, skill_label, category, confidence, mentions, source, classified_as}
        ],
        mandatory_skill_ids: [str],
        preferred_skill_ids: [str],
        unclassified_skill_ids: [str],
        warnings: [str],
      }

    Note: classification is heuristic. The 'classified_as' field reflects
    the best guess; users should review the output.
    """
    warnings = []
    if not jd_text or not jd_text.strip():
        return {
            "extracted_skills": [],
            "mandatory_skill_ids": [],
            "preferred_skill_ids": [],
            "unclassified_skill_ids": [],
            "warnings": ["The job description text is empty."],
        }

    extracted = extract_skills_from_jd(jd_text)

    # Split JD into sentence-level fragments and check for signal words
    # to help classify each skill.
    sentences = re.split(r"[.\n;]", jd_text)

    # Build a map: skill_id → sentences that mention it
    skill_sentences: Dict[str, List[str]] = {s["skill_id"]: [] for s in extracted}
    for sentence in sentences:
        for skill in extracted:
            for alias_phrase in _build_skill_phrases(skill["skill_id"]):
                if re.search(re.escape(alias_phrase), sentence, re.IGNORECASE):
                    skill_sentences[skill["skill_id"]].append(sentence)
                    break

    mandatory_ids = []
    preferred_ids = []
    unclassified_ids = []

    for skill in extracted:
        sid = skill["skill_id"]
        relevant_sentences = skill_sentences.get(sid, [])
        is_required = any(_REQUIRED_SIGNALS.search(s) for s in relevant_sentences)
        is_preferred = any(_PREFERRED_SIGNALS.search(s) for s in relevant_sentences)

        if is_required and not is_preferred:
            skill["classified_as"] = "mandatory"
            mandatory_ids.append(sid)
        elif is_preferred and not is_required:
            skill["classified_as"] = "preferred"
            preferred_ids.append(sid)
        else:
            # Cannot determine; flag as unclassified
            skill["classified_as"] = "unclassified"
            unclassified_ids.append(sid)

    if not extracted:
        warnings.append(
            "No recognized skills were found in the job description. "
            "The description may use non-standard terminology. "
            "You can manually add required skills to the comparison."
        )
    elif not mandatory_ids:
        warnings.append(
            "Could not identify which skills are mandatory vs preferred "
            "from the job description text. All detected skills are marked "
            "as unclassified — please review them."
        )

    return {
        "extracted_skills": extracted,
        "mandatory_skill_ids": mandatory_ids,
        "preferred_skill_ids": preferred_ids,
        "unclassified_skill_ids": unclassified_ids,
        "warnings": warnings,
    }


def _build_skill_phrases(skill_id: str) -> List[str]:
    """
    Return a short list of representative phrases for a skill_id,
    used for sentence-level classification.
    """
    label = get_skill_label(skill_id)
    phrases = [label]
    # Add the snake_case form as a fallback phrase
    phrases.append(skill_id.replace("_", " "))
    return phrases


# ---------------------------------------------------------------------------
# Role comparison
# ---------------------------------------------------------------------------

def compare_roles(role_ids: List[str]) -> Dict:
    """
    Compare multiple roles side by side.

    Returns:
      {
        roles: [role_requirements dict, ...],
        shared_skills: [skill_id, ...],        # skills required by ALL roles
        unique_skills: {role_id: [skill_id]},  # skills unique to each role
        overlap_matrix: {role_id: {role_id: int}},  # count of shared skills
      }
    """
    requirements = {rid: get_role_requirements(rid) for rid in role_ids}
    requirements = {rid: req for rid, req in requirements.items() if req}

    if len(requirements) < 2:
        return {
            "roles": list(requirements.values()),
            "shared_skills": [],
            "unique_skills": {},
            "overlap_matrix": {},
        }

    skill_sets: Dict[str, Set[str]] = {}
    for rid, req in requirements.items():
        all_ids = set(s["skill_id"] for s in req["mandatory_skills"] + req["preferred_skills"])
        skill_sets[rid] = all_ids

    # Skills shared by ALL compared roles
    shared = set.intersection(*skill_sets.values()) if skill_sets else set()

    # Skills unique to each role
    unique: Dict[str, List[str]] = {}
    for rid, skill_set in skill_sets.items():
        others = set.union(*(v for k, v in skill_sets.items() if k != rid))
        unique[rid] = sorted(skill_set - others)

    # Pairwise overlap matrix
    overlap: Dict[str, Dict[str, int]] = {}
    for rid1, set1 in skill_sets.items():
        overlap[rid1] = {}
        for rid2, set2 in skill_sets.items():
            overlap[rid1][rid2] = len(set1 & set2)

    return {
        "roles": list(requirements.values()),
        "shared_skills": sorted(shared),
        "unique_skills": unique,
        "overlap_matrix": overlap,
    }


