import argparse
import sqlite3
import datetime
from math import radians, cos, sin, asin, sqrt
from elevation_module import ElevationLookup

parser = argparse.ArgumentParser(
    add_help=True,
    description="Script to generate trips and aggregate stationary points.")
parser.add_argument("--verbose", "-v", action="store_true", help="Prints more information.")
parser.add_argument("-sqlite", default="../largeDB.db", help="Name of sqlite .db file.")
parser.add_argument("-topo_data", default="../topography_resources/output_SRTMGL3.tif", help="Filename of .tiff geodata.")
args = parser.parse_args()

verbose = args.verbose
sqlite_connection = sqlite3.connect(args.sqlite)
sqlite_cursor = sqlite_connection.cursor()
engine = ElevationLookup(args.topo_data)

# CONSTANTS
WALKING_MIN_SPEED = 2
WALKING_MAX_SPEED = 6
CYCLING_MAX_SPEED = 20
STATIONARY_MERGE_RADIUS = 100  # meters

TRIPS_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT,
    hashed_key TEXT,
    latitude REAL,
    longitude REAL,
    velocity REAL,
    distance REAL,
    motion_state TEXT,
    time_spent REAL,
    transport_mode TEXT,
    elevation REAL
)
'''

PLACES_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS places (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude REAL,
    longitude REAL,
    significance REAL,
    unique_tags INTEGER
)
'''

class bcolors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    ORANGE = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def pretty_print(color, message):
    print(color + message + bcolors.ENDC)

def get_distance(point1, point2):
    R = 6372.8
    lat1, lon1 = point1
    lat2, lon2 = point2
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    lat1 = radians(lat1)
    lat2 = radians(lat2)
    a = sin(dLat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dLon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return round(R * c * 1000)


def get_time_difference(time_str1, time_str2):
    t1 = datetime.datetime.strptime(time_str1, "%Y-%m-%d %H:%M:%S")
    t2 = datetime.datetime.strptime(time_str2, "%Y-%m-%d %H:%M:%S")
    return (t2 - t1).total_seconds()

def _insert_record(table_name, columns, values):
    column_list = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders})"
    sqlite_cursor.execute(sql, values)


def insert_trip(values):
    new = values + [engine.get_elevation(values[2], values[3])]
    _insert_record(
        "trips",
        ["time", "hashed_key", "latitude", "longitude", "velocity", "distance", "motion_state", "time_spent", "transport_mode", "elevation"],
        new
    )


def insert_place(values):
    _insert_record(
        "places",
        ["latitude", "longitude", "significance", "unique_tags"],
        values,
    )


def initialize_table(table_name, create_sql):
    sqlite_cursor.execute(create_sql)
    sqlite_cursor.execute(f"DELETE FROM {table_name}")


