from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

import httpx

from supplier_bridge.domain import SupplierCostPolicy, SupplierOffer, SupplierOfferSnapshot


class DistribuidoraMayoristaClient:
    """Adaptador HTTP de la lista de deseos de Distribuidora Mayorista."""

    provider_id = "distribuidora-mayorista"
    _login_path = "/es/iniciar-sesion"
    _wishlist_path = "/es/module/blockwishlist/view"

    def __init__(
        self,
        base_url: str,
        email: str,
        password: str,
        wishlist_id: str,
        cost_policy: SupplierCostPolicy,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._email = email
        self._password = password
        self._wishlist_id = wishlist_id
        self._cost_policy = cost_policy

    async def fetch_snapshot(self) -> SupplierOfferSnapshot:
        self._assert_configured()
        async with httpx.AsyncClient(follow_redirects=False, timeout=30.0) as client:
            cookies = await self._login(client)
            first = await self._fetch_page(client, cookies, 1)
            total_pages = self._total_pages(first.get("pagination"))
            raw_products = list(first.get("products", []))
            for page in range(2, total_pages + 1):
                response = await self._fetch_page(client, cookies, page)
                raw_products.extend(response.get("products", []))
        products = tuple(self.to_offer(raw, self._cost_policy) for raw in raw_products if isinstance(raw, Mapping))
        return SupplierOfferSnapshot(
            provider_id=self.provider_id,
            retrieved_at=datetime.now(UTC),
            products=products,
        )

    def cost_policy(self) -> SupplierCostPolicy:
        return self._cost_policy

    async def _login(self, client: httpx.AsyncClient) -> httpx.Cookies:
        login_url = f"{self._base_url}{self._login_path}"
        initial = await client.get(login_url)
        cookies = initial.cookies
        response = await client.post(
            login_url,
            data={"back": "", "email": self._email, "password": self._password, "submitLogin": "1"},
            cookies=cookies,
        )
        if response.status_code not in {200, 302}:
            raise RuntimeError(f"Login en {self.provider_id} falló con HTTP {response.status_code}")
        cookies.update(response.cookies)
        return cookies

    async def _fetch_page(self, client: httpx.AsyncClient, cookies: httpx.Cookies, page: int) -> Mapping[str, Any]:
        params: dict[str, str] = {"id_wishlist": self._wishlist_id, "from-xhr": ""}
        if page > 1:
            params["page"] = str(page)
        response = await client.get(
            f"{self._base_url}{self._wishlist_path}",
            params=params,
            cookies=cookies,
            headers={"accept": "application/json, text/javascript, */*; q=0.01"},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise ValueError("La respuesta del proveedor no es un objeto JSON")
        return payload

    def _assert_configured(self) -> None:
        missing = [
            name
            for name, value in {
                "DISTRIBUIDORA_MAYORISTA_EMAIL": self._email,
                "DISTRIBUIDORA_MAYORISTA_PASSWORD": self._password,
                "DISTRIBUIDORA_MAYORISTA_WISHLIST_ID": self._wishlist_id,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(f"Faltan variables de configuración: {', '.join(missing)}")

    @staticmethod
    def to_offer(raw: Mapping[str, Any], cost_policy: SupplierCostPolicy) -> SupplierOffer:
        supplier_product_id = str(raw.get("id_product", raw.get("id", ""))).strip()
        name = str(raw.get("name", "")).strip()
        if not supplier_product_id or not name:
            raise ValueError("La oferta del proveedor necesita id_product e identificador de producto")
        units_per_pack = DistribuidoraMayoristaClient._parse_decimal(raw.get("unit_price_ratio", 1))
        published_unit_price = DistribuidoraMayoristaClient._parse_euro(raw.get("unit_price"))
        if published_unit_price == 0 and units_per_pack > 0:
            published_unit_price = DistribuidoraMayoristaClient._parse_euro(raw.get("price")) / units_per_pack
        return SupplierOffer(
            supplier_product_id=supplier_product_id,
            name=name,
            unit_cost_with_tax_and_surcharge=apply_cost_policy(published_unit_price, cost_policy),
            available=raw.get("availability") != "unavailable",
            barcode=_first_text(raw, "ean13", "ean", "barcode", "product_barcode"),
            supplier_reference=_first_text(raw, "reference", "product_reference", "supplier_reference"),
        )

    @staticmethod
    def _total_pages(pagination: Any) -> int:
        if not isinstance(pagination, Mapping):
            return 1
        for key in ("pages_count", "total_pages", "pages", "last_page"):
            value = pagination.get(key)
            if value is None:
                continue
            try:
                pages = int(str(value))
            except (TypeError, ValueError):
                continue
            if pages > 0:
                return pages
        return 1

    @staticmethod
    def _parse_euro(value: Any) -> Decimal:
        return DistribuidoraMayoristaClient._parse_decimal(value)

    @staticmethod
    def _parse_decimal(value: Any) -> Decimal:
        if value is None:
            return Decimal("0")
        filtered = "".join(character for character in str(value) if character.isdigit() or character in ",.-")
        cleaned = filtered.replace(",", ".")
        try:
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return Decimal("0")


def apply_cost_policy(published_unit_price: Decimal, policy: SupplierCostPolicy) -> Decimal:
    """Convierte el precio publicado a coste final sin aplicar recargos dos veces."""
    vat_factor = Decimal("1") + policy.vat_rate
    surcharge_factor = Decimal("1") + policy.equivalence_surcharge_rate
    if policy.price_includes_vat and policy.price_includes_equivalence_surcharge:
        total = published_unit_price
    elif policy.price_includes_vat:
        net = published_unit_price / vat_factor
        total = published_unit_price + (net * policy.equivalence_surcharge_rate)
    elif policy.price_includes_equivalence_surcharge:
        net = published_unit_price / surcharge_factor
        total = published_unit_price + (net * policy.vat_rate)
    else:
        total = published_unit_price * (Decimal("1") + policy.vat_rate + policy.equivalence_surcharge_rate)
    return total.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _first_text(raw: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
