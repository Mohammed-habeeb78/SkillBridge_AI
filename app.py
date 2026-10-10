"""
app.py — SkillBridge AI main Streamlit application.

Pages (sidebar navigation):
  1. 🏠 Home
  2. 👤 My Profile
  3. 📄 Resume Upload
  4. 🎯 Career Goal & Gap Analysis
  5. 📊 Dashboard
  6. 🗺️ Learning Roadmap
  7. 📝 Resume Feedback
  8. ⚖️ Role Comparison
  9. 🧠 Skill Assessment
  10. 📥 Export Report

Run with:  streamlit run app.py
"""

import os
import sys
import json
import io
from datetime import datetime
from typing import Dict, List, Optional

import streamlit as st

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# ── Application modules ───────────────────────────────────────────────────────
from config import APP_NAME, APP_VERSION, DISCLAIMER, ALLOWED_RESUME_EXTENSIONS, MAX_RESUME_SIZE_BYTES
from database import db
from modules.resume_parser import parse_resume, detect_sections
from modules.skill_extractor import (
    extract_skills_from_resume,
    normalize_skill_list,
    list_all_skills,
    get_skill_label,
    get_quiz_for_skill,
    score_quiz,
    QUIZ_QUESTIONS,
)
from modules.job_analyzer import (
    get_all_roles,
    get_role,
    get_role_requirements,
    get_role_titles,
    compare_roles,
)
from modules.skill_matcher import analyze_skill_gap, compare_candidate_across_roles
from modules.readiness_score import calculate_readiness_score, compare_scores
from modules.recommendation_engine import generate_roadmap
from modules.resume_feedback import generate_resume_feedback
from modules.progress_tracker import (
    get_progress_summary,
    mark_task,
    get_assessment_history,
    apply_quiz_result_to_profile,
)

# ── Plotly (optional) ─────────────────────────────────────────────────────────
try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=APP_NAME,
    page_icon="🌉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Database init ─────────────────────────────────────────────────────────────
db.init_db()


# ══════════════════════════════════════════════════════════════════════════════
# Session state helpers
# ══════════════════════════════════════════════════════════════════════════════

def _ss(key: str, default=None):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


def _init_session():
    _ss("user_id", None)
    _ss("user_name", "")
    _ss("page", "Home")
    _ss("resume_text", "")
    _ss("resume_skills", [])          # [{skill_id, skill_label, ...}]
    _ss("confirmed_skills", [])       # canonical skill_id strings
    _ss("gap_analysis", None)
    _ss("score_result", None)
    _ss("roadmap", None)
    _ss("current_assessment_id", None)
    _ss("selected_role_id", None)


_init_session()


# ══════════════════════════════════════════════════════════════════════════════
# Sidebar navigation
# ══════════════════════════════════════════════════════════════════════════════

