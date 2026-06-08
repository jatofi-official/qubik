import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import seaborn as sns

conn = sqlite3.connect("releaseDB.db")

# 1. Fetch intersections (using a simplified distance approximation for speed)
query = """
SELECT 
    DATE(t1.time) as date,
    SUBSTR(t1.hashed_key, 1, 6) as tracker_A,  -- Shortened hash for clean labels
    SUBSTR(t2.hashed_key, 1, 6) as tracker_B,
    COUNT(*) as intersection_strength
FROM trips t1
JOIN trips t2 ON DATE(t1.time) = DATE(t2.time) 
             AND t1.hashed_key < t2.hashed_key
WHERE ABS(t1.latitude - t2.latitude) < 0.001 
  AND ABS(t1.longitude - t2.longitude) < 0.001
GROUP BY date, t1.hashed_key, t2.hashed_key
"""
df = pd.read_sql_query(query, conn)

# 2. Filter for a specific test date to keep it daily
target_date = "2026-04-29" # Or hardcode a day like "2026-05-21"
day_df = df[df['date'] == target_date]

# 3. Pivot into a square interaction matrix
matrix = day_df.pivot(index='tracker_A', columns='tracker_B', values='intersection_strength').fillna(0)

# Make the matrix symmetric for a true matrix view
all_trackers = list(set(day_df['tracker_A']).union(set(day_df['tracker_B'])))
matrix = matrix.reindex(index=all_trackers, columns=all_trackers, fill_value=0)
matrix = matrix + matrix.T

# 4. Plot
plt.figure(figsize=(8, 6))
sns.heatmap(matrix, annot=True, cmap="YlGnBu", cbar_kws={'label': 'Intersection Pings'})
plt.title(f"Social Interaction Matrix — {target_date}")
plt.tight_layout()
plt.savefig(f"social_matrix_{target_date}.png", dpi=300)