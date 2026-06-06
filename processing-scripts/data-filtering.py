import argparse
import sqlite3
import sys
from math import radians, cos, sin, asin, sqrt, atan2, degrees
import datetime
import heapq


parser = argparse.ArgumentParser(add_help=True, description="Script used for inserting locations of a single tag into database. Expects data in json format.")
parser.add_argument("--verbose", "-v", action ="store_true", help="Prints more information. Used for manual testing.")
parser.add_argument("-sqlite", default="../largeDB.db", help="Name of sqlite .db file.")
parser.add_argument("--debug", "-d", action ="store_true", help="Prints even more information. Used for debugging.")

# Parsing arguments
args = parser.parse_args()

verbose = args.verbose 

sqlite_connection = sqlite3.connect(args.sqlite)
sqlite_cursor = sqlite_connection.cursor()

# CONSTANTS
WINDOW_TIME = datetime.timedelta(minutes=1)
IDLE_GAP = datetime.timedelta(minutes=30)

CONFIDENCE_MULTIPLIER = 1000
ACCURACY_MULTIPLIER = 1

MINIMUM_STATIC_SCORE = 1800

DISTANCE_MERGE = 150

# Graph constants
VELOCITY_CUTOFF_KMH = 160
ANGLE_PENALTY_CUTOFF = 120
TURN_PENALTY_MULTIPLIER = 150

ANGLE_CUTOFF = 140
VELOCITY_ANGLE_CUTOFF = 60
DISTANCE_MULTIPLIER = 5


# PARAMETERS
debug = args.debug


#   COLORS FOR OUTPUT
class bcolors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    ORANGE = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def pretty_print(color, message):
    print(color + message + bcolors.ENDC)


# I found this snippet. We do not need geodesic distance, it is too expensive and 
# we do not need that high precision, when the accuracy of points is relatively poor
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

    return round(R * c * 1000) #We can safely round this, the accuracy won't be affected at all

def get_time_difference(old, new):
    new_time = datetime.datetime.strptime(new[1], "%Y-%m-%d %H:%M:%S")
    old_time = datetime.datetime.strptime(old[1], "%Y-%m-%d %H:%M:%S")
    return new_time - old_time

# Handy snippet for calculating bearing between two points
def get_bearing(coord1, coord2):
    """
    Calculates the initial bearing from coord1 to coord2.
    Coordinates are tuples format: (latitude, longitude) in decimal degrees.
    Returns a float between 0 and 360 degrees (0 = North, 90 = East, etc.)
    """
    # Convert decimal degrees to radians
    lat1 = radians(coord1[0])
    lon1 = radians(coord1[1])
    lat2 = radians(coord2[0])
    lon2 = radians(coord2[1])

    delta_lon = lon2 - lon1

    # Spherical trigonometry formula for bearing
    x = sin(delta_lon) * cos(lat2)
    y = cos(lat1) * sin(lat2) - (sin(lat1) * cos(lat2) * cos(delta_lon))

    # Calculate initial bearing in radians and convert back to degrees
    initial_bearing = atan2(x, y)
    initial_bearing = degrees(initial_bearing)

    # Normalize to standard compass headings (0° to 360°)
    compass_bearing = (initial_bearing + 360) % 360

    return compass_bearing


def insert_clean_point(row):
    if verbose:
        print("Inserting clean point.")
    import_sql = "INSERT INTO clean_location_data (time, hashed_key, latitude, longitude, velocity, distance, motion_state, time_spent_here) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    
    sqlite_cursor.execute(import_sql, row)


def add_point(previous, new):
    distance = get_distance((previous[3], previous[4]), (new[3], new[4]))
    delta_seconds = get_time_difference(previous, new).total_seconds()

    if distance < DISTANCE_MERGE:
        insert_clean_point([new[1], new[2], new[3], new[4], 0, 0, "STATIONARY", delta_seconds / 60])
    else:
        velocity_kmh = (distance / 1000) / (delta_seconds / 3600) if delta_seconds > 0 else 0
        insert_clean_point([new[1], new[2], new[3], new[4], velocity_kmh, distance, "MOVING", 0])



