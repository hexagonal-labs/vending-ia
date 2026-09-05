"""Extracción determinista y conservadora de facturas de proveedores.

El bridge sólo extrae evidencia. No hace matching ni modifica el catálogo: una
línea que no pueda explicarse (importe, descuento o unidades de pack) queda
marcada para revisión humana.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .vision import VisionInvoice, VisionLine, extract_with_configured_vision

MAX_UPLOADED_INVOICE_BYTES = 20 * 1024 * 1024
_SUPPORTED_UPLOAD_SUFFIXES = frozenset({".pdf", ".jpg", ".jpeg", ".png", ".webp"})


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class InvoiceLine(ContractModel):
    raw_description: str = Field(alias="rawDescription")
    supplier_reference: str | None = Field(default=None, alias="supplierReference")
    barcode: str | None = None
    purchase_quantity: Decimal = Field(alias="purchaseQuantity")
    price_scope: str = Field(alias="priceScope")
    pack_expression: str | None = Field(default=None, alias="packExpression")
    units_per_pack: Decimal | None = Field(default=None, alias="unitsPerPack")
    pack_price_net: Decimal = Field(alias="packPriceNet")
    line_total_net: Decimal = Field(alias="lineTotalNet")
    vat_rate: Decimal = Field(alias="vatRate")
    validation_status: str = Field(alias="validationStatus")
    validation_reason: str | None = Field(default=None, alias="validationReason")


class ExtractedInvoice(ContractModel):
    contract_version: str = Field(default="supplier-invoice-ingestion/v1", alias="contractVersion")
    provider_id: str | None = Field(default=None, alias="providerId")
    supplier_name: str | None = Field(default=None, alias="supplierName")
    invoice_number: str | None = Field(default=None, alias="invoiceNumber")
    source_hash: str = Field(alias="sourceHash")
    ingested_at: datetime = Field(alias="ingestedAt")
    status: str
    lines: list[InvoiceLine]


class InvoiceLineCorrection(ContractModel):
    """Corrección humana de una línea antes de importarla al catálogo."""

    line_index: int = Field(ge=0, alias="lineIndex")
    raw_description: str | None = Field(default=None, alias="rawDescription")
    supplier_reference: str | None = Field(default=None, alias="supplierReference")
    barcode: str | None = None
    purchase_quantity: Decimal | None = Field(default=None, gt=0, alias="purchaseQuantity")
    pack_expression: str | None = Field(default=None, alias="packExpression")
    units_per_pack: Decimal | None = Field(default=None, gt=0, alias="unitsPerPack")
    pack_price_net: Decimal | None = Field(default=None, ge=0, alias="packPriceNet")
    line_total_net: Decimal | None = Field(default=None, ge=0, alias="lineTotalNet")
    vat_rate: Decimal | None = Field(default=None, ge=0, le=1, alias="vatRate")


def inspect_source(source_uri: str) -> dict[str, Any]:
    """Identifica el proveedor a partir del texto disponible en el archivo."""
    path = Path(source_uri)
    return inspect_text(_extract_text(path, path.read_bytes()))


def archive_source(source_uri: str) -> dict[str, str | bool]:
    """Copia un original al archivo duradero propiedad de invoice-bridge."""
    source = Path(source_uri)
    return _archive_data(source.read_bytes(), source.name)


def store_uploaded_source(filename: str, content_base64: str) -> dict[str, str | bool]:
    """Guarda un adjunto recibido por una API/chat en el archivo duradero.

    El contenido se recibe codificado para que un cliente de chat pueda enviar
    un PDF o imagen sin dar al servidor una ruta arbitraria de su sistema.
    """
    safe_name = _safe_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in _SUPPORTED_UPLOAD_SUFFIXES:
        supported = ", ".join(sorted(_SUPPORTED_UPLOAD_SUFFIXES))
        raise ValueError(f"Formato de factura no permitido ({suffix or 'sin extensión'}). Usa: {supported}.")
    max_base64_characters = (MAX_UPLOADED_INVOICE_BYTES * 4 + 2) // 3 + 4
    if len(content_base64) > max_base64_characters:
        raise ValueError(f"El archivo adjunto supera el máximo de {MAX_UPLOADED_INVOICE_BYTES // 1024 // 1024} MB.")
    try:
        data = base64.b64decode(content_base64, validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError("content_base64 no contiene un archivo Base64 válido.") from error
    if not data:
        raise ValueError("El archivo adjunto está vacío.")
    if len(data) > MAX_UPLOADED_INVOICE_BYTES:
        raise ValueError(f"El archivo adjunto supera el máximo de {MAX_UPLOADED_INVOICE_BYTES // 1024 // 1024} MB.")
    return _archive_data(data, safe_name)


def _archive_data(data: bytes, filename: str) -> dict[str, str | bool]:
    """Persiste bytes de factura de forma idempotente en el archivo propio."""
    source_hash = hashlib.sha256(data).hexdigest()
    archive_directory = _invoice_data_directory() / "uploads"
    archive_directory.mkdir(parents=True, exist_ok=True)
    destination = archive_directory / f"{source_hash}-{_safe_filename(filename)}"
    if destination.is_file():
        return {"sourceUri": str(destination), "sourceHash": source_hash, "duplicate": True}
    temporary_destination = archive_directory / f".{destination.name}.{os.getpid()}.tmp"
    temporary_destination.write_bytes(data)
    temporary_destination.replace(destination)
    return {"sourceUri": str(destination), "sourceHash": source_hash, "duplicate": False}


def inspect_text(text: str) -> dict[str, Any]:
    if "CASHORECA" in text.upper():
        return {
            "providerId": "cashoreca",
            "confidence": 1.0,
            "reason": "Razón social Cashoreca detectada.",
        }
    return {
        "providerId": None,
        "confidence": 0.0,
        "reason": "Proveedor no identificado con suficiente certeza.",
    }


def extract(source_uri: str, supplier_id: str | None = None) -> ExtractedInvoice:
    path = Path(source_uri)
    data = path.read_bytes()
    text = _extract_text(path, data)
    detected = inspect_text(text)
    provider_id = supplier_id or detected["providerId"]
    source_hash = hashlib.sha256(data).hexdigest()

    # Un PDF digital con todas sus líneas verificadas no necesita IA. En fotos,
    # escaneos o texto parcial, la extracción se hace exclusivamente con visión.
    native_lines = parse_cashoreca(text) if provider_id == "cashoreca" else []
    if _all_lines_valid(native_lines):
        return _cashoreca_invoice(text, source_hash, native_lines)

    if _is_visual_document(path):
        visual_invoice = extract_with_configured_vision(path, data)
        return _from_vision(visual_invoice, source_hash, supplier_id)

    if provider_id != "cashoreca":
        return ExtractedInvoice(
            providerId=provider_id,
            sourceHash=source_hash,
            ingestedAt=datetime.now(UTC),
            status="PROVEEDOR_PENDIENTE",
            lines=[],
        )

    return _cashoreca_invoice(text, source_hash)


def revise_invoice(invoice: dict[str, Any], corrections: list[dict[str, Any]]) -> ExtractedInvoice:
    """Aplica correcciones humanas y vuelve a validar la factura de forma determinista."""
    extracted = ExtractedInvoice.model_validate(invoice)
    if extracted.provider_id != "cashoreca":
        raise ValueError("Solo se pueden revisar facturas Cashoreca en este momento.")
    lines = list(extracted.lines)
    for raw_correction in corrections:
        correction = InvoiceLineCorrection.model_validate(raw_correction)
        if correction.line_index >= len(lines):
            raise ValueError(f"La línea {correction.line_index} no existe en la factura.")
        lines[correction.line_index] = _apply_line_correction(lines[correction.line_index], correction)
    return extracted.model_copy(
        update={
            "lines": lines,
            "status": "EXTRACTED" if _all_lines_valid(lines) else "REVIEW_REQUIRED",
        }
    )


def parse_cashoreca(text: str) -> list[InvoiceLine]:
    """Parsea la exportación tabular de Cashoreca.

    Las columnas son REF | EAN | ARTÍCULO | CANTID | PRE/U | DTO% | IMPORTE | IVA.
    PRE/U es el precio neto por pack; IMPORTE permite validarlo ante descuentos.
    """
    parsed_lines: list[InvoiceLine] = []
    for raw_line in text.splitlines():
        columns = [column.strip() for column in raw_line.split("|")]
        if len(columns) != 8:
            continue
        numeric_values = tuple(_decimal(columns[index]) for index in (3, 4, 5, 6, 7))
        quantity, price_per_pack, discount, line_total, vat = numeric_values
        if any(value is None for value in numeric_values) or quantity is None or quantity <= 0:
            continue
        assert price_per_pack is not None and discount is not None and line_total is not None and vat is not None
        parsed_lines.append(_invoice_line(columns[2], columns[0] or None, columns[1] or None, quantity, price_per_pack,
                                          discount, line_total, vat, None, None))
    if parsed_lines:
        return parsed_lines
    return _parse_cashoreca_plain_table(text)


def _parse_cashoreca_plain_table(text: str) -> list[InvoiceLine]:
    """Parsea una tabla de texto que no conserva separadores verticales."""
    parsed_lines: list[InvoiceLine] = []
    pattern = re.compile(
        r"^\s*(?P<reference>\S+)\s+(?P<barcode>\d{8,14})\s+"
        r"(?P<description>.+?)\s+(?P<quantity>\d+(?:[,.]\d+)?)\s+"
        r"(?P<price>\d+(?:[,.]\d+)?)\s+(?P<discount>\d+(?:[,.]\d+)?)\s+"
        r"(?P<total>\d+(?:[,.]\d+)?)\s+(?P<vat>\d+(?:[,.]\d+)?%?)\s*$",
        re.IGNORECASE,
    )
    for raw_line in text.splitlines():
        match = pattern.match(raw_line)
        if match is None:
            continue
        fields = match.groupdict()
        numeric = tuple(_decimal(fields[name]) for name in ("quantity", "price", "discount", "total", "vat"))
        if any(value is None for value in numeric):
            continue
        quantity, price_per_pack, discount, line_total, vat = numeric
        if quantity is None or quantity <= 0:
            continue
        assert price_per_pack is not None and discount is not None and line_total is not None and vat is not None
        parsed_lines.append(
            _invoice_line(
                fields["description"],
                fields["reference"],
                fields["barcode"],
                quantity,
                price_per_pack,
                discount,
                line_total,
                vat,
                None,
                None,
            )
        )
    return parsed_lines


def _from_vision(vision: VisionInvoice, source_hash: str, supplier_id: str | None) -> ExtractedInvoice:
    provider_id = supplier_id or vision.provider_id
    if provider_id != "cashoreca":
        return ExtractedInvoice(
            providerId=provider_id,
            supplierName=vision.supplier_name,
            invoiceNumber=vision.invoice_number,
            sourceHash=source_hash,
            ingestedAt=datetime.now(UTC),
            status="PROVEEDOR_PENDIENTE",
            lines=[],
        )
    lines = [_line_from_vision(line) for line in vision.lines]
    return ExtractedInvoice(
        providerId="cashoreca",
        supplierName=vision.supplier_name or "CASHORECA",
        invoiceNumber=vision.invoice_number,
        sourceHash=source_hash,
        ingestedAt=datetime.now(UTC),
        status="EXTRACTED" if _all_lines_valid(lines) else "REVIEW_REQUIRED",
        lines=lines,
    )


def _cashoreca_invoice(
    text: str,
    source_hash: str,
    lines: list[InvoiceLine] | None = None,
) -> ExtractedInvoice:
    parsed_lines = lines if lines is not None else parse_cashoreca(text)
    return ExtractedInvoice(
        providerId="cashoreca",
        supplierName="CASHORECA",
        invoiceNumber=_first(r"N[ºO°]?\s*FAC\s*[:.]?\s*([A-Z0-9-]+)", text),
        sourceHash=source_hash,
        ingestedAt=datetime.now(UTC),
        status="EXTRACTED" if _all_lines_valid(parsed_lines) else "REVIEW_REQUIRED",
        lines=parsed_lines,
    )


def _all_lines_valid(lines: list[InvoiceLine]) -> bool:
    return bool(lines) and all(line.validation_status == "VALID" for line in lines)


def _line_from_vision(line: VisionLine) -> InvoiceLine:
    required = (line.purchase_quantity, line.price_per_pack_net, line.line_total_net, line.vat_rate)
    if any(value is None for value in required):
        return InvoiceLine(
            rawDescription=line.raw_description,
            supplierReference=line.supplier_reference,
            barcode=line.barcode,
            purchaseQuantity=line.purchase_quantity or Decimal("0"),
            priceScope="unknown",
            packExpression=line.pack_expression,
            unitsPerPack=line.units_per_pack,
            packPriceNet=Decimal("0"),
            lineTotalNet=line.line_total_net or Decimal("0"),
            vatRate=line.vat_rate or Decimal("0"),
            validationStatus="REVIEW_REQUIRED",
            validationReason="Visión incompleta: faltan cantidad, PRE/U, IMPORTE o IVA.",
        )
    assert line.purchase_quantity is not None
    assert line.price_per_pack_net is not None
    assert line.line_total_net is not None
    assert line.vat_rate is not None
    return _invoice_line(
        line.raw_description,
        line.supplier_reference,
        line.barcode,
        line.purchase_quantity,
        line.price_per_pack_net,
        line.discount_percent or Decimal("0"),
        line.line_total_net,
        line.vat_rate,
        line.pack_expression,
        line.units_per_pack,
    )


def _apply_line_correction(line: InvoiceLine, correction: InvoiceLineCorrection) -> InvoiceLine:
    current = line.model_dump()
    for field_name in correction.model_fields_set - {"line_index"}:
        current[field_name] = getattr(correction, field_name)
    return _invoice_line(
        str(current["raw_description"]),
        current["supplier_reference"],
        current["barcode"],
        current["purchase_quantity"],
        current["pack_price_net"],
        Decimal("0"),
        current["line_total_net"],
        current["vat_rate"],
        current["pack_expression"],
        current["units_per_pack"],
    )


def _invoice_line(
    description: str,
    supplier_reference: str | None,
    barcode: str | None,
    quantity: Decimal,
    price_per_pack: Decimal,
    discount: Decimal,
    line_total: Decimal,
    vat: Decimal,
    pack_expression: str | None,
    units_per_pack: Decimal | None,
) -> InvoiceLine:
    expected_total = quantity * price_per_pack * (Decimal("1") - discount / Decimal("100"))
    is_consistent = abs(expected_total - line_total) <= Decimal("0.02")
    pack = _pack_expression(description)
    detected_units = units_per_pack or (Decimal(pack[1]) if pack else None)
    expression = pack_expression or (pack[0] if pack else None)
    validation_reason = None
    if not is_consistent:
        validation_reason = "CANTID × PRE/U × (1 - DTO%) no coincide con IMPORTE."
    elif detected_units is None:
        validation_reason = "No se han podido determinar las unidades por pack."
    return InvoiceLine(
        rawDescription=description,
        supplierReference=supplier_reference,
        barcode=barcode,
        purchaseQuantity=quantity,
        priceScope="pack" if detected_units else "unknown",
        packExpression=expression,
        unitsPerPack=detected_units,
        packPriceNet=line_total / quantity,
        lineTotalNet=line_total,
        vatRate=vat / Decimal("100") if vat > 1 else vat,
        validationStatus="VALID" if is_consistent and detected_units else "REVIEW_REQUIRED",
        validationReason=validation_reason,
    )


def _extract_text(path: Path, data: bytes) -> str:
    if path.suffix.lower() != ".pdf":
        return data.decode("utf-8", errors="ignore")
    try:
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    except Exception:  # PDF corrupto, protegido o sin dependencia opcional.
        return ""


def _is_visual_document(path: Path) -> bool:
    return path.suffix.lower() in {".pdf", ".jpg", ".jpeg", ".png", ".webp"}


def _invoice_data_directory() -> Path:
    return Path(os.getenv("INVOICE_DATA_DIR", "/var/lib/invoice-bridge"))


def _safe_filename(filename: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", Path(filename).name).strip(".-")
    return safe or "invoice"


def _decimal(value: str) -> Decimal | None:
    normalized = re.sub(r"[^0-9,.-]", "", value).replace(",", ".")
    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None


def _pack_expression(description: str) -> tuple[str, str] | None:
    # "40G*14" expresa 14 unidades por pack. Un peso sin multiplicador, como
    # "454GR", no se interpreta como un pack.
    match = re.search(
        r"\b(?:(\d+(?:[.,]\d+)?\s*(?:g|gr|kg|ml|cl|l)\s*)?([x*+])\s*(\d+)|(\d+)\s*([x*+])\s*(\d+))\b",
        description,
        re.IGNORECASE,
    )
    if match is None:
        return None
    if match.group(1) is not None:
        return match.group(0).replace(" ", "").replace("+", "*"), match.group(3)
    return match.group(0).replace(" ", "").replace("+", "*"), match.group(6)


def _first(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1) if match else None