def _sidebar():
    st.sidebar.image(
        "https://img.shields.io/badge/SkillBridge_AI-1.0.0-blue?style=for-the-badge",
        use_container_width=True,
    )
    st.sidebar.markdown(f"### {APP_NAME}")
    st.sidebar.caption(f"v{APP_VERSION} — {' SDG 8 Aligned'}")

    if st.session_state.user_id:
        user = db.get_user(st.session_state.user_id)
        st.sidebar.success(f"👤 {user['display_name']}")
        if st.sidebar.button("Log Out / Switch User"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            _init_session()
            st.rerun()
    else:
        st.sidebar.warning("No active profile. Go to **My Profile** to get started.")

    st.sidebar.divider()

    pages = [
        ("🏠", "Home"),
        ("👤", "My Profile"),
        ("📄", "Resume Upload"),
        ("🎯", "Career Goal & Gap Analysis"),
        ("📊", "Dashboard"),
        ("🗺️", "Learning Roadmap"),
        ("📝", "Resume Feedback"),
        ("⚖️", "Role Comparison"),
        ("🧠", "Skill Assessment"),
        ("📥", "Export Report"),
    ]

    for icon, page_name in pages:
        label = f"{icon} {page_name}"
        if st.sidebar.button(label, use_container_width=True,
                              type="primary" if st.session_state.page == page_name else "secondary"):
            st.session_state.page = page_name
            st.rerun()

    st.sidebar.divider()
    st.sidebar.caption(
        "SkillBridge AI supports SDG 8: Decent Work and Economic Growth. "
        "This tool provides guidance only and does not guarantee employment outcomes."
    )


# ══════════════════════════════════════════════════════════════════════════════
# Page: Home
# ══════════════════════════════════════════════════════════════════════════════

def page_home():
    st.title("🌉 SkillBridge AI")
    st.subheader("Intelligent Career Readiness & Skill Gap Analysis")

    st.markdown("""
    **SkillBridge AI** helps students and fresh graduates understand the gap between
    their current skills and the requirements of their target careers.

    #### What it does
    - **Parses your resume** (PDF or DOCX) and extracts your technical skills
    - **Analyzes job requirements** for 9 popular tech career paths
    - **Identifies skill gaps** with importance rankings
    - **Calculates a transparent readiness score** (not a hiring predictor — see disclaimer)
    - **Generates a personalized learning roadmap** with curated free resources
    - **Gives resume improvement suggestions** based on your target role
    - **Tracks your progress** as you complete learning tasks

    #### How to get started
    1. Go to **👤 My Profile** and create your profile
    2. Upload your resume on **📄 Resume Upload** (optional but recommended)
    3. Select your target career on **🎯 Career Goal & Gap Analysis**
    4. View your results on **📊 Dashboard** and **🗺️ Learning Roadmap**
    """)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Supported Career Paths", "9")
    with col2:
        st.metric("Skill Definitions", f"{len(list_all_skills())}+")
    with col3:
        st.metric("Learning Resources", "50+")

    st.info(f"**Disclaimer:** {DISCLAIMER}", icon="ℹ️")

    st.markdown("---")
    st.caption(
        "Built for academic demonstration purposes. "
        "Job role descriptions are representative examples, not current verified vacancies. "
        "Aligned with **SDG 8 — Decent Work and Economic Growth**."
    )


# ══════════════════════════════════════════════════════════════════════════════
# Page: My Profile
# ══════════════════════════════════════════════════════════════════════════════

def page_profile():
    st.title("👤 My Profile")

    # ── Load existing users ───────────────────────────────────────────────────
    users = db.list_users()
    if users:
        st.subheader("Load Existing Profile")
        user_options = {f"{u['display_name']} (ID {u['id']})": u["id"] for u in users}
        selected_label = st.selectbox("Select a profile", ["— Create New —"] + list(user_options.keys()))
        if selected_label != "— Create New —" and st.button("Load Profile"):
            uid = user_options[selected_label]
            st.session_state.user_id = uid
            skills = db.get_user_skills(uid)
            st.session_state.confirmed_skills = [s["skill_id"] for s in skills]
            st.success("Profile loaded.")
            st.rerun()
        st.divider()

    # ── Create / edit profile form ────────────────────────────────────────────
    if st.session_state.user_id:
        user = db.get_user(st.session_state.user_id)
        st.subheader(f"Editing: {user['display_name']}")
    else:
        st.subheader("Create New Profile")
        user = {}

    with st.form("profile_form"):
        col1, col2 = st.columns(2)
        with col1:
            display_name = st.text_input("Display Name *", value=user.get("display_name", ""))
            email = st.text_input("Email (optional)", value=user.get("email", "") or "")
            education_level = st.selectbox(
                "Education Level",
                ["", "High School", "Diploma", "Bachelor's", "Master's", "PhD", "Other"],
                index=["", "High School", "Diploma", "Bachelor's", "Master's", "PhD", "Other"].index(
                    user.get("education_level", "") or ""
                ) if user.get("education_level") in ["", "High School", "Diploma", "Bachelor's", "Master's", "PhD", "Other"] else 0
            )
        with col2:
            degree = st.text_input("Degree / Programme", value=user.get("degree", "") or "")
            branch = st.text_input("Branch / Specialization", value=user.get("branch", "") or "")
            graduation_year = st.number_input(
                "Graduation Year",
                min_value=2000, max_value=2035,
                value=user.get("graduation_year") or datetime.now().year,
            )

        st.markdown("#### Skills")
        st.caption(
            "Enter your skills as a comma-separated list. "
            "Be honest — only include skills you could discuss in an interview."
        )
        all_skill_list = sorted([s["label"] for s in list_all_skills()])
        current_confirmed = st.session_state.confirmed_skills or []
        current_labels = [get_skill_label(sid) for sid in current_confirmed]

        manual_skills = st.multiselect(
            "Select your skills from the list",
            options=all_skill_list,
            default=[lbl for lbl in current_labels if lbl in all_skill_list],
        )

        free_text_skills = st.text_area(
            "Additional skills not in the list above (comma-separated)",
            placeholder="e.g. Figma, Adobe XD, R, Rust",
        )

        submitted = st.form_submit_button("Save Profile", type="primary")

    if submitted:
        if not display_name.strip():
            st.error("Display name is required.")
            return

        # Normalize skill inputs
        normalized = normalize_skill_list(manual_skills)
        if free_text_skills.strip():
            extras = [s.strip() for s in free_text_skills.split(",") if s.strip()]
            normalized += normalize_skill_list(extras)

        skill_records = [
            {
                "skill_id": s["skill_id"],
                "skill_label": s["skill_label"],
                "proficiency": "claimed",
                "source": "manual",
            }
            for s in normalized
        ]

        if st.session_state.user_id:
            db.update_user(
                st.session_state.user_id,
                display_name=display_name,
                email=email or None,
                education_level=education_level,
                degree=degree,
                branch=branch,
                graduation_year=int(graduation_year),
            )
            db.set_user_skills(st.session_state.user_id, skill_records)
        else:
            uid = db.create_user(
                display_name=display_name,
                email=email or None,
                education_level=education_level,
                degree=degree,
                branch=branch,
                graduation_year=int(graduation_year),
            )
            st.session_state.user_id = uid
            db.set_user_skills(uid, skill_records)

        st.session_state.confirmed_skills = [s["skill_id"] for s in skill_records]
        st.success("Profile saved successfully!")

        # Show unrecognized skills warning
        unrecognized = [s for s in normalized if not s["recognized"]]
        if unrecognized:
            st.warning(
                f"The following {len(unrecognized)} skill(s) were not found in the skill dictionary "
                "and are stored as-is. They will not be matched against job requirements:\n"
                + ", ".join(s["original"] for s in unrecognized)
            )

    # ── Delete data section ────────────────────────────────────────────────────
    if st.session_state.user_id:
        st.divider()
        with st.expander("⚠️ Delete My Data"):
            st.warning(
                "This will permanently delete your profile, all skill records, "
                "assessments, and resume data. This cannot be undone."
            )
            if st.button("Delete All My Data", type="secondary"):
                db.delete_user(st.session_state.user_id)
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                _init_session()
                st.success("All your data has been deleted.")
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Page: Resume Upload
# ══════════════════════════════════════════════════════════════════════════════

def page_resume():
    st.title("📄 Resume Upload")

    if not st.session_state.user_id:
        st.warning("Please create a profile first (👤 My Profile).")
        return

    st.markdown(
        "Upload your resume (PDF or DOCX). The system will extract text and identify skills. "
        "You will be able to review and correct the extracted results before they are used."
    )

    uploaded = st.file_uploader(
        "Choose your resume file",
        type=["pdf", "docx"],
        accept_multiple_files=False,
    )

    if uploaded is None:
        # Show last parsed resume if available
        last = db.get_latest_resume(st.session_state.user_id)
        if last and last["status"] == "parsed":
            st.info(f"Last uploaded: **{last['filename']}** — {len(last['parsed_skills'])} skills detected.")
        return

    # ── Validate ──────────────────────────────────────────────────────────────
    ext = os.path.splitext(uploaded.name.lower())[1]
    if ext not in ALLOWED_RESUME_EXTENSIONS:
        st.error(f"Unsupported file type '{ext}'. Please upload a .pdf or .docx file.")
        return

    file_bytes = uploaded.read()
    if len(file_bytes) > MAX_RESUME_SIZE_BYTES:
        st.error(f"File exceeds the {MAX_RESUME_SIZE_BYTES // (1024*1024)} MB limit.")
        return

    # ── Parse ─────────────────────────────────────────────────────────────────
    with st.spinner("Extracting text from resume…"):
        parse_result = parse_resume(file_bytes, uploaded.name)

    if not parse_result["success"]:
        st.error("Text extraction failed.")
        for w in parse_result["warnings"]:
            st.warning(w)
        st.info("You can still add your skills manually in the Profile page.")
        return

    for w in parse_result["warnings"]:
        st.caption(f"ℹ️ {w}")

    text = parse_result["text"]
    st.session_state.resume_text = text

    # ── Skill extraction ──────────────────────────────────────────────────────
    with st.spinner("Identifying skills in resume…"):
        sections = detect_sections(text)
        extracted = extract_skills_from_resume(text, sections)

    st.session_state.resume_skills = extracted

    # Save to DB
    resume_id = db.save_resume_upload(
        st.session_state.user_id,
        uploaded.name,
        extracted_text=text,
        parsed_skills=[s["skill_id"] for s in extracted],
        status="parsed",
    )

    st.success(f"✅ Extracted {len(extracted)} skills from **{uploaded.name}**.")

    # ── Review and confirm ────────────────────────────────────────────────────
    st.subheader("Review Extracted Skills")
    st.caption(
        "These skills were detected in your resume. Check or uncheck them. "
        "**Detected does not mean mastered** — treat these as 'claimed skills' "
        "that you should be able to discuss in an interview."
    )

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.write("**Skill**")
    with col2:
        st.write("**Category**")
    with col3:
        st.write("**Include?**")

    confirmed_ids = []
    for skill in extracted:
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            st.write(skill["skill_label"])
        with c2:
            st.caption(skill["category"].replace("_", " ").title())
        with c3:
            checked = st.checkbox(
                "Include",
                value=True,
                key=f"resume_skill_{skill['skill_id']}",
                label_visibility="collapsed",
            )
            if checked:
                confirmed_ids.append(skill["skill_id"])

    # Also include any manually-entered skills from the profile
    profile_skills = db.get_user_skills(st.session_state.user_id)
    profile_ids = [s["skill_id"] for s in profile_skills if s["source"] == "manual"]
    all_confirmed = list(set(confirmed_ids + profile_ids))

    if st.button("✅ Confirm Skills & Update Profile", type="primary"):
        skill_records = []
        for sid in confirmed_ids:
            skill_records.append({
                "skill_id": sid,
                "skill_label": get_skill_label(sid),
                "proficiency": "claimed",
                "source": "resume",
            })
        for sid in profile_ids:
            if sid not in confirmed_ids:
                skill_records.append({
                    "skill_id": sid,
                    "skill_label": get_skill_label(sid),
                    "proficiency": "claimed",
                    "source": "manual",
                })
        db.set_user_skills(st.session_state.user_id, skill_records)
        st.session_state.confirmed_skills = [s["skill_id"] for s in skill_records]
        st.success("Skills updated from resume. Proceed to Career Goal & Gap Analysis.")

    # ── Raw text preview ──────────────────────────────────────────────────────
    with st.expander("View extracted text (first 2000 characters)"):
        st.text(text[:2000] + ("…" if len(text) > 2000 else ""))


# ══════════════════════════════════════════════════════════════════════════════
# Page: Career Goal & Gap Analysis
# ══════════════════════════════════════════════════════════════════════════════

def page_gap_analysis():
    st.title("🎯 Career Goal & Gap Analysis")

    if not st.session_state.user_id:
        st.warning("Please create a profile first.")
        return

    skills = db.get_user_skills(st.session_state.user_id)
    candidate_ids = [s["skill_id"] for s in skills]

    if not candidate_ids:
        st.warning(
            "No skills on your profile yet. "
            "Upload a resume or add skills manually in My Profile."
        )

    # ── Role selector ─────────────────────────────────────────────────────────
    role_titles = get_role_titles()
    role_map = {title: rid for rid, title in role_titles}

    st.subheader("Select Your Target Career Role")
    selected_title = st.selectbox(
        "Target career role",
        options=[t for _, t in role_titles],
        index=0,
    )
    selected_role_id = role_map[selected_title]

    # ── Optional: paste a job description ─────────────────────────────────────
    with st.expander("📋 Paste a specific job description (optional)"):
        st.caption(
            "If you have a specific job advertisement in mind, paste it below. "
            "The system will extract the required skills from it."
        )
        jd_text = st.text_area("Job description text", height=200)
        if jd_text.strip():
            from modules.job_analyzer import analyze_job_description
            jd_result = analyze_job_description(jd_text)
            if jd_result["extracted_skills"]:
                st.success(f"Extracted {len(jd_result['extracted_skills'])} skills from the job description.")
                jd_skill_ids = [s["skill_id"] for s in jd_result["extracted_skills"]]
                st.caption(", ".join(get_skill_label(s) for s in jd_skill_ids[:15]))
            for w in jd_result["warnings"]:
                st.warning(w)

    # ── Run analysis ──────────────────────────────────────────────────────────
    if st.button("🔍 Run Skill Gap Analysis", type="primary"):
        if not candidate_ids:
            st.error("You need at least one skill on your profile to run the analysis.")
            return

        with st.spinner("Analysing skill gap…"):
            req = get_role_requirements(selected_role_id)
            gap = analyze_skill_gap(candidate_ids, req)
            score = calculate_readiness_score(gap)
            roadmap = generate_roadmap(gap, candidate_ids)

        # Persist
        assessment_id = db.save_assessment(
            user_id=st.session_state.user_id,
            role_id=selected_role_id,
            role_title=req["title"],
            readiness_score=score["score"],
            matched=[s["skill_id"] for s in gap["mandatory_match"] + gap["preferred_match"]],
            missing=[s["skill_id"] for s in gap["mandatory_missing"] + gap["preferred_missing"]],
            partial=[s["skill_id"] for s in gap["mandatory_partial"] + gap["preferred_partial"]],
            breakdown={
                "mandatory_score": score["mandatory_score"],
                "preferred_score": score["preferred_score"],
            },
        )
        # Save roadmap tasks
        if roadmap.get("all_tasks"):
            db.save_roadmap_tasks(
                assessment_id,
                st.session_state.user_id,
                [{"skill_id": t["skill_id"], "skill_label": t["skill_label"],
                  "stage": t["stage"], "priority": t["priority"]}
                 for t in roadmap["all_tasks"]],
            )

        st.session_state.gap_analysis = gap
        st.session_state.score_result = score
        st.session_state.roadmap = roadmap
        st.session_state.current_assessment_id = assessment_id
        st.session_state.selected_role_id = selected_role_id

        st.success("Analysis complete! View your results below or navigate to the Dashboard.")
        _display_gap_summary(gap, score)


def _display_gap_summary(gap: Dict, score: Dict):
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Readiness Score", f"{score['score']}/100", help=score["formula_explanation"])
    with col2:
        st.metric("Band", score["band"])
    with col3:
        st.metric("Matched Skills", gap["summary"]["matched_count"])
    with col4:
        st.metric("Skills to Develop", gap["summary"]["missing_count"])

    st.caption(score["band_description"])

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("✅ Matched Skills")
        if gap["mandatory_match"]:
            st.markdown("**Mandatory:**")
            for s in gap["mandatory_match"]:
                st.markdown(f"- {s['skill_label']}")
        if gap["preferred_match"]:
            st.markdown("**Preferred:**")
            for s in gap["preferred_match"]:
                st.markdown(f"- {s['skill_label']}")
        if not gap["mandatory_match"] and not gap["preferred_match"]:
            st.caption("No direct matches found.")

        if gap["mandatory_partial"] or gap["preferred_partial"]:
            st.subheader("🔶 Partial Matches")
            for s in gap["mandatory_partial"] + gap["preferred_partial"]:
                with st.expander(f"↗ {s['skill_label']}"):
                    st.caption(s.get("explanation", ""))

    with col_b:
        st.subheader("❌ Missing Skills")
        st.markdown("**Mandatory (highest priority):**")
        if gap["mandatory_missing"]:
            for s in gap["mandatory_missing"]:
                st.markdown(f"- **{s['skill_label']}** — {s.get('reason','')}")
        else:
            st.markdown("*All mandatory skills covered!*")

        if gap["preferred_missing"]:
            st.markdown("**Preferred:**")
            for s in gap["preferred_missing"][:5]:
                st.markdown(f"- {s['skill_label']}")

    st.info(DISCLAIMER, icon="ℹ️")


# ══════════════════════════════════════════════════════════════════════════════
# Page: Dashboard
# ══════════════════════════════════════════════════════════════════════════════

def page_dashboard():
    st.title("📊 Dashboard")

    if not st.session_state.user_id:
        st.warning("Please create a profile first.")
        return

    user = db.get_user(st.session_state.user_id)
    skills = db.get_user_skills(st.session_state.user_id)
    assessments = db.get_assessments(st.session_state.user_id)
    progress = get_progress_summary(st.session_state.user_id)

    # ── Profile summary ────────────────────────────────────────────────────────
    st.subheader(f"Welcome, {user['display_name']}")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Skills on Profile", len(skills))
    with col2:
        st.metric("Assessments Run", len(assessments))
    with col3:
        st.metric("Roadmap Tasks Completed", progress["completed_tasks"])
    with col4:
        pct = progress["overall_pct"]
        st.metric("Roadmap Progress", f"{pct}%")

    # ── Latest score ───────────────────────────────────────────────────────────
    if assessments:
        latest = assessments[0]
        st.divider()
        st.subheader("Latest Assessment")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Role", latest["role_title"])
        with c2:
            st.metric("Readiness Score", f"{latest['readiness_score']}/100")
        with c3:
            st.metric("Date", latest["created_at"][:10])

        if PLOTLY_AVAILABLE:
            _render_gauge(latest["readiness_score"])

        # Score history chart
        if len(assessments) > 1:
            st.subheader("Score History")
            dates = [a["created_at"][:10] for a in reversed(assessments)]
            scores_vals = [a["readiness_score"] for a in reversed(assessments)]
            role_labels = [a["role_title"] for a in reversed(assessments)]
            if PLOTLY_AVAILABLE:
                fig = px.line(
                    x=dates, y=scores_vals,
                    labels={"x": "Date", "y": "Readiness Score"},
                    title="Readiness Score Over Time",
                    hover_name=role_labels,
                    markers=True,
                )
                fig.update_layout(yaxis_range=[0, 100])
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.line_chart(dict(zip(dates, scores_vals)))

    # ── Skill breakdown ────────────────────────────────────────────────────────
    if skills:
        st.divider()
        st.subheader("Your Skills Profile")
        from collections import Counter
        cat_counts = Counter(s.get("proficiency", "claimed") for s in skills)
        if PLOTLY_AVAILABLE:
            fig2 = px.bar(
                x=list(cat_counts.keys()),
                y=list(cat_counts.values()),
                labels={"x": "Proficiency Level", "y": "Count"},
                title="Skills by Proficiency Level",
                color=list(cat_counts.keys()),
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.bar_chart(dict(cat_counts))

    # ── Roadmap progress per stage ─────────────────────────────────────────────
    if progress["stages"]:
        st.divider()
        st.subheader("Roadmap Progress by Stage")
        for stage in progress["stages"]:
            col_l, col_r = st.columns([3, 1])
            with col_l:
                st.progress(stage["pct"] / 100, text=f"{stage['label']}: {stage['pct']}%")
            with col_r:
                st.caption(f"{stage['completed']}/{stage['total']} done")

    st.info(DISCLAIMER, icon="ℹ️")


def _render_gauge(score: float):
    if not PLOTLY_AVAILABLE:
        return
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": "Career Readiness Score"},
        delta={"reference": 60},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#3b82d4"},
            "steps": [
                {"range": [0, 40], "color": "#fee2e2"},
                {"range": [40, 60], "color": "#fef3c7"},
                {"range": [60, 80], "color": "#d1fae5"},
                {"range": [80, 100], "color": "#a7f3d0"},
            ],
            "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": 80},
        },
    ))
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# Page: Learning Roadmap
# ══════════════════════════════════════════════════════════════════════════════

