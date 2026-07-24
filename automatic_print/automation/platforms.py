from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErpPlatform:
    name: str
    host: str

    @property
    def production_items_url(self) -> str:
        return (
            f"https://{self.host}/factory/fnsz-sale/"
            "produceManage/produceItemsManage"
        )

    @property
    def production_batches_url(self) -> str:
        return (
            f"https://{self.host}/factory/fnsz-sale/produceManage/"
            "produceChainManage/productionBatch/index"
        )


ERP_PLATFORMS = {
    "Haloo": ErpPlatform("Haloo", "haloopod.merchant.hihumbird.com"),
    "莆田": ErpPlatform("莆田", "putiandiy.merchant.hihumbird.com"),
    "隆丰": ErpPlatform("隆丰", "longfeng.merchant.hihumbird.com"),
}


def get_erp_platform(name: str) -> ErpPlatform:
    try:
        return ERP_PLATFORMS[name]
    except KeyError as error:
        raise ValueError(f"不支持的 ERP 平台：{name}") from error
