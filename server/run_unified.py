#!/usr/bin/env python3
"""
Run the unified TicketStats server (Deck + Relative Table APIs).
Combines both services on port 5000.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.deck.app import get_app

if __name__ == "__main__":
    app = get_app()
    
    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    print(f"🚀 Starting TicketStats Unified Server")
    print(f"   • Deck API: http://{host}:{port}/api/v1/deck/")
    print(f"   • Relative API: http://{host}:{port}/api/relative")
    print(f"   • Health: http://{host}:{port}/health")
    print(f"   • Debug: {debug}\n")
    
    app.run(host=host, port=port, debug=debug, threaded=True)