def page_roadmap():
    st.title("🗺️ Learning Roadmap")

    if not st.session_state.user_id:
        st.warning("Please create a profile first.")
        return

    if not st.session_state.roadmap:
        st.info("Run a Career Goal & Gap Analysis first to generate your roadmap.")
        return

    roadmap = st.session_state.roadmap
    st.markdown(f"**{roadmap['summary']}**")
    st.caption(f"Total estimated study time: ~{roadmap['total_estimated_hours']} hours")

    # Load task statuses from DB
    db_tasks = {
        t["skill_id"]: t
        for t in db.get_roadmap_tasks(
            st.session_state.user_id,
            st.session_state.current_assessment_id
        )
    }

    for stage in roadmap["stages"]:
        with st.expander(f"📌 {stage['label']}", expanded=(stage["stage"] == 1)):
            st.caption(stage["description"])
            for task in stage["tasks"]:
                sid = task["skill_id"]
                db_task = db_tasks.get(sid, {})
                task_id = db_task.get("id")
                current_status = db_task.get("status", "pending")

                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    badge = "✅" if current_status == "completed" else "🔄" if current_status == "in_progress" else "⏳"
                    st.markdown(f"**{badge} {task['skill_label']}**")
                    if task.get("reason"):
                        st.caption(f"Why: {task['reason'][:200]}")
                    if task.get("unmet_prerequisites"):
                        prereq_labels = ", ".join(get_skill_label(p) for p in task["unmet_prerequisites"])
                        st.warning(f"Learn first: {prereq_labels}", icon="⚠️")
                with col2:
                    st.caption(f"~{task['estimated_hours']}h")
                with col3:
                    if task_id:
                        new_status = st.selectbox(
                            "Status",
                            ["pending", "in_progress", "completed"],
                            index=["pending", "in_progress", "completed"].index(current_status),
                            key=f"task_status_{task_id}",
                            label_visibility="collapsed",
                        )
                        if new_status != current_status:
                            mark_task(task_id, new_status)
                            st.rerun()

                # Resources
                if task.get("resources"):
                    with st.container():
                        for res in task["resources"]:
                            st.markdown(f"  📚 [{res['title']}]({res['url']}) — *{res['platform']}*")

                # Mini project
                if task.get("mini_project") and task["match_type"] != "stage4":
                    st.info(f"🛠️ **Mini-project:** {task['mini_project']}", icon="🔨")

                st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# Page: Resume Feedback
