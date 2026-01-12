#!/usr/bin/env python3
"""
Simple runner script for the Prediction Market Tracker.

This starts the tracker without needing to remember uvicorn commands.

Usage:
    python run.py
    
Or make it executable:
    chmod +x run.py
    ./run.py
"""
import uvicorn
import os
import sys

def main():
    # Add project root to path
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)
    
    # Get settings from environment
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "true").lower() == "true"
    
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║           🐋 Prediction Market Whale Tracker 🐋           ║
    ╠═══════════════════════════════════════════════════════════╣
    ║  Starting server...                                       ║
    ║                                                           ║
    ║  API Docs:    http://{host}:{port}/docs                    ║
    ║  Health:      http://{host}:{port}/health                  ║
    ║  Alerts:      http://{host}:{port}/alerts                  ║
    ╚═══════════════════════════════════════════════════════════╝
    """.format(host=host, port=port))
    
    # Run the server
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
