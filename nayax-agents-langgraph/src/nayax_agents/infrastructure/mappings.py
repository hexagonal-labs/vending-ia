from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import yaml

from nayax_agents.domain import ProductMapping


def load_product_mappings(path: Path) -> Sequence[ProductMapping]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        raise ValueError(f"El mapping debe ser una lista YAML: {path}")
    return [
        ProductMapping(
            nayax_product=str(item["nayaxProduct"]),
            supplier_product_id=str(item["supplierProductId"]),
        )
        for item in raw
    ]