def handle_key_fixed(key):
    if verbose:
        pretty_print(bcolors.BOLD, f"\n=== Getting location_data for key {key} ===")

    get_sql = "SELECT * FROM location_data WHERE hashed_key = ? ORDER BY time ASC"
    sqlite_cursor.execute(get_sql, (key,))
    location_data = sqlite_cursor.fetchall()

    if len(location_data) == 0:
        if verbose:
            print("Found no location data")
        return False

    previous_time = datetime.datetime.strptime(location_data[0][1], "%Y-%m-%d %H:%M:%S")

    anchor = None
    i = 0
    while i < len(location_data):
        # DEBUG
        # if debug:
        #     if i>200:
        #         break

        row = location_data[i]
        current_time = datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S")
        
        # Check if an IDLE_GAP exists or if we need a fresh boot milestone
        if current_time - previous_time > IDLE_GAP or anchor is None:
            anchor = None
            group = []
            skip = 0

            group_condition = True
            while group_condition and (i + skip) < len(location_data):
                point = location_data[i + skip]
                point_time = datetime.datetime.strptime(point[1], "%Y-%m-%d %H:%M:%S")

                # Measure window separation from the group-starting row
                difference = point_time - current_time
                if difference > WINDOW_TIME:
                    group_condition = False
                else:
                    group.append(point)
                    skip += 1

            if debug:
                pretty_print(bcolors.CYAN, f"i = {i}, IDLE ACTIVATED, {current_time - previous_time}, group size: {len(group)}")
            
            # We try to choose the next anchor, one with best score above threshold
            scores = []
            for current_point in group:
                score = CONFIDENCE_MULTIPLIER * current_point[6] - ACCURACY_MULTIPLIER * current_point[5]
                scores.append((current_point, score))
                if debug:
                    print(f"Confidence: {current_point[6]}, Accuracy: {current_point[5]}, Score: {score}")

            best = max(scores, key=lambda x: x[1])
            if best[1] > MINIMUM_STATIC_SCORE:  # We have new anchor.
                anchor = best[0]
                insert_clean_point([best[0][1], best[0][2], best[0][3], best[0][4], None, None, "INIT", None]) 
                
                # Advance tracking time directly to our confirmed new anchor
                previous_time = datetime.datetime.strptime(anchor[1], "%Y-%m-%d %H:%M:%S")
                if debug:
                    pretty_print(bcolors.GREEN, f"New anchor. Skipping: {skip}")
                
                # Jump past the entire consumed group
                i += skip
            else:
                if debug:
                    pretty_print(bcolors.RED, f"No new anchor chosen. Skipping: {skip}")
                
                # If selection fails, advance time tracking and slide forward safely by 1 step
                previous_time = current_time
                i += skip 
        
        # There is no gap, we have an anchor, we choose the next points
        # Note: this part was especially difficult, I did write the code myself, I debugged it with the help of AI.
        else:
            if debug:
                pretty_print(bcolors.HEADER, f"i = {i}, FINDING NEXT POINTS")
            found = False            

            # We have to calculate groups until we get one with a point with confidence 3
            groups = []
            end_point = None

            # Creating groups
            while i < len(location_data) and not found:
                row = location_data[i]
                window_base_time = datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S")

                group = []
                skip = 0

                group_condition = True
                while group_condition and (i + skip) < len(location_data):
                    point = location_data[i + skip]
                    point_time = datetime.datetime.strptime(point[1], "%Y-%m-%d %H:%M:%S")

                    # FIX: Measure window separation relative to the start of THIS specific group
                    if (point_time - window_base_time) > WINDOW_TIME:
                        group_condition = False
                    else:
                        group.append(point)
                        
                        # FIX: Check milestone state natively inside the valid window cluster
                        if point[6] == 3:
                            found = True
                            end_point = point

                            if debug:
                                pretty_print(bcolors.GREEN, f"Found anchor at i = {i}, skipping: {skip}, time: {point[1]}")
                            # We stop adding more points to this window bucket once ground truth is hit
                            skip += 1
                            break
                        
                        skip += 1

                if found:
                    i += skip
                    break
                else:
                    # Here we append groups. We first clean them and merge points that are too close
                    scores_and_points = []
                    for point in group:
                        point_score = CONFIDENCE_MULTIPLIER * point[6] - ACCURACY_MULTIPLIER * point[5]
                        scores_and_points.append((point, point_score))

                    # Sort by score descending (best points first)
                    scores_and_points.sort(key=lambda x: x[1], reverse=True)

                    clean_group = []
                    for point, score in scores_and_points:
                        merged = False
                        for clean_point in clean_group:
                            distance = get_distance((point[3], point[4]), (clean_point[3], clean_point[4]))
                            if distance < DISTANCE_MERGE:
                                merged = True
                                break
                        
                        if not merged:
                            clean_group.append(point)

                    groups.append(clean_group)
                    i += skip

                # If we didn't find any confidence 3 point, we choose the final endpoint as the best point from the last group. 
                if i >= len(location_data):
                    if groups:
                        fallback_group = groups.pop()
                        scores = []
                        for point in fallback_group:
                            score = CONFIDENCE_MULTIPLIER * point[6] - ACCURACY_MULTIPLIER * point[5]
                            scores.append((point, score))
                        
                        best_fallback = max(scores, key=lambda x: x[1])
                        end_point = best_fallback[0]
                        
                        break

            
                
            # Processing groups

            # if debug:
            #     print(f"GROUPS: {len(groups)} ")

            # We found the next anchor in the right next window. We just add it.
            if len(groups) ==0:
                add_point(anchor, end_point)

                anchor = end_point
                previous_time = datetime.datetime.strptime(anchor[1], "%Y-%m-%d %H:%M:%S")


            else:
                start_point = anchor

                dijkstra_graph = build_layered_graph(start_point, groups, end_point)

                if verbose:
                    print("Finding optimal path...")
                result_ids = dijkstra_shortest_path(dijkstra_graph, start_point[0], end_point[0])


            



    return True

