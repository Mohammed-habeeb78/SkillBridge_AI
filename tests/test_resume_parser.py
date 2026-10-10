"""
tests/test_resume_parser.py — Unit tests for resume_parser.py
"""
import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from modules.resume_parser import _clean_text, detect_sections, _match_header, parse_resume


class TestCleanText:
    def test_removes_nbsp(self):
        result = _clean_text("Hello\xa0World")
        assert "\xa0" not in result
        assert "Hello World" in result

    def test_collapses_extra_spaces(self):
        result = _clean_text("too    many   spaces")
        assert "too many spaces" in result

    def test_preserves_newlines(self):
        result = _clean_text("line one\nline two")
        assert "\n" in result

    def test_removes_excess_blank_lines(self):
        text = "a\n\n\n\nb"
        result = _clean_text(text)
        # Should have at most one blank line between a and b
        assert result.count("\n\n\n") == 0

    def test_empty_input(self):
        assert _clean_text("") == ""

    def test_strips_leading_trailing(self):
        result = _clean_text("   hello   ")
        assert result == "hello"


class TestSectionDetection:
    def test_skills_section_detected(self):
        text = "Skills\nPython\nJavaScript\n\nEducation\nBSc Computer Science"
        sections = detect_sections(text)
        assert "skills" in sections
        assert "Python" in sections["skills"]

    def test_education_section_detected(self):
        text = "Education\nBSc Computer Science, 2023"
        sections = detect_sections(text)
        assert "education" in sections

    def test_experience_section_detected(self):
        text = "Work Experience\nIntern at XYZ Corp"
        sections = detect_sections(text)
        assert "experience" in sections

    def test_unknown_content_in_other(self):
        text = "John Doe\njohn@example.com\n+91 9999999999"
        sections = detect_sections(text)
        # Contact info should fall to 'other' or summary
        assert "other" in sections or "summary" in sections

    def test_empty_text(self):
        sections = detect_sections("")
        assert isinstance(sections, dict)


class TestMatchHeader:
    def test_skills_header(self):
        assert _match_header("Skills") == "skills"
        assert _match_header("Technical Skills") == "skills"
        assert _match_header("SKILLS:") == "skills"

    def test_education_header(self):
        assert _match_header("Education") == "education"
        assert _match_header("EDUCATION") == "education"

    def test_projects_header(self):
        assert _match_header("Projects") == "projects"
        assert _match_header("Academic Projects") == "projects"

    def test_not_a_header(self):
        assert _match_header("I have strong Python skills") is None
        assert _match_header("") is None

    def test_long_line_not_header(self):
        long_line = "This is a long description that definitely is not a section header at all"
        assert _match_header(long_line) is None


class TestParseResumeDispatcher:
    def test_unsupported_format(self):
        result = parse_resume(b"content", "resume.txt")
        assert result["success"] is False
        assert ".txt" in result["warnings"][0]

    def test_empty_pdf_bytes_fails_gracefully(self):
        result = parse_resume(b"", "resume.pdf")
        # Should fail gracefully, not raise
        assert result["success"] is False
        assert len(result["warnings"]) > 0

    def test_empty_docx_bytes_fails_gracefully(self):
        result = parse_resume(b"", "resume.docx")
        assert result["success"] is False
        assert len(result["warnings"]) > 0

    def test_extension_preserved_in_result(self):
        result = parse_resume(b"", "test.pdf")
        assert result["extension"] == ".pdf"

    def test_filename_preserved_in_result(self):
        result = parse_resume(b"", "myresume.docx")
        assert result["filename"] == "myresume.docx"
