"""
modules/resume_feedback.py — Analyze a resume against a job role and provide
actionable improvement suggestions.

Features:
  - Identifies skills the user claims but hasn't put on their resume.
  - Flags vague or weak action verbs in project/experience descriptions.
  - Recommends relevant keywords based on the target role.
  - Suggests stronger, achievement-oriented phrasing.
  - NEVER invents experience, achievements, or skills.
  - All suggestions are presented as drafts requiring user confirmation.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.skill_extractor import get_skill_label
from modules.job_analyzer import get_role_requirements


# ---------------------------------------------------------------------------
# Weak / vague verb patterns (heuristic)
# ---------------------------------------------------------------------------

_WEAK_VERBS = [
    "worked on", "worked with", "helped", "assisted", "did",
    "was responsible for", "responsible for", "involved in",
    "participated in", "contributed to", "part of", "dealt with",
    "handled", "used", "utilized", "utilised",
]

_WEAK_VERB_RE = re.compile(
    r"\b(" + "|".join(re.escape(v) for v in _WEAK_VERBS) + r")\b",
    re.IGNORECASE,
)

# Strong action verbs to suggest instead
_STRONG_VERBS = [
    "Designed", "Developed", "Built", "Implemented", "Engineered",
    "Automated", "Optimized", "Reduced", "Improved", "Delivered",
    "Deployed", "Architected", "Led", "Created", "Analyzed",
    "Integrated", "Migrated", "Refactored", "Tested", "Launched",
]

# Patterns that suggest a missing quantification opportunity
_VAGUE_DESCRIPTION_PATTERNS = [
    re.compile(r"\b(some|various|several|many|a few|a lot of)\b", re.IGNORECASE),
    re.compile(r"\b(good|great|excellent|strong)\s+(understanding|knowledge|familiarity)\b", re.IGNORECASE),
    re.compile(r"\b(etc\.?|and so on|and more)\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Main feedback function
# ---------------------------------------------------------------------------

def generate_resume_feedback(
    resume_text: str,
    extracted_resume_skills: List[str],   # canonical skill_ids found in resume
    confirmed_candidate_skills: List[str],  # canonical skill_ids confirmed by user
    role_id: str,
    user_projects: Optional[List[Dict]] = None,
) -> Dict:
    """
    Generate structured resume improvement feedback.

    Returns:
      {
        missing_from_resume: [
          {skill_id, skill_label, suggestion}
        ],
        keyword_gaps: [str],
        weak_phrase_instances: [
          {original_phrase, suggestion, line_preview}
        ],
        vague_descriptions: [str],
        section_feedback: [str],
        project_suggestions: [str],
        positive_observations: [str],
        overall_feedback: str,
        disclaimer: str,
      }
    """
    req = get_role_requirements(role_id)
    if not req:
        return {
            "missing_from_resume": [],
            "keyword_gaps": [],
            "weak_phrase_instances": [],
            "vague_descriptions": [],
            "section_feedback": ["Role not found; could not generate targeted feedback."],
            "project_suggestions": [],
            "positive_observations": [],
            "overall_feedback": "Could not generate feedback: role not found.",
            "disclaimer": _DISCLAIMER,
        }

    # ── Skills confirmed by user but absent from resume ──────────────────────
    resume_skill_set = set(extracted_resume_skills)
    confirmed_set = set(confirmed_candidate_skills)
    role_required_ids = {s["skill_id"] for s in req["mandatory_skills"] + req["preferred_skills"]}

    missing_from_resume = []
    for sid in confirmed_set - resume_skill_set:
        if sid in role_required_ids:
            suggestion = (
                f"Consider adding '{get_skill_label(sid)}' to your Skills section "
                f"if you have used it in a project or course. "
                "Only include it if you can discuss it confidently in an interview."
            )
            missing_from_resume.append({
                "skill_id": sid,
                "skill_label": get_skill_label(sid),
                "suggestion": suggestion,
            })

    # ── Keyword gaps relative to role ────────────────────────────────────────
    # High-weight role skills not mentioned anywhere in the resume text
    resume_lower = resume_text.lower()
    keyword_gaps = []
    for skill_entry in req["mandatory_skills"]:
        sid = skill_entry["skill_id"]
        label = get_skill_label(sid)
        if label.lower() not in resume_lower and sid not in resume_skill_set:
            keyword_gaps.append(label)

    # ── Weak verb detection ───────────────────────────────────────────────────
    weak_phrases = []
    for line in resume_text.splitlines():
        for match in _WEAK_VERB_RE.finditer(line):
            strong_suggestion = _suggest_strong_verb(line, match.group(0))
            weak_phrases.append({
                "original_phrase": match.group(0),
                "suggestion": strong_suggestion,
                "line_preview": line.strip()[:120],
            })

    # ── Vague description detection ───────────────────────────────────────────
    vague_lines = []
    for line in resume_text.splitlines():
        for pattern in _VAGUE_DESCRIPTION_PATTERNS:
            if pattern.search(line):
                vague_lines.append(
                    f"'{line.strip()[:100]}' — consider replacing vague qualifiers "
                    "with specific metrics or outcomes."
                )
                break  # one warning per line

    # ── Section-level structural feedback ────────────────────────────────────
    section_feedback = _check_sections(resume_text)

    # ── Project suggestions ───────────────────────────────────────────────────
    project_suggestions = _suggest_projects(req, confirmed_candidate_skills)

    # ── Positive observations ─────────────────────────────────────────────────
    positive_observations = []
    high_weight_matched = [
        s for s in req["mandatory_skills"]
        if s["skill_id"] in resume_skill_set and s["weight"] >= 0.8
    ]
    if high_weight_matched:
        labels = ", ".join(get_skill_label(s["skill_id"]) for s in high_weight_matched[:4])
        positive_observations.append(
            f"Your resume mentions high-importance skills: {labels}. "
            "These are strong signals for recruiters."
        )

    if not vague_lines and not weak_phrases:
        positive_observations.append(
            "The resume text does not contain obvious weak verbs or vague qualifiers "
            "in the sections analysed."
        )

    # ── Overall summary ───────────────────────────────────────────────────────
    issues = len(missing_from_resume) + len(weak_phrases) + len(vague_lines)
    if issues == 0:
        overall = (
            "Your resume looks strong against the analysed criteria. "
            "Review the keyword gap list and ensure all relevant projects are included."
        )
    elif issues <= 3:
        overall = (
            f"{issues} improvement area(s) identified. "
            "Address the missing-from-resume skills and weak phrases first."
        )
    else:
        overall = (
            f"{issues} improvement areas identified across your resume. "
            "Work through the suggestions below; start with missing keywords and weak action verbs."
        )

    return {
        "missing_from_resume": missing_from_resume,
        "keyword_gaps": keyword_gaps[:10],   # cap to top 10
        "weak_phrase_instances": weak_phrases[:10],
        "vague_descriptions": vague_lines[:10],
        "section_feedback": section_feedback,
        "project_suggestions": project_suggestions,
        "positive_observations": positive_observations,
        "overall_feedback": overall,
        "disclaimer": _DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _suggest_strong_verb(line: str, weak: str) -> str:
    """Suggest a strong verb as a replacement hint (not a full rewrite)."""
    line_lower = line.lower()
    # Pick the best-fit strong verb based on keywords in the surrounding line
    if any(k in line_lower for k in ["build", "develop", "create", "write", "code"]):
        strong = "Developed"
    elif any(k in line_lower for k in ["test", "debug", "fix"]):
        strong = "Tested"
    elif any(k in line_lower for k in ["deploy", "run", "launch", "release"]):
        strong = "Deployed"
    elif any(k in line_lower for k in ["design", "plan", "architect"]):
        strong = "Designed"
    elif any(k in line_lower for k in ["analys", "study", "research", "investigat"]):
        strong = "Analyzed"
    elif any(k in line_lower for k in ["improve", "optimis", "optimiz", "reduc"]):
        strong = "Optimized"
    else:
        strong = "Implemented"
    return (
        f"Replace '{weak}' with a stronger action verb (e.g. '{strong}'). "
        "Quantify the outcome where possible (e.g. 'reduced loading time by 30%')."
    )


def _check_sections(resume_text: str) -> List[str]:
    """Identify potentially missing or thin resume sections."""
    text_lower = resume_text.lower()
    feedback = []

    # Section existence checks
    if not any(kw in text_lower for kw in ["project", "portfolio"]):
        feedback.append(
            "No Projects section detected. Adding 1–2 relevant projects significantly "
            "strengthens a student or entry-level resume."
        )
    if not any(kw in text_lower for kw in ["certif", "course", "training"]):
        feedback.append(
            "No Certifications/Courses section detected. "
            "Even free online certificates (Coursera, IBM SkillsBuild) are worth including."
        )
    if not any(kw in text_lower for kw in ["skill", "technolog", "language", "framework"]):
        feedback.append(
            "No dedicated Skills section detected. "
            "A concise technical skills section makes your resume easier to scan."
        )
    if len(resume_text.split()) < 150:
        feedback.append(
            "The resume appears quite short. "
            "Consider expanding project descriptions with outcomes and technologies used."
        )
    return feedback


def _suggest_projects(req: Dict, candidate_skills: List[str]) -> List[str]:
    """Suggest relevant project ideas based on the role and candidate's existing skills."""
    suggestions = []
    role_title = req.get("title", "this role")
    candidate_set = set(candidate_skills)

    # Build suggestions from candidate's confirmed skills that match the role
    matched_mandatory = [
        s["skill_id"] for s in req.get("mandatory_skills", [])
        if s["skill_id"] in candidate_set
    ]

    if len(matched_mandatory) >= 2:
        combined = " and ".join(get_skill_label(s) for s in matched_mandatory[:3])
        suggestions.append(
            f"Build an end-to-end project using {combined} that solves a real problem "
            f"relevant to a {role_title}. Host it on GitHub with a clear README."
        )

    if "python" in candidate_set and "rest_api" in candidate_set:
        suggestions.append(
            "Create a REST API project with authentication, database integration, "
            "and at least 80% test coverage. Document the API using Swagger/OpenAPI."
        )

    if "machine_learning" in candidate_set or "scikit_learn" in candidate_set:
        suggestions.append(
            "Complete a Kaggle competition (even just the titanic beginner challenge) "
            "and write a clear notebook explaining your feature engineering and model choices."
        )

    if not suggestions:
        suggestions.append(
            f"Develop a personal project that demonstrates at least three of the core "
            f"technical skills required for a {role_title}. "
            "Focus on quality and documentation over quantity of features."
        )

    return suggestions[:3]


_DISCLAIMER = (
    "Resume suggestions are heuristic observations based on text analysis. "
    "They are offered as prompts for your own review, NOT as verified assessments. "
    "Do not add skills, achievements, or experience to your resume that you cannot "
    "honestly and accurately substantiate."
)
