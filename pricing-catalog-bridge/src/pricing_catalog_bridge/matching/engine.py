from __future__ import annotations

from rapidfuzz.fuzz import ratio

from pricing_catalog_bridge.domain import MatchCandidate, ProductMatch, SupplierOffer, VendingProduct

from .normalization import NormalizedProduct, normalize_ean, normalize_product_name

AUTO_MATCH_THRESHOLD = 0.95
REVIEW_MATCH_THRESHOLD = 0.75


class ProductMatcher:
    """Matcher explicable. Nunca confirma una asociación con datos contradictorios."""

    def match(
        self,
        vending_product: VendingProduct,
        supplier_offers: tuple[SupplierOffer, ...],
        confirmed_mappings: dict[str, str],
    ) -> ProductMatch:
        if not supplier_offers:
            return ProductMatch(
                canonical_product_id=vending_product.canonical_product_id,
                supplier_product_id=None,
                status="SOURCE_INCOMPLETE",
                method="none",
                confidence=0.0,
                alternatives=(),
                reason="El proveedor no tiene ofertas actuales en el catálogo local.",
            )

        ean_match = self._ean_match(vending_product, supplier_offers)
        if ean_match is not None:
            return ean_match

        mapped_supplier_id = confirmed_mappings.get(vending_product.canonical_product_id)
        if mapped_supplier_id is not None:
            mapped_offer = next(
                (offer for offer in supplier_offers if offer.supplier_product_id == mapped_supplier_id),
                None,
            )
            if mapped_offer is not None:
                return ProductMatch(
                    canonical_product_id=vending_product.canonical_product_id,
                    supplier_product_id=mapped_offer.supplier_product_id,
                    status="MATCHED_CONFIRMED",
                    method="confirmed_mapping",
                    confidence=1.0,
                    alternatives=(),
                    reason="Mapping confirmado previamente para este proveedor.",
                )
            return ProductMatch(
                canonical_product_id=vending_product.canonical_product_id,
                supplier_product_id=None,
                status="SOURCE_INCOMPLETE",
                method="confirmed_mapping",
                confidence=0.0,
                alternatives=(),
                reason="El mapping confirmado apunta a una oferta que ya no está disponible en el catálogo actual.",
            )

        return self._attribute_match(vending_product, supplier_offers)

    def _ean_match(
        self, vending_product: VendingProduct, supplier_offers: tuple[SupplierOffer, ...]
    ) -> ProductMatch | None:
        ean = normalize_ean(vending_product.ean)
        if ean is None:
            return None
        matches = [offer for offer in supplier_offers if normalize_ean(offer.barcode) == ean]
        if len(matches) != 1:
            return None
        offer = matches[0]
        return ProductMatch(
            canonical_product_id=vending_product.canonical_product_id,
            supplier_product_id=offer.supplier_product_id,
            status="MATCHED_EXACT",
            method="ean",
            confidence=1.0,
            alternatives=(),
            reason="EAN/GTIN coincidente y único.",
        )

    def _attribute_match(
        self, vending_product: VendingProduct, supplier_offers: tuple[SupplierOffer, ...]
    ) -> ProductMatch:
        source = normalize_product_name(vending_product.product_name)
        scored = sorted(
            (
                (score, reason, offer)
                for offer in supplier_offers
                for score, reason in [self._score(source, normalize_product_name(offer.name))]
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        best_score, best_reason, best_offer = scored[0]
        alternatives = tuple(
            MatchCandidate(
                supplier_product_id=offer.supplier_product_id,
                name=offer.name,
                confidence=score,
                reason=reason,
            )
            for score, reason, offer in scored[:3]
            if score > 0
        )

        if best_score == 1.0:
            return ProductMatch(
                canonical_product_id=vending_product.canonical_product_id,
                supplier_product_id=best_offer.supplier_product_id,
                status="MATCHED_EXACT",
                method="normalized_attributes",
                confidence=best_score,
                alternatives=alternatives[1:],
                reason=best_reason,
            )
        if best_score >= AUTO_MATCH_THRESHOLD:
            return ProductMatch(
                canonical_product_id=vending_product.canonical_product_id,
                supplier_product_id=best_offer.supplier_product_id,
                status="MATCHED_EXACT",
                method="fuzzy",
                confidence=best_score,
                alternatives=alternatives[1:],
                reason=best_reason,
            )
        if best_score >= REVIEW_MATCH_THRESHOLD:
            return ProductMatch(
                canonical_product_id=vending_product.canonical_product_id,
                supplier_product_id=best_offer.supplier_product_id,
                status="PENDING_REVIEW",
                method="fuzzy",
                confidence=best_score,
                alternatives=alternatives,
                reason=best_reason,
            )
        return ProductMatch(
            canonical_product_id=vending_product.canonical_product_id,
            supplier_product_id=None,
            status="UNMATCHED",
            method="none",
            confidence=best_score,
            alternatives=alternatives,
            reason=best_reason,
        )

    def _score(self, source: NormalizedProduct, candidate: NormalizedProduct) -> tuple[float, str]:
        if not source.tokens or not candidate.tokens:
            return 0.0, "Nombre de producto incompleto para comparar."
        if source.content_unit and candidate.content_unit:
            if source.content_unit != candidate.content_unit or source.content_value != candidate.content_value:
                return 0.0, "El tamaño o la unidad de contenido no coincide."
        if source.format and candidate.format and source.format != candidate.format:
            return 0.0, "El formato de venta no coincide."
        if source.tokens == candidate.tokens:
            return 1.0, "Nombre, contenido y formato normalizados coinciden."
        intersection = len(source.tokens & candidate.tokens)
        union = len(source.tokens | candidate.tokens)
        token_overlap = intersection / union
        text_similarity = ratio(source.normalized_name, candidate.normalized_name) / 100
        score = round((token_overlap * 0.55) + (text_similarity * 0.45), 4)
        return score, "Coincidencia aproximada de nombre con atributos compatibles."
