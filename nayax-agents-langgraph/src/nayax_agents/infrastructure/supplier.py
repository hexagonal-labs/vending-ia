from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from nayax_agents.domain import SupplierProduct


class DistribuidoraMayoristaClient:
    provider_id = "distribuidora-mayorista"
    _login_path = "/es/iniciar-sesion"
    _wishlist_path = "/es/module/blockwishlist/view"

    def __init__(self, base_url: str, email: str, password: str, wishlist_id: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._email = email
        self._password = password
        self._wishlist_id = wishlist_id

    async def fetch_products(self) -> list[SupplierProduct]:
        async with httpx.AsyncClient(follow_redirects=False, timeout=30.0) as client:
            cookies = await self._login(client)
            first = await self._fetch_page(client, cookies, 1)
            total_pages = self._total_pages(first.get("pagination"))
            raw_products = list(first.get("products", []))
            for page in range(2, total_pages + 1):
                response = await self._fetch_page(client, cookies, page)
                raw_products.extend(response.get("products", []))
            return [self._to_product(item) for item in raw_products]

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
    def _to_product(raw: Mapping[str, Any]) -> SupplierProduct:
        return SupplierProduct(
            id=str(raw.get("id_product", raw.get("id", ""))),
            name=str(raw.get("name", "")),
            unit_price=DistribuidoraMayoristaClient._parse_euro(raw.get("unit_price")),
            units_per_pack=DistribuidoraMayoristaClient._parse_decimal(raw.get("unit_price_ratio", 1)),
            box_price=DistribuidoraMayoristaClient._parse_euro(raw.get("price")),
            available=raw.get("availability") != "unavailable",
        )

    @staticmethod
    def _parse_euro(value: Any) -> Decimal:
        return DistribuidoraMayoristaClient._parse_decimal(value)

    @staticmethod
    def _parse_decimal(value: Any) -> Decimal:
        if value is None:
            return Decimal("0")
        cleaned = "".join(char for char in str(value) if char.isdigit() or char in ",.-").replace(",", ".")
        try:
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return Decimal("0")