# ══════════════════════════════════════════════════════════════════════════════

def page_resume_feedback():
    st.title("📝 Resume Feedback")

    if not st.session_state.user_id:
        st.warning("Please create a profile first.")
        return

    if not st.session_state.selected_role_id:
        st.info("Run a Career Goal & Gap Analysis first to get role-specific feedback.")
        return

    resume_text = st.session_state.resume_text
    if not resume_text:
        st.info("Upload a resume first on the Resume Upload page for detailed feedback.")
        resume_text = ""

    skills = db.get_user_skills(st.session_state.user_id)
    confirmed_ids = [s["skill_id"] for s in skills]
    resume_skill_ids = [s["skill_id"] for s in st.session_state.resume_skills]

    role_id = st.session_state.selected_role_id
    role = get_role(role_id)
    st.subheader(f"Feedback for: {role['title']}")

    with st.spinner("Generating resume feedback…"):
        feedback = generate_resume_feedback(
            resume_text=resume_text,
            extracted_resume_skills=resume_skill_ids,
            confirmed_candidate_skills=confirmed_ids,
            role_id=role_id,
        )

    st.markdown(f"### Overall\n{feedback['overall_feedback']}")
    st.caption(f"**Note:** {feedback['disclaimer']}")
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        if feedback["positive_observations"]:
            st.subheader("✅ Strengths")
            for obs in feedback["positive_observations"]:
                st.success(obs)

        if feedback["missing_from_resume"]:
            st.subheader("📎 Skills Confirmed But Not on Resume")
            st.caption("These skills are in your profile but were not found in your resume text.")
            for item in feedback["missing_from_resume"]:
                with st.expander(item["skill_label"]):
                    st.caption(item["suggestion"])

    with col2:
        if feedback["keyword_gaps"]:
            st.subheader("🔑 Missing Keywords")
            st.caption("High-priority role keywords not found in your resume:")
            for kw in feedback["keyword_gaps"]:
                st.markdown(f"- {kw}")

        if feedback["section_feedback"]:
            st.subheader("📋 Section Observations")
            for sf in feedback["section_feedback"]:
                st.warning(sf)

    if feedback["weak_phrase_instances"]:
        st.subheader("✍️ Weak Phrase Suggestions")
        st.caption("Consider replacing these phrases with stronger action verbs:")
        for item in feedback["weak_phrase_instances"][:5]:
            with st.expander(f'"{item["original_phrase"]}" in: …{item["line_preview"][:80]}…'):
                st.markdown(f"💡 **Suggestion:** {item['suggestion']}")

    if feedback["vague_descriptions"]:
        st.subheader("🔍 Vague Descriptions")
        for v in feedback["vague_descriptions"][:5]:
            st.warning(v)

    if feedback["project_suggestions"]:
        st.subheader("🛠️ Suggested Projects to Add")
        for proj in feedback["project_suggestions"]:
            st.info(proj)


