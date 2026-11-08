<?php
// Copy to db.php (not committed) and fill in. Lives outside the web root.

mysqli_report(MYSQLI_REPORT_OFF);

$mysqli = new mysqli('localhost', 'owntracks', 'CHANGE_ME', 'owntracks');
if (!$mysqli->connect_errno) {
	$mysqli->set_charset('utf8mb4');
}
// No HTML output here: the endpoint checks $mysqli->connect_errno itself.
