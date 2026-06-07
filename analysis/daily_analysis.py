import argparse
import sqlite3
from datetime import timedelta, datetime
from math import radians, cos, sin, asin, sqrt

parser = argparse.ArgumentParser(
    add_help=True,
    description="Script to generate trips and aggregate stationary points.")
parser.add_argument("--verbose", "-v", action="store_true", help="Prints more information.")
parser.add_argument("-sqlite", default="../releaseDB.db", help="Name of sqlite .db file.")
args = parser.parse_args()

verbose = args.verbose
sqlite_connection = sqlite3.connect(args.sqlite)
sqlite_cursor = sqlite_connection.cursor()

DAILY_STATS_SQL = '''
CREATE TABLE IF NOT EXISTS daily_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hashed_key TEXT,
    date TEXT,
    pings INTEGER,
    valid INTEGER,
    rejected INTEGER,
    max_speed TEXT,
    min_elevation TEXT,
    max_elevation TEXT,
    elevation_gain REAL,
    minutes_stationary INTEGER
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

def get_db_connection():
    conn = sqlite3.connect(args.sqlite)
    conn.row_factory = sqlite3.Row
    return conn

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


def get_daily_stats(hashed_key, date):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Using LIKE is significantly faster because it can leverage database indexes
    date_like = f"{date}%"

    # Pings
    sql = "SELECT COUNT(*) FROM location_data WHERE hashed_key = ? AND time LIKE ?"
    cursor.execute(sql, (hashed_key, date_like))
    total_pings = cursor.fetchone()[0]

    sql = "SELECT COUNT(*) FROM clean_location_data WHERE hashed_key = ? AND time LIKE ?" 
    cursor.execute(sql, (hashed_key, date_like))
    valid_pings = cursor.fetchone()[0]

    rejected_pings = total_pings - valid_pings

    day_start = datetime.strptime(date, '%Y-%m-%d')
    day_end = day_start + timedelta(days=1)
    day_start_str = day_start.strftime('%Y-%m-%d %H:%M:%S')


    # Fetch trips that overlap with the target day, along with the single trip recorded right before midnight
    sql = """
        SELECT time, velocity, motion_state, time_spent, elevation 
        FROM trips 
        WHERE hashed_key = ? AND time >= (
            SELECT IFNULL(MAX(time), '1970-01-01') 
            FROM trips 
            WHERE hashed_key = ? AND time < ?
        )
        ORDER BY time ASC
    """
    cursor.execute(sql, (hashed_key, hashed_key, day_start_str))
    
    total_stationary_minutes = 0
    max_speed = 0
    min_elevation = float('inf')
    max_elevation = float('-inf')
    elevations = []

    for row in cursor.fetchall():
        end_time = datetime.strptime(row['time'], "%Y-%m-%d %H:%M:%S")
        time_spent = row['time_spent'] or 0
        start_time = end_time - timedelta(minutes=time_spent)
        
        # If we've started looping iget_raw_datanto trips entirely in the future, we can safely stop looking
        if start_time >= day_end:
            break
        
        # Clamp logic: Only calculate time that occurred strictly inside the 24h day boundary
        overlap_start = max(start_time, day_start)
        overlap_end = min(end_time, day_end)
        overlap_duration_minutes = max(0.0, (overlap_end - overlap_start).total_seconds() / 60.0)
        
        e = row['elevation']

        if end_time < day_start:
            # This point is from strictly before the day started, append it only to ground the initial elevation gain
            if e is not None:
                elevations.append(e)
            continue
        
        if row['motion_state'] == 'STATIONARY':
            total_stationary_minutes += overlap_duration_minutes
        elif row['motion_state'] == 'MOVING':
            v = row['velocity']
            if v and v > max_speed:
                max_speed = v
        
        if e is not None:
            if e < min_elevation: min_elevation = round(e)
            if e > max_elevation: max_elevation = round(e)
            elevations.append(e)

    conn.close()

    if min_elevation == float('inf'): min_elevation = "-"
    if max_elevation == float('-inf'): max_elevation = "-"

    elevation_gain = 0
    for i in range(1, len(elevations)):
        diff = elevations[i] - elevations[i-1]
        if diff > 0:
            elevation_gain += diff

    return {
        "pings": total_pings,
        "valid": valid_pings,
        "rejected": rejected_pings,
        "max_speed": f"{round(max_speed, 1)} km/h",
        "min_elevation": f"{min_elevation} m",
        "max_elevation": f"{max_elevation} m",
        "elevation_gain": round(elevation_gain),
        "minutes_stationary": int(total_stationary_minutes)
    }


def initialize_table(table_name, create_sql):
    sqlite_cursor.execute(create_sql)
    sqlite_cursor.execute(f"DELETE FROM {table_name}")

def generate_daily_stats():
    if verbose:
        pretty_print(bcolors.HEADER, "Creating 'daily_stats' table...")

    initialize_table("daily_stats", DAILY_STATS_SQL)

    sqlite_cursor.execute("SELECT hashed_key FROM tags")
    tags = sqlite_cursor.fetchall()

    for (key,) in tags:
        if verbose:
            pretty_print(bcolors.BOLD, f"\n=== Processing daily stats for key {key} ===")

        # Find the overall date range for this tracker to establish our loop boundaries
        sqlite_cursor.execute("SELECT MIN(DATE(time)), MAX(DATE(time)) FROM location_data WHERE hashed_key = ?", (key,))
        row = sqlite_cursor.fetchone()
        
        if not row or not row[0]:
            if verbose:
                print("No data found for this tag.")
            continue
            
        current_date = datetime.strptime(row[0], '%Y-%m-%d')
        end_date = datetime.strptime(row[1], '%Y-%m-%d')
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            
            # Instead of running the heavy calculation on dead days, quickly check if there are any pings at all
            sqlite_cursor.execute("SELECT COUNT(*) FROM location_data WHERE hashed_key = ? AND time LIKE ?", (key, f"{date_str}%"))
            if sqlite_cursor.fetchone()[0] > 0:
                stats = get_daily_stats(key, date_str)
                values = [key, date_str, stats["pings"], stats["valid"], stats["rejected"], stats["max_speed"], stats["min_elevation"], stats["max_elevation"], stats["elevation_gain"], stats["minutes_stationary"]]
            else:
                values = [key, date_str, None, None, None, None, None, None, None, None]

            _insert_record("daily_stats", ["hashed_key", "date", "pings", "valid", "rejected", "max_speed", "min_elevation", "max_elevation", "elevation_gain", "minutes_stationary"], values)
            current_date += timedelta(days=1)
            
    sqlite_connection.commit()
    if verbose:
        pretty_print(bcolors.GREEN, "\nDaily stats table successfully generated!")

if __name__ == "__main__":
    generate_daily_stats()
