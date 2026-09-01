<?php
$dbPath = __DIR__ . '/../data/app.db';

try {
    $pdo = new PDO("sqlite:" . $dbPath);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    $pdo->exec("PRAGMA foreign_keys = ON;");
    return $pdo;
} catch (PDOException $e) {
    die(json_encode([
        "ok" => false,
        "error" => ["code" => "DB_ERROR", "message" => $e->getMessage()]
    ]));
}
