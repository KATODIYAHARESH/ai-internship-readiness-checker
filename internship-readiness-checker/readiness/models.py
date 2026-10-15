"""Typed data containers shared by every layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class StudentProfile:
    """Everything the scoring engine needs to know about a student."""

    name: str = "Anonymous"
    major: str = "Unknown"
    cgpa: float = 0.0  # 10-point scale
    projects: int = 0
    internships: int = 0
    certifications: int = 0
    communication_score: float = 0.0  # 0-100
    aptitude_score: float = 0.0  # 0-100
    skills: tuple[str, ...] = ()
    student_id: int | None = None
    target_role: str | None = None

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "StudentProfile":
        """Build a profile from a DataFrame row / dict, tolerating missing keys."""
        skills = row.get("skills") or ()
        if isinstance(skills, str):
            skills = [s for s in skills.split("|") if s]
        sid = row.get("id")
        return cls(
            name=str(row.get("name") or "Anonymous"),
            major=str(row.get("major") or "Unknown"),
            cgpa=row.get("cgpa") or 0.0,
            projects=row.get("projects") or 0,
            internships=row.get("internships") or 0,
            certifications=row.get("certifications") or 0,
            communication_score=row.get("communication_score") or 0.0,
            aptitude_score=row.get("aptitude_score") or 0.0,
            skills=tuple(str(s) for s in skills),
            student_id=int(sid) if sid is not None else None,
            target_role=row.get("target_role"),
        )


@dataclass(frozen=True)
class ComponentScore:
    """One weighted slice of the readiness score, with a human explanation."""

    name: str
    weight: float
    fraction: float  # 0..1 achieved
    points: float  # weight * fraction
    detail: str

    @property
    def lost(self) -> float:
        """Points left on the table for this component."""
        return self.weight - self.points


@dataclass(frozen=True)
class ScoreResult:
    """Explainable, role-specific readiness result."""

    role: str
    total: float  # 0..100, one decimal
    level: str
    components: tuple[ComponentScore, ...]
    matched_required: tuple[str, ...]
    missing_required: tuple[str, ...]
    matched_preferred: tuple[str, ...]
    missing_preferred: tuple[str, ...]

    @property
    def breakdown(self) -> dict[str, float]:
        """Component name -> points earned."""
        return {c.name: c.points for c in self.components}

    @property
    def skills_match_pct(self) -> float:
        """Share of required skills the student already has (0-100)."""
        total = len(self.matched_required) + len(self.missing_required)
        return 100.0 * len(self.matched_required) / total if total else 0.0

    def component(self, name: str) -> ComponentScore:
        """Look a component up by name."""
        for comp in self.components:
            if comp.name == name:
                return comp
        raise KeyError(name)


@dataclass(frozen=True)
class ActionItem:
    """A single, concrete improvement step."""

    title: str
    category: str  # skill | projects | experience | certifications | communication | academics
    impact_points: float
    effort_hours: int
    priority: str  # High | Medium | Low
    steps: tuple[str, ...]
    project_idea: str | None = None
    skill: str | None = None


@dataclass(frozen=True)
class JobDescription:
    """A sample internship posting used for semantic matching."""

    id: str
    role: str
    title: str
    company: str
    text: str


@dataclass(frozen=True)
class JobMatch:
    """Semantic similarity between a resume and one job description."""

    job: JobDescription
    similarity: float  # 0..100
    backend: str


@dataclass
class Assessment:
    """Everything the UI, the report builder and the mentor need for one student."""

    profile: StudentProfile
    role: str
    result: ScoreResult
    actions: list[ActionItem] = field(default_factory=list)
    role_scores: dict[str, float] = field(default_factory=dict)
    insights: list[str] = field(default_factory=list)
    source: str = "student"

    @property
    def potential_score(self) -> float:
        """Estimated score after completing the five highest-priority actions."""
        gain = sum(a.impact_points for a in self.actions[:5])
        return round(min(100.0, self.result.total + gain), 1)
