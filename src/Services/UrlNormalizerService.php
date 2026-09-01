<?php
namespace App\Services;

class UrlNormalizerService {
    private array $allowedDomains;

    public function __construct(array $allowedDomains = ['prom.ua', 'shafa.ua', 'bigl.ua']) {
        $this->allowedDomains = $allowedDomains;
    }

    public function cleanUrl(string $rawUrl): string {
        $parsed = parse_url(trim($rawUrl));
        
        if (!isset($parsed['scheme']) || !isset($parsed['host'])) {
            throw new \InvalidArgumentException("Некорректный формат URL");
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
            throw new \InvalidArgumentException("Домен {$host} не входит в список разрешенных");
        }

        $scheme = strtolower($parsed['scheme']);
        $path = $parsed['path'] ?? '';
        $cleanQuery = '';

        if (isset($parsed['query'])) {
            parse_str($parsed['query'], $queryParams);
            $forbiddenKeys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'gclid', 'fbclid', 'ref', 'a', 'b'];
            
            $filteredParams = array_filter(
                $queryParams,
                fn($key) => !in_array(strtolower($key), $forbiddenKeys),
                ARRAY_FILTER_USE_KEY
            );

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
