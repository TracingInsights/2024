import json
import logging
import os
from typing import Dict, List, Optional, Tuple, Union

import fastf1
import pandas as pd
import requests

import utils

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("telemetry_extraction.log"), logging.StreamHandler()],
)
logger = logging.getLogger("telemetry_extractor")
logging.getLogger("fastf1").setLevel(logging.WARNING)
logging.getLogger("fastf1").propagate = False

# Enable caching
fastf1.Cache.enable_cache("cache")

DEFAULT_YEAR = 2024
PROTO = "https"
HOST = "api.multiviewer.app"
HEADERS = {"User-Agent": f"FastF1/"}

# Global cache for session objects to prevent reloading
SESSION_CACHE = {}
CIRCUIT_INFO_CACHE = {}


class TelemetryExtractor:
    """class to handle extraction of F1 drivers and circuit data."""

    def __init__(
        self,
        year: int = DEFAULT_YEAR,
        events: List[str] = None,
        sessions: List[str] = None,
    ):
        """Initialize the TelemetryExtractor."""
        self.year = year
        self.events = events or [
           # "Bahrain Grand Prix",
           
            # "Australian Grand Prix",
            # "Japanese Grand Prix",
            
            # "Emilia Romagna Grand Prix",
            # "Monaco Grand Prix",
            # "Canadian Grand Prix",
            # "Spanish Grand Prix",
            
            # "British Grand Prix",
            # "Hungarian Grand Prix",
            # "Belgian Grand Prix",
            # "Dutch Grand Prix",
            # "Italian Grand Prix",
            # "Azerbaijan Grand Prix",
            # "Singapore Grand Prix",
            
            # "Mexico City Grand Prix",
            
            # "Las Vegas Grand Prix",
           
            "Miami Grand Prix",
             # "Saudi Arabian Grand Prix",
        ]
        self.sessions = sessions or [
            "Practice 1",
        "Sprint Qualifying",
        "Sprint",
        "Qualifying",
        "Race",
        ]

    def get_session(
        self, event: Union[str, int], session: str, load_telemetry: bool = False
    ) -> fastf1.core.Session:
        """Get a cached session object to prevent reloading."""
        cache_key = f"{self.year}-{event}-{session}"
        if cache_key not in SESSION_CACHE:
            f1session = fastf1.get_session(self.year, event, session)
            f1session.load(telemetry=load_telemetry, weather=True, messages=True)
            SESSION_CACHE[cache_key] = f1session
        return SESSION_CACHE[cache_key]

    def session_drivers_list(self, event: Union[str, int], session: str) -> List[str]:
        """Get list of driver codes for a given event and session."""
        try:
            f1session = self.get_session(event, session)
            return list(f1session.laps["Driver"].unique())
        except Exception as e:
            logger.error(f"Error getting driver list for {event} {session}: {str(e)}")
            return []

    def session_drivers(
        self, event: Union[str, int], session: str
    ) -> Dict[str, List[Dict[str, str]]]:
        """Get drivers available for a given event and session."""
        try:
            f1session = self.get_session(event, session)
            laps = f1session.laps
            team_colors = utils.team_colors(self.year)
            laps["color"] = laps["Team"].map(team_colors)

            unique_drivers = laps["Driver"].unique()

            drivers = [
                {
                    "driver": driver,
                    "team": laps[laps.Driver == driver].Team.iloc[0],
                }
                for driver in unique_drivers
            ]

            return {"drivers": drivers}
        except Exception as e:
            logger.error(f"Error getting drivers for {event} {session}: {str(e)}")
            return {"drivers": []}

    def get_circuit_info(self, event: str, session: str) -> Optional[Dict[str, List]]:
        """Get circuit corner information."""
        cache_key = f"{self.year}-{event}-{session}"

        if cache_key in CIRCUIT_INFO_CACHE:
            return CIRCUIT_INFO_CACHE[cache_key]

        try:
            f1session = self.get_session(event, session)
            circuit_key = f1session.session_info["Meeting"]["Circuit"]["Key"]

            # Try to get corner data from fastf1 first
            try:
                circuit_info = f1session.get_circuit_info()
                corners = circuit_info.corners
                # Get the rotation from the circuit info
                rotation = circuit_info.rotation

                corner_info = {
                    "CornerNumber": corners["Number"].tolist(),
                    "X": corners["X"].tolist(),
                    "Y": corners["Y"].tolist(),
                    "Angle": corners["Angle"].tolist(),
                    "Distance": corners["Distance"].tolist(),
                    "Rotation": rotation  # Add rotation information
                }
                CIRCUIT_INFO_CACHE[cache_key] = corner_info
                return corner_info
            except (AttributeError, KeyError):
                # Fall back to API method if fastf1 method fails
                circuit_info, rotation = self._get_circuit_info_from_api(circuit_key)
                if circuit_info is not None:
                    corner_info = {
                        "CornerNumber": circuit_info["Number"].tolist(),
                        "X": circuit_info["X"].tolist(),
                        "Y": circuit_info["Y"].tolist(),
                        "Angle": circuit_info["Angle"].tolist(),
                        "Distance": (circuit_info["Distance"] / 10).tolist(),
                        "Rotation": rotation  # Add rotation information from API
                    }
                    CIRCUIT_INFO_CACHE[cache_key] = corner_info
                    return corner_info

            logger.warning(f"Could not get corner data for {event} {session}")
            return None
        except Exception as e:
            logger.error(f"Error getting circuit info for {event} {session}: {str(e)}")
            return None

    def _get_circuit_info_from_api(self, circuit_key: int) -> Tuple[Optional[pd.DataFrame], float]:
        """Get circuit information from the MultiViewer API."""
        url = f"{PROTO}://{HOST}/api/v1/circuits/{circuit_key}/{self.year}"
        try:
            response = requests.get(url, headers=HEADERS)
            if response.status_code != 200:
                logger.debug(f"[{response.status_code}] {response.content.decode()}")
                return None, 0.0

            data = response.json()
            # Extract rotation from the API response
            rotation = float(data.get("rotation", 0.0))

            rows = []
            for entry in data["corners"]:
                rows.append(
                    (
                        float(entry.get("trackPosition", {}).get("x", 0.0)),
                        float(entry.get("trackPosition", {}).get("y", 0.0)),
                        int(entry.get("number", 0)),
                        str(entry.get("letter", "")),
                        float(entry.get("angle", 0.0)),
                        float(entry.get("length", 0.0)),
                    )
                )

            return pd.DataFrame(
                rows, columns=["X", "Y", "Number", "Letter", "Angle", "Distance"]
            ), rotation
        except Exception as e:
            logger.error(f"Error fetching circuit data from API: {str(e)}")
            return None, 0.0

    def process_event_session(self, event: str, session: str) -> None:
        """Process a single event and session, extracting drivers and circuit data."""
        logger.info(f"Processing {event} - {session}")

        # Create base directory for this event/session
        base_dir = f"{event}/{session}"
        os.makedirs(base_dir, exist_ok=True)

        try:
            # Load session data once
            f1session = self.get_session(event, session, load_telemetry=True)

            # Save drivers information
            drivers_info = self.session_drivers(event, session)
            with open(f"{base_dir}/drivers.json", "w") as json_file:
                json.dump(drivers_info, json_file)

            # Save circuit corner information
            corner_info = self.get_circuit_info(event, session)
            if corner_info:
                with open(f"{base_dir}/corners.json", "w") as json_file:
                    json.dump(corner_info, json_file)

        except Exception as e:
            logger.error(f"Error processing {event} - {session}: {str(e)}")

    def process_all_data(self) -> None:
        """Process all configured events and sessions."""
        logger.info(f"Starting extraction for {self.year} season")
        logger.info(f"Events: {self.events}")
        logger.info(f"Sessions: {self.sessions}")

        for event in self.events:
            for session in self.sessions:
                self.process_event_session(event, session)

        logger.info("Extraction completed")

