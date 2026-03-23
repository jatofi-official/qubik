-- This code is for MySQL databases
CREATE DATABASE tag_tracker;
USE tag_tracker;

CREATE TABLE tags(
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    name TEXT,
    hashed_key TEXT
);

CREATE TABLE location_data (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    time DATETIME NOT NULL,
    latitude DOUBLE NOT NULL,
    longitude DOUBLE NOT NULL,
    accuracy INTEGER,
    battery VARCHAR(50),
    confidence INTEGER
);