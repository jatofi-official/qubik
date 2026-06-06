-- This code is for MySQL databases
CREATE TABLE tags(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    hashed_key TEXT UNIQUE NOT NULL
);

CREATE TABLE location_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT NOT NULL,
    hashed_key TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    accuracy INTEGER,
    -- I dropped battery info, since OpenHaystack has it just as a placeholder
    confidence INTEGER,

    FOREIGN KEY (hashed_key) REFERENCES tags(hashed_key),
    UNIQUE (time, hashed_key)
);

CREATE TABLE clean_location_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT NOT NULL,
    hashed_key TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    velocity REAL,
    distance REAL,
    motion_state TEXT,
    time_spent_here INTEGER,
    cluster_id TEXT,

    FOREIGN KEY (hashed_key) REFERENCES tags(hashed_key),
    UNIQUE (time, hashed_key)
);