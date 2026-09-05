from __future__ import annotations

from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from supplier_bridge.domain import SupplierCostPolicy


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    distribuidora_mayorista_base_url: str = "https://distribucionmayorista.online"
    distribuidora_mayorista_email: str = ""
    distribuidora_mayorista_password: str = ""
    distribuidora_mayorista_wishlist_id: str = ""
    distribuidora_mayorista_price_includes_vat: bool = False
    distribuidora_mayorista_price_includes_equivalence_surcharge: bool = False
    distribuidora_mayorista_vat_rate: Decimal = Field(default=Decimal("0.21"), ge=0, le=1)
    distribuidora_mayorista_equivalence_surcharge_rate: Decimal = Field(default=Decimal("0.052"), ge=0, le=1)

    def distribuidora_mayorista_cost_policy(self) -> SupplierCostPolicy:
        return SupplierCostPolicy(
            price_includes_vat=self.distribuidora_mayorista_price_includes_vat,
            price_includes_equivalence_surcharge=self.distribuidora_mayorista_price_includes_equivalence_surcharge,
            vat_rate=self.distribuidora_mayorista_vat_rate,
            equivalence_surcharge_rate=self.distribuidora_mayorista_equivalence_surcharge_rate,
        )