# ══════════════════════════════════════════════════════════════════════════════
# Page: Role Comparison
# ══════════════════════════════════════════════════════════════════════════════

def page_role_comparison():
    st.title("⚖️ Career Role Comparison")

    if not st.session_state.user_id:
        st.warning("Please create a profile first.")
        return

    skills = db.get_user_skills(st.session_state.user_id)
    candidate_ids = [s["skill_id"] for s in skills]

    role_titles = get_role_titles()
    role_map = {title: rid for rid, title in role_titles}
    all_titles = [t for _, t in role_titles]

    st.subheader("Select Roles to Compare (2–3 roles)")
    selected_titles = st.multiselect(
        "Choose career roles",
        options=all_titles,
        default=all_titles[:2] if len(all_titles) >= 2 else all_titles,
        max_selections=3,
    )

    if len(selected_titles) < 2:
        st.info("Select at least 2 roles to compare.")
        return

    selected_role_ids = [role_map[t] for t in selected_titles]

    if st.button("Compare Roles", type="primary"):
        with st.spinner("Comparing…"):
            reqs = [get_role_requirements(rid) for rid in selected_role_ids]
            gaps = compare_candidate_across_roles(candidate_ids, reqs)
            scores = compare_scores(gaps)
            comparison = compare_roles(selected_role_ids)

        st.subheader("Your Readiness Scores per Role")
        cols = st.columns(len(scores))
        for i, sr in enumerate(scores):
            with cols[i]:
                st.metric(sr["role_title"], f"{sr['score']}/100")
                st.caption(sr["band"])
                st.progress(sr["score"] / 100)

        if PLOTLY_AVAILABLE:
            fig = px.bar(
                x=[s["role_title"] for s in scores],
                y=[s["score"] for s in scores],
                color=[s["band"] for s in scores],
                labels={"x": "Role", "y": "Readiness Score"},
                title="Readiness Score by Career Role",
            )
            fig.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)

        # Shared skills
        if comparison["shared_skills"]:
            st.subheader("🔗 Skills Required by All Selected Roles")
            labels = [get_skill_label(s) for s in comparison["shared_skills"]]
            st.markdown(", ".join(f"**{l}**" for l in labels))

        # Unique skills per role
        st.subheader("🎯 Skills Unique to Each Role")
        ucols = st.columns(len(selected_role_ids))
        for i, rid in enumerate(selected_role_ids):
            with ucols[i]:
                role = get_role(rid)
                st.markdown(f"**{role['title']}**")
                unique = comparison["unique_skills"].get(rid, [])
                if unique:
                    for sid in unique:
                        st.markdown(f"- {get_skill_label(sid)}")
                else:
                    st.caption("No skills unique to this role among those compared.")

        # Skill gap per role
        st.subheader("❌ Skills You Still Need (per role)")
        for gap in gaps:
            with st.expander(gap["role_title"]):
                if gap["mandatory_missing"]:
                    st.markdown("**Missing mandatory:**")
                    for s in gap["mandatory_missing"]:
                        st.markdown(f"- {s['skill_label']}")
                else:
                    st.success("All mandatory skills covered!")

                if gap["preferred_missing"]:
                    st.markdown("**Missing preferred:**")
                    for s in gap["preferred_missing"][:4]:
                        st.markdown(f"- {s['skill_label']}")


