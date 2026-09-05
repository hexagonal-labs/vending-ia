from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from .mcp_client import BridgeMcpClient
from .settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    current = settings or Settings()
    uploads_dir = current.invoice_upload_staging_dir / "uploads"
    staged_dir = current.invoice_upload_staging_dir / "staged"
    invoice_client = BridgeMcpClient(
        current.invoice_bridge_dir,
        "invoice_bridge.server",
        current.bridge_python_command,
        {"INVOICE_DATA_DIR": str(current.invoice_data_dir)},
    )
    catalog_client = BridgeMcpClient(
        current.pricing_catalog_bridge_dir,
        "pricing_catalog_bridge.interfaces.mcp_server",
        current.bridge_python_command,
        {"PRICING_DATA_DIR": str(current.pricing_data_dir)},
    )
    app = FastAPI(title="Carga temporal de facturas")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return _page("Carga una factura", _upload_form())

    @app.get("/api/vision-status")
    async def vision_status() -> JSONResponse:
        """Muestra si el bridge recibió la configuración, sin revelar secretos."""
        return JSONResponse(await invoice_client.call("vision_configuration", {}))

    @app.post("/api/uploads")
    async def upload_invoice(file: UploadFile = File(...)) -> JSONResponse:  # noqa: B008
        content = await file.read()
        if not content:
            raise HTTPException(400, "El fichero está vacío.")
        if len(content) > current.invoice_upload_max_bytes:
            raise HTTPException(413, "El fichero supera el tamaño máximo configurado.")
        upload_id = uuid4().hex
        filename = _safe_filename(file.filename or "factura")
        destination = uploads_dir / f"{upload_id}-{filename}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        try:
            archived = await invoice_client.call("archive_invoice", {"source_uri": str(destination)})
            invoice = await invoice_client.call("extract_invoice", {"source_uri": str(archived["sourceUri"])})
        except Exception as error:
            destination.unlink(missing_ok=True)
            raise HTTPException(422, f"No se pudo extraer la factura: {error}") from error
        destination.unlink(missing_ok=True)
        staged_dir.mkdir(parents=True, exist_ok=True)
        staged = {"uploadId": upload_id, "sourcePath": archived["sourceUri"], "invoice": invoice}
        (staged_dir / f"{upload_id}.json").write_text(
            json.dumps(staged, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return JSONResponse(
            {"uploadId": upload_id, "invoice": invoice, "confirmUrl": f"/api/uploads/{upload_id}/confirm"}
        )

    @app.post("/api/uploads/{upload_id}/confirm")
    async def confirm_invoice(upload_id: str) -> JSONResponse:
        staged_path = _staged_path(staged_dir, upload_id)
        staged = _read_staged(staged_path)
        invoice = cast(dict[str, Any], staged["invoice"])
        if invoice.get("status") != "EXTRACTED":
            raise HTTPException(
                422,
                "La factura no está lista para importar; requiere revisión del proveedor o extracción.",
            )
        source_hash = str(invoice["sourceHash"])
        result = await catalog_client.call(
            "record_supplier_invoice",
            {
                "invoice": invoice,
                "idempotency_key": f"upload:{source_hash}",
                "equivalence_surcharge_rate": current.invoice_equivalence_surcharge_rate,
            },
        )
        staged_path.unlink(missing_ok=True)
        return JSONResponse(result)

    return app


def _staged_path(staged_dir: Path, upload_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", upload_id):
        raise HTTPException(404, "Carga no encontrada.")
    return staged_dir / f"{upload_id}.json"


def _read_staged(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise HTTPException(404, "Carga no encontrada.")
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict) or not isinstance(parsed.get("invoice"), dict):
        raise HTTPException(500, "La carga guardada no es válida.")
    return parsed


def _safe_filename(filename: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", Path(filename).name).strip(".-") or "factura"


def _upload_form() -> str:
    return """
<form id="upload"><input type="file" name="file" accept="application/pdf,image/*,.txt" required>
<button>Extraer factura</button></form><pre id="result"></pre>
<button id="confirm" hidden>Confirmar e importar</button>
<script>
let uploaded;
document.querySelector('#upload').onsubmit=async event=>{event.preventDefault();
 const response=await fetch('/api/uploads',{method:'POST',body:new FormData(event.target)});
 const payload=await response.json(); document.querySelector('#result').textContent=JSON.stringify(payload,null,2);
 if(response.ok){uploaded=payload; document.querySelector('#confirm').hidden=false;}}
document.querySelector('#confirm').onclick=async()=>{const response=await fetch(uploaded.confirmUrl,{method:'POST'});
 document.querySelector('#result').textContent=JSON.stringify(await response.json(),null,2);};
</script>
"""


def _page(title: str, body: str) -> str:
    return f"<!doctype html><html><body><h1>{html.escape(title)}</h1>{body}</body></html>"


def main() -> None:
    import uvicorn

    settings = Settings()
    uvicorn.run(create_app(settings), host=settings.invoice_upload_host, port=settings.invoice_upload_port)


app = create_app()
