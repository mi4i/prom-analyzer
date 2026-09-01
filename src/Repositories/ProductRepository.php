<?php
namespace App\Repositories;

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
