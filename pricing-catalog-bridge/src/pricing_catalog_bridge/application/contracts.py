from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pricing_catalog_bridge.domain import SupplierOffer, SupplierOfferSnapshot, VendingProduct

SUPPLIER_OFFER_SNAPSHOT_CONTRACT_VERSION = "supplier-offer-snapshot/v1"
SUPPLIER_INVOICE_INGESTION_CONTRACT_VERSION = "supplier-invoice-ingestion/v1"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SupplierOfferV1(ContractModel):
    supplier_product_id: str = Field(min_length=1, alias="supplierProductId")
    name: str = Field(min_length=1)
    unit_cost_with_tax_and_surcharge: Decimal = Field(ge=0, alias="unitCostWithTaxAndSurcharge")
    available: bool
    barcode: str | None = Field(default=None, alias="barcode")
    supplier_reference: str | None = Field(default=None, alias="supplierReference")

    def to_domain(self) -> SupplierOffer:
        return SupplierOffer(
            supplier_product_id=self.supplier_product_id,
            name=self.name.strip(),
            unit_cost_with_tax_and_surcharge=self.unit_cost_with_tax_and_surcharge,
            available=self.available,
            barcode=_optional_text(self.barcode),
            supplier_reference=_optional_text(self.supplier_reference),
        )


class SupplierOfferSnapshotV1(ContractModel):
    contract_version: Literal["supplier-offer-snapshot/v1"] = Field(alias="contractVersion")
    provider_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$", alias="providerId")
    retrieved_at: datetime = Field(alias="retrievedAt")
    products: list[SupplierOfferV1]

    @field_validator("retrieved_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("retrievedAt debe incluir zona horaria")
        return value

    def to_domain(self) -> SupplierOfferSnapshot:
        return SupplierOfferSnapshot(
            provider_id=self.provider_id.strip(),
            observed_at=self.retrieved_at,
            offers=tuple(product.to_domain() for product in self.products),
        )


class RecordSnapshotRequestV1(ContractModel):
    idempotency_key: str = Field(min_length=1, max_length=200, alias="idempotencyKey")
    snapshot: SupplierOfferSnapshotV1


class InvoiceLineV1(ContractModel):
    raw_description: str = Field(min_length=1, alias="rawDescription")
    supplier_reference: str | None = Field(default=None, alias="supplierReference")
    barcode: str | None = None
    purchase_quantity: Decimal = Field(gt=0, alias="purchaseQuantity")
    price_scope: Literal["pack", "unit", "unknown"] = Field(alias="priceScope")
    pack_expression: str | None = Field(default=None, alias="packExpression")
    units_per_pack: Decimal | None = Field(default=None, gt=0, alias="unitsPerPack")
    pack_price_net: Decimal = Field(ge=0, alias="packPriceNet")
    line_total_net: Decimal = Field(ge=0, alias="lineTotalNet")
    vat_rate: Decimal = Field(ge=0, le=1, alias="vatRate")
    validation_status: Literal["VALID", "REVIEW_REQUIRED"] = Field(alias="validationStatus")
    validation_reason: str | None = Field(default=None, alias="validationReason")


class SupplierInvoiceIngestionV1(ContractModel):
    contract_version: Literal["supplier-invoice-ingestion/v1"] = Field(alias="contractVersion")
    provider_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$", alias="providerId")
    supplier_name: str | None = Field(default=None, alias="supplierName")
    invoice_number: str | None = Field(default=None, alias="invoiceNumber")
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$", alias="sourceHash")
    ingested_at: datetime = Field(alias="ingestedAt")
    status: Literal["EXTRACTED", "REVIEW_REQUIRED", "PROVEEDOR_PENDIENTE"]
    lines: list[InvoiceLineV1]

    @field_validator("ingested_at")
    @classmethod
    def require_timezone_for_invoice(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("ingestedAt debe incluir zona horaria")
        return value


class RecordInvoiceRequestV1(ContractModel):
    idempotency_key: str = Field(min_length=1, max_length=200, alias="idempotencyKey")
    equivalence_surcharge_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1, alias="equivalenceSurchargeRate")
    invoice: SupplierInvoiceIngestionV1


class VendingProductV1(ContractModel):
    canonical_product_id: str = Field(pattern=r"^nayax:[1-9][0-9]*$", alias="canonicalProductId")
    product_name: str = Field(min_length=1, alias="productName")
    ean: str | None = None

    def to_domain(self) -> VendingProduct:
        return VendingProduct(
            canonical_product_id=self.canonical_product_id,
            product_name=self.product_name.strip(),
            ean=_optional_text(self.ean),
        )


class MatchProductsRequestV1(ContractModel):
    provider_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$", alias="providerId")
    vending_products: list[VendingProductV1] = Field(alias="vendingProducts")
    run_id: str = Field(min_length=1, max_length=200, alias="runId")
    idempotency_key: str = Field(min_length=1, max_length=200, alias="idempotencyKey")


class MachineProductPriceV1(ContractModel):
    machine_id: str = Field(min_length=1, alias="machineId")
    machine_name: str = Field(min_length=1, alias="machineName")
    selection: str | None = None
    canonical_product_id: str = Field(min_length=1, alias="canonicalProductId")
    product_name: str = Field(min_length=1, alias="productName")
    machine_price: Decimal | None = Field(default=None, ge=0, alias="machinePrice")


class MatchResultV1(ContractModel):
    canonical_product_id: str = Field(alias="canonicalProductId")
    supplier_product_id: str | None = Field(default=None, alias="supplierProductId")
    status: str
    method: str
    confidence: float
    reason: str
    review_id: str | None = Field(default=None, alias="reviewId")
    alternatives: list[dict[str, object]] = Field(default_factory=list)


class GenerateMachineSupplierReportRequestV1(ContractModel):
    provider_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$", alias="providerId")
    machine_products: list[MachineProductPriceV1] = Field(alias="machineProducts")
    matches: list[MatchResultV1]
    run_id: str = Field(min_length=1, max_length=200, alias="runId")


class LegacyNameMappingV1(ContractModel):
    nayax_product_name: str = Field(min_length=1, alias="nayaxProductName")
    supplier_product_id: str = Field(min_length=1, alias="supplierProductId")


class LegacyMappingReportRequestV1(ContractModel):
    provider_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$", alias="providerId")
    mappings: list[LegacyNameMappingV1]


def _optional_text(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None
