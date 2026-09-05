from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from invoice_upload_test import app as app_module
from invoice_upload_test.app import create_app
from invoice_upload_test.settings import Settings


def test_upload_extracts_and_confirms_cashoreca_invoice(tmp_path: Path) -> None:
    workspace = Path(__file__).parents[2]
    settings = Settings(
        invoice_bridge_dir=workspace / "invoice-bridge",
        pricing_catalog_bridge_dir=workspace / "pricing-catalog-bridge",
        pricing_data_dir=tmp_path / "pricing",
        invoice_data_dir=tmp_path / "invoice-bridge-data",
        invoice_upload_staging_dir=tmp_path / "temporary-ui-staging",
        bridge_python_command=sys.executable,
    )
    client = TestClient(create_app(settings))

    upload = client.post(
        "/api/uploads",
        files={
            "file": (
                "cashoreca.txt",
                b"CASHORECA\n260112066\n574|8429|COCA COLA LATA 330 ML 1*24|2|10.51|0|21.02|21\n",
                "text/plain",
            )
        },
    )

    assert upload.status_code == 200
    payload = upload.json()
    assert payload["invoice"]["status"] == "EXTRACTED"
    assert payload["invoice"]["lines"][0]["validationStatus"] == "VALID"

    confirmed = client.post(payload["confirmUrl"])

    assert confirmed.status_code == 200
    assert confirmed.json()["insertedOffers"] == 1
    assert list((tmp_path / "invoice-bridge-data" / "uploads").iterdir())
    assert not list((tmp_path / "temporary-ui-staging" / "uploads").iterdir())


def test_upload_exposes_the_vision_failure_reason(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    class FailingInvoiceClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        async def call(self, tool_name: str, _arguments: object) -> dict[str, str]:
            if tool_name == "archive_invoice":
                return {"sourceUri": str(tmp_path / "archived.pdf")}
            if tool_name == "extract_invoice":
                raise RuntimeError("HTTP 400: el Gateway no admite esta entrada visual.")
            return {}

    monkeypatch.setattr(app_module, "BridgeMcpClient", FailingInvoiceClient)
    settings = Settings(
        invoice_bridge_dir=tmp_path / "invoice-bridge",
        pricing_catalog_bridge_dir=tmp_path / "pricing-catalog-bridge",
        pricing_data_dir=tmp_path / "pricing",
        invoice_data_dir=tmp_path / "invoice-bridge-data",
        invoice_upload_staging_dir=tmp_path / "temporary-ui-staging",
        bridge_python_command=sys.executable,
    )
    client = TestClient(create_app(settings))

    upload = client.post("/api/uploads", files={"file": ("invoice.pdf", b"pdf-data", "application/pdf")})

    assert upload.status_code == 422
    assert "Gateway no admite" in upload.json()["detail"]
