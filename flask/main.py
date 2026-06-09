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


@app.route('/overview')
def overview():
    current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M GMT")
    return render_template('overview.html', current_time=current_time)

@app.route('/api/overview')
def api_overview():
    conn = get_db_connection()
    cursor = conn.cursor()

    # KPIs
    cursor.execute("SELECT COUNT(DISTINCT hashed_key) FROM tags WHERE hashed_key != ''")
    monitored_tags = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM location_data")
    total_pings = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM clean_location_data")
    valid_pings = cursor.fetchone()[0]
    health = round((valid_pings / total_pings) * 100, 1) if total_pings and total_pings > 0 else 0
    cursor.execute("SELECT COUNT(*) FROM places WHERE significance > 60")
    significant_places = cursor.fetchone()[0]

    # Trends (Aggregated by day)
    cursor.execute("SELECT DATE(time) as date, COUNT(*) as count FROM trips GROUP BY DATE(time) ORDER BY DATE(time)")
    pings_over_time = [dict(row) for row in cursor.fetchall()]
    cursor.execute("SELECT DATE(time) as date, COUNT(DISTINCT hashed_key) as count FROM trips GROUP BY DATE(time) ORDER BY DATE(time)")
    active_tags_over_time = [dict(row) for row in cursor.fetchall()]

    # Highlights
    cursor.execute("SELECT MAX(velocity) FROM trips WHERE motion_state = 'MOVING'")
    max_speed = cursor.fetchone()[0] or 0
    cursor.execute("SELECT SUM(elevation_gain) FROM daily_stats")
    elevation_gain = cursor.fetchone()[0] or 0
    cursor.execute("SELECT SUM(time_spent) FROM trips WHERE motion_state = 'STATIONARY'")
    stationary_minutes = cursor.fetchone()[0] or 0
    stationary_days = round(stationary_minutes / (60 * 24), 1)

    # Mode Split & Places
    cursor.execute("SELECT transport_mode, SUM(distance) as count FROM trips WHERE transport_mode != 'UNKNOWN' GROUP BY transport_mode ORDER BY count DESC")
    mode_split = [dict(row) for row in cursor.fetchall()]
    cursor.execute("SELECT latitude, longitude, significance, unique_tags, is_overnight FROM places ORDER BY significance DESC LIMIT 10")
    top_places = [dict(row) for row in cursor.fetchall()]
    conn.close()

    def format_number(num):
        if num >= 1000000: return f"{num/1000000:.1f}M"
        if num >= 1000: return f"{num/1000:.1f}k"
        return str(num)

    return jsonify({
        "kpis": { "monitored_tags": monitored_tags, "valid_pings_formatted": format_number(valid_pings), "data_health": health, "significant_places": significant_places },
        "trends": { "pings_over_time": pings_over_time, "active_tags_over_time": active_tags_over_time },
        "highlights": { "max_speed": round(max_speed, 1), "elevation_gain": round(elevation_gain), "stationary_days": stationary_days },
        "mode_split": mode_split,
        "top_places": top_places
    })


@app.route('/individual')
def individual_default():
    # Redirect to a default testing hash if none is provided
    return redirect(url_for('individual', param='3nbbTczUGeECZYuKlFnCOP0gfuPBzTsMjxcbsGMrFuI='))



@app.route('/social')
def social_default():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(time) FROM trips")
    res = cursor.fetchone()[0]
    conn.close()
    
    latest_date = res.split(' ')[0] if res else datetime.today().strftime('%Y-%m-%d')
    return redirect(url_for('social', date=latest_date))

@app.route('/social/<string:date>')
def social(date):
    try:
        current_date = datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        current_date = datetime(2026, 6, 6)
        
    prev_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
    current_date_str = current_date.strftime('%Y-%m-%d')

    raw_data = get_all_raw_data(current_date_str)

    return render_template("social.html", target_date=current_date_str, prev_date=prev_date, next_date=next_date, raw_data=raw_data)

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
            "max_speed": f"{row['max_speed']} km/h" if row['max_speed'] is not None else "0 km/h",
            "min_elevation": f"{row['min_elevation']} m" if row['min_elevation'] is not None else "-",
            "max_elevation": f"{row['max_elevation']} m" if row['max_elevation'] is not None else "-",
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

def get_all_raw_data(date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT hashed_key, name FROM tags WHERE hashed_key != ''")
    tags = cursor.fetchall()
    conn.close()

    all_data = {}
    for tag in tags:
        hk = tag['hashed_key']
        data = get_raw_data(hk, date)
        if data:
            all_data[hk] = {
                "name": tag['name'],
                "data": data
            }
            
    return all_data


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

@app.route('/api/social/<string:date>')
def api_social(date):
    try:
        current_date = datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        current_date = datetime(2026, 6, 6)
    
    prev_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
    current_date_str = current_date.strftime('%Y-%m-%d')

    raw_data = get_all_raw_data(current_date_str)

    return jsonify({
        "current_date": current_date_str,
        "prev_date": prev_date,
        "next_date": next_date,
        "raw_data": raw_data
    })

@app.route('/api/places')
def api_places():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Cutoof is set to 30 minutes. It should filter out many redundant points
    cursor.execute("SELECT * FROM places WHERE significance > 30 ORDER BY significance DESC")
    places = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(places)

if __name__ == '__main__':
    app.run(debug=True)
