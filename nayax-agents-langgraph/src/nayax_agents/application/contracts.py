"""Contratos versionados que cruzan los límites de los bridges.

Los modelos son deliberadamente pequeños: cada workflow consume únicamente los
campos que necesita y puede fallar pronto si un bridge cambia su contrato.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NAYAX_MACHINE_PRODUCTS_CONTRACT_VERSION = "nayax-machine-products/v1"
SUPPLIER_OFFER_SNAPSHOT_CONTRACT_VERSION = "supplier-offer-snapshot/v1"
SUPPLIER_INVOICE_INGESTION_CONTRACT_VERSION = "supplier-invoice-ingestion/v1"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class NayaxCatalogProductV1(ContractModel):
    product_name: str | None = Field(default=None, alias="productName")
    ean_code: str | None = Field(default=None, alias="eanCode")


class NayaxProductPricesV1(ContractModel):
    machine: Decimal | None = None
    cash: Decimal | None = None


class NayaxStockReadingV1(ContractModel):
    missing: int | None = None
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class NayaxProductStockV1(ContractModel):
    par: int | None = None
    available: int | None = None
    missing: int | None = None
    alert_threshold: int | None = Field(default=None, alias="alertThreshold")
    at_or_above_alert_threshold: bool | None = Field(default=None, alias="atOrAboveAlertThreshold")
    status: Literal["full", "partial", "empty", "unknown"] | None = None
    source: Literal["dex", "mdb"] | None = None
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    readings: dict[str, NayaxStockReadingV1] | None = None


class NayaxMachineProductV1(ContractModel):
    machine_product_id: str = Field(alias="machineProductId")
    machine_id: int = Field(alias="machineId")
    nayax_product_id: int | None = Field(default=None, alias="nayaxProductId")
    name: str = ""
    catalog_product: NayaxCatalogProductV1 | None = Field(default=None, alias="catalogProduct")
    prices: NayaxProductPricesV1
    stock: NayaxProductStockV1 | None = None
    needs_restock: bool | None = Field(default=None, alias="needsRestock")


class NayaxMachineProductsResponseV1(ContractModel):
    contract_version: Literal["nayax-machine-products/v1"] = Field(alias="contractVersion")
    machine_id: int = Field(alias="machineId")
    products: list[NayaxMachineProductV1]


# Contratos de entrada ya preparados para los próximos bridges. En fase 1 se
# validan con fixtures, pero todavía no activan OCR, almacenamiento ni matching.
class SupplierOfferV1(ContractModel):
    supplier_product_id: str = Field(alias="supplierProductId")
    name: str
    unit_cost_with_tax_and_surcharge: Decimal = Field(alias="unitCostWithTaxAndSurcharge")
    available: bool


class SupplierOfferSnapshotV1(ContractModel):
    contract_version: Literal["supplier-offer-snapshot/v1"] = Field(alias="contractVersion")
    provider_id: str = Field(alias="providerId")
    retrieved_at: datetime = Field(alias="retrievedAt")
    products: list[SupplierOfferV1]


class SupplierInvoiceLineV1(ContractModel):
    raw_description: str = Field(alias="rawDescription")
    purchase_quantity: Decimal = Field(alias="purchaseQuantity")
    price_scope: Literal["unit", "pack", "case"] = Field(alias="priceScope")
    pack_expression: str | None = Field(default=None, alias="packExpression")
    pack_price_net: Decimal = Field(alias="packPriceNet")
    line_total_net: Decimal = Field(alias="lineTotalNet")
    vat_rate: Decimal = Field(alias="vatRate")


class SupplierInvoiceIngestionV1(ContractModel):
    contract_version: Literal["supplier-invoice-ingestion/v1"] = Field(alias="contractVersion")
    provider_id: str = Field(alias="providerId")
    invoice_number: str = Field(alias="invoiceNumber")
    ingested_at: datetime = Field(alias="ingestedAt")
    lines: list[SupplierInvoiceLineV1]
