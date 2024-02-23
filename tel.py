import json
import os

import fastf1
import numpy as np

import utils

fastf1.Cache.enable_cache("cache")
YEAR = 2024


def events_available(year: int) -> any:
    # get events available for a given year
    data = utils.LatestData(year)
    events = data.get_events()
    return events


events = [
    
    'Pre-Season Testing', 

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

def sessions_available(year: int, event: str | int) -> any:
    # get sessions available for a given year and event
    event = str(event)
    data = utils.LatestData(year)
    sessions = data.get_sessions(event)
    return sessions



def session_drivers(year: int, event: str | int, session: str) -> any:
    # get drivers available for a given year, event and session
    import fastf1

    f1session = fastf1.get_testing_session(year, event, session)
    f1session.load(telemetry=True, weather=False, messages=False)

    laps = f1session.laps
    team_colors = utils.team_colors(year)
    # add team_colors dict to laps on Team column
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


def session_drivers_list(year: int, event: str | int, session: str) -> any:
    # get drivers available for a given year, event and session
    import fastf1

    f1session = fastf1.get_testing_session(year, event, session)
    f1session.load(telemetry=True, weather=False, messages=False)

    laps = f1session.laps

    unique_drivers = laps["Driver"].unique()

    return list(unique_drivers)


def laps_data(year: int, event: str | int, session: str, driver: str) -> any:
    # get drivers available for a given year, event, and session
    f1session = fastf1.get_testing_session(year, event, session)
    f1session.load(telemetry=False, weather=False, messages=False)
    laps = f1session.laps

    # add team_colors dict to laps on Team column

    # for each driver in drivers, get the Team column from laps and get the color from team_colors dict
    drivers_data = []

    driver_laps = laps.pick_driver(driver)
    driver_laps["LapTime"] = driver_laps["LapTime"].dt.total_seconds()
    # remove rows where LapTime is null
    driver_laps = driver_laps[driver_laps.LapTime.notnull()]

    drivers_data = {
        "time": driver_laps["LapTime"].tolist(),
        "lap": driver_laps["LapNumber"].tolist(),
        "compound": driver_laps["Compound"].tolist(),
    }

    return drivers_data


# # Example usage:
# result = laps_data(2018, "Bahrain", "R", "GAS")
# result


def accCalc(allLapsDriverTelemetry, Nax, Nay, Naz):
    vx = allLapsDriverTelemetry["Speed"] / 3.6
    time_float = allLapsDriverTelemetry["Time"] / np.timedelta64(1, "s")
    dtime = np.gradient(time_float)
    ax = np.gradient(vx) / dtime

    for i in np.arange(1, len(ax) - 1).astype(int):
        if ax[i] > 25:
            ax[i] = ax[i - 1]

    ax_smooth = np.convolve(ax, np.ones((Nax,)) / Nax, mode="same")
    x = allLapsDriverTelemetry["X"]
    y = allLapsDriverTelemetry["Y"]
    z = allLapsDriverTelemetry["Z"]

    dx = np.gradient(x)
    dy = np.gradient(y)
    dz = np.gradient(z)

    theta = np.arctan2(dy, (dx + np.finfo(float).eps))
    theta[0] = theta[1]
    theta_noDiscont = np.unwrap(theta)

    dist = allLapsDriverTelemetry["Distance"]
    ds = np.gradient(dist)
    dtheta = np.gradient(theta_noDiscont)

    for i in np.arange(1, len(dtheta) - 1).astype(int):
        if abs(dtheta[i]) > 0.5:
            dtheta[i] = dtheta[i - 1]

    C = dtheta / (ds + 0.0001)  # To avoid division by 0

    ay = np.square(vx) * C
    indexProblems = np.abs(ay) > 150
    ay[indexProblems] = 0

    ay_smooth = np.convolve(ay, np.ones((Nay,)) / Nay, mode="same")

    # for z
    z_theta = np.arctan2(dz, (dx + np.finfo(float).eps))
    z_theta[0] = z_theta[1]
    z_theta_noDiscont = np.unwrap(z_theta)

    dist = allLapsDriverTelemetry["Distance"]
    ds = np.gradient(dist)
    z_dtheta = np.gradient(z_theta_noDiscont)

    for i in np.arange(1, len(z_dtheta) - 1).astype(int):
        if abs(z_dtheta[i]) > 0.5:
            z_dtheta[i] = z_dtheta[i - 1]

    z_C = z_dtheta / (ds + 0.0001)  # To avoid division by 0

    az = np.square(vx) * z_C
    indexProblems = np.abs(az) > 150
    az[indexProblems] = 0

    az_smooth = np.convolve(az, np.ones((Naz,)) / Naz, mode="same")

    allLapsDriverTelemetry["Ax"] = ax_smooth
    allLapsDriverTelemetry["Ay"] = ay_smooth
    allLapsDriverTelemetry["Az"] = az_smooth

    return allLapsDriverTelemetry


def telemetry_data(year, event, session: str, driver, lap_number):
    f1session = fastf1.get_testing_session(year, event, session)
    f1session.load(telemetry=True, weather=False, messages=False)
    laps = f1session.laps

    driver_laps = laps.pick_driver(driver)
    driver_laps["LapTime"] = driver_laps["LapTime"].dt.total_seconds()

    # get the telemetry for lap_number
    selected_lap = driver_laps[driver_laps.LapNumber == lap_number]

    telemetry = selected_lap.get_telemetry()

    acc_tel = accCalc(telemetry, 3, 9, 9)

    acc_tel["Time"] = acc_tel["Time"].dt.total_seconds()

    laptime = selected_lap.LapTime.values[0]
    # data_key = f"{driver} - Lap {int(lap_number)} - {year} - {session} - [{laptime}]"
    data_key = f"{year}-{event}-{session}-{driver}-{lap_number}"

    acc_tel["DRS"] = acc_tel["DRS"].apply(lambda x: 1 if x in [10, 12, 14] else 0)
    acc_tel["Brake"] = acc_tel["Brake"].apply(lambda x: 1 if x == True else 0)

    telemetry_data = {
        "tel": {
            "time": acc_tel["Time"].tolist(),
            "rpm": acc_tel["RPM"].tolist(),
            "speed": acc_tel["Speed"].tolist(),
            "gear": acc_tel["nGear"].tolist(),
            "throttle": acc_tel["Throttle"].tolist(),
            "brake": acc_tel["Brake"].tolist(),
            "drs": acc_tel["DRS"].tolist(),
            "distance": acc_tel["Distance"].tolist(),
            "rel_distance": acc_tel["RelativeDistance"].tolist(),
            "acc_x": acc_tel["Ax"].tolist(),
            "acc_y": acc_tel["Ay"].tolist(),
            "acc_z": acc_tel["Az"].tolist(),
            "x": acc_tel["X"].tolist(),
            "y": acc_tel["Y"].tolist(),
            "z": acc_tel["Z"].tolist(),
            "dataKey": data_key,
        }
    }
    return telemetry_data


# Your list of events
events_list = events

# Loop through each event
for event in events_list:
    # Get sessions for the current event
    # sessions = sessions_available(YEAR, event)
    sessions =  [
      "Practice 3",
    
    ]
    

    # Loop through each session and create a folder within the event folder
    for session in sessions:
        drivers = session_drivers_list(2024, 1, 3)
        

        for driver in drivers:
            f1session = fastf1.get_testing_session(2024, 1, 3)
            f1session.load(telemetry=False, weather=False, messages=False)
            laps = f1session.laps
            driver_laps = laps.pick_driver(driver)
            driver_laps["LapNumber"] = driver_laps["LapNumber"].astype(int)
            driver_lap_numbers = round(driver_laps["LapNumber"]).tolist()
            

            for lap_number in driver_lap_numbers:
                driver_folder = f"{event}/{session}/{driver}"
                if not os.path.exists(driver_folder):
                    os.makedirs(driver_folder)

                try:

                    telemetry = telemetry_data(2024, 1, 3, driver, lap_number)


                    # print(telemetry)

                    # Specify the file path where you want to save the JSON data
                    file_path = f"{driver_folder}/{lap_number}_tel.json"

                    # Save the dictionary to a JSON file
                    with open(file_path, "w") as json_file:
                        json.dump(telemetry, json_file)
                except:
                    continue
