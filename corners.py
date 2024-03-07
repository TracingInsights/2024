import fastf1
import os
import json


YEAR = 2024
EVENT = "BAHRAIN GRAND PRIX"
SESSION = "RACE"

events = [
    # "Pre-Season Testing"
    "Bahrain Grand Prix",
    # 'Bahrain Grand Prix', 'Saudi Arabian Grand Prix',
    #     'Australian Grand Prix',
    # 'Azerbaijan Grand Prix',
    # 'Miami Grand Prix',
    # 'Monaco Grand Prix',
    # 'Spanish Grand Prix', 'Canadian Grand Prix',
    # 'Austrian Grand Prix',
    # 'British Grand Prix', 'Hungarian Grand Prix',
    # 'Belgian Grand Prix',
    # 'Dutch Grand Prix', 'Italian Grand Prix',
    # 'Singapore Grand Prix',
    # 'United States Grand Prix',
    # 'Mexico City Grand Prix',
    # 'São Paulo Grand Prix',
    # 'Las Vegas Grand Prix', 'Abu Dhabi Grand Prix',     'Japanese Grand Prix',
]
sessions = [
    "Practice 1",
      "Practice 2",
      "Practice 3",
      "Qualifying",
      "Race",
]


for event in events:
    for session in sessions:
        f1session = fastf1.get_session(YEAR, event, session)
        f1session.load()
        circuit_info = f1session.get_circuit_info().corners
        corner_info ={
            "CornerNumber": circuit_info['Number'].tolist(),
            "X": circuit_info['X'].tolist(),
            "Y": circuit_info['Y'].tolist(),
            "Angle": circuit_info['Angle'].tolist(),
            "Distance": circuit_info['Distance'].tolist(),
        }

        driver_folder = f"{EVENT}/{SESSION}"
        file_path = f"{EVENT}/{SESSION}/corners.json"
        if not os.path.exists(driver_folder):
            os.makedirs(driver_folder)
        # Save the dictionary to a JSON file
        with open(file_path, "w") as json_file:
            json.dump(corner_info, json_file)
