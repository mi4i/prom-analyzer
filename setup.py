import os

# Описание всех папок и файлов проекта
files = {
    "config/database.php": """<?php
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
""",

    "data/backups/.gitkeep": "",

    "src/Services/UrlNormalizerService.php": """<?php
namespace App\\Services;

class UrlNormalizerService {
    private array $allowedDomains;

    public function __construct(array $allowedDomains = ['prom.ua', 'shafa.ua', 'bigl.ua']) {
        $this->allowedDomains = $allowedDomains;
    }

    public function cleanUrl(string $rawUrl): string {
        $parsed = parse_url(trim($rawUrl));
        if (!isset($parsed['scheme']) || !isset($parsed['host'])) {
            throw new \\InvalidArgumentException("Некорректный формат URL");
        }
        $host = strtolower($parsed['host']);
        $isAllowed = false;
        foreach ($this->allowedDomains as $domain) {
            if ($host === $domain || str_ends_with($host, '.' . $domain)) {
                $isAllowed = true;
                break;
            }
        }
        if (!$isAllowed) {
            throw new \\InvalidArgumentException("Домен {$host} не входит в список разрешенных");
        }
        $scheme = strtolower($parsed['scheme']);
        $path = $parsed['path'] ?? '';
        $cleanQuery = '';
        if (isset($parsed['query'])) {
            parse_str($parsed['query'], $queryParams);
            $forbiddenKeys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'gclid', 'fbclid', 'ref', 'a', 'b'];
            $filteredParams = array_filter($queryParams, fn($key) => !in_array(strtolower($key), $forbiddenKeys), ARRAY_FILTER_USE_KEY);
            if (!empty($filteredParams)) {
                $cleanQuery = '?' . http_build_query($filteredParams);
            }
        }
        return "{$scheme}://{$host}{$path}{$cleanQuery}";
    }

    public function generateProductId(string $cleanUrl): string {
        $hash = substr(md5($cleanUrl), 0, 10);
        return "prom_{$hash}";
    }
}
""",

    "src/Repositories/ProductRepository.php": """<?php
namespace App\\Repositories;

use PDO;

class ProductRepository {
    private PDO $db;

    public function __construct(PDO $db) {
        $this->db = $db;
    }

    public function saveProduct(array $data): void {
        $sql = "
            INSERT INTO products (
                product_id, schema_version, title, clean_url, image_url, 
                status, currency, sale_price, cost_price, shipping_cost, 
                return_cost, payment_fee, updated_at
            ) VALUES (
                :product_id, 1, :title, :clean_url, :image_url, 
                :status, :currency, :sale_price, :cost_price, :shipping_cost, 
                :return_cost, :payment_fee, CURRENT_TIMESTAMP
            )
            ON CONFLICT(product_id) DO UPDATE SET
                title = EXCLUDED.title,
                image_url = EXCLUDED.image_url,
                status = EXCLUDED.status,
                sale_price = EXCLUDED.sale_price,
                cost_price = EXCLUDED.cost_price,
                shipping_cost = EXCLUDED.shipping_cost,
                return_cost = EXCLUDED.return_cost,
                payment_fee = EXCLUDED.payment_fee,
                updated_at = CURRENT_TIMESTAMP
        ";

        $stmt = $this->db->prepare($sql);
        $stmt->execute([
            ':product_id'    => $data['product_id'],
            ':title'         => $data['title'],
            ':clean_url'     => $data['clean_url'],
            ':image_url'     => $data['image_url'] ?? null,
            ':status'        => $data['status'] ?? 'active',
            ':currency'      => $data['currency'] ?? 'UAH',
            ':sale_price'    => (float)($data['sale_price'] ?? 0),
            ':cost_price'    => (float)($data['cost_price'] ?? 0),
            ':shipping_cost' => (float)($data['shipping_cost'] ?? 0),
            ':return_cost'   => (float)($data['return_cost'] ?? 0),
            ':payment_fee'   => (float)($data['payment_fee'] ?? 0)
        ]);

        if (!empty($data['supplier'])) {
            $this->saveSupplier($data['product_id'], $data['supplier']);
        }
    }

    public function findById(string $productId): ?array {
        $stmt = $this->db->prepare("SELECT * FROM products WHERE product_id = :id");
        $stmt->execute([':id' => $productId]);
        $product = $stmt->fetch(PDO::FETCH_ASSOC);
        return $product ?: null;
    }

    private function saveSupplier(string $productId, array $supplier): void {
        $stmt = $this->db->prepare("
            INSERT INTO product_suppliers (product_id, name, url, is_primary)
            VALUES (:pid, :name, :url, 1)
        ");
        $stmt->execute([
            ':pid'  => $productId,
            ':name' => $supplier['name'] ?? 'Неизвестный поставщик',
            ':url'  => $supplier['url'] ?? ''
        ]);
    }
}
""",

    "src/Services/UnitEconomicsService.php": """<?php
namespace App\\Services;

class UnitEconomicsService {
    public function calculatePlanned(array $params): array {
        $salePrice     = (float)($params['sale_price'] ?? 0);
        $costPrice    = (float)($params['cost_price'] ?? 0);
        $approvalRate  = ((float)($params['approval_rate'] ?? 100)) / 100.0;
        $buyoutRate    = ((float)($params['buyout_rate'] ?? 100)) / 100.0;
        $shippingCost  = (float)($params['shipping_cost'] ?? 0);
        $returnCost    = (float)($params['return_cost'] ?? 0);
        $cplTarget     = (float)($params['cpl_target'] ?? 0);

        $effectiveCpl = $approvalRate > 0 ? ($cplTarget / $approvalRate) : 0;
        $expectedLogistics = ($buyoutRate * $shippingCost) + ((1.0 - $buyoutRate) * $returnCost);
        $netProfit = ($salePrice * $buyoutRate) - ($costPrice * $buyoutRate) - $expectedLogistics - $effectiveCpl;

        return [
            'effective_cpl'      => round($effectiveCpl, 2),
            'expected_logistics' => round($expectedLogistics, 2),
            'net_profit'         => round($netProfit, 2),
            'is_profitable'      => $netProfit > 0
        ];
    }
}
""",

    "src/Services/LandingBuilderService.php": """<?php
namespace App\\Services;

use App\\Repositories\\ProductRepository;

class LandingBuilderService {
    private ProductRepository $repository;

    public function __construct(ProductRepository $repository) {
        $this->repository = $repository;
    }

    public function buildLandingPayload(string $productId): array {
        $product = $this->repository->findById($productId);
        if (!$product) {
            throw new \\Exception("Товар {$productId} не найден", 404);
        }
        $slugSuggestion = strtolower(trim(preg_replace('/[^A-Za-z0-9-]+/', '-', $product['title']), '-'));
        return [
            "product_id"      => $product['product_id'],
            "title"           => $product['title'],
            "slug_suggestion" => $slugSuggestion,
            "price"           => (float)$product['sale_price'],
            "old_price"       => round((float)$product['sale_price'] * 1.3),
            "currency"        => $product['currency'],
            "headline"        => $product['title'],
            "subheadline"     => "",
            "cta"             => "Заказать",
            "images"          => !empty($product['image_url']) ? [$product['image_url']] : []
        ];
    }
}
""",

    "src/Services/PromParserService.php": """<?php
namespace App\\Services;

class PromParserService {
    private UrlNormalizerService $urlNormalizer;

    public function __construct(UrlNormalizerService $urlNormalizer) {
        $this->urlNormalizer = $urlNormalizer;
    }

    public function parseUrl(string $rawUrl): array {
        $cleanUrl = $this->urlNormalizer->cleanUrl($rawUrl);
        $productId = $this->urlNormalizer->generateProductId($cleanUrl);
        return [
            'product_id' => $productId,
            'clean_url'  => $cleanUrl,
            'title'      => 'Тестовый товар',
            'sale_price' => 450.0,
            'currency'   => 'UAH',
            'status'     => 'active'
        ];
    }
}
""",

    "public/index.php": """<?php
header("Content-Type: application/json; charset=UTF-8");

require_once __DIR__ . '/../src/Services/UrlNormalizerService.php';
require_once __DIR__ . '/../src/Services/UnitEconomicsService.php';
require_once __DIR__ . '/../src/Services/LandingBuilderService.php';
require_once __DIR__ . '/../src/Services/PromParserService.php';
require_once __DIR__ . '/../src/Repositories/ProductRepository.php';

$pdo = require __DIR__ . '/../config/database.php';

$uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);

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
""",

    ".gitignore": """
.env
/data/*.db
/data/*.sqlite
/data/backups/*
!.gitkeep
*.log
.DS_Store
.idea/
.vscode/
""",

    ".env.example": """
APP_ENV=production
APP_PORT=8080
API_AUTH_TOKEN=change_me_to_secure_token
DB_PATH=./data/app.db
ALLOWED_PARSER_DOMAINS=prom.ua,shafa.ua,bigl.ua
"""
}

# Автоматическое создание папок и файлов
for filepath, content in files.items():
    folder = os.path.dirname(filepath)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content.strip())
    print(f"✅ Создан: {filepath}")

print("\\n🎉 Вся структура проекта успешно создана!")
