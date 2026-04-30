#!/usr/bin/env python3
"""Run the TickerStats FastAPI server."""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "false").lower() == "true"

    print("Starting TickerStats API Server (FastAPI)")
    print(f"   • FastAPI docs: http://{host}:{port}/docs")
    print(f"   • User API:     http://{host}:{port}/api/user/*")
    print(f"   • Relative API: http://{host}:{port}/api/relative")
    print(f"   • Deck API:     http://{host}:{port}/api/v1/deck/*")
    print(f"   • Health:       http://{host}:{port}/health")
    print(f"   • Debug: {debug}\n")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info",
    )
