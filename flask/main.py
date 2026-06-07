from flask import Flask, render_template, redirect, url_for, jsonify
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
database_name = "../largeDB.db"

def get_db_connection():
    conn = sqlite3.connect(database_name)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('main.html')


@app.route('/individual')
def individual_default():
    # Redirect to a default testing hash if none is provided
    return redirect(url_for('individual', hashed_key='3nbbTczUGeECZYuKlFnCOP0gfuPBzTsMjxcbsGMrFuI='))

def get_total_stats(hashed_key):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Pings
    sql = "SELECT COUNT(*) FROM location_data WHERE hashed_key = ?"
    cursor.execute(sql, (hashed_key,))

    total_pings = cursor.fetchone()[0]

    sql = "SELECT COUNT(*) FROM clean_location_data WHERE hashed_key = ?"
    cursor.execute(sql, (hashed_key,))

    valid_pings = cursor.fetchone()[0]

    rejected_pings = total_pings-valid_pings

    # Min/max elevation
    sql = "SELECT MIN(elevation), MAX(elevation) FROM trips WHERE hashed_key = ?"

    cursor.execute(sql, (hashed_key,))

    min_elevation, max_elevation = cursor.fetchone()

    # Max speed 
    sql = "SELECT MAX(velocity) FROM trips WHERE hashed_key = ? and motion_state = 'MOVING'" 

    cursor.execute(sql, (hashed_key,))

    max_speed = cursor.fetchone()[0] or 0

    # Days active
    sql = "SELECT COUNT(DISTINCT DATE(time)) FROM trips WHERE hashed_key = ?" #we get this from clean_data, because theoretically if a tag has been idle for the whole day it will register in the next day

    cursor.execute(sql, (hashed_key,))
    days_active = cursor.fetchone()[0]

    conn.close()

    return {
        "days_active": days_active,
        "pings": total_pings,
        "valid": valid_pings,
        "rejected": rejected_pings,
        "max_speed": f"{round(max_speed, 1)} km/h",
        "min_elevation": f"{min_elevation} m",
        "max_elevation": f"{max_elevation} m"
    }


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
        
        # If we've started looping into trips entirely in the future, we can safely stop looking
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

    hours_stationary = int(total_stationary_minutes // 60)
    minutes_stationary = int(total_stationary_minutes % 60)

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
        "hours_stationary": hours_stationary,
        "minutes_stationary": minutes_stationary
    }

@app.route('/individual/<path:hashed_key>')
def individual(hashed_key):
    current_date = datetime(2026, 6, 6)
    
    prev_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
    current_date_str = current_date.strftime('%Y-%m-%d')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT hashed_key, name FROM tags")
    tags = cursor.fetchall()
    conn.close()

    tracker_name = "Unknown Tracker"
    for tag in tags:
        if tag['hashed_key'] == hashed_key:
            tracker_name = tag['name']
            break

    total_stats = get_total_stats(hashed_key)
    daily_stats = get_daily_stats(hashed_key, current_date_str)

    return render_template("individual.html", current_date=current_date_str, prev_date=prev_date, next_date=next_date, tracker_name=tracker_name, total=total_stats, daily=daily_stats, hashed_key=hashed_key, tags=tags)


# Really smart solution that solves the issue of always reloading the page
@app.route('/api/stats/<path:hashed_key>/<string:date>')
def api_stats(hashed_key, date):
    try:
        current_date = datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        current_date = datetime(2026, 6, 6)
    
    prev_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
    current_date_str = current_date.strftime('%Y-%m-%d')

    daily_stats = get_daily_stats(hashed_key, current_date_str)

    return jsonify({
        "current_date": current_date_str,
        "prev_date": prev_date,
        "next_date": next_date,
        "daily": daily_stats
    })

if __name__ == '__main__':
    app.run(debug=True)
