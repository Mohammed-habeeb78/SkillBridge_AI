"""
modules/pdf_report.py — Generate a professional PDF career readiness report.

Uses ReportLab (pure-Python, no headless browser required).
Returns the PDF as bytes so Streamlit can serve it with st.download_button.

Layout:
  Page 1  — Cover: name, role, score, date, band
  Page 2  — Candidate Profile & Skills Summary
  Page 3  — Skill Gap Analysis (matched / partial / missing)
  Page 4+ — Personalized Learning Roadmap (multi-page)
  Last    — Limitations & Disclaimer
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Dict, List, Optional

# ── ReportLab imports ─────────────────────────────────────────────────────────
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    HRFlowable,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.frames import Frame

# ── Palette ───────────────────────────────────────────────────────────────────
_NAVY   = colors.HexColor("#1e3a5f")
_BLUE   = colors.HexColor("#3b82d4")
_LIGHT  = colors.HexColor("#dbeafe")
_GREEN  = colors.HexColor("#065f46")
_GREEN_BG = colors.HexColor("#d1fae5")
_AMBER  = colors.HexColor("#92400e")
_AMBER_BG = colors.HexColor("#fef3c7")
_RED    = colors.HexColor("#991b1b")
_RED_BG = colors.HexColor("#fee2e2")
_GRAY   = colors.HexColor("#57606a")
_BORDER = colors.HexColor("#e5e7eb")
_WHITE  = colors.white
_BLACK  = colors.HexColor("#1f2328")

PAGE_W, PAGE_H = A4
MARGIN = 2 * cm


# ── Style registry ────────────────────────────────────────────────────────────

def _styles():
    base = getSampleStyleSheet()
    s = {}

    s["cover_title"] = ParagraphStyle(
        "cover_title", fontName="Helvetica-Bold",
        fontSize=28, textColor=_WHITE, leading=34, alignment=TA_CENTER,
    )
    s["cover_subtitle"] = ParagraphStyle(
        "cover_subtitle", fontName="Helvetica",
        fontSize=13, textColor=_LIGHT, leading=18, alignment=TA_CENTER,
    )
    s["cover_meta"] = ParagraphStyle(
        "cover_meta", fontName="Helvetica",
        fontSize=10, textColor=_LIGHT, leading=14, alignment=TA_CENTER,
    )
    s["cover_score"] = ParagraphStyle(
        "cover_score", fontName="Helvetica-Bold",
        fontSize=52, textColor=_WHITE, leading=58, alignment=TA_CENTER,
    )
    s["cover_score_label"] = ParagraphStyle(
        "cover_score_label", fontName="Helvetica",
        fontSize=11, textColor=_LIGHT, leading=14, alignment=TA_CENTER,
    )
    s["h1"] = ParagraphStyle(
        "h1", fontName="Helvetica-Bold",
        fontSize=16, textColor=_NAVY, leading=22, spaceBefore=14, spaceAfter=6,
    )
    s["h2"] = ParagraphStyle(
        "h2", fontName="Helvetica-Bold",
        fontSize=12, textColor=_NAVY, leading=16, spaceBefore=10, spaceAfter=4,
    )
    s["body"] = ParagraphStyle(
        "body", fontName="Helvetica",
        fontSize=9.5, textColor=_BLACK, leading=14, spaceAfter=4,
    )
    s["body_bold"] = ParagraphStyle(
        "body_bold", fontName="Helvetica-Bold",
        fontSize=9.5, textColor=_BLACK, leading=14, spaceAfter=4,
    )
    s["small"] = ParagraphStyle(
        "small", fontName="Helvetica",
        fontSize=8, textColor=_GRAY, leading=12, spaceAfter=2,
    )
    s["bullet"] = ParagraphStyle(
        "bullet", fontName="Helvetica",
        fontSize=9.5, textColor=_BLACK, leading=14,
        leftIndent=14, bulletIndent=4, spaceAfter=3,
    )
    s["tag_green"] = ParagraphStyle(
        "tag_green", fontName="Helvetica-Bold",
        fontSize=8.5, textColor=_GREEN, leading=12,
    )
    s["tag_amber"] = ParagraphStyle(
        "tag_amber", fontName="Helvetica-Bold",
        fontSize=8.5, textColor=_AMBER, leading=12,
    )
    s["tag_red"] = ParagraphStyle(
        "tag_red", fontName="Helvetica-Bold",
        fontSize=8.5, textColor=_RED, leading=12,
    )
    s["disclaimer"] = ParagraphStyle(
        "disclaimer", fontName="Helvetica-Oblique",
        fontSize=8, textColor=_GRAY, leading=12, spaceAfter=4,
    )
    s["footer"] = ParagraphStyle(
        "footer", fontName="Helvetica",
        fontSize=7, textColor=_GRAY, leading=10, alignment=TA_CENTER,
    )
    return s


# ── Page templates ────────────────────────────────────────────────────────────

def _cover_background(canvas, doc):
    """Draw the navy cover gradient background."""
    canvas.saveState()
    canvas.setFillColor(_NAVY)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # Accent bar at bottom
    canvas.setFillColor(_BLUE)
    canvas.rect(0, 0, PAGE_W, 1.5 * cm, fill=1, stroke=0)
    canvas.restoreState()


def _page_header_footer(canvas, doc):
    """Draw header and footer on content pages."""
    canvas.saveState()
    # Top bar
    canvas.setFillColor(_NAVY)
    canvas.rect(0, PAGE_H - 1.2 * cm, PAGE_W, 1.2 * cm, fill=1, stroke=0)
    canvas.setFillColor(_WHITE)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(MARGIN, PAGE_H - 0.8 * cm, "SkillBridge AI — Career Readiness Report")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.8 * cm,
                           datetime.now().strftime("%d %b %Y"))
    # Bottom bar
    canvas.setFillColor(_BORDER)
    canvas.rect(0, 0, PAGE_W, 0.8 * cm, fill=1, stroke=0)
    canvas.setFillColor(_GRAY)
    canvas.setFont("Helvetica", 7)
    canvas.drawCentredString(
        PAGE_W / 2, 0.25 * cm,
        f"Page {doc.page}  |  Indicative skills-coverage report only — not an employment predictor",
    )
    canvas.restoreState()


# ── Section helpers ───────────────────────────────────────────────────────────

def _hr(story):
    story.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER, spaceAfter=6))


def _section_heading(story, text, styles):
    story.append(Paragraph(text, styles["h1"]))
    _hr(story)


def _skill_badge_table(skills: List[str], tag_style, styles) -> Table:
    """Render a list of skills as a flowing badge-style table row."""
    if not skills:
        return Table([[Paragraph("None", styles["small"])]])

    # Wrap every badge in a coloured box via a mini-Table
    cells = []
    row = []
    for i, label in enumerate(skills):
        cell = Table(
            [[Paragraph(label, tag_style)]],
            colWidths=[None],
        )
        cell.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1),
             _GREEN_BG if tag_style == styles["tag_green"] else
             _AMBER_BG if tag_style == styles["tag_amber"] else _RED_BG),
            ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        row.append(cell)
        if len(row) == 4:
            cells.append(row)
            row = []
    if row:
        while len(row) < 4:
            row.append("")
        cells.append(row)

    t = Table(cells, colWidths=[(PAGE_W - 2 * MARGIN) / 4] * 4)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def _score_bar(story, score: float, styles):
    """Render a visual progress bar for the score."""
    bar_width = PAGE_W - 2 * MARGIN
    filled = bar_width * (score / 100)

    if score >= 80:
        bar_color = colors.HexColor("#10b981")
    elif score >= 60:
        bar_color = colors.HexColor("#3b82d4")
    elif score >= 40:
        bar_color = colors.HexColor("#f59e0b")
    else:
        bar_color = colors.HexColor("#ef4444")

    bar_table = Table(
        [["", ""]],
        colWidths=[filled, bar_width - filled],
        rowHeights=[12],
    )
    bar_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), bar_color),
        ("BACKGROUND", (1, 0), (1, 0), _BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(bar_table)
    story.append(Spacer(1, 4))


# ══════════════════════════════════════════════════════════════════════════════
# Main builder
# ══════════════════════════════════════════════════════════════════════════════

def build_pdf_report(
    user: Dict,
    skills: List[Dict],
    gap: Dict,
    score: Dict,
    roadmap: Dict,
    feedback: Optional[Dict] = None,
) -> bytes:
    """
    Build a professional PDF report and return it as bytes.

    Args:
        user:     db.get_user() dict
        skills:   db.get_user_skills() list
        gap:      skill_matcher.analyze_skill_gap() dict
        score:    readiness_score.calculate_readiness_score() dict
        roadmap:  recommendation_engine.generate_roadmap() dict
        feedback: resume_feedback.generate_resume_feedback() dict (optional)

    Returns:
        PDF bytes suitable for st.download_button().
    """
    buf = io.BytesIO()
    styles = _styles()

    # ── Document setup ────────────────────────────────────────────────────────
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN + 0.5 * cm,
        bottomMargin=MARGIN,
        title="SkillBridge AI — Career Readiness Report",
        author=user.get("display_name", "Candidate"),
    )

    cover_frame = Frame(0, 0, PAGE_W, PAGE_H, id="cover_frame")
    content_frame = Frame(
        MARGIN, MARGIN,
        PAGE_W - 2 * MARGIN,
        PAGE_H - 2 * MARGIN - 1.2 * cm,  # leave room for header
        id="content_frame",
    )

    doc.addPageTemplates([
        PageTemplate(id="Cover", frames=[cover_frame], onPage=_cover_background),
        PageTemplate(id="Content", frames=[content_frame], onPage=_page_header_footer),
    ])

    story = []

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 1 — Cover
    # ══════════════════════════════════════════════════════════════════════════
    story.append(NextPageTemplate("Cover"))
    story.append(Spacer(1, 3.5 * cm))

    story.append(Paragraph("SkillBridge AI", styles["cover_title"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Career Readiness Report", styles["cover_subtitle"]))
    story.append(Spacer(1, 2 * cm))

    # Score circle (simulated with large bold number)
    story.append(Paragraph(f"{score['score']}", styles["cover_score"]))
    story.append(Paragraph("out of 100", styles["cover_score_label"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        f"Readiness Band: <b>{score['band']}</b>",
        styles["cover_subtitle"],
    ))
    story.append(Spacer(1, 2.5 * cm))

    # Candidate details
    name = user.get("display_name", "—")
    role_title = gap.get("role_title", "—")
    degree = " | ".join(filter(None, [
        user.get("education_level", ""),
        user.get("degree", ""),
        user.get("branch", ""),
        str(user.get("graduation_year", "")) if user.get("graduation_year") else "",
    ]))
    story.append(Paragraph(name, styles["cover_subtitle"]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(f"Target Role: <b>{role_title}</b>", styles["cover_meta"]))
    if degree:
        story.append(Paragraph(degree, styles["cover_meta"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%d %B %Y')}",
        styles["cover_meta"],
    ))
    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph(
        "Aligned with SDG 8 — Decent Work and Economic Growth",
        styles["cover_meta"],
    ))

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 2 — Profile & Score Detail
    # ══════════════════════════════════════════════════════════════════════════
    story.append(NextPageTemplate("Content"))
    story.append(PageBreak())

    _section_heading(story, "1. Candidate Profile", styles)

    profile_data = [
        ["Name", user.get("display_name", "—")],
        ["Education Level", user.get("education_level", "—") or "—"],
        ["Degree / Programme", user.get("degree", "—") or "—"],
        ["Branch / Specialization", user.get("branch", "—") or "—"],
        ["Graduation Year", str(user.get("graduation_year", "—")) if user.get("graduation_year") else "—"],
        ["Total Skills on Profile", str(len(skills))],
        ["Target Career Role", gap.get("role_title", "—")],
        ["Report Date", datetime.now().strftime("%d %B %Y")],
    ]
    profile_table = Table(
        profile_data,
        colWidths=[5.5 * cm, PAGE_W - 2 * MARGIN - 5.5 * cm],
    )
    profile_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), _NAVY),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_WHITE, colors.HexColor("#f7f8fa")]),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(profile_table)
    story.append(Spacer(1, 0.5 * cm))

    # Score detail
    _section_heading(story, "2. Readiness Score Summary", styles)

    story.append(Paragraph(
        f"<b>Overall Score: {score['score']} / 100 — {score['band']}</b>",
        styles["body_bold"],
    ))
    story.append(Spacer(1, 3))
    _score_bar(story, score["score"], styles)

    score_data = [
        ["Metric", "Value"],
        ["Overall Readiness Score", f"{score['score']} / 100"],
        ["Mandatory Skills Score", f"{score['mandatory_score']} / 100"],
        ["Preferred Skills Score", f"{score['preferred_score']} / 100"],
        ["Mandatory Skills Covered Weight", f"{score['mandatory_covered_weight']:.2f} / {score['mandatory_total_weight']:.2f}"],
        ["Preferred Skills Covered Weight", f"{score['preferred_covered_weight']:.2f} / {score['preferred_total_weight']:.2f}"],
        ["Skills Matched (exact)", str(gap["summary"]["matched_count"])],
        ["Skills Partially Matched", str(gap["summary"]["partial_count"])],
        ["Skills Missing", str(gap["summary"]["missing_count"])],
    ]
    score_table = Table(
        score_data,
        colWidths=[9 * cm, PAGE_W - 2 * MARGIN - 9 * cm],
    )
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_WHITE, colors.HexColor("#f7f8fa")]),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(score["band_description"], styles["body"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"<i>Formula: {score['formula_explanation']}</i>", styles["small"]))

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 3 — Skill Gap Analysis
    # ══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    _section_heading(story, "3. Skill Gap Analysis", styles)

    # Matched skills
    story.append(Paragraph("[Matched]  Matched Skills", styles["h2"]))
    matched_all = gap["mandatory_match"] + gap["preferred_match"]
    if matched_all:
        matched_data = [["Skill", "Tier", "Weight", "Match"]]
        for s in matched_all:
            tier = "Mandatory" if s.get("mandatory", True) else "Preferred"
            matched_data.append([
                s["skill_label"], tier, f"{s['weight']:.2f}", "Exact ✓",
            ])
        mt = Table(matched_data, colWidths=[7 * cm, 3 * cm, 2 * cm, 3 * cm])
        mt.setStyle(_gap_table_style(_GREEN))
        story.append(mt)
    else:
        story.append(Paragraph("No matched skills found.", styles["body"]))
    story.append(Spacer(1, 0.4 * cm))

    # Partial matches
    partial_all = gap["mandatory_partial"] + gap["preferred_partial"]
    if partial_all:
        story.append(Paragraph("[Partial]  Partially Matched Skills", styles["h2"]))
        partial_data = [["Skill", "Tier", "Weight", "Matched Via"]]
        for s in partial_all:
            tier = "Mandatory" if s.get("mandatory", True) else "Preferred"
            via = ", ".join(s.get("matched_by", []))
            partial_data.append([s["skill_label"], tier, f"{s['weight']:.2f}", via])
        pt = Table(partial_data, colWidths=[7 * cm, 3 * cm, 2 * cm, 3 * cm])
        pt.setStyle(_gap_table_style(colors.HexColor("#f59e0b")))
        story.append(pt)
        story.append(Spacer(1, 0.4 * cm))

    # Missing mandatory
    story.append(Paragraph("[Missing]  Missing Mandatory Skills", styles["h2"]))
    if gap["mandatory_missing"]:
        miss_data = [["Skill", "Weight", "Why It Matters"]]
        for s in gap["mandatory_missing"]:
            miss_data.append([
                s["skill_label"],
                f"{s['weight']:.2f}",
                Paragraph(s.get("reason", "")[:120], styles["small"]),
            ])
        miss_table = Table(miss_data, colWidths=[5 * cm, 2 * cm, PAGE_W - 2 * MARGIN - 7 * cm])
        miss_table.setStyle(_gap_table_style(colors.HexColor("#ef4444")))
        story.append(miss_table)
    else:
        story.append(Paragraph(
            "All mandatory skills are covered — excellent!", styles["body"]
        ))
    story.append(Spacer(1, 0.4 * cm))

    # Missing preferred
    if gap["preferred_missing"]:
        story.append(Paragraph("[Optional]  Missing Preferred Skills", styles["h2"]))
        pref_miss_data = [["Skill", "Weight"]]
        for s in gap["preferred_missing"]:
            pref_miss_data.append([s["skill_label"], f"{s['weight']:.2f}"])
        pmt = Table(pref_miss_data, colWidths=[10 * cm, 5 * cm])
        pmt.setStyle(_gap_table_style(_GRAY))
        story.append(pmt)

    # ══════════════════════════════════════════════════════════════════════════
    # PAGES 4+ — Learning Roadmap
    # ══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    _section_heading(story, "4. Personalized Learning Roadmap", styles)

    story.append(Paragraph(roadmap["summary"], styles["body"]))
    story.append(Spacer(1, 0.3 * cm))

    for stage in roadmap.get("stages", []):
        story.append(Paragraph(stage["label"], styles["h2"]))
        story.append(Paragraph(stage["description"], styles["small"]))
        story.append(Spacer(1, 0.2 * cm))

        for task in stage["tasks"]:
            if task.get("match_type") == "stage4":
                # Stage 4 meta-tasks
                story.append(Paragraph(f">> {task['skill_label']}", styles["body_bold"]))
                story.append(Paragraph(task.get("reason", ""), styles["small"]))
                story.append(Spacer(1, 0.15 * cm))
                continue

            # Task row
            task_data = [
                [
                    Paragraph(f"<b>{task['skill_label']}</b>", styles["body_bold"]),
                    Paragraph(
                        f"~{task['estimated_hours']}h  |  "
                        f"{'Mandatory' if task.get('mandatory') else 'Preferred'}",
                        styles["small"],
                    ),
                ],
                [
                    Paragraph(task.get("reason", "")[:200], styles["small"]),
                    "",
                ],
            ]
            if task.get("resources"):
                res = task["resources"][0]
                task_data.append([
                    Paragraph(
                        f"Resource: <a href='{res['url']}'>{res['title']}</a> ({res['platform']})",
                        styles["small"],
                    ),
                    "",
                ])
            if task.get("mini_project"):
                task_data.append([
                    Paragraph(f"Mini-project: {task['mini_project'][:160]}", styles["small"]),
                    "",
                ])

            task_table = Table(
                task_data,
                colWidths=[PAGE_W - 2 * MARGIN - 3.5 * cm, 3.5 * cm],
            )
            # Build TableStyle commands; SPAN rows conditionally to avoid
            # ReportLab errors when the row index doesn't exist.
            task_style_cmds = [
                ("BACKGROUND", (0, 0), (-1, 0),
                 _LIGHT if task.get("mandatory") else colors.HexColor("#f7f8fa")),
                ("SPAN", (0, 1), (-1, 1)),
                ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
            if len(task_data) > 2:
                task_style_cmds.append(("SPAN", (0, 2), (-1, 2)))
            if len(task_data) > 3:
                task_style_cmds.append(("SPAN", (0, 3), (-1, 3)))
            task_table.setStyle(TableStyle(task_style_cmds))
            story.append(task_table)
            story.append(Spacer(1, 4))

        story.append(Spacer(1, 0.3 * cm))

    # ══════════════════════════════════════════════════════════════════════════
    # Resume feedback section (if available)
    # ══════════════════════════════════════════════════════════════════════════
    if feedback:
        story.append(PageBreak())
        _section_heading(story, "5. Resume Improvement Suggestions", styles)

        story.append(Paragraph(feedback.get("overall_feedback", ""), styles["body"]))
        story.append(Spacer(1, 0.3 * cm))

        if feedback.get("positive_observations"):
            story.append(Paragraph("Strengths Observed", styles["h2"]))
            for obs in feedback["positive_observations"]:
                story.append(Paragraph(f"• {obs}", styles["bullet"]))

        if feedback.get("keyword_gaps"):
            story.append(Paragraph("Missing Role Keywords", styles["h2"]))
            story.append(Paragraph(
                "These high-importance role keywords were not found in your resume:",
                styles["body"],
            ))
            for kw in feedback["keyword_gaps"]:
                story.append(Paragraph(f"• {kw}", styles["bullet"]))

        if feedback.get("missing_from_resume"):
            story.append(Paragraph("Skills Confirmed But Not On Resume", styles["h2"]))
            for item in feedback["missing_from_resume"]:
                story.append(Paragraph(f"• <b>{item['skill_label']}:</b> {item['suggestion']}", styles["bullet"]))

        if feedback.get("weak_phrase_instances"):
            story.append(Paragraph("Weak Phrase Suggestions", styles["h2"]))
            for item in feedback["weak_phrase_instances"][:5]:
                story.append(Paragraph(
                    f"• Replace '<i>{item['original_phrase']}</i>': {item['suggestion']}",
                    styles["bullet"],
                ))

        if feedback.get("project_suggestions"):
            story.append(Paragraph("Suggested Portfolio Projects", styles["h2"]))
            for proj in feedback["project_suggestions"]:
                story.append(Paragraph(f"• {proj}", styles["bullet"]))

        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(feedback.get("disclaimer", ""), styles["disclaimer"]))

    # ══════════════════════════════════════════════════════════════════════════
    # Last page — Limitations & Disclaimer
    # ══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    _section_heading(story, "Limitations & Disclaimer", styles)

    limitations = [
        "This report is based on skills you have self-reported or that were detected in your resume. They have not been independently verified.",
        "Job role requirements are representative examples compiled from public career guidance sources, not current verified vacancies.",
        "The Readiness Score is an indicative skills-coverage measure. It is NOT a validated predictor of hiring success or employability.",
        "Scanned PDFs and DOCX text boxes cannot be parsed automatically; skills inside them may have been missed.",
        "Skills not found in the SkillBridge AI skills dictionary are stored as-is but are not matched against job requirements.",
        "The score reflects technical skill coverage only. Soft skills, communication ability, cultural fit, and interview performance are not assessed.",
        "Partial matches indicate related knowledge, not confirmed competency in the required skill.",
    ]
    for lim in limitations:
        story.append(Paragraph(f"• {lim}", styles["bullet"]))

    story.append(Spacer(1, 0.5 * cm))
    _hr(story)
    story.append(Paragraph(
        "SkillBridge AI is aligned with <b>SDG 8 — Decent Work and Economic Growth</b>. "
        "It supports Target 8.5 (productive employment for all) and Target 8.6 (reducing youth "
        "unemployment) by helping students identify competency gaps and plan professional development.",
        styles["body"],
    ))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        f"Report generated by SkillBridge AI v1.0.0 on {datetime.now().strftime('%d %B %Y at %H:%M UTC')}",
        styles["footer"],
    ))

    # ── Build ─────────────────────────────────────────────────────────────────
    doc.build(story)
    return buf.getvalue()


# ── Table style factory ───────────────────────────────────────────────────────

def _gap_table_style(header_color):
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_WHITE, colors.HexColor("#f7f8fa")]),
        ("GRID", (0, 0), (-1, -1), 0.4, _BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ])
