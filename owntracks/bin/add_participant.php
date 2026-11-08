<?php
// Usage: php add_participant.php <username> <tid>
if (PHP_SAPI !== 'cli' || $argc !== 3) { fwrite(STDERR, "Usage: php add_participant.php <username> <tid>\n"); exit(1); }
require dirname(__DIR__) . '/db.php';
if ($mysqli->connect_errno) { fwrite(STDERR, "DB error: {$mysqli->connect_error}\n"); exit(1); }
$alphabet = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789';
$pw = '';
for ($i = 0; $i < 24; $i++) $pw .= $alphabet[random_int(0, strlen($alphabet) - 1)];
$st = $mysqli->prepare('INSERT INTO participants (username, password_hash, tid, active, created_at) VALUES (?,?,?,1,?)');
$hash = password_hash($pw, PASSWORD_DEFAULT); $tid = substr($argv[2], 0, 8); $now = gmdate('Y-m-d H:i:s');
$st->bind_param('ssss', $argv[1], $hash, $tid, $now);
if (!$st->execute()) { fwrite(STDERR, "Insert failed: {$st->error}\n"); exit(1); }
echo "Participant '{$argv[1]}' created. Password (shown once): $pw\n";
