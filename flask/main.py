from flask import Flask, render_template, redirect, url_for, jsonify
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
database_name = "../releaseDB.db"

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
    return redirect(url_for('individual', param='3nbbTczUGeECZYuKlFnCOP0gfuPBzTsMjxcbsGMrFuI='))

@app.route('/individual/<path:param>') # We will parse params and then manually split them.
def individual(param):
    parts = param.split('/')
    date_str = parts[-1]
    
    is_date = False
    if len(date_str) == 10: # heuristics if it's a date
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            is_date = True
        except ValueError:
            pass
            
    if is_date:
        hashed_key = '/'.join(parts[:-1]) # bruh one of my keys just HAD to have / in it... it is what it is.
        date = date_str
    else:
        hashed_key = param
        conn = get_db_connection()
        cursor = conn.cursor()
        # Find the most recent ping for this specific tracker
        cursor.execute("SELECT MAX(time) FROM trips WHERE hashed_key = ?", (hashed_key,))
        res = cursor.fetchone()[0]
        conn.close()
        
        latest_date = res.split(' ')[0] if res else datetime.today().strftime('%Y-%m-%d')
        return redirect(url_for('individual', param=f"{hashed_key}/{latest_date}"))
        
    try:
        current_date = datetime.strptime(date, '%Y-%m-%d')
    except ValueError: # if there's no data for time
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
    raw_data = get_raw_data(hashed_key, current_date_str)

    return render_template("individual.html", current_date=current_date_str, prev_date=prev_date, next_date=next_date, tracker_name=tracker_name, total=total_stats, daily=daily_stats, hashed_key=hashed_key, tags=tags, raw_data=raw_data)

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

    sql = "SELECT * FROM daily_stats WHERE hashed_key = ? AND date = ?"
    cursor.execute(sql, (hashed_key, date))
    row = cursor.fetchone()
    conn.close()

    if row and row["pings"] is not None:
        return {
            "pings": row["pings"],
            "valid": row["valid"],
            "rejected": row["rejected"],
            "max_speed": row["max_speed"],
            "min_elevation": row["min_elevation"],
            "max_elevation": row["max_elevation"],
            "elevation_gain": row["elevation_gain"],
            "hours_stationary": row["minutes_stationary"] // 60,
            "minutes_stationary": row["minutes_stationary"] % 60
        }
    else:
        return {
            "pings": 0,
            "valid": 0,
            "rejected": 0,
            "max_speed": "0 km/h",
            "min_elevation": "-",
            "max_elevation": "-",
            "elevation_gain": 0,
            "hours_stationary": 0,
            "minutes_stationary": 0
        }

def get_raw_data(hashed_key, date):
    conn = get_db_connection()
    cursor = conn.cursor()
    date_like = f"{date}%"
    
    sql = """
        SELECT id, time as timestamp, latitude as lat, longitude as lng, 
               velocity, distance, motion_state, transport_mode as mode, 
               time_spent, elevation
        FROM trips
        WHERE hashed_key = ? AND time LIKE ?
        ORDER BY time ASC
    """
    cursor.execute(sql, (hashed_key, date_like))
    rows = cursor.fetchall()
    
    # Editing timestamps for js
    raw_data = []
    for row in rows:
        d = dict(row)
        d['timestamp'] = d['timestamp'].replace(' ', 'T')
        raw_data.append(d)


    # Getting first point from next day.
    next_day = (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    
    sql_next = """
        SELECT id, time as timestamp, latitude as lat, longitude as lng, 
               velocity, distance, motion_state, transport_mode as mode, 
               time_spent, elevation
        FROM trips
        WHERE hashed_key = ? AND time >= ?
        ORDER BY time ASC
        LIMIT 1
    """
    cursor.execute(sql_next, (hashed_key, next_day))
    next_row = cursor.fetchone()
    
    if next_row and next_row['motion_state'] != 'INIT':
        d = dict(next_row)
        d['timestamp'] = d['timestamp'].replace(' ', 'T')
        raw_data.append(d)
        
    conn.close()
    return raw_data

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
    raw_data = get_raw_data(hashed_key, current_date_str)

    return jsonify({
        "current_date": current_date_str,
        "prev_date": prev_date,
        "next_date": next_date,
        "daily": daily_stats,
        "raw_data": raw_data
    })

if __name__ == '__main__':
    app.run(debug=True)
