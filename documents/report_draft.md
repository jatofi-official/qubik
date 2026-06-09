# Draft Report: Analysis of Community Relayed Location Trackers

## Title page

- Project title: Analysis of community relayed location trackers
- Author: Jakub Samuel Hlavatý
- Date: June 2026
- Institution: [Your school / faculty name]

---

## Abstract

This report summarizes a technical analysis of movement data collected from custom OpenHaystack-compatible location trackers. The analysis pipeline imports encrypted tracker reports from a MySQL backend, converts them into SQLite for final processing, filters noisy position reports, reconstructs trips, estimates transport modes, and enriches locations with elevation data. The report also documents the command-line scripts used for each stage and provides static visualizations as required by the course. The main findings include the quality of the filtered data, daily mobility statistics, and the feasibility of using community relayed trackers for basic transport and interaction analytics.

---

## 1. Introduction

The goal of this project is to analyze movement data obtained from a set of community relayed location trackers. These trackers use the OpenHaystack ecosystem and are carried by volunteers who hand them off to other participants. The analysis aims to reconstruct each tracker’s journey, detect interaction events such as meetings or frequently visited places, classify transport modes, and calculate vertical altitude changes.

OpenHaystack trackers present a specific set of challenges. The location reports are generated periodically to preserve battery life, and each observation includes metadata such as latitude, longitude, accuracy, battery status, and confidence. Because the standard OpenHaystack interface provides only seven days of history, a custom backend with a MySQL database was used to collect and archive tracker reports over longer periods.

In this project, the focus is on how to transform raw tracker pings into actionable mobility information while handling noise, duplicate observations, and incomplete coverage.

---

## 2. Data Description

### 2.1 Data sources

The data is sourced from a custom server running a macless-haystack service. Trackers are registered in a MySQL database using a registration script, and periodic encrypted location reports are fetched from the OpenHaystack-compatible API. The raw data ingestion pipeline consists of:

- `register_tag.py` and `register_all.sh` for adding tracker metadata to the MySQL `tags` table.
- `fetch_tag_locations.py` and `fetch_all.sh` for retrieving encrypted reports from the local server endpoint.
- `insert_tag.py` for inserting decrypted JSON location records into MySQL `location_data`.

After collection, data is exported to SQLite via `mysql-to-sqlite-dump.py` to enable portable analysis on the school server.

### 2.2 Data structure

Each raw observation contains:

- `time`: timestamp of the ping
- `hashed_key` / `tracker_id`: unique tracker identifier
- `latitude` and `longitude`: GPS coordinates
- `accuracy`: reported GPS accuracy in meters
- `battery`: battery level category
- `confidence`: quality score from the tracker report

The cleaned SQLite database contains additional derived tables such as `clean_location_data`, `trips`, `places`, and `daily_stats`.

### 2.3 Data quantity and quality

The dataset includes multiple registered trackers and tens of thousands of location pings. The data quality is mixed:

- Some pings have low confidence or poor accuracy.
- Trackers may be idle for long periods, resulting in sparse data.
- Reports are periodically missing or delayed because of the tracker broadcast schedule.

As required by the project rules, the report should include basic data characteristics such as record counts, attribute ranges, and the overall dataset span. A section later in the report should include a table summarizing the number of tags, total pings, valid pings after filtering, and the time span covered.

---

## 3. Method Overview

The analysis pipeline is designed as a sequence of stages that convert raw tracker reports into interpretable mobility records.

1. **Data ingestion and conversion**: Raw MySQL data is copied into SQLite to support local analysis and to ensure reproducibility on school hardware.
2. **Data filtering**: The `data-filtering.py` script groups reports within minute-long windows, selects the most reliable anchor points, and removes noisy or implausible observations. After selecting an anchor, batches of pings are loaded until one batch contains a ping with confidence level 3. If there are multiple such points in the batch, the first one is selected. This point acts as a new anchor. Close points within each group are merged, and the most probable path between the previous anchor and the new anchor is chosen. This is done by creating a layered graph of candidate nodes, where each edge is assigned a movement penalty calculated as:

    edge cost = distance cost + accuracy cost + sharp turn penalty

This step produces a `clean_location_data` table with motion states and estimated travel distance.
3. **Trip reconstruction**: The `generate-trips.py` script aggregates cleaned points into a timeline of trips and stationary segments, assigns transport modes based on speed thresholds, and computes elevation at each point using a GeoTIFF DEM through `ElevationLookup`.
4. **Daily analytics**: The `daily_analysis.py` script computes per-day statistics such as ping counts, max/min elevation, elevation gain, and stationary time, storing results in `daily_stats`.
5. **Distribution analysis**: The `analyze_distributions.py` script produces graphs of key statistics and fits them with normal distributions to assess the empirical shape of mobility metrics.
Most processing is implemented as command-line Python scripts, which supports the course emphasis on shell-based workflows. Visualizations are also produced as static figures suitable for inclusion in the final PDF report.
This workflow is justified by the need to reduce raw noise before any transport or social inference can be trusted. Aggregation into trips and daily summaries avoids over-interpreting individual noisy GPS pings.

