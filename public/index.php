<?php
header("Content-Type: application/json; charset=UTF-8");

require_once __DIR__ . '/../src/Services/UrlNormalizerService.php';
require_once __DIR__ . '/../src/Services/UnitEconomicsService.php';
require_once __DIR__ . '/../src/Services/LandingBuilderService.php';
require_once __DIR__ . '/../src/Services/PromParserService.php';
require_once __DIR__ . '/../src/Repositories/ProductRepository.php';

$pdo = require __DIR__ . '/../config/database.php';
$repo = new App\Repositories\ProductRepository($pdo);

$uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);

// Проверка работы API
if ($uri === '/api/v1/health') {
    echo json_encode([
        "ok" => true,
        "schema_version" => 1,
        "data" => [
            "status" => "UP",
            "database" => "connected",
            "timestamp" => date('c')
        ]
    ]);
    exit;
}

// Парсинг товара по URL
if ($uri === '/api/v1/products/parse' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $input = json_decode(file_get_contents('php://input'), true);
    $rawUrl = $input['url'] ?? '';

    if (empty($rawUrl)) {
        http_response_code(400);
        echo json_encode(["ok" => false, "error" => ["code" => "INVALID_INPUT", "message" => "Поле 'url' обязательно"]]);
        exit;
    }

    try {
        $normalizer = new App\Services\UrlNormalizerService();
        $parser = new App\Services\PromParserService($normalizer);
        $parsedData = $parser->parseUrl($rawUrl);

        $repo->saveProduct($parsedData);

        echo json_encode(["ok" => true, "schema_version" => 1, "data" => $parsedData]);
    } catch (\Exception $e) {
        http_response_code(400);
        echo json_encode(["ok" => false, "error" => ["code" => "ERROR", "message" => $e->getMessage()]]);
    }
    exit;
}
