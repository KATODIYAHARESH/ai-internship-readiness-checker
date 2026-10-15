"""Resume parsing: PDF/text -> skills, section estimates and quality tips.

Everything here is offline and deterministic (regular expressions over the
alias table in ``catalog.json``), so it works on a laptop without internet.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import BinaryIO

from .catalog import skills_info

logger = logging.getLogger(__name__)

MAX_PDF_BYTES = 10 * 1024 * 1024
BULLETS = ("-", "*", "•", "▪", "●", "◦", "–", "·")

SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "education": ("education", "academics", "academic background", "qualifications"),
    "skills": ("skills", "technical skills", "key skills", "core competencies", "tech stack"),
    "projects": ("projects", "academic projects", "personal projects", "key projects", "project work"),
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "internships",
        "internship experience",
        "employment",
        "work history",
    ),
    "certifications": (
        "certifications",
        "certificates",
        "licenses & certifications",
        "courses",
        "training",
        "courses and certifications",
    ),
    "other": ("summary", "objective", "profile", "achievements", "awards", "activities", "extracurriculars", "interests", "languages", "references", "publications"),
}


class ResumeParseError(ValueError):
    """Raised when a resume file cannot be read (message is user-friendly)."""


@dataclass(frozen=True)
class ResumeInsights:
    """What we learned from a resume."""

    skills: tuple[str, ...] = ()
    projects: int = 0
    internships: int = 0
    certifications: int = 0
    cgpa: float | None = None
    word_count: int = 0
    sections: tuple[str, ...] = ()
    tips: tuple[str, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #
def extract_text_from_pdf(source: bytes | BinaryIO) -> str:
    """Extract text from a PDF given as bytes or a binary file-like object.

    Raises:
        ResumeParseError: for empty, encrypted, scanned/image-only or corrupt PDFs.
    """
    try:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise ResumeParseError("PDF support needs `pypdf` (pip install pypdf). Paste the text instead.") from exc

    data = source if isinstance(source, bytes) else source.read()
    if not data:
        raise ResumeParseError("The uploaded file is empty.")
    if len(data) > MAX_PDF_BYTES:
        raise ResumeParseError("PDF is larger than 10 MB. Please upload a smaller file or paste the text.")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:  # noqa: BLE001 - pypdf raises several types
                raise ResumeParseError("This PDF is password protected. Remove the password and retry.") from exc
        pages = [(page.extract_text() or "") for page in reader.pages]
    except ResumeParseError:
        raise
    except (PyPdfError, ValueError, OSError, KeyError) as exc:
        logger.warning("PDF parse failure: %s", exc)
        raise ResumeParseError("Could not read this PDF. Is it a valid, text-based PDF?") from exc

    text = "\n".join(pages).strip()
    if not text:
        raise ResumeParseError(
            "No selectable text found. The PDF looks scanned (image-only); paste the text instead."
        )
    return text


# --------------------------------------------------------------------------- #
# Skills
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _skill_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    """Compile one regex per canonical skill covering all of its aliases."""
    patterns: list[tuple[str, re.Pattern[str]]] = []
    for name, info in skills_info().items():
        aliases = {name.lower(), *(a.lower() for a in info.aliases)}
        body = "|".join(re.escape(a).replace(r"\ ", r"\s+") for a in sorted(aliases, key=len, reverse=True))
        patterns.append((name, re.compile(rf"(?<![A-Za-z0-9+#.])(?:{body})(?![A-Za-z0-9+#])", re.IGNORECASE)))
    return tuple(patterns)


def extract_skills(text: str) -> list[str]:
    """Return canonical skills mentioned in ``text`` (empty list for empty input)."""
    if not text or not text.strip():
        return []
    return [name for name, pattern in _skill_patterns() if pattern.search(text)]


# --------------------------------------------------------------------------- #
# Sections / counts
# --------------------------------------------------------------------------- #
def _heading_of(line: str) -> str | None:
    cleaned = re.sub(r"[^a-z& ]", "", line.strip().lower()).strip()
    if not cleaned or len(cleaned) > 40:
        return None
    for key, names in SECTION_ALIASES.items():
        if cleaned in names:
            return key
    return None


def split_sections(text: str) -> dict[str, list[str]]:
    """Group non-empty lines under the most recent recognised heading."""
    sections: dict[str, list[str]] = {}
    current = "header"
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        heading = _heading_of(line)
        if heading:
            current = heading
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _count_entries(lines: list[str]) -> int:
    """Estimate entries: non-bullet lines are titles; if all are bullets count bullets."""
    titles = [ln for ln in lines if not ln.startswith(BULLETS) and len(ln) > 3]
    bullets = [ln for ln in lines if ln.startswith(BULLETS)]
    return min(len(titles) or len(bullets), 10)  # capped: PDF line-wrapping can inflate counts


def guess_name(text: str, default: str = "Resume candidate") -> str:
    """Guess the candidate name from the first short line without an email/link."""
    for raw in (text or "").splitlines()[:6]:
        line = raw.strip()
        if line and len(line.split()) <= 4 and not re.search(r"[@/\d:|]", line) and _heading_of(line) is None:
            return line.title() if line.isupper() else line
    return default


def analyze_resume(text: str) -> ResumeInsights:
    """Extract skills, estimate section counts and generate quality tips.

    Estimates are heuristics; the UI lets the student correct them.
    """
    if not text or not text.strip():
        return ResumeInsights()

    sections = split_sections(text)
    skills = extract_skills(text)

    projects = _count_entries(sections.get("projects", []))
    exp_lines = sections.get("experience", [])
    internships = sum(
        1 for ln in exp_lines if re.search(r"\b(intern|internship|trainee|apprentice)\b", ln, re.I) and not ln.startswith(BULLETS)
    )
    if not internships:
        internships = len(re.findall(r"\b\w+\s+intern\b", " ".join(exp_lines), re.I))
    certs = _count_entries(sections.get("certifications", []))
    if not certs:
        certs = len(re.findall(r"\b(certified|certificate|certification)\b", text, re.I))
        certs = min(certs, 6)

    match = re.search(r"\b(?:cgpa|gpa)\s*[:\-]?\s*(\d{1,2}(?:\.\d{1,2})?)", text, re.I)
    cgpa: float | None = None
    if match:
        value = float(match.group(1))
        if 0 < value <= 10:
            cgpa = value

    words = len(re.findall(r"\w+", text))
    found = tuple(k for k in ("education", "skills", "projects", "experience", "certifications") if k in sections)
    tips: list[str] = []
    for key in ("projects", "skills", "education"):
        if key not in found:
            tips.append(f"Add a clear **{key.title()}** section heading so recruiters (and ATS) can find it.")
    if not re.search(r"\d+\s*%|\b\d{2,}\b", text):
        tips.append("Quantify impact (e.g. 'reduced report time by 40%'); no numbers were found.")
    if not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text):
        tips.append("Include a professional email address.")
    if not re.search(r"github\.com|linkedin\.com", text, re.I):
        tips.append("Link your GitHub and LinkedIn profiles.")
    if words < 120:
        tips.append("The resume is very short; expand project descriptions with problem, tools and results.")
    elif words > 900:
        tips.append("The resume is long; internship resumes work best on one page.")
    if len(skills) < 5:
        tips.append("Few recognisable skills were detected. List tools explicitly (e.g. 'Python, SQL, Git').")

    return ResumeInsights(
        skills=tuple(skills),
        projects=projects,
        internships=internships,
        certifications=certs,
        cgpa=cgpa,
        word_count=words,
        sections=found,
        tips=tuple(tips),
    )


SAMPLE_RESUME = """Aarav Mehta
aarav.mehta@example.com | github.com/aaravm | linkedin.com/in/aaravm

SUMMARY
Final-year Computer Science student interested in data and backend roles.

EDUCATION
B.Tech Computer Science, Example University - CGPA: 8.1/10 (2022-2026)

SKILLS
Python, SQL, MySQL, Pandas, NumPy, Excel, Git, GitHub, Matplotlib, Flask, Linux

PROJECTS
Sales Dashboard
- Built an interactive dashboard with Python, Pandas and Plotly for 12k+ orders; cut reporting time by 60%.
Library REST API
- Designed a Flask REST API with SQLite and wrote unit tests with pytest.
Movie Recommender
- Created a content-based recommender with scikit-learn and TF-IDF.

EXPERIENCE
Data Analyst Intern, BrightMart Pvt Ltd (Jun-Aug 2025)
- Automated weekly Excel reports with Python, saving 6 hours per week.

CERTIFICATIONS
Google Data Analytics Certificate
SQL (Advanced) - HackerRank
"""
