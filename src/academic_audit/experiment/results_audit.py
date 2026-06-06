from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


METRIC_COLUMNS = [
    "plan_actions",
    "plan_cost",
    "metric",
    "makespan",
    "total_time",
    "planner_wall_time",
    "nodes_generated",
    "nodes_expanded",
    "search_reported",
    "heuristic_reported",
]


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "si", "sí", "yes", "solved"}


def is_empty(value: Any) -> bool:
    return str(value).strip() in {"", "None", "null", "nan"}


def load_results(csv_path: Path | None, raw_dir: Path | None) -> dict | None:
    if not csv_path or not csv_path.exists():
        return None

    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    total = len(rows)
    solved = sum(1 for row in rows if truthy(row.get("solved", "")))
    planners = sorted({row.get("planner", "") for row in rows if row.get("planner")})
    problems = sorted({row.get("problem", "") for row in rows if row.get("problem")})
    expected = max(1, len(planners) * len(problems))
    matrix_pct = round(100 * total / expected) if expected else 0
    solved_pct = round(100 * solved / max(1, total))

    filled = 0
    possible = 0
    missing_by_col: dict[str, int] = {}
    for column in METRIC_COLUMNS:
        values = [row.get(column, "") for row in rows]
        possible += len(values)
        filled += sum(1 for value in values if not is_empty(value))
        missing_by_col[column] = sum(1 for value in values if is_empty(value))
    metric_pct = round(100 * filled / max(1, possible))

    raw_count = 0
    preflight_count = 0
    if raw_dir and raw_dir.exists():
        raw_files = list(raw_dir.glob("*.txt"))
        raw_count = len(raw_files)
        preflight_count = sum(1 for path in raw_files if "preflight" in path.name.lower())
    raw_pct = 100 if raw_count >= total else round(100 * raw_count / max(1, total))
    preflight_pct = 100 if preflight_count >= 1 else 0

    reliability = round(
        max(
            0,
            min(
                100,
                matrix_pct * 0.25
                + solved_pct * 0.25
                + metric_pct * 0.20
                + raw_pct * 0.20
                + preflight_pct * 0.10,
            ),
        )
    )
    return {
        "rows": total,
        "solved": solved,
        "solved_pct": solved_pct,
        "planners": planners,
        "problems": problems,
        "expected_matrix": expected,
        "matrix_pct": matrix_pct,
        "metric_completeness_pct": metric_pct,
        "raw_count": raw_count,
        "raw_pct": raw_pct,
        "preflight_files": preflight_count,
        "preflight_pct": preflight_pct,
        "reliability_pct": reliability,
        "missing_by_col": missing_by_col,
    }

