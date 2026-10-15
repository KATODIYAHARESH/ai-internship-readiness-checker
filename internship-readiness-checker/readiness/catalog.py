"""Roles, skills and sample job descriptions loaded from ``data/catalog.json``.

The JSON file is the single source of truth: add a role or a skill playbook
there and every layer (scoring, extraction, action plan, seed data) picks it up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

from .config import CATALOG_PATH
from .models import JobDescription


class CatalogError(RuntimeError):
    """Raised when the catalog file is missing or malformed."""


@dataclass(frozen=True)
class RoleSpec:
    """A target role with required and nice-to-have skills."""

    name: str
    description: str
    required: tuple[str, ...]
    preferred: tuple[str, ...]

    @property
    def all_skills(self) -> tuple[str, ...]:
        """Required skills followed by preferred skills."""
        return self.required + self.preferred


@dataclass(frozen=True)
class SkillInfo:
    """Learning playbook for one skill."""

    name: str
    aliases: tuple[str, ...]
    hours: int
    steps: tuple[str, ...]
    project: str


@lru_cache(maxsize=1)
def _raw() -> dict:
    try:
        with CATALOG_PATH.open(encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise CatalogError(f"Catalog file not found: {CATALOG_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise CatalogError(f"Catalog file is not valid JSON: {exc}") from exc


@lru_cache(maxsize=1)
def roles() -> dict[str, RoleSpec]:
    """All target roles keyed by name."""
    out: dict[str, RoleSpec] = {}
    for name, spec in _raw()["roles"].items():
        out[name] = RoleSpec(
            name=name,
            description=spec.get("description", ""),
            required=tuple(spec["required"]),
            preferred=tuple(spec.get("preferred", [])),
        )
    return out


def role_names() -> list[str]:
    """Role names in catalog order."""
    return list(roles())


def get_role(name: str) -> RoleSpec:
    """Return a role by name or raise ``ValueError`` with the valid options."""
    try:
        return roles()[name]
    except KeyError:
        raise ValueError(f"Unknown role {name!r}. Choose one of: {', '.join(roles())}") from None


@lru_cache(maxsize=1)
def skills_info() -> dict[str, SkillInfo]:
    """Skill playbooks keyed by canonical skill name."""
    return {
        name: SkillInfo(
            name=name,
            aliases=tuple(info.get("aliases", [])),
            hours=int(info.get("hours", 15)),
            steps=tuple(info.get("steps", [])),
            project=info.get("project", ""),
        )
        for name, info in _raw()["skills"].items()
    }


def all_skill_names() -> list[str]:
    """Every canonical skill in the catalog, sorted alphabetically."""
    return sorted(skills_info())


def get_skill_info(skill: str) -> SkillInfo | None:
    """Playbook for ``skill`` or ``None`` if it is not in the catalog."""
    return skills_info().get(skill)


@lru_cache(maxsize=1)
def alias_map() -> dict[str, str]:
    """Lower-cased alias (and canonical name) -> canonical skill name."""
    mapping: dict[str, str] = {}
    for name, info in skills_info().items():
        mapping[name.lower()] = name
        for alias in info.aliases:
            mapping.setdefault(alias.lower(), name)
    return mapping


def normalize_skill(raw: str) -> str | None:
    """Map free text such as ``'sklearn'`` to ``'Scikit-learn'`` (or ``None``)."""
    if not isinstance(raw, str):
        return None
    return alias_map().get(raw.strip().lower())


def normalize_skills(raw: Iterable[str]) -> list[str]:
    """Normalise, de-duplicate (keeping order) and drop unknown skills."""
    seen: dict[str, None] = {}
    for item in raw or ():
        canon = normalize_skill(item)
        if canon:
            seen.setdefault(canon, None)
    return list(seen)


@lru_cache(maxsize=1)
def job_descriptions() -> tuple[JobDescription, ...]:
    """Sample internship postings used by the semantic matcher."""
    return tuple(JobDescription(**jd) for jd in _raw().get("job_descriptions", []))