# ══════════════════════════════════════════════════════════════════════════════
# Page: Skill Assessment (Quiz)
# ══════════════════════════════════════════════════════════════════════════════

def page_assessment():
    st.title("🧠 Skill Assessment")

    if not st.session_state.user_id:
        st.warning("Please create a profile first.")
        return

    st.markdown(
        "Take a short quiz to validate your self-reported skill level. "
        "Results are used as **supplementary evidence** — a single quiz is not "
        "a definitive measure of ability."
    )

    skills_with_quizzes = [
        sid for sid in QUIZ_QUESTIONS.keys()
    ]
    labels = [get_skill_label(s) for s in skills_with_quizzes]
    skill_label_map = dict(zip(labels, skills_with_quizzes))

    selected_skill_label = st.selectbox("Select a skill to assess", sorted(labels))
    skill_id = skill_label_map[selected_skill_label]
    questions = get_quiz_for_skill(skill_id)

    if not questions:
        st.info("No quiz available for this skill yet.")
        return

    st.subheader(f"Quiz: {selected_skill_label}")
    st.caption(f"{len(questions)} questions")

    answers: List[int] = []
    with st.form(f"quiz_{skill_id}"):
        for i, q in enumerate(questions):
            st.markdown(f"**Q{i+1}. {q['q']}**")
            choice = st.radio(
                f"q_{i}",
                options=q["options"],
                key=f"q_{skill_id}_{i}",
                label_visibility="collapsed",
            )
            answers.append(q["options"].index(choice) if choice in q["options"] else 0)
            st.divider()

        submitted = st.form_submit_button("Submit Quiz", type="primary")

    if submitted:
        result = score_quiz(skill_id, answers)
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Score", f"{result['score']}/{result['max_score']}")
        with col2:
            st.metric("Percentage", f"{result['percentage']}%")
        with col3:
            status = "✅ Passed" if result["passed"] else "❌ Not Passed"
            st.metric("Result", status)

        if result["passed"]:
            st.success(
                f"Well done! Your {selected_skill_label} knowledge has been noted as 'beginner-verified' on your profile."
            )
            apply_quiz_result_to_profile(st.session_state.user_id, skill_id, passed=True)
        else:
            st.warning(
                "Not enough correct answers to update your proficiency level. "
                "Review the explanations below and try again after more practice."
            )

        st.subheader("Answer Review")
        for item in result["detail"]:
            icon = "✅" if item["correct"] else "❌"
            with st.expander(f"{icon} {item['question'][:80]}"):
                st.write(f"**Your answer:** {item['user_answer']}")
                st.write(f"**Correct answer:** {item['correct_answer']}")
                st.caption(f"Explanation: {item['explanation']}")

        # Save to DB
        db.save_quiz_attempt(
            st.session_state.user_id,
            skill_id,
            result["score"],
            result["max_score"],
            result["detail"],
        )

        # Show past attempts
        past = db.get_quiz_attempts(st.session_state.user_id, skill_id)
        if len(past) > 1:
            st.subheader("Your Previous Attempts")
            for att in past[1:4]:
                pct = round(att["score"] / att["max_score"] * 100, 1) if att["max_score"] else 0
                st.caption(f"{att['attempted_at'][:10]} — {att['score']}/{att['max_score']} ({pct}%)")


