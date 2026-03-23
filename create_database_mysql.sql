-- This code is for MySQL databases
CREATE DATABASE tag_tracker;
USE tag_tracker;

CREATE TABLE tags(
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255),
    hashed_key VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE location_data (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    time DATETIME NOT NULL,
    hashed_key VARCHAR(50),
    latitude DOUBLE NOT NULL,
    longitude DOUBLE NOT NULL,
    accuracy INTEGER,
    battery VARCHAR(50),
    confidence INTEGER,

    CONSTRAINT tag_hash_foreign_key 
        FOREIGN KEY (hashed_key) 
        REFERENCES tags(hashed_key)

    CONSTRAINT unique_tag
        UNIQUE (time,hashed_key)
);