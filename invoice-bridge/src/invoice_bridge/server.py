from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .core import archive_source, extract, inspect_source, revise_invoice, store_uploaded_source
from .vision import vision_configuration as get_vision_configuration


def create_server() -> FastMCP:
    server = FastMCP(
        "invoice-bridge",
        instructions=(
            "Extrae facturas y detecta el proveedor. No realiza matching ni actualiza precios; "
            "las líneas ambiguas quedan pendientes de revisión."
        ),
    )

    @server.tool()
    def inspect_invoice(source_uri: str) -> dict[str, Any]:
        """Identifica el proveedor de una factura local sin modificar ningún dato."""
        return inspect_source(source_uri)

    @server.tool()
    def vision_configuration() -> dict[str, object]:
        """Devuelve proveedor, modelo y presencia de configuración sin exponer secretos."""
        return get_vision_configuration()

    @server.tool()
    def archive_invoice(source_uri: str) -> dict[str, str | bool]:
        """Archiva el original en el almacenamiento duradero de invoice-bridge."""
        return archive_source(source_uri)

    @server.tool()
    def upload_invoice(filename: str, content_base64: str) -> dict[str, str | bool]:
        """Recibe un PDF o imagen Base64 desde un chat y lo archiva de forma idempotente."""
        return store_uploaded_source(filename, content_base64)

    @server.tool()
    def extract_invoice(source_uri: str, supplier_id: str | None = None) -> dict[str, Any]:
        """Extrae una factura al contrato supplier-invoice-ingestion/v1."""
        return extract(source_uri, supplier_id).model_dump(mode="json", by_alias=True)

    @server.tool()
    def revise_extracted_invoice(invoice: dict[str, Any], corrections: list[dict[str, Any]]) -> dict[str, Any]:
        """Aplica correcciones humanas a líneas y recalcula su validación antes de importar."""
        return revise_invoice(invoice, corrections).model_dump(mode="json", by_alias=True)

    return server


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
