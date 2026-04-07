from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@lru_cache(maxsize=8)
def load_yaml_config(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        return {}
    content = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(content, dict):
        return {}
    return content
