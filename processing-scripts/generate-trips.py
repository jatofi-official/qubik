import argparse
import sqlite3
import datetime
from math import radians, cos, sin, asin, sqrt

parser = argparse.ArgumentParser(add_help=True, description="Script to generate trips and aggregate stationary points.")
parser.add_argument("--verbose", "-v", action ="store_true", help="Prints more information.")
parser.add_argument("-sqlite", default="../largeDB.db", help="Name of sqlite .db file.")
args = parser.parse_args()

verbose = args.verbose

# CONSTANTS
WALKING_MIN_SPEED = 2
WALKING_MAX_SPEED = 6
CYCLING_MAX_SPEED = 20
STATIONARY_MERGE_RADIUS = 100 # meters

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
    a = sin(dLat/2)**2 + cos(lat1)*cos(lat2)*sin(dLon/2)**2
    c = 2*asin(sqrt(a))
    return round(R * c * 1000)

def get_time_difference(time_str1, time_str2):
    t1 = datetime.datetime.strptime(time_str1, "%Y-%m-%d %H:%M:%S")
    t2 = datetime.datetime.strptime(time_str2, "%Y-%m-%d %H:%M:%S")
    return (t2 - t1).total_seconds()

def generate_trips():
    conn = sqlite3.connect(args.sqlite)
    cursor = conn.cursor()

    if verbose:
        pretty_print(bcolors.HEADER, "Creating 'trips' table...")

    cursor.execute('''
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
            transport_mode TEXT
        )
    ''')
    # Clear existing trips to avoid duplicates on reruns
    cursor.execute('DELETE FROM trips')

    cursor.execute("SELECT hashed_key FROM tags")
    tag_keys = cursor.fetchall()

    if verbose:
        print(f"Found {len(tag_keys)} unique tags.")

    for key_tuple in tag_keys:
        key = key_tuple[0]
        if verbose:
            pretty_print(bcolors.BOLD, f"\n=== Processing trips for key {key} ===")
        
        cursor.execute("SELECT * FROM clean_location_data WHERE hashed_key = ? ORDER BY time ASC", (key,))
        location_data = cursor.fetchall()

        if not location_data:
            continue

        prev_row_data = None
        stationary_clusters = [] # Used to match and weight stationary positions
        current_stationary = None
        last_anchor_time = None
        
        for row in location_data:
            time_str = row[1]
            lat = row[3]
            lon = row[4]
            orig_motion_state = row[7]

            if prev_row_data is None or orig_motion_state == "INIT":
                if current_stationary:
                    cursor.execute('''
                        INSERT INTO trips (time, hashed_key, latitude, longitude, velocity, distance, motion_state, time_spent, transport_mode)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (current_stationary['time'], key, current_stationary['lat'], current_stationary['lon'], current_stationary['velocity'], current_stationary['distance'], "STATIONARY", current_stationary['time_spent'], "STATIONARY"))
                    current_stationary = None

                # Initial point
                cursor.execute('''
                    INSERT INTO trips (time, hashed_key, latitude, longitude, velocity, distance, motion_state, time_spent, transport_mode)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (time_str, key, lat, lon, None, None, "INIT", 0, "UNKNOWN"))
                prev_row_data = {'time': time_str, 'lat': lat, 'lon': lon}
                last_anchor_time = time_str
                continue

            delta_seconds = get_time_difference(prev_row_data['time'], time_str)
            
            # Recalculate distance using previous (potentially clustered/weighted) location
            distance = get_distance((prev_row_data['lat'], prev_row_data['lon']), (lat, lon))
            
            # Recalculate velocity based on new true distance
            velocity = (distance / 1000) / (delta_seconds / 3600) if delta_seconds > 0 else 0

            if orig_motion_state == "STATIONARY" or velocity < WALKING_MIN_SPEED:
                motion_state = "STATIONARY"
                transport_mode = "STATIONARY"
                time_spent = delta_seconds / 60
                
                # Try to match with existing stationary clusters. I am proud that this works really well:D
                matched_cluster = None
                min_dist = STATIONARY_MERGE_RADIUS
                
                for cluster in stationary_clusters:
                    dist_to_cluster = get_distance((lat, lon), (cluster['lat'], cluster['lon']))
                    if dist_to_cluster < min_dist:
                        min_dist = dist_to_cluster
                        matched_cluster = cluster
                
                if matched_cluster:
                    # Calculate the new weighted average to snap position to the cluster's evolving hub
                    c = matched_cluster['count']
                    lat = ((matched_cluster['lat'] * c) + lat) / (c + 1)
                    lon = ((matched_cluster['lon'] * c) + lon) / (c + 1)
                    
                    matched_cluster['lat'] = lat
                    matched_cluster['lon'] = lon
                    matched_cluster['count'] = c + 1
                else:
                    # Add a new stationary cluster hub to the list
                    stationary_clusters.append({'lat': lat, 'lon': lon, 'count': 1})
                
                # Merge logic for consecutive stationary points
                if current_stationary:
                    current_stationary['lat'] = lat
                    current_stationary['lon'] = lon
                    current_stationary['time_spent'] += time_spent
                    current_stationary['count'] += 1
                else:
                    # Start tracking a new stationary sequence
                    current_stationary = {
                        'time': time_str,
                        'lat': lat,
                        'lon': lon,
                        'velocity': velocity,
                        'distance': distance,
                        'time_spent': time_spent,
                        'count': 1
                    }
                
                # Update anchor to the latest stationary point so next movement measures from here
                last_anchor_time = time_str
            else:
                motion_state = "MOVING"
                time_spent = get_time_difference(last_anchor_time, time_str) / 60 if last_anchor_time else 0
                if velocity <= WALKING_MAX_SPEED:
                    transport_mode = "WALKING"
                elif velocity <= CYCLING_MAX_SPEED:
                    transport_mode = "RUNNING/CYCLING"
                else:
                    transport_mode = "DRIVING/TRAIN"

                # If we were previously stationary, flush the aggregated result before inserting the moving point
                if current_stationary:
                    cursor.execute('''
                        INSERT INTO trips (time, hashed_key, latitude, longitude, velocity, distance, motion_state, time_spent, transport_mode)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (current_stationary['time'], key, current_stationary['lat'], current_stationary['lon'], current_stationary['velocity'], current_stationary['distance'], "STATIONARY", current_stationary['time_spent'], "STATIONARY"))
                    current_stationary = None

                cursor.execute('''
                    INSERT INTO trips (time, hashed_key, latitude, longitude, velocity, distance, motion_state, time_spent, transport_mode)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (time_str, key, lat, lon, velocity, distance, motion_state, time_spent, transport_mode))

            # Update the previous location. If it was stationary, it saves the updated clustered coordinates
            prev_row_data = {'time': time_str, 'lat': lat, 'lon': lon}

        # Flush any remaining stationary sequence at the very end of the tracker's history
        if current_stationary:
            cursor.execute('''
                INSERT INTO trips (time, hashed_key, latitude, longitude, velocity, distance, motion_state, time_spent, transport_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (current_stationary['time'], key, current_stationary['lat'], current_stationary['lon'], current_stationary['velocity'], current_stationary['distance'], "STATIONARY", current_stationary['time_spent'], "STATIONARY"))

    conn.commit()
    if verbose:
        pretty_print(bcolors.GREEN, "\nTrips table successfully generated!")

def generate_places():
    conn = sqlite3.connect(args.sqlite)
    cursor = conn.cursor()

    if verbose:
        pretty_print(bcolors.HEADER, "Creating 'places' table...")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS places (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            latitude REAL,
            longitude REAL,
            significance REAL,
            unique_tags INTEGER
        )
    ''')
    # Clear existing places to avoid duplicates on reruns
    cursor.execute('DELETE FROM places')

    # We can pull all stationary points from the already computed trips table
    cursor.execute("SELECT hashed_key, latitude, longitude, time_spent FROM trips WHERE motion_state = 'STATIONARY'")
    stationary_trips = cursor.fetchall()

    places_clusters = []

    for row in stationary_trips:
        key, lat, lon, time_spent = row
        if time_spent is None:
            time_spent = 0
            
        matched_cluster = None
        min_dist = STATIONARY_MERGE_RADIUS
        
        for cluster in places_clusters:
            dist_to_cluster = get_distance((lat, lon), (cluster['lat'], cluster['lon']))
            if dist_to_cluster < min_dist:
                min_dist = dist_to_cluster
                matched_cluster = cluster
        
        if matched_cluster:
            c = matched_cluster['count']
            matched_cluster['lat'] = ((matched_cluster['lat'] * c) + lat) / (c + 1)
            matched_cluster['lon'] = ((matched_cluster['lon'] * c) + lon) / (c + 1)
            matched_cluster['significance'] += time_spent
            matched_cluster['unique_tags'].add(key)
            matched_cluster['count'] += 1
        else:
            places_clusters.append({'lat': lat, 'lon': lon, 'significance': time_spent, 'unique_tags': {key}, 'count': 1})

    for cluster in places_clusters:
        cursor.execute('''
            INSERT INTO places (latitude, longitude, significance, unique_tags)
            VALUES (?, ?, ?, ?)
        ''', (cluster['lat'], cluster['lon'], cluster['significance'], len(cluster['unique_tags'])))

    conn.commit()
    if verbose:
        pretty_print(bcolors.GREEN, "\nPlaces table successfully generated!")

generate_trips()
generate_places()