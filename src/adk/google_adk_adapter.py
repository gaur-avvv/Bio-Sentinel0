from __future__ import annotations

import importlib
from typing import Any


class GoogleADKBridge:
    """Optional bridge metadata for environments that install Google ADK."""

    def __init__(self) -> None:
        self._module = self._try_import_google_adk()

    def _try_import_google_adk(self) -> Any | None:
        for mod_name in ("google.adk", "google_adk"):
            try:
                return importlib.import_module(mod_name)
            except Exception:
                continue
        return None

    @property
    def available(self) -> bool:
        return self._module is not None

    def status(self) -> dict[str, Any]:
        if not self.available:
            return {
                "available": False,
                "message": "Google ADK package not detected. Using internal ADK runtime.",
            }
        return {
            "available": True,
            "module": getattr(self._module, "__name__", "google.adk"),
            "message": "Google ADK detected and can be wired for external orchestration.",
        }
