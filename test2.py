import networkx as nx

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
# Create a graph object
G = nx.Graph()


# Add edges weighted by how strong their connection was
for _, row in day_df.iterrows():
    G.add_edge(row['tracker_A'], row['tracker_B'], weight=row['intersection_strength'])

plt.figure(figsize=(8, 8))
pos = nx.spring_layout(G, k=0.5) # Positions nodes cleanly using a physical spring simulation

# Draw elements
nx.draw_networkx_nodes(G, pos, node_color='orchid', node_size=700)
nx.draw_networkx_labels(G, pos, font_size=10, font_family="sans-serif")

# Scale edge thicknesses by how many times they crossed paths
edges = G.edges(data=True)
weights = [e[2]['weight'] / df['intersection_strength'].max() * 5 for e in edges]
nx.draw_networkx_edges(G, pos, width=weights, edge_color='gray', alpha=0.6)

plt.title(f"Social Proximity Network — {target_date}")
plt.axis('off')
plt.tight_layout()
plt.savefig(f"social_network_{target_date}.png", dpi=300)