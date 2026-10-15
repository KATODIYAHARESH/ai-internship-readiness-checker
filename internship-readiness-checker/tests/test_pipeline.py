"""Smoke tests for seed data, resume parsing, recommendations, mentor fallback and reports."""

from __future__ import annotations

from pathlib import Path

import pytest

from readiness import analytics, database as db
from readiness.llm import ask_mentor, check_ollama, rule_based_reply
from readiness.models import StudentProfile
from readiness.reports import build_markdown_report, build_pdf_report
from readiness.resume import SAMPLE_RESUME, ResumeParseError, analyze_resume, extract_skills, extract_text_from_pdf
from readiness.semantic import match_jobs
from readiness.seed import generate_students
from readiness.service import assess


@pytest.fixture()
def database(tmp_path: Path) -> Path:
    path = tmp_path / "t.db"
    assert db.ensure_database(path, count=80, seed=1) == 80
    return path


def test_seed_generates_80_unique_valid_students(database: Path) -> None:
    df = db.fetch_students_df(database)
    assert len(df) == 80
    assert df["name"].is_unique
    assert df["cgpa"].between(0, 10).all()
    assert df["skills"].map(len).min() >= 0
    assert generate_students(10, 5) == generate_students(10, 5)  # deterministic


def test_campus_analytics(database: Path) -> None:
    scored = analytics.score_dataframe(db.fetch_students_df(database))
    kpis = analytics.campus_kpis(scored)
    assert kpis["students"] == 80
    assert 0 <= kpis["pct_ready"] <= 100
    assert not analytics.top_skill_gaps(scored).empty
    assert (analytics.at_risk_students(scored)["score"] < 50).all()
    assert b"name" in analytics.to_csv_bytes(scored)
    # empty frames never crash
    empty = analytics.score_dataframe(db.fetch_students_df(database).iloc[0:0])
    assert analytics.campus_kpis(empty)["students"] == 0
    assert analytics.by_department(empty).empty


def test_resume_extraction_and_empty_input() -> None:
    skills = extract_skills(SAMPLE_RESUME)
    assert {"Python", "SQL", "Pandas", "Git", "Excel"} <= set(skills)
    noisy = extract_skills("I used GitHub and React.js, the rest of the team used Excel.")
    assert {"Git", "React", "Excel"} <= set(noisy)
    assert "REST APIs" not in noisy  # the English word 'rest' is not a skill
    info = analyze_resume(SAMPLE_RESUME)
    assert info.projects == 3 and info.internships == 1 and info.certifications == 2
    assert info.cgpa == pytest.approx(8.1)
    assert analyze_resume("").skills == ()
    assert extract_skills("   ") == []
    with pytest.raises(ResumeParseError):
        extract_text_from_pdf(b"")
    with pytest.raises(ResumeParseError):
        extract_text_from_pdf(b"not a pdf at all")


def test_pdf_roundtrip_and_reports() -> None:
    profile = StudentProfile(name="Test Student", cgpa=8, projects=2, skills=("Python", "SQL"))
    a = assess(profile, "Data Analyst")
    md = build_markdown_report(a)
    assert "Internship Readiness Report" in md and "Personalised action plan" in md
    pdf_bytes = build_pdf_report(a)
    assert pdf_bytes.startswith(b"%PDF")
    text = extract_text_from_pdf(pdf_bytes)  # our own report is parseable
    assert "Readiness" in text


def test_assessment_actions_are_sorted_and_specific() -> None:
    a = assess(StudentProfile(name="X", skills=("Python",)), "Backend Developer")
    assert a.actions, "a weak profile must produce actions"
    skill_actions = [x for x in a.actions if x.skill]
    assert all(x.steps for x in skill_actions)
    ranks = {"High": 0, "Medium": 1, "Low": 2}
    assert [ranks[x.priority] for x in a.actions] == sorted(ranks[x.priority] for x in a.actions)
    assert a.potential_score >= a.result.total


def test_mentor_falls_back_when_ollama_is_down() -> None:
    a = assess(StudentProfile(name="Sam Lee", cgpa=7, skills=("Python",)), "Data Analyst")
    reply = ask_mentor("Why is my score low?", a, host="http://127.0.0.1:9", use_llm=True)
    assert reply.source == "rule-based" and "Data Analyst" in reply.text
    assert ask_mentor("", a).source == "system"
    assert "SQL" in rule_based_reply("How do I learn SQL?", a)
    assert "role-specific readiness scores" in rule_based_reply("Which role fits me best?", a)
    assert "weeks" in rule_based_reply("What should I learn first?", a)
    assert not check_ollama(host="http://127.0.0.1:9").online


def test_semantic_matching_prefers_the_right_role() -> None:
    matches = match_jobs(SAMPLE_RESUME, backend="tfidf")
    assert matches and matches[0].similarity >= matches[-1].similarity
    assert matches[0].job.role in {"Data Analyst", "Backend Developer"}
    assert match_jobs("", "tfidf") == []
