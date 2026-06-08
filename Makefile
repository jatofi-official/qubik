DB_FILE = largeDB.db
RELEASE_DB = releaseDB.db
USER = root
PASSWORD = ""
DATABASE = tag_tracker
HOST = localhost
PORT = 7777

.PHONY: all pipeline clean deploy create-db clean-pipeline-db analysis


all: pipeline

# Used for creating database if MySQL database is available
create-db: clean $(DB_FILE)

# DO NOT RUN WITHOUT MYSQL DATABASE
clean:
	rm -f $(DB_FILE)
	rm -f $(RELEASE_DB)	

$(DB_FILE):
	sqlite3 $(DB_FILE) < create_database_sqlite.sql
	python3 processing-scripts/mysql-to-sqlite-dump.py $(USER) $(PASSWORD) -database $(DATABASE) -host $(HOST) -sqlite $(DB_FILE) -v

# Cleans the output of pipeline, does not delete critical data
clean-pipeline-db:
	sqlite3 $(DB_FILE) 'DROP TABLE IF EXISTS clean_location_data; DROP TABLE IF EXISTS trips; DROP TABLE IF EXISTS places;'

pipeline: $(DB_FILE)
	@echo ""
	@echo "DATA FILTERING"
	@echo "----------------"
	python3 processing-scripts/data-filtering.py -sqlite $(DB_FILE) -v
	@echo ""
	@echo "GENERATING TRIP"
	@echo "----------------"
#   Really smart way of choosing the first .tif file
	python3 processing-scripts/generate-trips.py -sqlite $(DB_FILE) -topo_data $(firstword $(wildcard topography_resources/*tif)) -v
	@echo ""

# DO NOT RUN ON SCHOOL COMPUTER
# The releaseDB is slightly manually edited.
# From my experience, it is sometimes better to fix a few outliers that to work hours
# on creating a fix that fixes them.
$(RELEASE_DB):
	cp $(DB_FILE) $(RELEASE_DB)

analysis: $(RELEASE_DB) clean-analysis-db
	cd analysis && python3 daily_analysis.py -sqlite ../$(RELEASE_DB) -v

clean-analysis-db: $(RELEASE_DB)
	sqlite3 $(RELEASE_DB) 'DROP TABLE IF EXISTS daily_stats;'


deploy: analysis
	cd flask  && export FLASK_APP=main.py && flask run --port=$(PORT)


