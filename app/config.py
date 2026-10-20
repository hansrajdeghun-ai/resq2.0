"""Central configuration. Every credential and tunable lives here."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_env: str = "dev"
    use_mocks: bool = True
    log_level: str = "INFO"
    kill_switch: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./resq.sqlite3"

    # Kapture (ledger) — live UAT access provided
    kapture_base_url: str = "https://resqplatform.prep.ril.com/api"
    kapture_credential_id: str = "kapture"
    kapture_secret_key: str = ""
    kapture_checksum_key: str = ""  # pending; create APIs mock until set
    # TLS: default certifi. On a machine behind a TLS-inspecting SASE proxy
    # (e.g. Check Point Harmony), point this at a bundle that includes the
    # corporate root (see scripts/make_ca_bundle.sh). Empty => certifi default.
    kapture_ca_bundle: str = ""
    kapture_verify_ssl: bool = True

    # GCP Pub/Sub
    gcp_project_id: str = "sr-prj-rrl-retail-release-resq"
    pubsub_subscription: str = "fynd-hackathon-sub"
    google_application_credentials: str = ""

    # WhatsApp Cloud API
    whatsapp_access_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_webhook_verify_token: str = "resq-verify"
    whatsapp_api_version: str = "v21.0"
    wa_phone_id_customer: str = ""
    wa_phone_id_owner: str = ""
    wa_phone_id_field: str = ""
    wa_phone_id_area: str = ""

    # LLM — Claude preferred; OpenAI used when only an OpenAI key is present
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_vision_model: str = "gpt-4o"
    ai_daily_token_cap: int = 2_000_000

    @property
    def llm_provider(self) -> str | None:
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        return None

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider is not None

    # Payments
    upi_provider_url: str = ""
    upi_merchant_id: str = ""

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def kapture_create_ready(self) -> bool:
        """The two B2B create APIs need the checksum key; mock until present."""
        return bool(self.kapture_checksum_key) and not self.use_mocks

    def wa_phone_id_for(self, role: str) -> str:
        return {
            "customer": self.wa_phone_id_customer,
            "owner": self.wa_phone_id_owner,
            "field": self.wa_phone_id_field,
            "area": self.wa_phone_id_area,
        }.get(role, "")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