def is_data_available(year, events, sessions):
    """
    Check if data is available for the specified year, events, and sessions.

    Args:
        year: The F1 season year
        events: List of event names to check
        sessions: List of session names to check

    Returns:
        bool: True if data is available, False otherwise
    """
    try:
        # Try to load the first event and session as a test
        if not events or not sessions:
            logger.warning("No events or sessions specified to check")
            return False

        event = events[0]
        session = sessions[0]

        logger.info(f"Checking data availability for {year} {event} {session}...")

        # Try to get the session without loading telemetry
        f1session = fastf1.get_session(year, event, session)
        f1session.load(telemetry=False, weather=False, messages=False)

        # Check if we have lap data
        if f1session.laps.empty:
            logger.info(f"No lap data available yet for {year} {event} {session}")
            return False

        # Check if we have at least one driver
        if len(f1session.laps["Driver"].unique()) == 0:
            logger.info(f"No driver data available yet for {year} {event} {session}")
            return False

        logger.info(f"Data is available for {year} {event} {session}")
        return True

    except Exception as e:
        logger.info(f"Data not yet available: {str(e)}")
        return False


def main():
    """Main entry point for the script."""
    try:
        # Create extractor
        extractor = TelemetryExtractor()

        

        # Wait for data to be available
        wait_time = 30  # seconds between checks
        max_attempts = 720  # 12 hours max wait time (720 * 60 seconds)
        attempt = 0

        logger.info(f"Starting to wait for {extractor.year} season data...")

        while attempt < max_attempts:
            if is_data_available(extractor.year, extractor.events, extractor.sessions):
                logger.info(
                    f"Data is available for {extractor.year} season. Starting extraction..."
                )
                extractor.process_all_data()
                break
            else:
                attempt += 1
                logger.info(
                    f"Data not yet available. Waiting {wait_time} seconds before retry ({attempt}/{max_attempts})..."
                )
                time.sleep(wait_time)

                # Check memory usage and clear if needed
                check_memory_usage()

        if attempt >= max_attempts:
            logger.error(
                f"Exceeded maximum wait time ({max_attempts * wait_time / 3600} hours). Exiting."
            )

    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")
        raise


if __name__ == "__main__":
    main()
