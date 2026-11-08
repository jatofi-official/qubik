CREATE TABLE participants (
  id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  tid VARCHAR(8) NOT NULL,
  active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL
) ENGINE=InnoDB;

CREATE TABLE gps_points (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  participant_id INT UNSIGNED NOT NULL,
  device VARCHAR(100) NULL,          -- X-Limit-D (informational)
  limit_user VARCHAR(100) NULL,      -- X-Limit-U (informational, never used for identity)
  msg_id VARCHAR(64) NULL,           -- OwnTracks _id
  tst INT UNSIGNED NOT NULL,         -- time of GPS fix, Unix seconds UTC
  created_at_device INT UNSIGNED NULL,
  received_at DATETIME NOT NULL,     -- server time, UTC
  lat DECIMAL(10,7) NOT NULL,
  lon DECIMAL(10,7) NOT NULL,
  acc INT NULL, alt INT NULL, vel INT NULL, batt INT NULL, bs TINYINT NULL,
  conn VARCHAR(4) NULL, trigger_t VARCHAR(4) NULL, tid VARCHAR(8) NULL,
  raw_json TEXT NOT NULL,
  UNIQUE KEY uq_point (participant_id, tst, lat, lon),
  UNIQUE KEY uq_msg (participant_id, msg_id),   -- NULL msg_id is allowed multiple times
  KEY idx_part_tst (participant_id, tst),
  FOREIGN KEY (participant_id) REFERENCES participants(id)
) ENGINE=InnoDB;

-- Non-location messages and rejected/invalid payloads
CREATE TABLE message_log (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  participant_id INT UNSIGNED NULL,
  received_at DATETIME NOT NULL,
  type VARCHAR(32) NULL,
  reason VARCHAR(255) NULL,
  raw_json TEXT NOT NULL,
  KEY idx_part (participant_id)
) ENGINE=InnoDB;