# ══════════════════════════════════════════════════════════════════════════════
# Page: Export Report
# ══════════════════════════════════════════════════════════════════════════════

def page_export():
    st.title("📥 Export Report")

    if not st.session_state.user_id:
        st.warning("Please create a profile first.")
        return

    if not st.session_state.gap_analysis:
        st.info("Run a Career Goal & Gap Analysis first to generate an exportable report.")
        return

    gap = st.session_state.gap_analysis
    score = st.session_state.score_result
    roadmap = st.session_state.roadmap
    user = db.get_user(st.session_state.user_id)
    skills = db.get_user_skills(st.session_state.user_id)

    # ── PDF export (primary) ──────────────────────────────────────────────────
    st.subheader("📄 Professional PDF Report")
    st.markdown(
        "Download a fully formatted, multi-page PDF report containing your candidate "
        "profile, readiness score, skill gap analysis, and personalized learning roadmap."
    )

    # Optionally include resume feedback if it was generated this session
    feedback_for_pdf = None
    if st.session_state.selected_role_id:
        resume_text = st.session_state.resume_text or ""
        resume_skill_ids = [s["skill_id"] for s in st.session_state.resume_skills]
        confirmed_ids = [s["skill_id"] for s in skills]
        if resume_text or confirmed_ids:
            try:
                from modules.resume_feedback import generate_resume_feedback
                feedback_for_pdf = generate_resume_feedback(
                    resume_text=resume_text,
                    extracted_resume_skills=resume_skill_ids,
                    confirmed_candidate_skills=confirmed_ids,
                    role_id=st.session_state.selected_role_id,
                )
            except Exception:
                feedback_for_pdf = None

    include_feedback = st.checkbox(
        "Include Resume Improvement Suggestions in PDF",
        value=feedback_for_pdf is not None,
        disabled=feedback_for_pdf is None,
        help="Only available if you have run the analysis with a selected role.",
    )

    if st.button("⬇️ Generate & Download PDF Report", type="primary"):
        try:
            from modules.pdf_report import build_pdf_report
            with st.spinner("Building PDF…"):
                pdf_bytes = build_pdf_report(
                    user=user,
                    skills=skills,
                    gap=gap,
                    score=score,
                    roadmap=roadmap,
                    feedback=feedback_for_pdf if include_feedback else None,
                )
            filename = (
                f"skillbridge_report_{user['display_name'].replace(' ', '_')}_"
                f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            )
            st.download_button(
                label="📄 Download PDF",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf",
                type="primary",
            )
            st.success("PDF ready! Click **Download PDF** above to save it.")
        except ImportError:
            st.error(
                "ReportLab is not installed. Run `pip install reportlab` then restart the app."
            )
        except Exception as e:
            st.error(f"PDF generation failed: {e}")

    st.divider()

    # ── PDF contents preview ──────────────────────────────────────────────────
    with st.expander("📋 What's included in the PDF"):
        st.markdown("""
**Cover Page**
- Candidate name, target role, readiness score, band, and date

**Section 1 — Candidate Profile**
- Education, degree, branch, graduation year, total skills

**Section 2 — Readiness Score Summary**
- Score table: overall, mandatory, preferred scores and weights
- Visual progress bar
- Band description and scoring formula

**Section 3 — Skill Gap Analysis**
- ✅ Matched skills (mandatory + preferred) with weights
- 🔶 Partially matched skills with explanation
- ❌ Missing mandatory skills with importance reasons
- ⬜ Missing preferred skills

**Section 4 — Personalized Learning Roadmap**
- All stages with tasks, estimated hours, resource links, and mini-projects

**Section 5 — Resume Improvement Suggestions** *(if included)*
- Strengths, keyword gaps, weak phrase suggestions, project recommendations

**Final Page — Limitations & Disclaimer**
- SDG 8 alignment note
        """)

    st.divider()

    # ── Secondary: Skills CSV ─────────────────────────────────────────────────
    st.subheader("📊 Export Skills as CSV")
    st.caption("A flat CSV of all skills on your profile — useful for spreadsheet analysis.")
    import csv
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["skill_id", "skill_label", "proficiency", "source"])
    for s in skills:
        writer.writerow([s["skill_id"], s["skill_label"], s.get("proficiency", ""), s.get("source", "")])
    st.download_button(
        "⬇️ Download Skills CSV",
        data=buf.getvalue(),
        file_name="my_skills.csv",
        mime="text/csv",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Main router
# ══════════════════════════════════════════════════════════════════════════════

def main():
    _sidebar()
    page = st.session_state.page

    if page == "Home":
        page_home()
    elif page == "My Profile":
        page_profile()
    elif page == "Resume Upload":
        page_resume()
    elif page == "Career Goal & Gap Analysis":
        page_gap_analysis()
    elif page == "Dashboard":
        page_dashboard()
    elif page == "Learning Roadmap":
        page_roadmap()
    elif page == "Resume Feedback":
        page_resume_feedback()
    elif page == "Role Comparison":
        page_role_comparison()
    elif page == "Skill Assessment":
        page_assessment()
    elif page == "Export Report":
        page_export()
    else:
        page_home()


if __name__ == "__main__":
    main()
