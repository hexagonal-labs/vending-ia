from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    nayax_llm_provider: Literal["openai", "openclaw_gateway"] = "openai"
    openai_api_key: str = ""
    openai_base_url: str | None = None
    nayax_llm_model: str = "gpt-5.4-mini"
    nayax_llm_temperature: float = 0.0
    nayax_llm_timeout_seconds: float = 30.0
    openclaw_gateway_url: str = "http://127.0.0.1:18789/v1"
    openclaw_gateway_token: str = ""
    openclaw_gateway_model: str = "openclaw/nayax-langgraph-bridge"
    openclaw_gateway_timeout_seconds: float = 120.0
    nayax_bridge_dir: Path = Path("../nayax-bridge")
    nayax_node_command: str = "node"
    supplier_bridge_dir: Path = Path("../supplier-bridge")
    pricing_catalog_bridge_dir: Path = Path("../pricing-catalog-bridge")
    invoice_bridge_dir: Path = Path("../invoice-bridge")
    bridge_python_command: str = "python"
    pricing_data_dir: Path = Path("data/pricing")
    pricing_default_provider_id: str = "distribuidora-mayorista"
    pricing_default_provider_source: Literal["api", "catalog"] = "api"
    nayax_checkpoint_db: Path = Path("data/checkpoints.db")
    max_machine_fetch_concurrency: int = Field(default=4, ge=1, le=20)
    distribuidora_mayorista_base_url: str = "https://distribucionmayorista.online"
    distribuidora_mayorista_email: str = ""
    distribuidora_mayorista_password: str = ""
    distribuidora_mayorista_wishlist_id: str = ""
