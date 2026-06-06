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

DISTANCE_MERGE = 150

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

        group_condition = True
        while group_condition and (i + skip + 1) < len(location_data):
            current_time = datetime.datetime.strptime(location_data[i+skip+1][1], "%Y-%m-%d %H:%M:%S")
            difference = current_time - s_time
            if difference > WINDOW_TIME:
                group_condition = False
            else:
                group.append(location_data[i+skip+1])
                skip += 1
        
        current_time = s_time

        # Choose new initial anchor
        if current_time - previous_time > IDLE_GAP or anchor is None:
            anchor =  None
            if debug:
                pretty_print(bcolors.CYAN,f"IDLE ACTIVATED, {current_time - previous_time}, group size: {len(group)}")
            
            scores = []
            for current_point in group:
                score = CONFIDENCE_MULTIPLIER * current_point[6] - ACCURACY_MULTIPLIER * current_point[5]
                scores.append((current_point, score))
                if debug:
                    print(f"Confidence: {current_point[6]}, Accuracy: {current_point[5]}, Score: {score}")

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

            found = False

            for c in group:
                # We automatically take one with confidence 3
                if c[6] == 3:
                    # We have found the next point.
                    distance = get_distance((anchor[3], anchor[4]), (c[3], c[4]))
                    c_time = datetime.datetime.strptime(c[1], "%Y-%m-%d %H:%M:%S")
                    anchor_time = datetime.datetime.strptime(anchor[1], "%Y-%m-%d %H:%M:%S")
                    delta_seconds = (c_time - anchor_time).total_seconds()

                    if distance < DISTANCE_MERGE:
                        delta_minutes = delta_seconds / 60
                        insert_clean_point([c[1], c[2], c[3], c[4], 0, 0, "STATIONARY", delta_minutes]) 
                    else:
                        velocity_kmh = (distance / 1000) / (delta_seconds / 3600)
                        insert_clean_point([c[1], c[2], c[3], c[4], velocity_kmh, distance, "MOVING", 0]) 

                    anchor = c
                    found = True
                    break

            # We have to calculate groups until we get one with a point with confidence 3
            if not found:
                groups = [group]
                end = None

                # Creating groups
                while True:
                    skip2 = 0
                    if i + skip + skip2 + 1 >= len(location_data):
                        break

                    group = [location_data[i + skip]]
                    s_time = datetime.datetime.strptime(location_data[i + skip][1], "%Y-%m-%d %H:%M:%S")


                    group_condition = True

                    
                    while group_condition and (i + skip + skip2 + 1) < len(location_data):
                        current_point = location_data[i + skip + skip2 + 1]
                        current_time = datetime.datetime.strptime(current_point[1], "%Y-%m-%d %H:%M:%S")
                        difference = current_time - s_time

                        if current_point[6] == 3:
                            found = True
                            end = current_point

                        if difference > WINDOW_TIME:
                            group_condition = False
                        else:
                            group.append(current_point)
                            skip2 += 1


                    skip += skip2
                    if found or (i + skip + skip2 + 1) >= len(location_data):
                        break
                    else:
                        groups.append(group)
                        s_time = current_time
                    
                # Processing groups
                # TODO implement later
                start = anchor
                # end is the first confidence ==3 point. Here we edit the points and run dijkstra

                
        if (i + skip + 1) < len(location_data):
            previous_time = current_time


        i += 1 + skip

    # sqlite_connection.commit()

    return True

def handle_key_fixed(key):
    if verbose:
        pretty_print(bcolors.BOLD, f"\n=== Getting location_data for key {key} ===")

    get_sql = "SELECT * FROM location_data WHERE hashed_key = ? ORDER BY time ASC"
    sqlite_cursor.execute(get_sql, (key,))
    location_data = sqlite_cursor.fetchall()

    if len(location_data) == 0:
        if verbose:
            print("Found no location data")
        return False

    previous_time = datetime.datetime.strptime(location_data[0][1], "%Y-%m-%d %H:%M:%S")

    anchor = None
    i = 0
    while i < len(location_data):
        # DEBUG
        # if debug:
        #     if i>200:
        #         break

        row = location_data[i]
        current_time = datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S")
        
        # Check if an IDLE_GAP exists or if we need a fresh boot milestone
        if current_time - previous_time > IDLE_GAP or anchor is None:
            anchor = None
            group = []
            skip = 0

            group_condition = True
            while group_condition and (i + skip) < len(location_data):
                point = location_data[i + skip]
                point_time = datetime.datetime.strptime(point[1], "%Y-%m-%d %H:%M:%S")

                # Measure window separation from the group-starting row
                difference = point_time - current_time
                if difference > WINDOW_TIME:
                    group_condition = False
                else:
                    group.append(point)
                    skip += 1

            if debug:
                pretty_print(bcolors.CYAN, f"IDLE ACTIVATED, {current_time - previous_time}, group size: {len(group)}")
            
            # We try to choose the next anchor, one with best score above threshold
            scores = []
            for current_point in group:
                score = CONFIDENCE_MULTIPLIER * current_point[6] - ACCURACY_MULTIPLIER * current_point[5]
                scores.append((current_point, score))
                if debug:
                    print(f"Confidence: {current_point[6]}, Accuracy: {current_point[5]}, Score: {score}")

            best = max(scores, key=lambda x: x[1])
            if best[1] > MINIMUM_STATIC_SCORE:  # We have new anchor.
                anchor = best[0]
                insert_clean_point([best[0][1], best[0][2], best[0][3], best[0][4], None, None, "INIT", None]) 
                
                # Advance tracking time directly to our confirmed new anchor
                previous_time = datetime.datetime.strptime(anchor[1], "%Y-%m-%d %H:%M:%S")
                if debug:
                    pretty_print(bcolors.GREEN, f"New anchor. Skipping: {skip}")
                
                # Jump past the entire consumed group
                i += skip
            else:
                if debug:
                    pretty_print(bcolors.RED, f"No new anchor chosen. Skipping: {skip}")
                
                # If selection fails, advance time tracking and slide forward safely by 1 step
                previous_time = current_time
                i += skip 
        
        # There is no gap, we choose next point
        else:
            # Placeholder for your standard rolling kinematic window block (Choosing next point)
            # This handles when there is an active anchor and no idle gap
            pass
            i += 1

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
            result = handle_key_fixed(key[0])
            if result:
                break


    if verbose:
        print("Done!")


filter_location_data()