def generate_trips():
    if verbose:
        pretty_print(bcolors.HEADER, "Creating 'trips' table...")

    initialize_table("trips", TRIPS_TABLE_SQL)

    sqlite_cursor.execute("SELECT hashed_key FROM tags")
    tag_keys = sqlite_cursor.fetchall()

    if verbose:
        print(f"Found {len(tag_keys)} unique tags.")

    for key_tuple in tag_keys:
        key = key_tuple[0]
        if verbose:
            pretty_print(bcolors.BOLD, f"\n=== Processing trips for key {key} ===")

        sqlite_cursor.execute(
            "SELECT * FROM clean_location_data WHERE hashed_key = ? ORDER BY time ASC",
            (key,),
        )
        location_data = sqlite_cursor.fetchall()

        if not location_data:
            continue

        prev_row_data = None
        stationary_clusters = []
        current_stationary = None
        last_anchor_time = None

        for row in location_data:
            time_str = row[1]
            lat = row[3]
            lon = row[4]
            orig_motion_state = row[7]

            if prev_row_data is None or orig_motion_state == "INIT":
                if current_stationary:
                    insert_trip([
                        current_stationary["time"],
                        key,
                        current_stationary["lat"],
                        current_stationary["lon"],
                        current_stationary["velocity"],
                        current_stationary["distance"],
                        "STATIONARY",
                        current_stationary["time_spent"],
                        "STATIONARY",
                    ])
                    current_stationary = None

                insert_trip([time_str, key, lat, lon, None, None, "INIT", 0, "UNKNOWN"])

                prev_row_data = {"time": time_str, "lat": lat, "lon": lon}
                last_anchor_time = time_str
                continue

            delta_seconds = get_time_difference(prev_row_data["time"], time_str)
            distance = get_distance((prev_row_data["lat"], prev_row_data["lon"]),(lat, lon))
            velocity = (distance / 1000) / (delta_seconds / 3600) if delta_seconds > 0 else 0

            if orig_motion_state == "STATIONARY" or velocity < WALKING_MIN_SPEED:
                time_spent = delta_seconds / 60
                matched_cluster = None
                min_dist = STATIONARY_MERGE_RADIUS

                for cluster in stationary_clusters:
                    dist_to_cluster = get_distance((lat, lon), (cluster["lat"], cluster["lon"]))
                    if dist_to_cluster < min_dist:
                        min_dist = dist_to_cluster
                        matched_cluster = cluster

                if matched_cluster:
                    c = matched_cluster["count"]
                    lat = ((matched_cluster["lat"] * c) + lat) / (c + 1)
                    lon = ((matched_cluster["lon"] * c) + lon) / (c + 1)
                    matched_cluster["lat"] = lat
                    matched_cluster["lon"] = lon
                    matched_cluster["count"] = c + 1
                else:
                    stationary_clusters.append({"lat": lat, "lon": lon, "count": 1})

                if current_stationary:
                    current_stationary["lat"] = lat
                    current_stationary["lon"] = lon
                    current_stationary["time_spent"] += time_spent
                    current_stationary["count"] += 1
                else:
                    current_stationary = {
                        "time": time_str,
                        "lat": lat,
                        "lon": lon,
                        "velocity": velocity,
                        "distance": distance,
                        "time_spent": time_spent,
                        "count": 1,
                    }

                last_anchor_time = time_str
            else:
                if current_stationary:
                    insert_trip([
                        current_stationary["time"],
                        key,
                        current_stationary["lat"],
                        current_stationary["lon"],
                        current_stationary["velocity"],
                        current_stationary["distance"],
                        "STATIONARY",
                        current_stationary["time_spent"],
                        "STATIONARY",
                    ])
                    current_stationary = None

                time_spent = (
                    get_time_difference(last_anchor_time, time_str) / 60
                    if last_anchor_time
                    else 0
                )
                motion_state = "MOVING"
                if velocity <= WALKING_MAX_SPEED:
                    transport_mode = "WALKING"
                elif velocity <= CYCLING_MAX_SPEED:
                    transport_mode = "RUNNING/CYCLING"
                else:
                    transport_mode = "DRIVING/TRAIN"

                insert_trip([time_str, key, lat, lon, velocity, distance, motion_state, time_spent, transport_mode])

            prev_row_data = {"time": time_str, "lat": lat, "lon": lon}

        if current_stationary:
            insert_trip([
                current_stationary["time"],
                key,
                current_stationary["lat"],
                current_stationary["lon"],
                current_stationary["velocity"],
                current_stationary["distance"],
                "STATIONARY",
                current_stationary["time_spent"],
                "STATIONARY",
            ])

    sqlite_connection.commit()
    if verbose:
        pretty_print(bcolors.GREEN, "\nTrips table successfully generated!")


def generate_places():
    if verbose:
        pretty_print(bcolors.HEADER, "Creating 'places' table...")

    initialize_table("places", PLACES_TABLE_SQL)

    sqlite_cursor.execute(
        "SELECT hashed_key, latitude, longitude, time_spent FROM trips WHERE motion_state = 'STATIONARY'",
    )
    stationary_trips = sqlite_cursor.fetchall()

    places_clusters = []

    for key, lat, lon, time_spent in stationary_trips:
        if time_spent is None:
            time_spent = 0

        matched_cluster = None
        min_dist = STATIONARY_MERGE_RADIUS

        for cluster in places_clusters:
            dist_to_cluster = get_distance((lat, lon), (cluster["lat"], cluster["lon"]))
            if dist_to_cluster < min_dist:
                min_dist = dist_to_cluster
                matched_cluster = cluster

        if matched_cluster:
            c = matched_cluster["count"]
            matched_cluster["lat"] = ((matched_cluster["lat"] * c) + lat) / (c + 1)
            matched_cluster["lon"] = ((matched_cluster["lon"] * c) + lon) / (c + 1)
            matched_cluster["significance"] += time_spent
            matched_cluster["unique_tags"].add(key)
            matched_cluster["count"] += 1
        else:
            places_clusters.append(
                {
                    "lat": lat,
                    "lon": lon,
                    "significance": time_spent,
                    "unique_tags": {key},
                    "count": 1,
                }
            )

    for cluster in places_clusters:
        insert_place([
            cluster["lat"],
            cluster["lon"],
            cluster["significance"],
            len(cluster["unique_tags"]),
        ])

    sqlite_connection.commit()
    if verbose:
        pretty_print(bcolors.GREEN, "\nPlaces table successfully generated!")


generate_trips()
generate_places()
