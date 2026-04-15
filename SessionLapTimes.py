"""
Season Session Laptimes Merger
==============================
Combines per-driver ``laptimes.json`` files that already exist for a session
into a single session-level ``session_laptimes.json`` file.

Output directory:
{event_name}/{session_name}/session_laptimes.json

Configuration style intentionally mirrors ``LapTimes.py``:
- Set ``DEFAULT_YEAR``
- Uncomment one or more values in ``TARGET_EVENT_NAMES_LIST``
- Select one or more values in ``TARGET_SESSIONS``

Behavior:
- Overwrites existing ``session_laptimes.json``
- Skips missing driver ``laptimes.json`` files and logs them
- Merges into one column-oriented structure by concatenating each key's arrays
- Pads missing keys/short arrays with ``"None"`` to preserve row alignment
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Constants & Configuration
# ---------------------------------------------------------------------------

DEFAULT_YEAR = 2024
# Keep one or more uncommented events in this list.
TARGET_EVENT_NAMES_LIST = [
    # "Australian Grand Prix",
    # "Chinese Grand Prix",
    # "Japanese Grand Prix",
    # "Bahrain Grand Prix",
    # "Saudi Arabian Grand Prix",
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
TARGET_EVENT_NAMES = [event.strip() for event in TARGET_EVENT_NAMES_LIST if event.strip()]
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


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("session_laptimes_merge.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("session_laptimes_merger")


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Dict[str, List[object]]:
    with path.open("r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a JSON object.")
    return data


def _write_json(path: Path, obj: Dict[str, List[object]]) -> None:
    with path.open("w", encoding="utf-8") as file_obj:
        json.dump(obj, file_obj, ensure_ascii=False)


def _resolve_season_root(year: int, root_dir: Path | None) -> Path:
    """
    Resolve the directory that contains season event folders.

    This supports both common layouts:
    - {cwd}/{event_name}/{session_name}
    - {cwd}/{year}/{event_name}/{session_name}
    """
    base_dir = (root_dir or Path.cwd()).resolve()
    if base_dir.name == str(year):
        return base_dir

    nested_year_dir = base_dir / str(year)
    if nested_year_dir.is_dir():
        logger.info("Using nested season directory: %s", nested_year_dir)
        return nested_year_dir

    return base_dir


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------


def _infer_row_count(data: Dict[str, object], source_path: Path) -> int:
    list_lengths = [len(value) for value in data.values() if isinstance(value, list)]
    if not list_lengths:
        raise ValueError(f"{source_path} does not contain any column arrays.")
    return max(list_lengths)


def _normalize_driver_columns(
    data: Dict[str, object],
    row_count: int,
    driver_label: str,
) -> Dict[str, List[object]]:
    normalized: Dict[str, List[object]] = {}

    for key, value in data.items():
        if not isinstance(value, list):
            logger.warning(
                "Ignoring non-list key '%s' for driver %s while merging session data",
                key,
                driver_label,
            )
            continue

        values = list(value)
        if len(values) < row_count:
            logger.warning(
                "Padding key '%s' for driver %s from %d to %d rows",
                key,
                driver_label,
                len(values),
                row_count,
            )
            values.extend(["None"] * (row_count - len(values)))
        elif len(values) > row_count:
            logger.warning(
                "Truncating key '%s' for driver %s from %d to %d rows",
                key,
                driver_label,
                len(values),
                row_count,
            )
            values = values[:row_count]

        normalized[key] = values

    return normalized


def _merge_driver_payloads(
    payloads: List[Tuple[str, int, Dict[str, List[object]]]]
) -> Dict[str, List[object]]:
    ordered_keys: List[str] = []
    for _, _, payload in payloads:
        for key in payload.keys():
            if key not in ordered_keys:
                ordered_keys.append(key)

    merged = {key: [] for key in ordered_keys}

    for driver_label, row_count, payload in payloads:
        for key in ordered_keys:
            values = payload.get(key)
            if values is None:
                logger.warning(
                    "Missing key '%s' for driver %s, padding %d rows with 'None'",
                    key,
                    driver_label,
                    row_count,
                )
                merged[key].extend(["None"] * row_count)
                continue
            merged[key].extend(values)

    return merged


# ---------------------------------------------------------------------------
# Merger
# ---------------------------------------------------------------------------


class SessionLapTimesMerger:
    """Merge existing driver-level laptimes into session-level files."""

    def __init__(self, year: int = DEFAULT_YEAR, root_dir: Path | None = None):
        self.year = year
        self.root_dir = _resolve_season_root(year, root_dir)

    def process_event_session(self, event_name: str, session_name: str) -> None:
        label = f"{event_name} - {session_name}"
        session_dir = self.root_dir / event_name / session_name

        if not session_dir.is_dir():
            logger.warning("Session directory not found for %s at %s", label, session_dir)
            return

        driver_dirs = sorted(path for path in session_dir.iterdir() if path.is_dir())
        if not driver_dirs:
            logger.warning("No driver directories found for %s", label)
            return

        payloads: List[Tuple[str, int, Dict[str, List[object]]]] = []
        missing_drivers: List[str] = []

        for driver_dir in driver_dirs:
            driver = driver_dir.name
            laptimes_path = driver_dir / "laptimes.json"

            if not laptimes_path.is_file():
                logger.warning("Missing laptimes.json for %s in %s", driver, label)
                missing_drivers.append(driver)
                continue

            try:
                raw_data = _load_json(laptimes_path)
                row_count = _infer_row_count(raw_data, laptimes_path)
                payloads.append(
                    (
                        driver,
                        row_count,
                        _normalize_driver_columns(raw_data, row_count, driver),
                    )
                )
            except Exception as exc:
                logger.error("Skipping %s in %s: %s", driver, label, exc)

        if missing_drivers:
            logger.info(
                "Skipped %d missing driver file(s) for %s: %s",
                len(missing_drivers),
                label,
                ", ".join(missing_drivers),
            )

        if not payloads:
            logger.warning("No valid driver laptimes found for %s", label)
            return

        merged = _merge_driver_payloads(payloads)
        output_path = session_dir / "session_laptimes.json"
        _write_json(output_path, merged)

        total_rows = sum(row_count for _, row_count, _ in payloads)
        logger.info(
            "Wrote %s with %d merged rows from %d driver file(s)",
            output_path,
            total_rows,
            len(payloads),
        )

    def process_all(self) -> None:
        logger.info("Starting session laptimes merge for %d", self.year)

        sessions = [session for session in TARGET_SESSIONS if session.strip()]
        if not sessions:
            logger.warning("No TARGET_SESSIONS configured — nothing to merge.")
            return

        for event_name in TARGET_EVENT_NAMES:
            logger.info("Processing %s (%s)", event_name, ", ".join(sessions))
            for session_name in sessions:
                try:
                    self.process_event_session(event_name, session_name)
                except Exception as exc:
                    logger.error("Failed %s %s: %s", event_name, session_name, exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    merger = SessionLapTimesMerger(year=DEFAULT_YEAR)
    merger.process_all()


if __name__ == "__main__":
    main()
