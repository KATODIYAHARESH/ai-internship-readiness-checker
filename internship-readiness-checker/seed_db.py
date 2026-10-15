"""Seed script: generate synthetic students into SQLite.

Usage::

    python seed_db.py                    # 80 students -> data/readiness.db
    python seed_db.py --count 120 --seed 7
    python seed_db.py --db /tmp/demo.db --no-reset
"""

from __future__ import annotations

import argparse
import sys
from contextlib import closing
from pathlib import Path

from readiness import config as cfg
from readiness import database as db
from readiness.analytics import campus_kpis, score_dataframe
from readiness.seed import generate_students


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = argparse.ArgumentParser(description="Generate synthetic students into SQLite.")
    parser.add_argument("--count", type=int, default=cfg.DEFAULT_STUDENT_COUNT, help="number of students (default: 80)")
    parser.add_argument("--seed", type=int, default=cfg.DEFAULT_SEED, help="random seed (default: 42)")
    parser.add_argument("--db", type=Path, default=cfg.DB_PATH, help="SQLite file (default: data/readiness.db)")
    parser.add_argument("--no-reset", action="store_true", help="append instead of dropping existing tables")
    args = parser.parse_args(argv)

    if args.count <= 0:
        print("error: --count must be positive", file=sys.stderr)
        return 2

    try:
        with closing(db.connect(args.db)) as conn:
            if args.no_reset:
                db.init_schema(conn)
            else:
                db.reset_schema(conn)
            inserted = db.insert_students(conn, generate_students(args.count, args.seed))
    except Exception as exc:  # noqa: BLE001 - CLI boundary: report and exit non-zero
        print(f"error: could not seed database: {exc}", file=sys.stderr)
        return 1

    scored = score_dataframe(db.fetch_students_df(args.db))
    kpis = campus_kpis(scored)
    print(f"Inserted {inserted} students into {args.db}")
    print(
        f"Average readiness {kpis['avg_score']} | Ready {kpis['pct_ready']}% | "
        f"Almost ready {kpis['pct_almost']}% | Needs work {kpis['pct_needs_work']}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
