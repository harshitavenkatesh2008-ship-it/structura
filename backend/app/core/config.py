from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Structura"
    environment: str = "development"

    # Supabase credentials & persistence settings
    supabase_url: str | None = None
    supabase_key: SecretStr | None = None
    supabase_service_role_key: SecretStr | None = None
    supabase_bucket: str = "documents"
    persistence_backend: str = "auto"  # "auto", "supabase", "memory"

    # Recovery configuration
    job_recovery_enabled: bool = True
    job_stale_timeout_seconds: int = 3600

    @property
    def is_supabase_configured(self) -> bool:
        """True when Supabase credentials and URL are present and not forced to memory."""
        if self.persistence_backend == "memory":
            return False
        has_url = bool(self.supabase_url and self.supabase_url.strip())
        key = self.supabase_service_role_key or self.supabase_key
        has_key = bool(key and key.get_secret_value().strip())
        return has_url and has_key

    def get_effective_supabase_key(self) -> str | None:
        """Returns the raw service role key or public key if configured, else None."""
        key = self.supabase_service_role_key or self.supabase_key
        return key.get_secret_value() if key else None


settings = Settings()
