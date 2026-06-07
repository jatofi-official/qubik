from flask import Flask, render_template, redirect, url_for
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
    # Redirect to a default testing date if no date is provided
    return redirect(url_for('individual', date='2026-06-02'))


@app.route('/individual/<string:date>')
def individual(date):
    try:
        current_date = datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        current_date = datetime(2026, 6, 2)
    
    prev_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
    current_date_str = current_date.strftime('%Y-%m-%d')

    # Dummy data
    tracker_name = "3nbbTczUGeE... (Fleet Alpha)"
    total_stats = {
        "days_active": 42,
        "pings": 15204,
        "valid": 15000,
        "rejected": 204,
        "max_speed": "120 km/h",
        "min_elevation": "130 m",
        "max_elevation": "250 m"
    }
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

    return render_template("individual.html", current_date=current_date_str, prev_date=prev_date, next_date=next_date, tracker_name=tracker_name, total=total_stats, daily=daily_stats)

if __name__ == '__main__':
    app.run(debug=True)
