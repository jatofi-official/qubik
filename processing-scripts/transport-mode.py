import argparse
import sqlite3
import sys
from math import radians, cos, sin, asin, sqrt, atan2, degrees
import datetime
import heapq


parser = argparse.ArgumentParser(add_help=True, description="Script used for inserting locations of a single tag into database. Expects data in json format.")
parser.add_argument("--verbose", "-v", action ="store_true", help="Prints more information. Used for manual testing.")
parser.add_argument("-sqlite", default="../largeDB.db", help="Name of sqlite .db file.")
parser.add_argument("--debug", "-d", action ="store_true", help="Prints even more information. Used for debugging.")

# Parsing arguments
args = parser.parse_args()

verbose = args.verbose 

sqlite_connection = sqlite3.connect(args.sqlite)
sqlite_cursor = sqlite_connection.cursor()

# CONSTANTS

WALKING_MIN_SPEED = 2
WALKING_MAX_SPEED = 6
CYCLING_MAX_SPEED = 20



# PARAMETERS
debug = args.debug


#   COLORS FOR OUTPUT
class bcolors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    ORANGE = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def pretty_print(color, message):
    print(color + message + bcolors.ENDC)


# I found this snippet. We do not need geodesic distance, it is too expensive and 
# we do not need that high precision, when the accuracy of points is relatively poor
def get_distance(point1, point2):
    R = 6372.8

    lat1, lon1 = point1
    lat2, lon2 = point2

    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    lat1 = radians(lat1)
    lat2 = radians(lat2)

    a = sin(dLat/2)**2 + cos(lat1)*cos(lat2)*sin(dLon/2)**2
    c = 2*asin(sqrt(a))

    return round(R * c * 1000) #We can safely round this, the accuracy won't be affected at all

def get_time_difference(old, new):
    new_time = datetime.datetime.strptime(new[1], "%Y-%m-%d %H:%M:%S")
    old_time = datetime.datetime.strptime(old[1], "%Y-%m-%d %H:%M:%S")
    return new_time - old_time

# Handy snippet for calculating bearing between two points
def get_bearing(coord1, coord2):
    """
    Calculates the initial bearing from coord1 to coord2.
    Coordinates are tuples format: (latitude, longitude) in decimal degrees.
    Returns a float between 0 and 360 degrees (0 = North, 90 = East, etc.)
    """
    # Convert decimal degrees to radians
    lat1 = radians(coord1[0])
    lon1 = radians(coord1[1])
    lat2 = radians(coord2[0])
    lon2 = radians(coord2[1])

    delta_lon = lon2 - lon1

    # Spherical trigonometry formula for bearing
    x = sin(delta_lon) * cos(lat2)
    y = cos(lat1) * sin(lat2) - (sin(lat1) * cos(lat2) * cos(delta_lon))

    # Calculate initial bearing in radians and convert back to degrees
    initial_bearing = atan2(x, y)
    initial_bearing = degrees(initial_bearing)

    # Normalize to standard compass headings (0° to 360°)
    compass_bearing = (initial_bearing + 360) % 360

    return compass_bearing




def handle_key_fixed(key):
    if verbose:
        pretty_print(bcolors.BOLD, f"\n=== Getting location_data for key {key} ===")

    # We only care about moving points from the cleaned database
    get_sql = "SELECT * FROM clean_location_data WHERE hashed_key = ? AND motion_state = 'MOVING' ORDER BY time ASC"
    sqlite_cursor.execute(get_sql, (key,))
    location_data = sqlite_cursor.fetchall()

    if len(location_data) == 0:
        if verbose:
            print("Found no moving location data")
        return False

    for row in location_data:
        row_id = row[0]
        velocity = row[5]

        if velocity is None:
            continue

        if velocity < WALKING_MIN_SPEED:
            mode = "UNKNOWN" # Speeds under 2km/h while 'MOVING'
        elif velocity <= WALKING_MAX_SPEED:
            mode = "WALKING"
        elif velocity <= CYCLING_MAX_SPEED:
            mode = "RUNNING/CYCLING"
        else:
            mode = "DRIVING/TRAIN"

        update_sql = "UPDATE clean_location_data SET transport_mode = ? WHERE id = ?"
        sqlite_cursor.execute(update_sql, (mode, row_id))

    sqlite_connection.commit()

    return True

def classify_transport_modes():
    try:
        # Automatically create the new column if it doesn't exist
        sqlite_cursor.execute("ALTER TABLE clean_location_data ADD COLUMN transport_mode TEXT")
        sqlite_connection.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists

    if verbose:
        print("=== Getting tag keys from sqlite database ===")

    tags_sql = "SELECT hashed_key FROM tags"
    sqlite_cursor.execute(tags_sql)
    tag_keys = sqlite_cursor.fetchall()

    if verbose:
        print(f"Found {len(tag_keys)} tags")

    for key in tag_keys:
        if key[0] != "":
            result = handle_key_fixed(key[0])


    if verbose:
        print("Done!")


classify_transport_modes()