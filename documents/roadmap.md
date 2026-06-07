# TODO

## Data processing
- Python script for extracting data from MySQL to Sqlite3
- Data filtering
    * For each tracker separately, by time pings (aggregates data from one ping in a 1 minute window)
    * Automatically calculates velocity, distance, time spent on place and groups trackers by location
    * Sliding window, judging algorithm based on confidence and relative velocity
    * Result will be a table which adds columns velocity (from previous to current), time spent on a place and distance

- Algoritm for data filtering:
    * We accept the first point as being correct.
    
    

Every calculation later is done on this aggregated data
### Transport classification
- Script for categorizing mode of travel
    * Will take in account speed and previous speed

### Altitude
- Download topographic data
    * Europe can be less accurate, Higher accuracy only for Slovakia
    * Fallback to less accurate data in case more accurate is missing
- Create API on my home server
- Script for adding topography 
    * Will process aggregated data and add column elevation
    
### Social interaciton
- Script for calculating social interracitons
    * Will process data time for all trackers in paralell.
    * Output will be:
        + Areas of interest (a tracker has spent some time on, multiple degrees)
        + Meetings (trackers have likely met)
        + Close event (trackers were close to each other)

## Data analysis and visualisation
- TODO
    
- we will create a flask

- homepage for each tracker.
    - static information:
        * days in operation
        * clean vs dirty data count
        * 
    - dynamic information for day
        * elevation profile
        * velocity profile (includes modes of transportation)
        * map of movement
        * animation???

------WE ARE HERE------

- homepage for multiple trackers
    - possible meeting points on map
    

Analysis:

- for each tag we want radius of gyration.
- cumulative distance for each mode of transport
- How many times two trackers met.
- density map for each point

Distribution:
- daily max speed
- daily radius of gyration
- daily elevation gain
- daily pings, 