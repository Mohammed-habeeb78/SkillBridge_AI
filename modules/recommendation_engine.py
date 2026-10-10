"""
modules/recommendation_engine.py — Generate personalized learning roadmaps.

Ranking logic:
  1. Mandatory missing skills are always ranked before preferred missing skills.
  2. Within each tier, skills are ranked by weight (importance) descending.
  3. Skills with partial matches are included at lower priority than fully
     missing skills of the same tier and weight, to address foundations first.
  4. The roadmap is divided into four stages:
       Stage 1 — Essential foundations (mandatory, weight >= 0.8)
       Stage 2 — Role-specific technical skills (remaining mandatory)
       Stage 3 — Preferred / complementary skills
       Stage 4 — Practical project and interview preparation

Design notes:
  - Resources are sourced from data/learning_resources.json.
  - If no resource is available for a skill, a generic search suggestion is
    provided rather than inventing a URL.
  - Mini-project suggestions are also drawn from the same file.
  - The roadmap engine does NOT recommend every missing skill at once;
    it caps recommendations at 10 skills per stage to avoid overwhelming users.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LEARNING_RESOURCES_FILE
from modules.skill_extractor import get_skill_label


# ---------------------------------------------------------------------------
# Resource loading
# ---------------------------------------------------------------------------

_resources_cache: Optional[Dict] = None


def _load_resources() -> Dict:
    global _resources_cache
    if _resources_cache is not None:
        return _resources_cache
    with open(LEARNING_RESOURCES_FILE, "r", encoding="utf-8") as f:
        _resources_cache = json.load(f)
    return _resources_cache


def get_resources_for_skill(skill_id: str) -> List[Dict]:
    data = _load_resources()
    return data.get("resources", {}).get(skill_id, [])


def get_mini_project(skill_id: str) -> Optional[str]:
    data = _load_resources()
    return data.get("mini_projects", {}).get(skill_id)


# ---------------------------------------------------------------------------
# Duration estimation
# ---------------------------------------------------------------------------

# Default study durations (hours) per skill category when no resource entry exists
_CATEGORY_DURATIONS: Dict[str, int] = {
    "programming_language": 40,
    "machine_learning": 60,
    "data_science": 20,
    "web_frontend": 25,
    "web_backend": 20,
    "devops": 15,
    "cloud": 10,
    "cybersecurity": 20,
    "database": 12,
    "methodology": 5,
    "other": 10,
}


def estimate_duration(skill_id: str) -> int:
    """Estimate hours to reach working proficiency for a skill."""
    resources = get_resources_for_skill(skill_id)
    if resources:
        # Sum the durations of the first 2 resources as a representative estimate
        return sum(r.get("duration_hours", 10) for r in resources[:2])
    # Fall back to category-based estimate
    from modules.skill_extractor import get_skill_category
    cat = get_skill_category(skill_id)
    return _CATEGORY_DURATIONS.get(cat, 10)


# ---------------------------------------------------------------------------
# Learning dependency ordering
# ---------------------------------------------------------------------------

# Skills that should be learned BEFORE the given skill where possible.
# This prevents recommending advanced topics before their foundations.
PREREQUISITES: Dict[str, List[str]] = {
    "pandas": ["python"],
    "numpy": ["python"],
    "scikit_learn": ["python", "pandas", "numpy", "statistics"],
    "machine_learning": ["python", "statistics", "numpy"],
    "deep_learning": ["machine_learning", "numpy", "python"],
    "natural_language_processing": ["python", "machine_learning"],
    "feature_engineering": ["pandas", "scikit_learn"],
    "model_evaluation": ["scikit_learn", "machine_learning"],
    "react": ["javascript", "html", "css"],
    "typescript": ["javascript"],
    "docker": ["linux_basics"],
    "kubernetes": ["docker", "linux_basics"],
    "ci_cd": ["git", "docker"],
    "infrastructure_as_code": ["cloud_basics", "linux_basics"],
    "algorithms": ["data_structures"],
    "design_patterns": ["object_oriented_programming"],
    "vulnerability_assessment": ["security_fundamentals", "networking_fundamentals"],
    "ethical_hacking_basics": ["security_fundamentals", "linux_basics"],
    "cloud_basics": ["linux_basics", "networking_fundamentals"],
}


def _has_unmet_prerequisites(skill_id: str, candidate_skill_ids: List[str]) -> List[str]:
    """Return list of prerequisite skill_ids that the candidate does not yet have."""
    prereqs = PREREQUISITES.get(skill_id, [])
    return [p for p in prereqs if p not in candidate_skill_ids]


# ---------------------------------------------------------------------------
# Stage assignment
# ---------------------------------------------------------------------------

def _assign_stage(skill_id: str, weight: float, mandatory: bool) -> int:
    if mandatory and weight >= 0.8:
        return 1   # Essential foundations
    elif mandatory:
        return 2   # Role-specific mandatory
    elif weight >= 0.65:
        return 3   # High-value preferred
    else:
        return 3   # All preferred go to stage 3


# ---------------------------------------------------------------------------
# Roadmap generation
# ---------------------------------------------------------------------------

def generate_roadmap(
    gap_analysis: Dict,
    candidate_skill_ids: List[str],
    max_skills_per_stage: int = 8,
) -> Dict:
    """
    Build a staged learning roadmap from a gap analysis result.

    Returns:
      {
        stages: [
          {
            stage: int,
            label: str,
            description: str,
            tasks: [
              {
                skill_id, skill_label, priority, stage,
                reason, resources, mini_project,
                estimated_hours, match_type,
                unmet_prerequisites: [skill_id],
              }
            ]
          }
        ],
        total_estimated_hours: int,
        total_tasks: int,
        summary: str,
      }
    """
    # Collect all skills that need improvement (missing + partial)
    raw_tasks = []

    for s in gap_analysis.get("mandatory_missing", []):
        raw_tasks.append({**s, "tier": "mandatory", "match_type": "missing"})
    for s in gap_analysis.get("mandatory_partial", []):
        raw_tasks.append({**s, "tier": "mandatory", "match_type": "partial"})
    for s in gap_analysis.get("preferred_missing", []):
        raw_tasks.append({**s, "tier": "preferred", "match_type": "missing"})
    for s in gap_analysis.get("preferred_partial", []):
        raw_tasks.append({**s, "tier": "preferred", "match_type": "partial"})

    if not raw_tasks:
        return {
            "stages": [],
            "total_estimated_hours": 0,
            "total_tasks": 0,
            "summary": (
                "Your skills profile already covers all assessed requirements for this role. "
                "Focus on practical projects and interview preparation."
            ),
        }

    # Rank: mandatory first, then by weight, then partial after missing of same weight
    def rank_key(t):
        tier_rank = 0 if t["tier"] == "mandatory" else 1
        match_rank = 0 if t["match_type"] == "missing" else 1
        return (tier_rank, match_rank, -t["weight"])

    raw_tasks.sort(key=rank_key)

    # Build task records with stage assignment and resource lookup
    all_tasks = []
    for priority, task in enumerate(raw_tasks, start=1):
        sid = task["skill_id"]
        stage = _assign_stage(sid, task["weight"], task["tier"] == "mandatory")
        resources = get_resources_for_skill(sid)
        mini_proj = get_mini_project(sid)
        unmet_prereqs = _has_unmet_prerequisites(sid, candidate_skill_ids)
        hours = estimate_duration(sid)

        reason = task.get("reason", "")
        if task["match_type"] == "partial":
            partial_note = task.get("explanation", "")
            reason = f"{reason} (Partial knowledge detected: {partial_note})" if reason else partial_note

        all_tasks.append({
            "skill_id": sid,
            "skill_label": get_skill_label(sid),
            "priority": priority,
            "stage": stage,
            "reason": reason,
            "resources": resources[:2],   # top 2 resources
            "mini_project": mini_proj or f"Build a small project that uses {get_skill_label(sid)}.",
            "estimated_hours": hours,
            "match_type": task["match_type"],
            "mandatory": task["tier"] == "mandatory",
            "unmet_prerequisites": unmet_prereqs,
        })

    # Stage 4 always exists: practical project + interview prep
    stage4_tasks = _build_stage4_tasks(gap_analysis)

    # Group tasks by stage (cap per stage to avoid overwhelm)
    stages_dict: Dict[int, List[Dict]] = {1: [], 2: [], 3: [], 4: stage4_tasks}
    for task in all_tasks:
        s = task["stage"]
        if len(stages_dict[s]) < max_skills_per_stage:
            stages_dict[s].append(task)

    stage_labels = {
        1: ("Stage 1: Essential Foundations",
            "Master these high-priority mandatory skills before progressing. "
            "They form the foundation for all other learning in this role."),
        2: ("Stage 2: Role-Specific Technical Skills",
            "Build the remaining mandatory technical competencies required for this role."),
        3: ("Stage 3: Preferred & Complementary Skills",
            "Add these preferred skills to strengthen your profile and differentiate yourself."),
        4: ("Stage 4: Projects, Portfolio & Interview Preparation",
            "Apply what you have learned through practical projects and prepare for interviews."),
    }

    stages = []
    for s_num in [1, 2, 3, 4]:
        tasks = stages_dict[s_num]
        if not tasks:
            continue
        label, description = stage_labels[s_num]
        stages.append({
            "stage": s_num,
            "label": label,
            "description": description,
            "tasks": tasks,
        })

    total_hours = sum(t["estimated_hours"] for t in all_tasks)
    total_tasks = sum(len(s["tasks"]) for s in stages)

    summary = (
        f"Your roadmap has {total_tasks} learning tasks across {len(stages)} stages, "
        f"estimated at approximately {total_hours} study hours in total. "
        f"Focus on Stage 1 skills first — they have the highest impact on your readiness score."
    )

    return {
        "stages": stages,
        "total_estimated_hours": total_hours,
        "total_tasks": total_tasks,
        "summary": summary,
        "all_tasks": all_tasks,   # flat list, useful for DB storage
    }


def _build_stage4_tasks(gap_analysis: Dict) -> List[Dict]:
    """Generate a fixed set of Stage 4 project and interview prep tasks."""
    role_title = gap_analysis.get("role_title", "your target role")
    return [
        {
            "skill_id": "portfolio_project",
            "skill_label": "Build a Portfolio Project",
            "priority": 90,
            "stage": 4,
            "reason": (
                f"A completed project demonstrating the core skills of a {role_title} "
                "is the most effective way to demonstrate practical ability to employers."
            ),
            "resources": [
                {
                    "title": "GitHub Portfolio Guide",
                    "url": "https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-github-profile",
                    "platform": "GitHub",
                    "type": "documentation",
                    "duration_hours": 1,
                }
            ],
            "mini_project": (
                f"Build a complete {role_title} portfolio project end-to-end "
                "and host it on GitHub with a clear README."
            ),
            "estimated_hours": 20,
            "match_type": "stage4",
            "mandatory": False,
            "unmet_prerequisites": [],
        },
        {
            "skill_id": "resume_keyword_optimisation",
            "skill_label": "Optimise Your Resume",
            "priority": 91,
            "stage": 4,
            "reason": (
                "Ensuring your resume accurately reflects your skills using "
                "terminology that matches job descriptions improves visibility "
                "in applicant tracking systems."
            ),
            "resources": [
                {
                    "title": "Resume Checklist – Harvard OCS",
                    "url": "https://ocs.fas.harvard.edu/resumes-cvs",
                    "platform": "Harvard OCS",
                    "type": "reference",
                    "duration_hours": 1,
                }
            ],
            "mini_project": (
                "Revise your resume using the improvement suggestions in SkillBridge AI, "
                "then ask a peer or mentor to review it."
            ),
            "estimated_hours": 3,
            "match_type": "stage4",
            "mandatory": False,
            "unmet_prerequisites": [],
        },
        {
            "skill_id": "interview_preparation",
            "skill_label": "Interview Preparation",
            "priority": 92,
            "stage": 4,
            "reason": (
                "Technical and behavioural interview preparation converts your skills "
                "into job offers."
            ),
            "resources": [
                {
                    "title": "LeetCode Interview Problems",
                    "url": "https://leetcode.com/problemset/",
                    "platform": "LeetCode",
                    "type": "practice",
                    "duration_hours": 20,
                },
                {
                    "title": "STAR Method for Behavioural Questions",
                    "url": "https://www.themuse.com/advice/star-interview-method",
                    "platform": "The Muse",
                    "type": "reference",
                    "duration_hours": 1,
                },
            ],
            "mini_project": (
                f"Complete 10 LeetCode problems relevant to {role_title} interviews "
                "and practise answering 5 behavioural questions using the STAR method."
            ),
            "estimated_hours": 15,
            "match_type": "stage4",
            "mandatory": False,
            "unmet_prerequisites": [],
        },
    ]
