"""Supabase HTTP client wrapper (Checkpoint 14).

Provides an asynchronous client for Supabase PostgREST tables and Storage API
using standard httpx requests.

Features:
- Never exposes secrets in logs or representations (keys are masked).
- Translates network/HTTP failures into controlled domain exceptions.
- Provides health checking and safe timeouts.
- Accepts an injected httpx.AsyncClient for deterministic offline testing.
"""

from typing import Any, Mapping
import logging
import httpx
from pydantic import SecretStr

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------- exceptions
class SupabaseError(Exception):
    """Base exception for all Supabase client operations."""

    def __init__(self, message: str, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class SupabaseConnectionError(SupabaseError):
    """Raised when the Supabase server cannot be reached."""


class SupabaseApiError(SupabaseError):
    """Raised when Supabase returns a non-2xx HTTP error status."""


# ------------------------------------------------------------------- client
class SupabaseClient:
    def __init__(
        self,
        url: str,
        key: str | SecretStr,
        *,
        timeout: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = url.rstrip("/")
        self._raw_key = key.get_secret_value() if isinstance(key, SecretStr) else str(key)
        self.timeout = timeout
        self._external_client = http_client
        self._internal_client: httpx.AsyncClient | None = None

    def __repr__(self) -> str:
        # Guarantee secrets are never printed in string representations or tracebacks
        return f"<SupabaseClient url='{self.base_url}' key='***'>"

    __str__ = __repr__

    @property
    def rest_url(self) -> str:
        return f"{self.base_url}/rest/v1"

    @property
    def storage_url(self) -> str:
        return f"{self.base_url}/storage/v1"

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self._raw_key,
            "Authorization": f"Bearer {self._raw_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._external_client is not None:
            return self._external_client
        if self._internal_client is None or self._internal_client.is_closed:
            self._internal_client = httpx.AsyncClient(timeout=self.timeout)
        return self._internal_client

    async def close(self) -> None:
        if self._internal_client is not None and not self._internal_client.is_closed:
            await self._internal_client.aclose()

    # ------------------------------------------------------------ health check
    async def health_check(self) -> bool:
        """Check if the Supabase endpoint is reachable and authenticated."""
        try:
            client = await self._get_http_client()
            response = await client.get(
                f"{self.rest_url}/",
                headers={"apikey": self._raw_key, "Authorization": f"Bearer {self._raw_key}"},
            )
            # PostgREST root returns OpenAPI spec (200) or 404/401 depending on config
            return response.status_code in {200, 404}
        except (httpx.RequestError, OSError):
            return False

    # ----------------------------------------------------------------- tables
    async def select(
        self,
        table: str,
        query_params: Mapping[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Query rows from a PostgREST table."""
        client = await self._get_http_client()
        url = f"{self.rest_url}/{table}"
        try:
            response = await client.get(url, headers=self._headers, params=query_params or {})
        except httpx.RequestError as exc:
            raise SupabaseConnectionError(f"Could not connect to Supabase: {exc}") from exc

        if response.status_code >= 400:
            raise SupabaseApiError(
                f"Supabase select on '{table}' failed with status {response.status_code}: {response.text}",
                status_code=response.status_code,
                details=response.text,
            )
        data = response.json()
        return data if isinstance(data, list) else [data]

    async def insert(
        self,
        table: str,
        record: dict[str, Any] | list[dict[str, Any]],
        *,
        upsert: bool = False,
    ) -> list[dict[str, Any]]:
        """Insert or upsert rows into a table."""
        client = await self._get_http_client()
        url = f"{self.rest_url}/{table}"
        headers = dict(self._headers)
        if upsert:
            headers["Prefer"] = "resolution=merge-duplicates,return=representation"

        try:
            response = await client.post(url, headers=headers, json=record)
        except httpx.RequestError as exc:
            raise SupabaseConnectionError(f"Could not connect to Supabase: {exc}") from exc

        if response.status_code >= 400:
            raise SupabaseApiError(
                f"Supabase insert on '{table}' failed with status {response.status_code}: {response.text}",
                status_code=response.status_code,
                details=response.text,
            )
        data = response.json()
        return data if isinstance(data, list) else [data]

    async def update(
        self,
        table: str,
        record: dict[str, Any],
        match_params: Mapping[str, str],
    ) -> list[dict[str, Any]]:
        """Update rows matching query parameters."""
        client = await self._get_http_client()
        url = f"{self.rest_url}/{table}"
        try:
            response = await client.patch(url, headers=self._headers, params=match_params, json=record)
        except httpx.RequestError as exc:
            raise SupabaseConnectionError(f"Could not connect to Supabase: {exc}") from exc

        if response.status_code >= 400:
            raise SupabaseApiError(
                f"Supabase update on '{table}' failed with status {response.status_code}: {response.text}",
                status_code=response.status_code,
                details=response.text,
            )
        data = response.json()
        return data if isinstance(data, list) else [data]

    async def delete(
        self,
        table: str,
        match_params: Mapping[str, str],
    ) -> list[dict[str, Any]]:
        """Delete rows matching query parameters."""
        client = await self._get_http_client()
        url = f"{self.rest_url}/{table}"
        try:
            response = await client.delete(url, headers=self._headers, params=match_params)
        except httpx.RequestError as exc:
            raise SupabaseConnectionError(f"Could not connect to Supabase: {exc}") from exc

        if response.status_code >= 400:
            raise SupabaseApiError(
                f"Supabase delete on '{table}' failed with status {response.status_code}: {response.text}",
                status_code=response.status_code,
                details=response.text,
            )
        data = response.json()
        return data if isinstance(data, list) else [data]

    # ---------------------------------------------------------------- storage
    async def upload_object(
        self,
        bucket: str,
        path: str,
        content: bytes,
        content_type: str = "application/json",
    ) -> str:
        """Upload raw bytes to Supabase Storage. Returns storage path key."""
        client = await self._get_http_client()
        url = f"{self.storage_url}/object/{bucket}/{path.lstrip('/')}"
        headers = {
            "apikey": self._raw_key,
            "Authorization": f"Bearer {self._raw_key}",
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        try:
            response = await client.post(url, headers=headers, content=content)
        except httpx.RequestError as exc:
            raise SupabaseConnectionError(f"Could not connect to Supabase storage: {exc}") from exc

        if response.status_code >= 400:
            raise SupabaseApiError(
                f"Supabase storage upload failed with status {response.status_code}: {response.text}",
                status_code=response.status_code,
                details=response.text,
            )
        return f"{bucket}/{path.lstrip('/')}"

    async def get_object(self, bucket: str, path: str) -> bytes | None:
        """Retrieve raw bytes from Supabase Storage."""
        client = await self._get_http_client()
        url = f"{self.storage_url}/object/{bucket}/{path.lstrip('/')}"
        headers = {
            "apikey": self._raw_key,
            "Authorization": f"Bearer {self._raw_key}",
        }
        try:
            response = await client.get(url, headers=headers)
        except httpx.RequestError as exc:
            raise SupabaseConnectionError(f"Could not connect to Supabase storage: {exc}") from exc

        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise SupabaseApiError(
                f"Supabase storage get failed with status {response.status_code}: {response.text}",
                status_code=response.status_code,
                details=response.text,
            )
        return response.content

    async def delete_object(self, bucket: str, path: str) -> bool:
        """Delete an object from Supabase Storage."""
        client = await self._get_http_client()
        url = f"{self.storage_url}/object/{bucket}/{path.lstrip('/')}"
        headers = {
            "apikey": self._raw_key,
            "Authorization": f"Bearer {self._raw_key}",
        }
        try:
            response = await client.delete(url, headers=headers)
        except httpx.RequestError as exc:
            raise SupabaseConnectionError(f"Could not connect to Supabase storage: {exc}") from exc

        if response.status_code == 404:
            return False
        if response.status_code >= 400:
            raise SupabaseApiError(
                f"Supabase storage delete failed with status {response.status_code}: {response.text}",
                status_code=response.status_code,
                details=response.text,
            )
        return True