def build_layered_graph(start_point, groups, end_point):
    layers = [[start_point]] + groups + [[end_point]]
    graph = {}

    # We also need a helper mapping to look backward one layer and check where we came from
    # Formatted as: { current_node_id: [list_of_possible_parent_nodes] }
    parent_map = {}

    for layer_idx in range(len(layers) - 1):
        current_layer = layers[layer_idx]
        next_layer = layers[layer_idx + 1]

        for node_a in current_layer:
            node_a_id = node_a[0]
            node_a_coords = (node_a[3], node_a[4])

            if node_a_id not in graph:
                graph[node_a_id] = {}

            for node_b in next_layer:
                node_b_id = node_b[0]
                node_b_coords = (node_b[3], node_b[4])

                # 1. Kinematic Math
                delta = get_time_difference(node_a, node_b)
                delta_seconds = delta.total_seconds()

                if delta_seconds <= 0:
                    continue

                distance = get_distance(node_a_coords, node_b_coords)
                velocity_kmh = (distance / 1000) / (delta_seconds / 3600)

                # Velocity Gate
                if velocity_kmh > VELOCITY_CUTOFF_KMH:
                    continue

                # 2. U-Turn / Bearing Validation
                # If node_a has known parents from the previous layer, check the turn angle
                turn_penalty = 0
                is_impossible_u_turn = False

                if node_a_id in parent_map and len(parent_map[node_a_id]) > 0:
                    # Calculate the outgoing bearing from A -> B
                    bearing_out = get_bearing(node_a_coords, node_b_coords)
                    
                    for parent_node in parent_map[node_a_id]:
                        parent_coords = (parent_node[3], parent_node[4])
                        # Calculate the incoming bearing from Parent -> A
                        bearing_in = get_bearing(parent_coords, node_a_coords)
                        
                        # Calculate the absolute difference between the angles
                        angle_diff = abs(bearing_out - bearing_in)
                        if angle_diff > 180:
                            angle_diff = 360 - angle_diff

                        # If the turn angle is extremely sharp (e.g., > 140 degrees) 
                        # AND the velocity is high, it's a ghost-ping zigzag pattern
                        if angle_diff > ANGLE_CUTOFF and velocity_kmh > VELOCITY_ANGLE_CUTOFF:
                            is_impossible_u_turn = True
                            break
                        
                        # Apply a rolling penalty for softer, but unnatural bends
                        if angle_diff > ANGLE_PENALTY_CUTOFF:
                            turn_penalty = max(turn_penalty, (angle_diff - ANGLE_PENALTY_CUTOFF) * TURN_PENALTY_MULTIPLIER)
                if is_impossible_u_turn:
                    continue

                # 3. Cost Calculation
                accuracy_cost = ACCURACY_MULTIPLIER * node_b[5]
                distance_cost = DISTANCE_MULTIPLIER * distance
                
                # Add the directional turn penalty directly to the edge weight
                edge_cost = distance_cost + accuracy_cost + turn_penalty

                # Map the valid forward edge
                graph[node_a_id][node_b_id] = edge_cost

                # Record that node_a is a valid parent for node_b for the next layer's loop
                if node_b_id not in parent_map:
                    parent_map[node_b_id] = []
                parent_map[node_b_id].append(node_a)

    if end_point[0] not in graph:
        graph[end_point[0]] = {}

    return graph


