"""
modules/skill_extractor.py — Identify and normalize skills from free text.

Approach (rule-based with TF-IDF support):
  1. Load the canonical skills dictionary (data/skills_dictionary.json).
  2. Build a lookup table: alias (lowercased) → canonical skill_id.
  3. Tokenize and scan the input text for alias matches (exact and phrase).
  4. Mark each detected skill as 'claimed' (not independently verified).
  5. Optionally rank skills mentioned in section context (skills section
     carries higher confidence than a passing mention in a summary).

This module intentionally does NOT use word-embedding similarity to avoid
treating distinct technologies (e.g. Python vs Java) as equivalent.
Explicit alias rules are used for normalization instead.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional, Set, Tuple

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SKILLS_DICT_FILE


# ---------------------------------------------------------------------------
# Dictionary loading & alias table construction
# ---------------------------------------------------------------------------

_alias_table: Optional[Dict[str, str]] = None   # alias → skill_id
_skill_meta: Optional[Dict[str, Dict]] = None   # skill_id → {label, category, ...}


def _load_dictionary() -> None:
    global _alias_table, _skill_meta
    if _alias_table is not None:
        return  # already loaded

    with open(SKILLS_DICT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    _alias_table = {}
    _skill_meta = {}

    for skill_id, meta in data["skills"].items():
        _skill_meta[skill_id] = meta
        # The canonical id itself is an alias
        _alias_table[skill_id.lower().replace("_", " ")] = skill_id
        _alias_table[skill_id.lower()] = skill_id
        # The label
        _alias_table[meta["label"].lower()] = skill_id
        # All listed aliases
        for alias in meta.get("aliases", []):
            _alias_table[alias.lower()] = skill_id


def get_skill_label(skill_id: str) -> str:
    """Return the human-readable label for a canonical skill id."""
    _load_dictionary()
    return _skill_meta.get(skill_id, {}).get("label", skill_id.replace("_", " ").title())


def get_skill_category(skill_id: str) -> str:
    _load_dictionary()
    return _skill_meta.get(skill_id, {}).get("category", "other")


def normalize_skill_name(raw: str) -> Optional[str]:
    """
    Map a raw skill string to its canonical skill_id.
    Returns None if no match is found.
    """
    _load_dictionary()
    key = raw.lower().strip()
    return _alias_table.get(key)


def list_all_skills() -> List[Dict]:
    """Return all skills as [{id, label, category}]."""
    _load_dictionary()
    return [
        {"id": sid, "label": meta["label"], "category": meta["category"]}
        for sid, meta in _skill_meta.items()
    ]


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

def extract_skills_from_text(
    text: str,
    section_context: Optional[str] = None
) -> List[Dict]:
    """
    Scan *text* for all known skill aliases.

    Args:
        text: Any free text (resume section, job description, etc.)
        section_context: Optional hint about which resume section this text
            came from ("skills", "experience", "projects", etc.).
            Skills found in a dedicated skills section are given a higher
            confidence label.

    Returns:
        List of dicts:
          {
            skill_id: str,
            skill_label: str,
            category: str,
            confidence: str,   # "high" | "medium" | "low"
            mentions: int,     # how many times found in text
            source: "resume"
          }
        Sorted by mention count descending, then label.
    """
    _load_dictionary()
    text_lower = text.lower()

    # We scan from longest alias to shortest to avoid short aliases masking longer ones.
    sorted_aliases = sorted(_alias_table.keys(), key=len, reverse=True)

    found: Dict[str, int] = {}  # skill_id → mention count

    # We'll mark consumed spans to avoid double-counting
    consumed: List[Tuple[int, int]] = []

    for alias in sorted_aliases:
        # Use word-boundary aware search.
        # The lookbehind/lookahead excludes any alphanumeric char plus common
        # tech punctuation so that e.g. "java" does NOT match inside "javascript".
        pattern = r"(?<![a-z0-9+#./_-])" + re.escape(alias) + r"(?![a-z0-9+#./_-])"
        for m in re.finditer(pattern, text_lower):
            start, end = m.start(), m.end()
            # Skip if this span overlaps an already-consumed match
            if any(s <= start < e or s < end <= e for s, e in consumed):
                continue
            skill_id = _alias_table[alias]
            consumed.append((start, end))
            found[skill_id] = found.get(skill_id, 0) + 1

    if not found:
        return []

    # Assign confidence based on section context and mention count
    high_confidence_sections = {"skills", "certifications"}
    results = []
    for skill_id, count in found.items():
        if section_context and section_context.lower() in high_confidence_sections:
            confidence = "high"
        elif count >= 2:
            confidence = "high"
        else:
            confidence = "medium"

        results.append({
            "skill_id": skill_id,
            "skill_label": get_skill_label(skill_id),
            "category": get_skill_category(skill_id),
            "confidence": confidence,
            "mentions": count,
            "source": "resume",
        })

    results.sort(key=lambda x: (-x["mentions"], x["skill_label"]))
    return results


def extract_skills_from_sections(sections: Dict[str, str]) -> List[Dict]:
    """
    Extract skills from a dict of {section_name: text} as returned by
    resume_parser.detect_sections().

    Merges results across sections, preferring higher confidence and
    higher mention count.
    """
    combined: Dict[str, Dict] = {}

    for section_name, section_text in sections.items():
        if not section_text.strip():
            continue
        skills = extract_skills_from_text(section_text, section_context=section_name)
        for skill in skills:
            sid = skill["skill_id"]
            if sid not in combined:
                combined[sid] = skill.copy()
            else:
                # Merge: accumulate mentions, keep highest confidence
                combined[sid]["mentions"] += skill["mentions"]
                if skill["confidence"] == "high":
                    combined[sid]["confidence"] = "high"

    result = list(combined.values())
    result.sort(key=lambda x: (-x["mentions"], x["skill_label"]))
    return result


def extract_skills_from_resume(
    resume_text: str,
    sections: Optional[Dict[str, str]] = None
) -> List[Dict]:
    """
    High-level entry point: extract skills from a full resume text,
    optionally using pre-detected sections for better confidence.
    """
    if sections:
        return extract_skills_from_sections(sections)
    # Fall back to scanning the whole text with no section context
    return extract_skills_from_text(resume_text, section_context=None)


def extract_skills_from_jd(jd_text: str) -> List[Dict]:
    """
    Extract required skills from a job description.
    Returns the same format as extract_skills_from_text, with source='jd'.
    """
    skills = extract_skills_from_text(jd_text, section_context=None)
    for s in skills:
        s["source"] = "jd"
    return skills


# ---------------------------------------------------------------------------
# Skill list normalization (for manually entered skill strings)
# ---------------------------------------------------------------------------

def normalize_skill_list(raw_skills: List[str]) -> List[Dict]:
    """
    Take a list of user-entered skill strings and normalize each to a
    canonical skill if possible, otherwise keep it as an 'unrecognized' entry.

    Returns list of {skill_id, skill_label, recognized: bool, original: str}.
    """
    _load_dictionary()
    result = []
    for raw in raw_skills:
        canonical = normalize_skill_name(raw.strip())
        if canonical:
            result.append({
                "skill_id": canonical,
                "skill_label": get_skill_label(canonical),
                "recognized": True,
                "original": raw,
            })
        else:
            # Keep unrecognized skills as-is so the user doesn't lose information
            result.append({
                "skill_id": _to_snake(raw),
                "skill_label": raw.strip().title(),
                "recognized": False,
                "original": raw,
            })
    return result


def _to_snake(s: str) -> str:
    """Convert arbitrary text to a snake_case identifier."""
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


# ---------------------------------------------------------------------------
# Quiz-based proficiency helpers
# ---------------------------------------------------------------------------

# A small, curated set of multiple-choice questions per skill.
# Stored here so no network access is required.
QUIZ_QUESTIONS: Dict[str, List[Dict]] = {
    "python": [
        {
            "q": "What is the output of: print(type([]))?",
            "options": ["<class 'list'>", "<class 'tuple'>", "<class 'array'>", "<class 'dict'>"],
            "answer": 0,
            "explanation": "[] creates a list object; type() returns its class.",
        },
        {
            "q": "Which keyword is used to define a generator function in Python?",
            "options": ["return", "yield", "async", "generate"],
            "answer": 1,
            "explanation": "yield turns a function into a generator.",
        },
        {
            "q": "What does the 'with' statement provide in Python?",
            "options": [
                "Loop control",
                "Context management (auto cleanup of resources)",
                "Exception chaining",
                "Module importing",
            ],
            "answer": 1,
            "explanation": "with invokes a context manager's __enter__ and __exit__ methods.",
        },
    ],
    "sql": [
        {
            "q": "Which SQL clause filters rows AFTER grouping?",
            "options": ["WHERE", "HAVING", "FILTER", "ON"],
            "answer": 1,
            "explanation": "HAVING filters the results of GROUP BY; WHERE filters before grouping.",
        },
        {
            "q": "What is the difference between INNER JOIN and LEFT JOIN?",
            "options": [
                "No difference",
                "INNER JOIN returns only matching rows; LEFT JOIN returns all left-table rows",
                "LEFT JOIN returns only matching rows; INNER JOIN returns all",
                "INNER JOIN is faster",
            ],
            "answer": 1,
            "explanation": "LEFT JOIN preserves all rows from the left table even when no match exists.",
        },
        {
            "q": "Which keyword removes duplicate rows from a SELECT result?",
            "options": ["UNIQUE", "DISTINCT", "FILTER", "GROUP BY"],
            "answer": 1,
            "explanation": "SELECT DISTINCT eliminates duplicate rows.",
        },
    ],
    "machine_learning": [
        {
            "q": "What does overfitting mean in a machine learning model?",
            "options": [
                "Model is too simple to learn the data",
                "Model memorises training data but fails to generalise",
                "Model was trained on too little data",
                "Model has too few parameters",
            ],
            "answer": 1,
            "explanation": "Overfitting occurs when a model learns noise in training data and loses generalization.",
        },
        {
            "q": "Which metric is most appropriate for an imbalanced classification problem?",
            "options": ["Accuracy", "F1-Score", "Mean Squared Error", "R²"],
            "answer": 1,
            "explanation": "F1-Score balances precision and recall, important when class distribution is skewed.",
        },
        {
            "q": "What is the purpose of cross-validation?",
            "options": [
                "Speed up model training",
                "Estimate model performance on unseen data using multiple train/test splits",
                "Increase the size of the dataset",
                "Prevent the model from using all features",
            ],
            "answer": 1,
            "explanation": "Cross-validation provides a more reliable performance estimate than a single hold-out split.",
        },
    ],
    "git": [
        {
            "q": "What does 'git rebase' do?",
            "options": [
                "Merges two branches with a merge commit",
                "Moves or replays commits on top of another base commit",
                "Reverts the last commit",
                "Creates a new branch",
            ],
            "answer": 1,
            "explanation": "rebase re-applies commits on top of the target branch, creating a linear history.",
        },
        {
            "q": "Which command stages all modified and new files for a commit?",
            "options": ["git commit -a", "git add .", "git push", "git stage --all"],
            "answer": 1,
            "explanation": "git add . stages all changes in the current directory.",
        },
        {
            "q": "What is a 'detached HEAD' state in Git?",
            "options": [
                "The HEAD pointer is missing",
                "HEAD points to a specific commit instead of a branch",
                "The repository is corrupted",
                "A merge conflict is unresolved",
            ],
            "answer": 1,
            "explanation": "Detached HEAD occurs when you check out a commit directly rather than a branch name.",
        },
    ],
    "javascript": [
        {
            "q": "What is the result of: typeof null?",
            "options": ["'null'", "'object'", "'undefined'", "'boolean'"],
            "answer": 1,
            "explanation": "typeof null === 'object' is a known JavaScript quirk inherited from its first version.",
        },
        {
            "q": "What does the '===' operator check?",
            "options": [
                "Value equality with type coercion",
                "Strict equality: value AND type",
                "Reference equality only",
                "Assignment",
            ],
            "answer": 1,
            "explanation": "=== checks both value and type; == performs type coercion first.",
        },
        {
            "q": "What is a Promise used for in JavaScript?",
            "options": [
                "Synchronous computations",
                "Representing the eventual result of an asynchronous operation",
                "Declaring constants",
                "Binding event handlers",
            ],
            "answer": 1,
            "explanation": "Promises model async operations with .then()/.catch() or async/await.",
        },
    ],
    "data_structures": [
        {
            "q": "What is the time complexity of searching an unsorted array of n elements?",
            "options": ["O(1)", "O(log n)", "O(n)", "O(n²)"],
            "answer": 2,
            "explanation": "Without sorting, you must inspect each element: O(n) linear search.",
        },
        {
            "q": "Which data structure follows LIFO (Last In, First Out)?",
            "options": ["Queue", "Stack", "Linked List", "Hash Table"],
            "answer": 1,
            "explanation": "A stack processes the most recently added element first.",
        },
        {
            "q": "In a hash table with a good hash function, what is the average case complexity for lookup?",
            "options": ["O(n)", "O(log n)", "O(1)", "O(n log n)"],
            "answer": 2,
            "explanation": "Hash tables provide O(1) average lookup by computing the key's bucket address directly.",
        },
    ],
}


def get_quiz_for_skill(skill_id: str) -> Optional[List[Dict]]:
    """Return quiz questions for a skill if available, else None."""
    return QUIZ_QUESTIONS.get(skill_id)


def score_quiz(skill_id: str, answers: List[int]) -> Dict:
    """
    Score a quiz attempt.

    Args:
        skill_id: canonical skill id
        answers: list of 0-based option indices chosen by the user

    Returns:
        {score, max_score, percentage, passed, detail: [{q, correct, user_answer, explanation}]}
    """
    questions = QUIZ_QUESTIONS.get(skill_id, [])
    if not questions:
        return {"score": 0, "max_score": 0, "percentage": 0.0, "passed": False, "detail": []}

    score = 0
    detail = []
    for i, q in enumerate(questions):
        user_ans = answers[i] if i < len(answers) else -1
        correct = user_ans == q["answer"]
        if correct:
            score += 1
        detail.append({
            "question": q["q"],
            "correct": correct,
            "user_answer": q["options"][user_ans] if 0 <= user_ans < len(q["options"]) else "Not answered",
            "correct_answer": q["options"][q["answer"]],
            "explanation": q["explanation"],
        })

    max_score = len(questions)
    percentage = round(score / max_score * 100, 1) if max_score else 0.0
    # Pass threshold: 67% (2/3 correct)
    passed = percentage >= 66.7

    return {
        "score": score,
        "max_score": max_score,
        "percentage": percentage,
        "passed": passed,
        "detail": detail,
    }
