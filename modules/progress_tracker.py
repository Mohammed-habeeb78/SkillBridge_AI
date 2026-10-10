"""
modules/progress_tracker.py — Track and report on a user's roadmap progress.

Responsibilities:
  - Load roadmap tasks from the database and summarise completion.
  - Calculate progress percentages per stage and overall.
  - Mark tasks as in_progress or completed.
  - Determine which skills have been verified via quiz vs. self-reported.
  - Generate a progress report suitable for display.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import db
from modules.skill_extractor import get_skill_label


# ---------------------------------------------------------------------------
# Progress summary
# ---------------------------------------------------------------------------

def get_progress_summary(user_id: int, assessment_id: Optional[int] = None) -> Dict:
    """
    Compute overall and per-stage progress for a user's roadmap.

    Returns:
      {
        total_tasks: int,
        completed_tasks: int,
        in_progress_tasks: int,
        overall_pct: float,
        stages: [
          {stage, label, total, completed, in_progress, pct}
        ],
        completed_skill_ids: [str],
        in_progress_skill_ids: [str],
        pending_skill_ids: [str],
      }
    """
    tasks = db.get_roadmap_tasks(user_id, assessment_id)
    if not tasks:
        return _empty_summary()

    total = len(tasks)
    completed = [t for t in tasks if t["status"] == "completed"]
    in_progress = [t for t in tasks if t["status"] == "in_progress"]
    pending = [t for t in tasks if t["status"] == "pending"]

    overall_pct = round(len(completed) / total * 100, 1) if total else 0.0

    # Per-stage breakdown
    stage_labels = {
        1: "Stage 1: Essential Foundations",
        2: "Stage 2: Role-Specific Skills",
        3: "Stage 3: Preferred Skills",
        4: "Stage 4: Projects & Interview Prep",
    }
    stages_data: Dict[int, Dict] = {}
    for task in tasks:
        s = task["stage"]
        if s not in stages_data:
            stages_data[s] = {"total": 0, "completed": 0, "in_progress": 0}
        stages_data[s]["total"] += 1
        if task["status"] == "completed":
            stages_data[s]["completed"] += 1
        elif task["status"] == "in_progress":
            stages_data[s]["in_progress"] += 1

    stages = []
    for s_num in sorted(stages_data):
        sd = stages_data[s_num]
        pct = round(sd["completed"] / sd["total"] * 100, 1) if sd["total"] else 0.0
        stages.append({
            "stage": s_num,
            "label": stage_labels.get(s_num, f"Stage {s_num}"),
            "total": sd["total"],
            "completed": sd["completed"],
            "in_progress": sd["in_progress"],
            "pct": pct,
        })

    return {
        "total_tasks": total,
        "completed_tasks": len(completed),
        "in_progress_tasks": len(in_progress),
        "overall_pct": overall_pct,
        "stages": stages,
        "completed_skill_ids": [t["skill_id"] for t in completed],
        "in_progress_skill_ids": [t["skill_id"] for t in in_progress],
        "pending_skill_ids": [t["skill_id"] for t in pending],
    }


def _empty_summary() -> Dict:
    return {
        "total_tasks": 0,
        "completed_tasks": 0,
        "in_progress_tasks": 0,
        "overall_pct": 0.0,
        "stages": [],
        "completed_skill_ids": [],
        "in_progress_skill_ids": [],
        "pending_skill_ids": [],
    }


# ---------------------------------------------------------------------------
# Task status updates
# ---------------------------------------------------------------------------

def mark_task(task_id: int, status: str) -> None:
    """Update a single task's status. status: pending | in_progress | completed."""
    if status not in ("pending", "in_progress", "completed"):
        raise ValueError(f"Invalid status: {status}")
    db.update_task_status(task_id, status)


def mark_tasks_bulk(task_ids: List[int], status: str) -> None:
    for tid in task_ids:
        db.update_task_status(tid, status)


# ---------------------------------------------------------------------------
# Historical progress (across assessments)
# ---------------------------------------------------------------------------

def get_assessment_history(user_id: int) -> List[Dict]:
    """
    Return all past assessments for a user with their readiness scores.
    Suitable for plotting a progress timeline.
    """
    assessments = db.get_assessments(user_id)
    history = []
    for a in assessments:
        history.append({
            "assessment_id": a["id"],
            "role_id": a["role_id"],
            "role_title": a["role_title"],
            "readiness_score": a["readiness_score"],
            "created_at": a["created_at"],
            "matched_count": len(a["matched_skills"]),
            "missing_count": len(a["missing_skills"]),
        })
    return history


# ---------------------------------------------------------------------------
# Quiz-based proficiency update
# ---------------------------------------------------------------------------

def apply_quiz_result_to_profile(
    user_id: int,
    skill_id: str,
    passed: bool,
) -> None:
    """
    After a quiz attempt, update the skill proficiency label if the user passed.
    Does NOT downgrade a skill if the quiz is failed — quizzes are supplementary
    evidence, not the sole arbiter of ability.
    """
    skill_label = get_skill_label(skill_id)
    current_skills = {s["skill_id"]: s for s in db.get_user_skills(user_id)}

    if passed:
        # Upgrade from 'claimed' to 'beginner' (quiz-verified)
        current_proficiency = current_skills.get(skill_id, {}).get("proficiency", "claimed")
        if current_proficiency in ("claimed", "beginner"):
            db.upsert_skill(
                user_id, skill_id, skill_label,
                proficiency="beginner", source="assessment"
            )
    # If failed: no change — failure on a basic quiz does not confirm absence of ability.


# ---------------------------------------------------------------------------
# Skill confidence summary for dashboard
# ---------------------------------------------------------------------------

def get_skill_confidence_summary(user_id: int) -> Dict:
    """
    Return skill counts grouped by proficiency level and source.
    """
    skills = db.get_user_skills(user_id)
    by_proficiency: Dict[str, int] = {}
    by_source: Dict[str, int] = {}

    for s in skills:
        p = s.get("proficiency", "claimed")
        src = s.get("source", "manual")
        by_proficiency[p] = by_proficiency.get(p, 0) + 1
        by_source[src] = by_source.get(src, 0) + 1

    return {
        "total": len(skills),
        "by_proficiency": by_proficiency,
        "by_source": by_source,
    }
