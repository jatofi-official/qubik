import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import argparse
from scipy.stats import norm
import sys


parser = argparse.ArgumentParser(
    add_help=True,
    description="Script to generate trips and aggregate stationary points.")
parser.add_argument("--verbose", "-v", action="store_true", help="Prints more information.")
parser.add_argument("-sqlite", default="../releaseDB.db", help="Name of sqlite .db file.")
args = parser.parse_args()

verbose = args.verbose

db_path = args.sqlite

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

def main():
    # Target database file
    
    # 1. SQL Query to aggregate daily metrics
    query = """
        SELECT 
            DATE(time) AS date,
            COUNT(*) AS valid_pings,
            MAX(velocity) AS max_speed,
            MIN(elevation) AS min_elevation,
            MAX(elevation) AS max_elevation,
            (MAX(elevation) - MIN(elevation)) AS elevation_gain,
            SUM(CASE WHEN motion_state = 'STATIONARY' THEN time_spent ELSE 0 END) AS minutes_stationary
        FROM trips
        GROUP BY DATE(time)
    """
    
    # Load to DataFrame
    try:
        if verbose:
            pretty_print(bcolors.HEADER, f"Connecting to {db_path}...")
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(query, conn) # Really handy function
        conn.close()
        if verbose:
            pretty_print(bcolors.GREEN, f"Successfully loaded {len(df)} daily records.")
    except sqlite3.Error as e:
        pretty_print(bcolors.RED, f"SQLite error occurred: {e}")
        return
    except Exception as e:
        pretty_print(bcolors.RED, f"An unexpected error occurred: {e}")
        return

    # 2. Setup visualization parameters
    metrics = [
        'valid_pings', 
        'max_speed', 
        'min_elevation', 
        'max_elevation', 
        'elevation_gain', 
        'minutes_stationary'
    ]
    
    titles = [
        'Valid Pings per Day', 
        'Max Speed per Day (km/h)', 
        'Min Elevation per Day (m)',
        'Max Elevation per Day (m)', 
        'Elevation Gain per Day (m)', 
        'Minutes Stationary per Day'
    ]
    
    # Create 2x3 grid of subplots
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten() # Flatten to 1D array for easier looping
    


    if verbose:
        print(f"Drawing graphs...")
    

    for i, metric in enumerate(metrics):
        ax = axes[i]
        
        # Drop missing data (NaN) before attempting to fit or plot distributions
        data = df[metric].dropna()
        
        if data.empty:
            if verbose:
                ax.set_title(f"{titles[i]} (No Data)", fontsize=14, pad=10)
            continue
            
        # Plot empirical data distribution (KDE) with a soft fill
        sns.kdeplot(data=data, ax=ax, fill=True, color='#4C72B0', alpha=0.5, label='Empirical KDE')
        
        # Fit a Normal Distribution to the empirical data
        # I am really glad there are tools like scipy. It was a pain to do this manually last semester XD
        mu, std = norm.fit(data)
        
        # Generate X-axis range for plotting the theoretical normal curve smoothly
        xmin, xmax = ax.get_xlim()
        x = np.linspace(xmin, xmax, 100)
        p = norm.pdf(x, mu, std)
        
        # Plot theoretical normal curve (red, dashed)
        ax.plot(x, p, 'r--', linewidth=2, label=f'Normal Fit\n$\mu = {mu:.2f}$\n$\sigma = {std:.2f}$')
        
        # Format subplot
        ax.set_title(titles[i], fontsize=14, pad=10)
        ax.set_xlabel(metric.replace('_', ' ').title(), fontsize=12)
        ax.set_ylabel('Density', fontsize=12)
        ax.legend(loc='best')
        ax.grid(True, linestyle='--', alpha=0.6)

        if verbose:
            sys.stdout.write("Progress: %d / %d \r" % (i, len(metrics))) # Although getting this handy code from stackoverflow, I had some error and asked AI for help fixing it
            if(i != len(metrics)):
                sys.stdout.flush()
            else:
                sys.stdout.write("\n")
                sys.stdout.flush()  

        
    # 4. Layout formatting and save output
    plt.tight_layout()
    output_filename = 'daily_mobility_distributions.png'
    plt.savefig(output_filename, dpi=300)
    if verbose:
        pretty_print(bcolors.GREEN, f"Successfully generated and saved '{output_filename}' at 300 DPI.")

if __name__ == '__main__':
    main()