<?php
// Usage: php add_participant.php <username> <tid>
if (PHP_SAPI !== 'cli' || $argc !== 3) { fwrite(STDERR, "Usage: php add_participant.php <username> <tid>\n"); exit(1); }
$c = require dirname(__DIR__) . '/config.php';
$pdo = new PDO($c['db_dsn'], $c['db_user'], $c['db_pass'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$alphabet = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789';
$pw = '';
for ($i = 0; $i < 24; $i++) $pw .= $alphabet[random_int(0, strlen($alphabet) - 1)];
$pdo->prepare('INSERT INTO participants (username, password_hash, tid, active, created_at) VALUES (?,?,?,1,?)')
    ->execute([$argv[1], password_hash($pw, PASSWORD_DEFAULT), substr($argv[2], 0, 8), gmdate('Y-m-d H:i:s')]);
echo "Participant '{$argv[1]}' created. Password (shown once): $pw\n";
