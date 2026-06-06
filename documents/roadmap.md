# TODO

## Data processing
- Python script for extracting data from MySQL to Sqlite3

------WE ARE HERE------

- Data filtering
    * For each tracker separately, by time pings (aggregates data from one ping in a 1 minute window)
    * Automatically calculates velocity, distance, time spent on place and groups trackers by location
    * Sliding window, judging algorithm based on confidence and relative velocity
    * Result will be a table which adds columns velocity (from previous to current), time spent on a place and distance

Every calculation later is done on this aggregated data
### Transport classification
- Script for categorizing mode of travel
    * Will take in account speed and previous speed

### Social interaciton
- Script for calculating social interracitons
    * Will process data time for all trackers in paralell.
    * Output will be:
        + Areas of interest (a tracker has spent some time on, multiple degrees)
        + Time trackers spent together
        + Meetings (trackers have likely met)
        + Close event (trackers were close to each other)

### Altitude
- Download topographic data
    * Europe can be less accurate, Higher accuracy only for Slovakia
    * Fallback to less accurate data in case more accurate is missing
- Create API on my home server
- Script for adding topography 
    * Will process aggregated data and add column elevation
    
## Data analysis and visualisation
- TODO
    

