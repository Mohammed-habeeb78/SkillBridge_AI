"""
config.py — Application-wide configuration constants.
All paths are resolved relative to this file so the app is portable.
"""
import os

# ── Base directory ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Data files ──────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(BASE_DIR, "data")
JOB_ROLES_FILE = os.path.join(DATA_DIR, "job_roles.json")
SKILLS_DICT_FILE = os.path.join(DATA_DIR, "skills_dictionary.json")
LEARNING_RESOURCES_FILE = os.path.join(DATA_DIR, "learning_resources.json")

# ── Database ─────────────────────────────────────────────────────────────────
DATABASE_DIR = os.path.join(BASE_DIR, "database")
DATABASE_FILE = os.path.join(DATABASE_DIR, "skillbridge.db")

# ── Exports ───────────────────────────────────────────────────────────────────
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")

# ── File upload ───────────────────────────────────────────────────────────────
ALLOWED_RESUME_EXTENSIONS = {".pdf", ".docx"}
MAX_RESUME_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# ── Skill matching ────────────────────────────────────────────────────────────
# Minimum token-overlap ratio to count a partial skill match
PARTIAL_MATCH_THRESHOLD = 0.5

# ── Readiness score ───────────────────────────────────────────────────────────
# Weights applied to the raw weighted-coverage score for mandatory vs. preferred tiers
MANDATORY_TIER_WEIGHT = 1.0
PREFERRED_TIER_WEIGHT = 0.4   # preferred skills contribute less to the overall score

# ── Assessment ────────────────────────────────────────────────────────────────
# Number of questions per skill quiz
QUIZ_QUESTIONS_PER_SKILL = 3

# ── App metadata ─────────────────────────────────────────────────────────────
APP_NAME = "SkillBridge AI"
APP_VERSION = "1.0.0"
SDG_ALIGNMENT = "SDG 8 — Decent Work and Economic Growth"
DISCLAIMER = (
    "The Career Readiness Score is an indicative skills-coverage measure "
    "based on the information you have provided. It is not a validated "
    "predictor of hiring success or employability."
)
