# OwnTracks endpoint

Public file: `webpage-live/endpoint/index.php` -> https://qubik.mustangy.sk/endpoint
Everything else (config, schema, CLI tools, logs) lives in `owntracks/`, outside the web root.

## Setup
1. `mysql -u root -p -e "CREATE DATABASE owntracks CHARACTER SET utf8mb4; CREATE USER 'owntracks'@'localhost' IDENTIFIED BY '...'; GRANT SELECT,INSERT ON owntracks.* TO 'owntracks'@'localhost';"`
   (use a separate admin user for `add_participant.php`, or grant it INSERT on participants too – INSERT is already included).
2. `mysql -u root -p owntracks < schema.sql`
3. `cp db.example.php db.php`, edit, `mkdir logs && chmod 770 logs` (writable by the PHP-FPM user, e.g. www-data).
4. `php bin/add_participant.php alice AL` – prints the password once.
5. Apache: `webpage-live/endpoint/.htaccess` passes the Authorization header (needs `AllowOverride FileInfo` / `All`
   for the site, and mod_rewrite). If you can't use .htaccess, put in the vhost: `CGIPassAuth On`.
   nginx equivalent: `fastcgi_param HTTP_AUTHORIZATION $http_authorization;`
6. OwnTracks app: Mode HTTP, URL `https://qubik.mustangy.sk/endpoint`, authentication = username/password.

Export: `php bin/export_csv.php alice 2026-11-01 2026-11-08 > alice.csv`

## Tests (replace PASS)
```bash
U=https://qubik.mustangy.sk/endpoint; A="alice:PASS"
P='{"_type":"location","lat":48.1486,"lon":17.1077,"tst":1762600000,"acc":10,"batt":80,"_id":"abc123"}'
# valid -> 200 [] and one row
curl -si -u $A -H 'Content-Type: application/json' -d "$P" $U
# same again -> 200 [], no new row
curl -si -u $A -H 'Content-Type: application/json' -d "$P" $U
# non-location -> 200 [], no point
curl -si -u $A -H 'Content-Type: application/json' -d '{"_type":"status","_id":"x"}' $U
# wrong password -> 401
curl -si -u alice:wrong -d "$P" $U
# GET -> 405
curl -si -u $A $U
# invalid JSON -> 400
curl -si -u $A -H 'Content-Type: application/json' -d '{oops' $U
# charset in Content-Type -> 200 []
curl -si -u $A -H 'Content-Type: application/json; charset=utf-8' -d '{"_type":"location","lat":48.15,"lon":17.11,"tst":1762600060}' $U
```
Check rows: `SELECT COUNT(*) FROM gps_points;` Errors are logged to `owntracks/logs/owntracks.log`.
