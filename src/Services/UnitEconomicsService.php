<?php
namespace App\Services;

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
