"""OCR local para facturas fotografiadas y PDF escaneados.

Este módulo no interpreta importes ni decide qué líneas se pueden importar. Su
única responsabilidad es convertir el documento visual en texto para que el
parser determinista de cada proveedor haga las validaciones habituales.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class TesseractOcrError(RuntimeError):
    """Error operativo, seguro para registrar, de la capa OCR."""


def extract_text_with_tesseract(path: Path) -> str | None:
    """Extrae texto con Tesseract o devuelve ``None`` si el OCR está desactivado.

    Un PDF se rasteriza localmente a 300 DPI antes de ejecutarlo página por
    página. Nunca se envía el documento fuera de la máquina.
    """
    if not _enabled():
        return None
    _require_command("tesseract")
    with tempfile.TemporaryDirectory(prefix="invoice-ocr-") as temporary_directory:
        temporary_path = Path(temporary_directory)
        pages = _pages_for_ocr(path, temporary_path)
        texts = [_tesseract(page) for page in pages]
    return "\n".join(text for text in texts if text.strip()).strip()


def log_ocr_failure(error: Exception) -> None:
    """Conserva un error breve sin registrar el contenido de la factura."""
    import logging

    logging.getLogger(__name__).warning("Falló el OCR local de factura: %s", error)


def _enabled() -> bool:
    return os.getenv("INVOICE_TESSERACT_ENABLED", "true").strip().lower() not in {"0", "false", "no"}


def _pages_for_ocr(path: Path, temporary_path: Path) -> list[Path]:
    if path.suffix.lower() != ".pdf":
        return [path]
    _require_command("pdftoppm")
    output_prefix = temporary_path / "page"
    _run(["pdftoppm", "-r", _dpi(), "-png", str(path), str(output_prefix)])
    pages = sorted(temporary_path.glob("page-*.png"))
    if not pages:
        raise TesseractOcrError("No se han podido rasterizar las páginas del PDF")
    return pages


def _tesseract(image_path: Path) -> str:
    result = _run(
        [
            "tesseract",
            str(image_path),
            "stdout",
            "-l",
            os.getenv("INVOICE_TESSERACT_LANGUAGES", "spa+eng"),
            "--oem",
            "1",
            "--psm",
            os.getenv("INVOICE_TESSERACT_PSM", "6"),
        ]
    )
    return result.stdout


def _dpi() -> str:
    configured = os.getenv("INVOICE_TESSERACT_DPI", "300")
    try:
        dpi = int(configured)
    except ValueError as error:
        raise TesseractOcrError("INVOICE_TESSERACT_DPI debe ser un entero") from error
    if dpi < 72 or dpi > 600:
        raise TesseractOcrError("INVOICE_TESSERACT_DPI debe estar entre 72 y 600")
    return str(dpi)


def _require_command(command: str) -> None:
    if shutil.which(command) is None:
        raise TesseractOcrError(f"No está instalado el comando local '{command}'")


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired as error:
        raise TesseractOcrError("El OCR local superó el tiempo máximo de 90 segundos") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.replace("\n", " ").strip()[:200]
        suffix = f": {detail}" if detail else ""
        raise TesseractOcrError(f"Tesseract no pudo procesar el documento{suffix}") from error
