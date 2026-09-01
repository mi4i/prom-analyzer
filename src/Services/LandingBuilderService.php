<?php
namespace App\Services;

use App\Repositories\ProductRepository;

class LandingBuilderService {
    private ProductRepository $repository;

    public function __construct(ProductRepository $repository) {
        $this->repository = $repository;
    }

    public function buildLandingPayload(string $productId): array {
        $product = $this->repository->findById($productId);
        if (!$product) {
            throw new \Exception("Товар {$productId} не найден", 404);
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
