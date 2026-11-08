<?php
// Usage: php export_csv.php <username> <from YYYY-MM-DD> <to YYYY-MM-DD> > out.csv   (UTC, inclusive)
if (PHP_SAPI !== 'cli' || $argc !== 4) { fwrite(STDERR, "Usage: php export_csv.php <username> <from> <to>\n"); exit(1); }
$c = require dirname(__DIR__) . '/config.php';
$pdo = new PDO($c['db_dsn'], $c['db_user'], $c['db_pass'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$from = strtotime($argv[2] . ' 00:00:00 UTC');
$to = strtotime($argv[3] . ' 23:59:59 UTC');
if ($from === false || $to === false) { fwrite(STDERR, "Bad date\n"); exit(1); }
$st = $pdo->prepare('SELECT g.tst, g.lat, g.lon, g.acc, g.alt, g.vel, g.batt, g.bs, g.conn, g.trigger_t, g.device
  FROM gps_points g JOIN participants p ON p.id = g.participant_id
  WHERE p.username = ? AND g.tst BETWEEN ? AND ? ORDER BY g.tst');
$st->execute([$argv[1], $from, $to]);
$out = fopen('php://stdout', 'w');
fputcsv($out, ['time_utc','lat','lon','acc','alt','vel','batt','bs','conn','trigger','device'], ',', '"', '');
while ($r = $st->fetch(PDO::FETCH_ASSOC)) {
    $r['tst'] = gmdate('Y-m-d\TH:i:s\Z', (int)$r['tst']);
    fputcsv($out, $r, ',', '"', '');
}
