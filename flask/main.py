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


def get_daily_stats(hashed_key):
    pass    




@app.route('/individual/<string:hashed_key>')
def individual(hashed_key):
    current_date = datetime(2026, 6, 6)
    
    prev_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
    current_date_str = current_date.strftime('%Y-%m-%d')

    # Dummy data
    tracker_name = "Shequanda"

    total_stats = get_total_stats(hashed_key)

    daily_stats = {
        "pings": 342,
        "valid": 340,
        "rejected": 2,
        "max_speed": "45 km/h",
        "min_elevation": "135 m",
        "max_elevation": "190 m",
        "elevation_gain": 450,
        "hours_stationary": 14,
        "minutes_stationary": 30
    }

    return render_template("individual.html", current_date=current_date_str, prev_date=prev_date, next_date=next_date, tracker_name=tracker_name, total=total_stats, daily=daily_stats, hashed_key=hashed_key)


@app.route('/api/stats/<string:hashed_key>/<string:date>')
def api_stats(hashed_key, date):
    try:
        current_date = datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        current_date = datetime(2026, 6, 6)
    
    prev_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
    current_date_str = current_date.strftime('%Y-%m-%d')

    # Dummy data
    daily_stats = {
        "pings": 342,
        "valid": 340,
        "rejected": 2,
        "max_speed": "45 km/h",
        "min_elevation": "135 m",
        "max_elevation": "190 m",
        "elevation_gain": 450,
        "hours_stationary": 14,
        "minutes_stationary": 30
    }

    # If changing dates, randomly mutate the dummy data slightly so you can see it change on the screen
    if current_date_str != "2026-06-02":
        daily_stats["pings"] = 120
        daily_stats["valid"] = 118
        daily_stats["max_speed"] = "15 km/h"

    return jsonify({
        "current_date": current_date_str,
        "prev_date": prev_date,
        "next_date": next_date,
        "daily": daily_stats
    })

if __name__ == '__main__':
    app.run(debug=True)