# Why does Lord give his toughest battles to his weakest soldiers 😭. I have JUST failed the TEA exam... and I need to implement dijkstra again.
def dijkstra_shortest_path(graph, start_node, end_node):
    # Track the lowest cumulative cost to reach each node
    # Initialized to infinity for all nodes except the starting anchor
    distances = {node: float('inf') for node in graph}
    distances[start_node] = 0

    # Track predecessors to rebuild the winning track backward at the finish line
    parents = {node: None for node in graph}

    # Min-priority queue storing tuples of: (cumulative_cost, node_id)
    priority_queue = [(0, start_node)]

    while priority_queue:
        current_distance, current_node = heapq.heappop(priority_queue)

        # If we reached our target destination, we can stop evaluating immediately
        if current_node == end_node:
            break

        # Skip processing if we already found a more efficient route to this node
        if current_distance > distances.get(current_node, float('inf')):
            continue

        # Check all valid time-forward edges spilling out of the current node
        neighbors = graph.get(current_node, {})
        for neighbor, edge_cost in neighbors.items():
            path_cost = current_distance + edge_cost

            # If this route is cheaper than any previously logged attempt, record it
            if path_cost < distances.get(neighbor, float('inf')):
                distances[neighbor] = path_cost
                parents[neighbor] = current_node
                heapq.heappush(priority_queue, (path_cost, neighbor))

    # Reconstruct the optimal path by reading back through the parent breadcrumbs
    path = []
    step = end_node
    
    # Trace backward until we hit the start node anchor
    while step is not None:
        path.append(step)
        step = parents.get(step)

    # Reverse the list so it flows in true chronological tracking order
    path.reverse()

    # Safety Check: If the path doesn't start at our anchor, no valid kinematic path was found
    if path[0] != start_node:
        return []

    return path



def filter_location_data():

    if verbose:
        print("=== Getting tag keys from sqlite database ===")

    tags_sql = "SELECT hashed_key FROM tags"
    sqlite_cursor.execute(tags_sql)
    tag_keys = sqlite_cursor.fetchall()

    if verbose:
        print(f"Found {len(tag_keys)} tags")

    for key in tag_keys:
        if key[0] != "":
            result = handle_key_fixed(key[0])
            if result:
                break


    if verbose:
        print("Done!")


filter_location_data()