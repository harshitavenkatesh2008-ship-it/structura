"""Specialist extractor registry for the SAFE pipeline.

Maps SAFE route identifiers to extractor capabilities.  The registry
distinguishes three states for every route:

- ``already_satisfied`` — the initial extractor matches the recommended
  route, so no specialist dispatch is needed.
- ``unavailable`` — a specialist is registered but cannot extract from a
  raw PDF region (it is a block assembler/validator only).
- ``unsupported`` — no specialist is registered for this route at all.

The registry is intentionally a passive lookup table.  It never calls an
extractor; that responsibility belongs to the pipeline service.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, Tuple, runtime_checkable


# ---------------------------------------------------------------------------
# Extractor capability protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class RegionExtractor(Protocol):
    """An extractor that can produce content from a raw PDF region."""

    def extract_region(
        self,
        file_path: str,
        page: int,
        bbox: Tuple[float, float, float, float],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Extract content from a specific page region.

        Returns a dict suitable for constructing a Document Graph block's
        ``content`` field.
        """
        ...


# ---------------------------------------------------------------------------
# Registry entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegistryEntry:
    """Describes a registered specialist extractor."""

    route: str
    can_extract_region: bool
    extractor: Optional[Any] = None

    @property
    def available(self) -> bool:
        """True when an extractor instance is present."""
        return self.extractor is not None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ExtractorRegistry:
    """Central lookup for specialist extractors.

    Instantiated once per pipeline run.  Extractors are registered via
    :meth:`register` and looked up via :meth:`lookup`.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, RegistryEntry] = {}

    def register(
        self,
        route: str,
        extractor: Any,
        *,
        can_extract_region: bool = False,
    ) -> None:
        """Register a specialist extractor for a SAFE route.

        Args:
            route: One of the SAFE route identifiers (e.g. ``"ocr"``).
            extractor: The extractor instance.
            can_extract_region: Whether this extractor can extract content
                from a raw PDF region (page + bbox).
        """
        self._entries[route] = RegistryEntry(
            route=route,
            can_extract_region=can_extract_region,
            extractor=extractor,
        )

    def lookup(self, route: str) -> Optional[RegistryEntry]:
        """Return the registry entry for *route*, or ``None``."""
        return self._entries.get(route)

    def resolve_status(
        self,
        recommended_route: str,
        initial_extractor: str,
    ) -> str:
        """Determine the route status for a block.

        Returns one of:
        - ``"already_satisfied"`` — recommended route matches the initial
          extractor.
        - ``"dispatched"`` — a specialist was dispatched (set by the
          pipeline after actual execution; the registry never returns
          this).
        - ``"unavailable"`` — a specialist is registered but cannot
          extract from a raw PDF region.
        - ``"unsupported"`` — no specialist is registered at all.
        """
        if recommended_route == initial_extractor:
            return "already_satisfied"

        entry = self.lookup(recommended_route)

        if entry is None:
            return "unsupported"

        if not entry.can_extract_region:
            return "unavailable"

        # The extractor CAN extract — the pipeline should dispatch it.
        # Return a sentinel so the pipeline knows to proceed.
        return "pending_dispatch"

    @property
    def registered_routes(self) -> Tuple[str, ...]:
        """Sorted tuple of all registered route identifiers."""
        return tuple(sorted(self._entries))


def build_default_registry() -> ExtractorRegistry:
    """Build the default registry with currently available specialists.

    By default in C11 base integration, the registry starts empty so that
    routes without an explicitly configured specialist are reported as
    'unsupported'. Specialists like OCRExtractor or test specialist extractors
    are registered explicitly or via helper factories.
    """
    return ExtractorRegistry()
