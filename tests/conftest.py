from __future__ import annotations

import sys
from pathlib import Path

# Ensure imports like `from src...` work regardless of how pytest is invoked.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
