"""SQLite data layer: schema, inserts and DataFrame loaders."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import pandas as pd

from . import config as cfg

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT    NOT NULL,
    major               TEXT    NOT NULL,
    year                INTEGER NOT NULL DEFAULT 3 CHECK (year BETWEEN 1 AND 5),
    cgpa                REAL    NOT NULL CHECK (cgpa BETWEEN 0 AND 10),
    projects            INTEGER NOT NULL DEFAULT 0 CHECK (projects >= 0),
    internships         INTEGER NOT NULL DEFAULT 0 CHECK (internships >= 0),
    certifications      INTEGER NOT NULL DEFAULT 0 CHECK (certifications >= 0),
    communication_score REAL    NOT NULL CHECK (communication_score BETWEEN 0 AND 100),
    aptitude_score      REAL    NOT NULL CHECK (aptitude_score BETWEEN 0 AND 100),
    target_role         TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS student_skills (
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    skill      TEXT    NOT NULL,
    PRIMARY KEY (student_id, skill)
);

CREATE INDEX IF NOT EXISTS idx_students_major ON students(major);
CREATE INDEX IF NOT EXISTS idx_skills_skill   ON student_skills(skill);
"""

STUDENT_COLUMNS = (
    "name",
    "major",
    "year",
    "cgpa",
    "projects",
    "internships",
    "certifications",
    "communication_score",
    "aptitude_score",
    "target_role",
)

_SELECT_STUDENTS = """
SELECT s.id, s.name, s.major, s.year, s.cgpa, s.projects, s.internships, s.certifications,
       s.communication_score, s.aptitude_score, s.target_role,
       COALESCE(GROUP_CONCAT(ss.skill, '|'), '') AS skills
FROM students s
LEFT JOIN student_skills ss ON ss.student_id = s.id
GROUP BY s.id
ORDER BY s.name
"""


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a connection (creating the parent folder) with foreign keys enabled."""
    path = Path(db_path or cfg.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they do not exist."""
    conn.executescript(SCHEMA)
    conn.commit()


def reset_schema(conn: sqlite3.Connection) -> None:
    """Drop and recreate all tables."""
    conn.executescript("DROP TABLE IF EXISTS student_skills; DROP TABLE IF EXISTS students;")
    init_schema(conn)


def insert_students(conn: sqlite3.Connection, records: Iterable[Mapping[str, object]]) -> int:
    """Insert student dicts (with a ``skills`` list). Returns the number inserted."""
    count = 0
    placeholders = ", ".join("?" for _ in STUDENT_COLUMNS)
    sql = f"INSERT INTO students ({', '.join(STUDENT_COLUMNS)}) VALUES ({placeholders})"
    with conn:  # single transaction
        for rec in records:
            cur = conn.execute(sql, [rec[c] for c in STUDENT_COLUMNS])
            skills: Sequence[str] = rec.get("skills", ())  # type: ignore[assignment]
            conn.executemany(
                "INSERT OR IGNORE INTO student_skills (student_id, skill) VALUES (?, ?)",
                [(cur.lastrowid, s) for s in skills],
            )
            count += 1
    return count


def count_students(db_path: str | Path | None = None) -> int:
    """Number of students in the database (0 if the table does not exist yet)."""
    try:
        with closing(connect(db_path)) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM students").fetchone()[0])
    except sqlite3.Error:
        return 0


def fetch_students_df(db_path: str | Path | None = None) -> pd.DataFrame:
    """Load every student with a ``skills`` list column. Empty DataFrame if no data."""
    columns = ["id", *STUDENT_COLUMNS, "skills"]
    try:
        with closing(connect(db_path)) as conn:
            df = pd.read_sql_query(_SELECT_STUDENTS, conn)
    except (sqlite3.Error, pd.errors.DatabaseError) as exc:
        logger.warning("Could not read students: %s", exc)
        return pd.DataFrame(columns=columns)
    df["skills"] = df["skills"].apply(lambda s: [x for x in str(s).split("|") if x])
    return df


def ensure_database(
    db_path: str | Path | None = None,
    count: int = cfg.DEFAULT_STUDENT_COUNT,
    seed: int = cfg.DEFAULT_SEED,
) -> int:
    """Seed the database on first run. Returns the number of students present."""
    existing = count_students(db_path)
    if existing > 0:
        return existing
    from .seed import generate_students  # local import avoids a circular import

    with closing(connect(db_path)) as conn:
        reset_schema(conn)
        inserted = insert_students(conn, generate_students(count, seed))
    logger.info("Seeded %d synthetic students into %s", inserted, db_path or cfg.DB_PATH)
    return inserted
