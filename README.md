<div align="center">

# 🌉 SkillBridge AI

### *Intelligent Career Readiness Assessment & Skill Gap Analysis*

**Know where you stand. Know where to go.**

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://sqlite.org)
[![ReportLab](https://img.shields.io/badge/PDF-ReportLab-blue?style=flat-square)](https://reportlab.com)
[![SDG 8](https://img.shields.io/badge/SDG%208-Decent%20Work%20%26%20Economic%20Growth-2ECC71?style=flat-square)](https://sdgs.un.org/goals/goal8)
[![License](https://img.shields.io/badge/License-Academic-lightgrey?style=flat-square)](#license)

<br/>

> **SkillBridge AI** helps undergraduate students and fresh graduates understand the gap between their current skills and the requirements of their target careers — and gives them a clear, actionable plan to close it.

</div>

---

## 📋 Table of Contents

- [Why SkillBridge AI?](#-why-skillbridge-ai)
- [Key Features](#-key-features)
- [Supported Career Roles](#-supported-career-roles)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [How It Works](#-how-it-works)
- [Readiness Score Formula](#-readiness-score-formula)
- [Technology Stack](#-technology-stack)
- [SDG Alignment](#-sdg-alignment)
- [Sample Walkthrough](#-sample-walkthrough)
- [Known Limitations](#-known-limitations)
- [License](#-license)

---

## 💡 Why SkillBridge AI?

Many students graduate with strong academic records but **no clear picture of whether they are ready for their target roles**. Existing job portals focus on matching — not on explaining *how* to improve.

SkillBridge AI bridges that gap by:

- 📄 Parsing your resume to extract skills automatically
- 🔍 Comparing your skills against curated role requirements
- 📊 Scoring your readiness transparently (with the formula shown, not hidden)
- 🗺️ Building a personalized, staged learning roadmap
- 📝 Suggesting concrete improvements to your resume
- 📥 Exporting a professional multi-page PDF report

> ⚠️ **Disclaimer:** The Career Readiness Score is an indicative skills-coverage measure based on the information you provide. It is **not** a validated predictor of hiring success or employability.

---

## ✨ Key Features

| # | Feature | What it does |
|---|---|---|
| 1 | 📄 **Resume Parsing** | Extracts text and skills from PDF and DOCX files; graceful fallback for scanned PDFs |
| 2 | 🧠 **Skill Extraction** | Rule-based NLP with alias normalization across 65+ canonical skills (e.g. `JS` → `JavaScript`) |
| 3 | 🎯 **Skill Gap Analysis** | Classifies every role requirement as matched, partially matched, or missing |
| 4 | 📊 **Readiness Score** | Transparent weighted coverage score (0–100) with full formula and per-skill contributions |
| 5 | 🗺️ **Learning Roadmap** | 4-stage personalized plan with curated free resources and mini-project prompts |
| 6 | 📝 **Resume Feedback** | Keyword gap detection, weak verb suggestions, and section-level improvement tips |
| 7 | ⚖️ **Role Comparison** | Side-by-side comparison of up to 3 career paths with shared/unique skill breakdown |
| 8 | 🧪 **Skill Assessment** | Multiple-choice quizzes for 6 core skills to add verified evidence to your profile |
| 9 | 📈 **Progress Tracking** | Mark roadmap tasks as in-progress or complete; view score history over time |
| 10 | 📥 **PDF Export** | Download a professionally styled, multi-page PDF report with cover page and all sections |

---

## 🎓 Supported Career Roles

<table>
<tr>
  <td>💻 Software Developer</td>
  <td>📊 Data Analyst</td>
  <td>🔬 Data Scientist</td>
</tr>
<tr>
  <td>🤖 Machine Learning Engineer</td>
  <td>🎨 Frontend Developer</td>
  <td>⚙️ Backend Developer</td>
</tr>
<tr>
  <td>🌐 Full-Stack Developer</td>
  <td>🔒 Cybersecurity Analyst</td>
  <td>☁️ Cloud Engineer</td>
</tr>
</table>

Each role includes weighted mandatory and preferred skills, importance reasons, tools, and an experience note — all editable in `data/job_roles.json`.

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.9+**
- **pip**

### 1 — Clone & install

```bash
git clone <your-repo-url>
cd skillbridge-ai
pip install -r requirements.txt
```

### 2 — Launch the app

```bash
streamlit run app.py
```

Opens at **http://localhost:8501** in your browser. No internet connection required for core analysis.

### 3 — Run the test suite

```bash
pytest tests/ -v
```

---

## 🗂️ Project Structure

```
skillbridge-ai/
│
├── 📄 app.py                        ← Streamlit app (10 pages)
├── ⚙️  config.py                    ← Paths, weights, constants
├── 📋 requirements.txt
├── 📖 README.md
│
├── 📁 data/
│   ├── job_roles.json               ← 9 roles with weighted skills & reasons
│   ├── skills_dictionary.json       ← 65+ skills with all known aliases
│   └── learning_resources.json      ← Curated free resources + mini-projects
│
├── 📁 modules/
│   ├── resume_parser.py             ← PDF & DOCX text extraction
│   ├── skill_extractor.py           ← Alias matching, normalization & quiz engine
│   ├── job_analyzer.py              ← Role loader & job description parser
│   ├── skill_matcher.py             ← Exact / partial / missing skill matching
│   ├── readiness_score.py           ← Weighted coverage score (0–100)
│   ├── recommendation_engine.py     ← 4-stage roadmap generator
│   ├── resume_feedback.py           ← Resume improvement suggestions
│   ├── progress_tracker.py          ← Roadmap progress & history
│   └── pdf_report.py                ← Professional PDF report builder (ReportLab)
│
├── 📁 database/
│   └── db.py                        ← SQLite schema & CRUD (8 tables)
│
├── 📁 tests/
│   ├── test_resume_parser.py
│   ├── test_skill_matching.py
│   ├── test_readiness_score.py
│   └── test_recommendations.py
│
└── 📁 exports/                      ← Downloaded PDF/CSV reports
```

---

## ⚙️ How It Works

```
 ┌─────────────────────────────────────────────────────────────────┐
 │                        SkillBridge AI Pipeline                  │
 └─────────────────────────────────────────────────────────────────┘

  📄 Resume Upload / Manual Profile Input
          │
          ▼
  📝 Document Text Extraction        ← resume_parser.py
          │                             (pdfplumber / python-docx)
          ▼
  🔍 Skill Extraction & Normalization ← skill_extractor.py
          │                             (alias lookup, 65+ skills)
          ▼
  👤 Candidate Profile Review        ← app.py  ·  My Profile page
          │
          ▼
  📋 Job Role / JD Analysis          ← job_analyzer.py
          │                             (9 built-in roles or pasted JD)
          ▼
  🎯 Skill Matching & Gap Analysis   ← skill_matcher.py
          │                             (exact / partial / missing)
          ▼
  📊 Career Readiness Score          ← readiness_score.py
          │                             (weighted formula, 0–100)
          ▼
  🗺️  Personalized Learning Roadmap  ← recommendation_engine.py
          │                             (4 stages, curated resources)
          ▼
  📈 Dashboard & Progress Tracking   ← app.py  ·  progress_tracker.py
          │
          ▼
  📥 Professional PDF Report Export  ← pdf_report.py  (ReportLab)
```

### Skill Matching in Detail

The system uses **explicit rule-based matching**, not text-embedding similarity, to prevent false technological equivalences:

| Match Type | Meaning | Example |
|---|---|---|
| ✅ **Exact** | Skill is directly on your profile | `Python` required → you have `Python` |
| 🔶 **Partial** | A related skill provides some coverage | `Docker` in profile → partial credit for `Kubernetes` |
| ❌ **Missing** | Skill is absent with no related evidence | No `SQL` anywhere in profile |

> `Python` and `Java` are **never** treated as equivalent — they share an ecosystem label but are distinct technologies.

---

## 📐 Readiness Score Formula

The score is **fully transparent** — the formula and every skill's contribution are shown in the app and the PDF report.

```
Readiness Score = 100 ×

  [ 1.0 × (mandatory_covered_weight ÷ mandatory_total_weight)
  + 0.4 × (preferred_covered_weight ÷ preferred_total_weight) ]

  ÷ 1.4
```

| Rule | Value |
|---|---|
| Partial match contribution | 50% of the skill's weight |
| Mandatory tier weight | 1.0 |
| Preferred tier weight | 0.4 |
| Score range | 0 – 100 |

**Score bands:**

| Band | Range | Meaning |
|---|---|---|
| 🟢 Excellent | 80 – 100 | Strong coverage; focus on projects & interview prep |
| 🔵 Good | 60 – 79 | Solid foundation; address remaining mandatory gaps |
| 🟡 Developing | 40 – 59 | Notable gaps; follow the roadmap |
| 🔴 Beginner | 0 – 39 | Building from the ground up; structured roadmap available |

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| **UI / App** | [Streamlit](https://streamlit.io) |
| **Language** | Python 3.9+ |
| **Resume Parsing** | [pdfplumber](https://github.com/jsvine/pdfplumber), [python-docx](https://python-docx.readthedocs.io) |
| **Data** | [pandas](https://pandas.pydata.org), [NumPy](https://numpy.org) |
| **Visualization** | [Plotly](https://plotly.com/python/) |
| **ML / Matching** | scikit-learn, rule-based NLP (no GPU required) |
| **PDF Generation** | [ReportLab](https://www.reportlab.com) |
| **Database** | SQLite (stdlib `sqlite3`) |
| **Testing** | [pytest](https://pytest.org) |

Everything runs **locally on a standard student laptop** — no GPU, no paid APIs, no continuous internet access.

---

## 🌍 SDG Alignment

<table>
<tr>
  <td width="80" align="center"><b>SDG 8</b></td>
  <td><b>Decent Work and Economic Growth</b></td>
</tr>
<tr>
  <td align="center">8.5</td>
  <td>Promote productive employment and decent work for all, including young people</td>
</tr>
<tr>
  <td align="center">8.6</td>
  <td>Reduce the proportion of young people not in employment, education, or training</td>
</tr>
</table>

SkillBridge AI supports these targets by helping students **identify competency gaps** and **plan professional development** before entering the job market. The platform does not claim to directly reduce unemployment — it is a guidance and self-assessment tool.

---

## 🎬 Sample Walkthrough

Follow this 10-step demo to see every feature in action:

```
Step 1  →  streamlit run app.py
Step 2  →  My Profile         Create a profile: "Demo Student", BSc Computer Science
Step 3  →  My Profile         Add skills: Python, SQL, pandas, Git
Step 4  →  Resume Upload      Upload a PDF resume (optional)
Step 5  →  Gap Analysis       Select "Data Scientist" → Run Skill Gap Analysis
Step 6  →  Dashboard          View the readiness gauge, matched/missing skills, history
Step 7  →  Learning Roadmap   Mark "Statistics" as in_progress
Step 8  →  Skill Assessment   Take the Python quiz to verify your level
Step 9  →  Role Comparison    Compare "Data Scientist" vs "Data Analyst"
Step 10 →  Export Report      Download the professional PDF report
```

---

## ⚠️ Known Limitations

| # | Limitation | Detail |
|---|---|---|
| 1 | **Scanned PDFs** | Text cannot be extracted from image-based PDFs; enter skills manually instead |
| 2 | **Unrecognized skills** | Skills outside the 65-skill dictionary are stored as-is but not role-matched |
| 3 | **Self-reported skills** | The system cannot independently verify claimed skills |
| 4 | **Quiz coverage** | Quiz-based verification is available for 6 skills only |
| 5 | **Role descriptions** | Built-in descriptions are representative examples, not current live vacancies |
| 6 | **DOCX text boxes** | Floating text boxes in DOCX files are not accessible via python-docx |
| 7 | **Score scope** | Readiness score covers technical skill gaps only — not soft skills, cultural fit, or interview performance |

---

## 📄 License

This project was developed for academic demonstration purposes under a university major-project brief. All external learning resources linked within the application are the property of their respective owners and platforms.

---

<div align="center">

**Built with Python · Streamlit · ReportLab · SQLite**

*Aligned with the United Nations Sustainable Development Goal 8*
*— Decent Work and Economic Growth —*

</div>
