# Project proposal: Analysis of community relayed location trackers
Jakub Samuel Hlavatý

### Project goal
The goal of this project is to analyze movement data colected from custom OpenHaystack location trackers. These devices will be distributed among volunteers who will pass them to others. The project aims to reconstruct the journey of each tracker, identify "interaction events" (trackers meeting, change of tracker owner etc.), classify the mode of transportation used and calculating vertical altitude traveled.

### Data collection and processing
Data will be initially collected via a custom server using a macless-haystack docker image with a MySQL database backend. This is due to the limitation of OpenHaystack, which only returns results for the past 7 days. For the scope of the project demonstration, data will be exported into a SQLite3 database to ensure compatibility with the school server.

Each record of gps location includes `tracker_id`, `latitude`, `longitude`, `accuracy`, `battery` and `confidence`. To preserve battery, each tracker broadcasts every few minutes. Data will be filtered and cleaned using python. We will also use altitude data from open source public sources using their api. 

### Proposed analysis
#### 1. Velocity and transport classification
Calculating the geodesic distance between pings, we will derive the average speed for each segment. These segments will be categorized into modes of transport (walking, cycling/running, driving, ets.) and aggregated into reports for each category.

#### 2. Social interaction
Data will be analyzed chronologically to find points in which multiple trackers appear within a specific spatial buffer (e.g., 50 meters) during the same time window. By identifying clusters of pings from different devices, we can infer "handoff" events where a tracker exchanged owners or "social meetings" where trackers traveled together for a certain duration.

#### 3. Altitude and Topographic Analysis
By integrating external elevation data with our GPS coordinates, we will reconstruct a 3D profile of each tracker. This allows for the calculation of total vertical gain and loss, which will further refine our transport classification (e.g., distinguishing between a slow cyclist climbing a steep hill and a pedestrian).

### Technology used
**Database**: MySQL for server backend. SQLite3 for final analysis. Cron + bash for running database scripts written in python.

**Data processing**: Python with multiple libraries including `geopy`, `sqlite3` or `requests` for API integration.

**Visualisation**: Libraries `matplotlib` and `seaborn` as well as other libraries for geographic visualisation.