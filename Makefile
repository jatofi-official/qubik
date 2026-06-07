DB_FILE = largeDB.db
RELEASE_DB = releaseDB.db
USER = root
PASSWORD = ""
DATABASE = tag_tracker
HOST = localhost

.PHONY: all pipeline clean deploy create-db clean-pipeline-db


all: pipeline deploy

# Used for creating database if MySQL database is available
create-db: clean $(DB_FILE)

# DO NOT RUN WITHOUT MYSQL DATABASE
clean:
	rm -f $(DB_FILE)

$(DB_FILE):
	sqlite3 $(DB_FILE) < create_database_sqlite.sql
	python3 processing-scripts/mysql-to-sqlite-dump.py $(USER) $(PASSWORD) -database $(DATABASE) -host $(HOST) -sqlite $(DB_FILE) -v

# Cleans the output of pipeline, does not delete critical data
clean-pipeline-db:
	sqlite3 largeDB.db 'DROP TABLE IF EXISTS clean_location_data; DROP TABLE IF EXISTS trips; DROP TABLE IF EXISTS places;'

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

deploy:
	cp $(DB_FILE) $(RELEASE_DB)
	cd flask  && export FLASK_APP=main.py && flask run --port=7777
