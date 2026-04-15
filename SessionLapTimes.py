"""
Session Lap Times Merger
========================
Builds session_laptimes.json files from existing per-driver laptimes.json files.

Expected input layout:
{root}/{event_name}/{session_name}/{driver}/laptimes.json
or, if a year directory exists:
{root}/{year}/{event_name}/{session_name}/{driver}/laptimes.json

Output:
{root}/{event_name}/{session_name}/session_laptimes.json
or:
{root}/{year}/{event_name}/{session_name}/session_laptimes.json

Configure the constants below, then run:
python3 MergeSessionLapTimes.py
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Iterable, Optional

import orjson

SESSION_LAPTIMES_FILENAME = "session_laptimes.json"
DRIVER_LAPTIMES_FILENAME = "laptimes.json"


# ---------------------------------------------------------------------------
# Constants & Configuration
# ---------------------------------------------------------------------------

DEFAULT_YEAR = 2024
DATA_ROOT = "."
# Keep exactly one uncommented event in this list.
TARGET_EVENT_NAMES_LIST = [
    # "Bahrain Grand Prix",
    # "Saudi Arabian Grand Prix",
    # "Australian Grand Prix",
    # "Japanese Grand Prix",
    # "Chinese Grand Prix",
    # "Miami Grand Prix",
    # "Emilia Romagna Grand Prix",
    # "Monaco Grand Prix",
    # "Canadian Grand Prix",
    # "Spanish Grand Prix",
    # "Austrian Grand Prix",
    # "British Grand Prix",
    # "Hungarian Grand Prix",
    # "Belgian Grand Prix",
    # "Dutch Grand Prix",
    # "Italian Grand Prix",
    # "Azerbaijan Grand Prix",
    # "Singapore Grand Prix",
    # "United States Grand Prix",
    # "Mexico City Grand Prix",
    # "São Paulo Grand Prix",
    # "Las Vegas Grand Prix",
    # "Qatar Grand Prix",
    "Abu Dhabi Grand Prix",
]
TARGET_EVENT_NAMES = [e.strip() for e in TARGET_EVENT_NAMES_LIST if e.strip()]
if not TARGET_EVENT_NAMES:
    raise ValueError("Set at least one active event in TARGET_EVENT_NAMES_LIST.")

AVAILABLE_SESSIONS = [
    "Practice 1",
    "Practice 2",
    "Practice 3",
    "Qualifying",
    "Sprint Qualifying",
    "Sprint",
    "Race",
]
# Select one or more sessions from AVAILABLE_SESSIONS.
TARGET_SESSIONS = [
    # "Practice 1",
    # "Practice 2",
    # "Practice 3",
    # "Qualifying",
    # "Sprint Qualifying",
    # "Sprint",
    "Race",
]
invalid_target_sessions = sorted(set(TARGET_SESSIONS) - set(AVAILABLE_SESSIONS))
if invalid_target_sessions:
    raise ValueError(
        "Invalid TARGET_SESSIONS value(s): " + ", ".join(invalid_target_sessions)
    )


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("merge_session_laptimes")


def _load_json(path: Path):
    with path.open("rb") as file_obj:
        raw = file_obj.read()
    if orjson is not None:
        return orjson.loads(raw)
    return json.loads(raw.decode("utf-8"))


def _write_json(path: Path, payload) -> None:
    with path.open("wb") as file_obj:
        if orjson is not None:
            file_obj.write(orjson.dumps(payload, option=orjson.OPT_INDENT_2))
            return
        file_obj.write(json.dumps(payload, indent=2).encode("utf-8"))


def _resolve_root_dir(base_root: Path, year: int) -> Path:
    year_root = base_root / str(year)
    if year_root.is_dir():
        logger.info("Using year directory: %s", year_root)
        return year_root
    logger.info("Year directory %s not found, using root: %s", year_root, base_root)
    return base_root


def _iter_event_dirs(root_dir: Path, selected_events: Optional[set[str]]) -> Iterable[Path]:
    for path in sorted(root_dir.iterdir()):
        if not path.is_dir():
            continue
        if selected_events and path.name not in selected_events:
            continue
        yield path


def _iter_session_dirs(
    event_dir: Path, selected_sessions: Optional[set[str]]
) -> Iterable[Path]:
    for path in sorted(event_dir.iterdir()):
        if not path.is_dir():
            continue
        if selected_sessions and path.name not in selected_sessions:
            continue
        yield path


def merge_session_dir(session_dir: Path) -> int:
    session_laptimes: Dict[str, dict] = {}

    for child in sorted(session_dir.iterdir()):
        if not child.is_dir():
            continue

        laptimes_path = child / DRIVER_LAPTIMES_FILENAME
        if not laptimes_path.is_file():
            continue

        session_laptimes[child.name] = _load_json(laptimes_path)

    if not session_laptimes:
        logger.info("Skipping %s: no per-driver laptimes found", session_dir)
        return 0

    output_path = session_dir / SESSION_LAPTIMES_FILENAME
    _write_json(output_path, session_laptimes)
    logger.info(
        "Wrote %s with %d driver payloads",
        output_path,
        len(session_laptimes),
    )
    return len(session_laptimes)


def merge_all_sessions(
    root_dir: Path,
    selected_events: Optional[set[str]] = None,
    selected_sessions: Optional[set[str]] = None,
) -> tuple[int, int]:
    merged_sessions = 0
    merged_drivers = 0

    for event_dir in _iter_event_dirs(root_dir, selected_events):
        for session_dir in _iter_session_dirs(event_dir, selected_sessions):
            driver_count = merge_session_dir(session_dir)
            if driver_count == 0:
                continue
            merged_sessions += 1
            merged_drivers += driver_count

    return merged_sessions, merged_drivers


def main() -> int:
    year = DEFAULT_YEAR
    root_dir = Path(DATA_ROOT).expanduser().resolve()

    if not root_dir.exists():
        logger.error("Root directory does not exist: %s", root_dir)
        return 1
    if not root_dir.is_dir():
        logger.error("Root path is not a directory: %s", root_dir)
        return 1

    events = [event for event in TARGET_EVENT_NAMES if isinstance(event, str) and event.strip()]
    if not events:
        logger.warning("No TARGET_EVENT_NAMES configured — nothing to merge.")
        return 0

    sessions = [session for session in TARGET_SESSIONS if isinstance(session, str) and session.strip()]
    if not sessions:
        logger.warning("No TARGET_SESSIONS configured — nothing to merge.")
        return 0

    selected_events = set(events)
    selected_sessions = set(sessions)
    resolved_root_dir = _resolve_root_dir(root_dir, year)

    merged_sessions, merged_drivers = merge_all_sessions(
        root_dir=resolved_root_dir,
        selected_events=selected_events,
        selected_sessions=selected_sessions,
    )

    if merged_sessions == 0:
        logger.warning(
            "No session_laptimes.json files were created under %s",
            resolved_root_dir,
        )
        return 0

    logger.info(
        "Merged %d session(s) across %d driver payload(s) for %d under %s",
        merged_sessions,
        merged_drivers,
        year,
        resolved_root_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
