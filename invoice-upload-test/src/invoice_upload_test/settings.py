from __future__ import annotations

import sys
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    invoice_bridge_dir: Path = Path("../invoice-bridge")
    pricing_catalog_bridge_dir: Path = Path("../pricing-catalog-bridge")
    invoice_data_dir: Path = Path("/var/lib/invoice-bridge")
    pricing_data_dir: Path = Path("/var/lib/pricing-catalog-bridge")
    invoice_upload_staging_dir: Path = Path("/tmp/invoice-upload-test")
    invoice_equivalence_surcharge_rate: str = "0.052"
    invoice_upload_max_bytes: int = Field(default=20 * 1024 * 1024, ge=1)
    invoice_upload_host: str = "127.0.0.1"
    invoice_upload_port: int = Field(default=8088, ge=1, le=65535)
    bridge_python_command: str = sys.executable
