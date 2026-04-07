from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.data.synthetic_generator import generate_synthetic_pairs


def main() -> None:
    out_dir = Path("artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "synthetic_pairs.json"
    pairs = generate_synthetic_pairs(n=200)
    out_file.write_text(json.dumps(pairs, indent=2), encoding="utf-8")
    print(f"Wrote {len(pairs)} synthetic pairs to {out_file}")


if __name__ == "__main__":
    main()
