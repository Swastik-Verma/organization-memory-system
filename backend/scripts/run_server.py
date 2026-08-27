"""
Start the FastAPI server.

Usage:
    python scripts/run_server.py
    python scripts/run_server.py --port 8000
    python scripts/run_server.py --reload    # auto-reload on code changes
"""

import argparse
import logging
import sys
from pathlib import Path

# Path setup
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root / "backend"))

import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)


def main():
    parser = argparse.ArgumentParser(description="Start the API server")
    parser.add_argument(
        "--host", default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port to listen on (default: 8000)",
    )
    parser.add_argument(
        "--reload", action="store_true",
        help="Enable auto-reload on code changes",
    )
    args = parser.parse_args()

    uvicorn.run(
        "src.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()