---

## 4. Results and Discussion

### 4.1 Initial exploration

Begin this section by describing how the raw dataset was inspected and validated. Useful tables and figures include:

- A table of tag counts and ping counts per tracker.
- A histogram of ping timestamps, showing the time coverage of the dataset.
- A scatter plot or count of accuracy values to demonstrate measurement quality.

Explain the axes and how to interpret the plots. For example: "The x-axis shows time in days and the y-axis shows the number of pings recorded per day. This plot demonstrates periods of active reporting and gaps in collection."

### 4.2 Data cleaning results

Summarize how raw data was filtered:

- Count of raw vs filtered pings
- Number of `INIT`, `STATIONARY`, and `MOVING` points in `clean_location_data`
- Any outlier removal rules applied (e.g. velocity cutoff at 160 km/h)

A table such as `Raw pings | Clean points | Stationary segments | Moving segments` will help readers understand the effect of cleaning.

Discuss whether the filtered data appears consistent, and whether any anomalies remain.

### 4.3 Trip reconstruction and transport classification

Present the main mobility metrics from `trips` and `daily_stats`:

- Daily valid ping counts
- Max speed per day
- Min/max elevation per day
- Estimated elevation gain per day
- Total stationary minutes per day

A chart produced by `analyze_distributions.py` should be described in detail: explain that each subplot shows an empirical density for a given metric, and a dashed red curve shows the fitted normal distribution.

If available, include a short summary table of transport mode counts. If transport mode classification is based on velocity thresholds, explain the thresholds and what each mode means.

### 4.4 Social interaction potential

Describe the intended method for finding meetings and handoff events, even if the current implementation does not fully compute them. Explain that social interaction detection is based on spatial proximity in a time window and that the report should contain examples of tracker co-location events if available.

### 4.5 Discussion of findings

Interpret the results in a technical way:

- Which tracker behaviors are clearly visible?
- Does the data show long stationary periods, regular travel corridors, or abrupt jumps?
- What can be inferred from elevation gain and transport mode classification?
- Are there signs that the filtering pipeline is successful or that additional filtering is required?

Also mention limitations:

- GPS noise and low confidence values
- Irregular tracker broadcast intervals
- Dependence on a single DEM source for elevation
- The absence of a validated ground truth for transport mode

### 4.6 Project compliance and reproducibility

This project follows the course requirements by using command-line scripts for data acquisition, preprocessing, and analysis. The submitted protocol should document the exact commands used to run each stage, the locations of scripts, and the external resources required. The final report includes static figures derived from the analysis and explains the meaning of each table and graph, including axes, color coding, and units.

---

## 5. Conclusion

Summarize the completed work and reflect on the project.

### 5.1 Achievements

- Built a pipeline that imports raw OpenHaystack tracker data from MySQL into SQLite.
- Implemented data filtering to produce cleaned location points and reconstructed trips.
- Added elevation lookup using a GeoTIFF DEM and produced daily mobility statistics.
- Generated analysis plots demonstrating the distribution of key metrics.

### 5.2 Challenges

- Handling noisy and sparse location reports was difficult.
- Establishing robust criteria for choosing anchor points and merging stationary data required careful tuning.
- Transport mode classification is only approximate because speed alone is a weak signal.

### 5.3 Lessons learned and recommendations

- In hindsight, building an explicit data validation step earlier would help catch anomalies sooner.
- It may be better to compute social interactions as a separate pass after trip reconstruction instead of mixing it with cleaning.
- Future work should include geospatial index support and better temporal interpolation for missing pings.
- The project demonstrates that community relayed trackers can be analyzed in a meaningful way, but their usefulness depends strongly on reporting density and quality.

---

## Appendix / Notes for writing

- Use the report’s results section to reference actual numbers once you have them from the database.
- Replace generic statements with exact metrics from `daily_stats`, `trips`, and the generated plots.
- In tables, always include column definitions and units.
- In figure captions, explain the axes, any color coding, and the data source.
- Mention any use of AI code generation or external tools in the protocol and report if applicable.
- If the project is done in a pair, describe the division of responsibilities; otherwise state that the work is individual.

---

## Suggested report structure in Markdown or PDF

1. Title page
2. Abstract
3. Introduction
4. Data Description
5. Method Overview
6. Results and Discussion
7. Conclusion
8. Appendix / References

Each section should be written in complete paragraphs, with technical clarity and no informal language.
