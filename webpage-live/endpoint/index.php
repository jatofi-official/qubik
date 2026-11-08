<?php
declare(strict_types=1);

// OwnTracks HTTP endpoint. Served at /endpoint (this is the only public file).
// Config lives outside the web root: <repo>/owntracks/config.php
$config = require dirname(__DIR__, 2) . '/owntracks/config.php';

const MAX_BODY = 65536;
const MIN_TST = 1577836800; // 2020-01-01 UTC

function logLine(array $cfg, string $msg): void {
    @error_log(gmdate('c') . ' ' . $msg . "\n", 3, $cfg['log_file']);
}

function respond(int $code, string $body = '[]'): never {
    http_response_code($code);
    header('Content-Type: application/json');
    echo $body;
    exit;
}

function unauthorized(): never {
    header('WWW-Authenticate: Basic realm="OwnTracks"');
    respond(401, '{"error":"unauthorized"}');
}

// Never leak errors to the client
ini_set('display_errors', '0');
set_exception_handler(function (Throwable $e) use ($config) {
    logLine($config, 'ERROR ' . $e->getMessage() . ' @ ' . $e->getFile() . ':' . $e->getLine());
    respond(500, '{"error":"server error"}');
});

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    respond(405, '{"error":"method not allowed"}');
}

// --- Credentials: Apache+FPM often hides PHP_AUTH_*, so try the fallbacks ---
$user = $_SERVER['PHP_AUTH_USER'] ?? null;
$pass = $_SERVER['PHP_AUTH_PW'] ?? null;
if ($user === null) {
    $h = $_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '';
    if (stripos($h, 'Basic ') === 0) {
        $decoded = base64_decode(substr($h, 6), true);
        if ($decoded !== false && str_contains($decoded, ':')) {
            [$user, $pass] = explode(':', $decoded, 2);
        }
    }
}
if ($user === null || $pass === null) unauthorized();

$pdo = new PDO($config['db_dsn'], $config['db_user'], $config['db_pass'], [
    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
    PDO::ATTR_EMULATE_PREPARES => false,
]);

$st = $pdo->prepare('SELECT id, password_hash, active FROM participants WHERE username = ?');
$st->execute([$user]);
$p = $st->fetch(PDO::FETCH_ASSOC);
// Always run password_verify (dummy hash if user unknown) to keep timing similar
$hash = $p['password_hash'] ?? '$2y$10$usesomesillystringforsaltuOq1ZtY1x0aKpYb1Zk4vKkq2X8h5W';
$ok = password_verify($pass, $hash);
if (!$p || !$ok || !(int)$p['active']) {
    logLine($config, 'AUTH FAIL user=' . substr($user, 0, 64));
    unauthorized();
}
$pid = (int)$p['id'];

// --- Body: max 64 KB, must be a JSON object ---
if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > MAX_BODY) respond(413, '{"error":"too large"}');
$raw = file_get_contents('php://input', false, null, 0, MAX_BODY + 1);
if ($raw === false || strlen($raw) > MAX_BODY) respond(413, '{"error":"too large"}');
$data = json_decode($raw, true);
if (!is_array($data) || ($data !== [] && array_is_list($data))) respond(400, '{"error":"invalid json"}');

$now = gmdate('Y-m-d H:i:s');
$type = is_string($data['_type'] ?? null) ? $data['_type'] : null;

function logMessage(PDO $pdo, int $pid, string $now, ?string $type, string $reason, string $raw): void {
    $pdo->prepare('INSERT INTO message_log (participant_id, received_at, type, reason, raw_json) VALUES (?,?,?,?,?)')
        ->execute([$pid, $now, $type !== null ? substr($type, 0, 32) : null, $reason, $raw]);
}

if ($type === 'encrypted') {
    logMessage($pdo, $pid, $now, $type, 'encrypted payload not supported', $raw);
    respond(200);
}
if ($type !== 'location') {
    logMessage($pdo, $pid, $now, $type, 'non-location message', $raw);
    respond(200);
}

// --- Validate location ---
$lat = $data['lat'] ?? null; $lon = $data['lon'] ?? null; $tst = $data['tst'] ?? null;
$reason = null;
if (!(is_int($lat) || is_float($lat)) || !(is_int($lon) || is_float($lon)) || !is_int($tst)) {
    $reason = 'missing or non-numeric lat/lon/tst';
} elseif ($lat < -90 || $lat > 90 || $lon < -180 || $lon > 180) {
    $reason = 'lat/lon out of range';
} elseif ($tst < MIN_TST || $tst > time() + 86400) {
    $reason = 'tst out of range';
}
if ($reason !== null) {
    logMessage($pdo, $pid, $now, $type, 'invalid: ' . $reason, $raw);
    respond(200);
}

// Optional fields: keep only well-typed values
$int = fn($k) => (isset($data[$k]) && is_int($data[$k])) ? $data[$k] : null;
$str = fn($k, $n) => (isset($data[$k]) && is_string($data[$k])) ? substr($data[$k], 0, $n) : null;
$hdr = fn($k) => isset($_SERVER[$k]) ? substr((string)$_SERVER[$k], 0, 100) : null;

// Duplicates (same point, or same msg_id) hit a unique key; the no-op update makes them silent.
$sql = 'INSERT INTO gps_points
  (participant_id, device, limit_user, msg_id, tst, created_at_device, received_at, lat, lon,
   acc, alt, vel, batt, bs, conn, trigger_t, tid, raw_json)
  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
  ON DUPLICATE KEY UPDATE id = id';
$pdo->prepare($sql)->execute([
    $pid, $hdr('HTTP_X_LIMIT_D'), $hdr('HTTP_X_LIMIT_U'), $str('_id', 64), $tst, $int('created_at'), $now,
    number_format((float)$lat, 7, '.', ''), number_format((float)$lon, 7, '.', ''),
    $int('acc'), $int('alt'), $int('vel'), $int('batt'), $int('bs'),
    $str('conn', 4), $str('t', 4), $str('tid', 8), $raw,
]);
respond(200);
