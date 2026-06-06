import argparse
import sqlite3
import sys
from math import radians, cos, sin, asin, sqrt
import datetime

parser = argparse.ArgumentParser(add_help=True, description="Script used for inserting locations of a single tag into database. Expects data in json format.")
parser.add_argument("--verbose", "-v", action ="store_true", help="Prints more information. Used for manual testing.")
parser.add_argument("-sqlite", default="../largeDB.db", help="Name of sqlite .db file.")

# Parsing arguments
args = parser.parse_args()

verbose = args.verbose 

sqlite_connection = sqlite3.connect(args.sqlite)
sqlite_cursor = sqlite_connection.cursor()

# CONSTANTS
WINDOW_TIME = datetime.timedelta(minutes=1)
IDLE_GAP = datetime.timedelta(minutes=30)

CONFIDENCE_MULTIPLIER = 1000
ACCURACY_MULTIPLIER = 1

MINIMUM_STATIC_SCORE = 1600

# PARAMETERS
debug = True


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

def insert_clean_point(row):
    if verbose:
        print("Inserting clean point.")
    import_sql = "INSERT INTO clean_location_data (time, hashed_key, latitude, longitude, velocity, distance, motion_state, time_spent_here) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    
    sqlite_cursor.execute(import_sql, row)



def handle_key(key):
    if verbose:
        pretty_print(bcolors.BOLD,f"\n=== Getting location_data for key {key} ===")

    get_sql = "SELECT * FROM location_data WHERE hashed_key = ? ORDER BY time ASC"
    sqlite_cursor.execute(get_sql, (key,))
    location_data = sqlite_cursor.fetchall()

    if len(location_data) == 0:
        if verbose:
            print("Found no location data")
        return False

    previous_time = datetime.datetime.strptime(location_data[0][1], "%Y-%m-%d %H:%M:%S")
    # Delta time calculation

    anchor = None
    
    i = 0
    while i < len(location_data):
        row = location_data[i]

        group = [row]
        
        s_time = datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S")
        skip = 0

        condition = True
        while condition and (i + skip + 1) < len(location_data):
            current_time = datetime.datetime.strptime(location_data[i+skip+1][1], "%Y-%m-%d %H:%M:%S")
            difference = current_time - s_time
            if difference > WINDOW_TIME:
                condition = False
            else:
                group.append(location_data[i+skip+1])
                skip += 1

        # Choose new initial anchor
        if current_time - previous_time > IDLE_GAP or anchor is None:
            anchor =  None
            if debug:
                pretty_print(bcolors.CYAN,f"IDLE ACTIVATED, {current_time - previous_time}, group size: {len(group)}")
            
            scores = []
            for candidate in group:
                score = CONFIDENCE_MULTIPLIER * candidate[6] - ACCURACY_MULTIPLIER * candidate[5]
                scores.append((candidate, score))
                if debug:
                    print(f"Confidence: {candidate[6]}, Accuracy: {candidate[5]}, Score: {score}")

            best = max(scores, key=lambda x: x[1])
            if best[1] > MINIMUM_STATIC_SCORE:
                anchor = best[0]
                # We insert null velocity or distance, initial state and -1 as a marker for time spent here
                insert_clean_point([best[0][1], best[0][2], best[0][3], best[0][4], None, None,"INIT", None]) 
                
                if debug:
                    pretty_print(bcolors.GREEN,f"New anchor: {best}")
            else:
                if debug:
                    pretty_print(bcolors.RED,"No new anchor chosen")

        # Choosing next point
        else:
            pass

            
                
        if (i + skip + 1) < len(location_data):
            previous_time = current_time


        i += 1 + skip

    sqlite_connection.commit()

    return True


def filter_location_data():

    if verbose:
        print("=== Getting tag keys from sqlite database ===")

    tags_sql = "SELECT hashed_key FROM tags"
    sqlite_cursor.execute(tags_sql)
    tag_keys = sqlite_cursor.fetchall()

    if verbose:
        print(f"Found {len(tag_keys)} tags")

    for key in tag_keys:
        if key[0] != "":
            result = handle_key(key[0])
            if result:
                break


    if verbose:
        print("Done!")


filter_location_data()