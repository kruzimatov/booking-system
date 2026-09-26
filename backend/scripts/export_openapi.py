"""Write the OpenAPI schema for the frontend type generator, without starting a server.

Usage (from backend/): uv run python -m scripts.export_openapi
"""

import json
from pathlib import Path

from app.main import create_app

TARGET = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def main() -> None:
    schema = create_app().openapi()
    TARGET.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {TARGET}")


if __name__ == "__main__":
    main()
