"""
WhatsApp Bot Platform
=====================

Multi-tenant WhatsApp bot platform using GreenAPI.
Supports multiple clients with isolated configurations.

Architecture:
- FastAPI server for receiving webhooks
- Tenant-scoped configurations
- AI-powered responses via OpenAI Assistants API
- IVR menu fallback

Author: MonsterDEVZ
"""

import os
import sys
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent / "packages"))

# Import WhatsApp Gateway
from apps.whatsapp_gateway.main import app

if __name__ == "__main__":
    import uvicorn

    # Get port from environment
    port = int(os.getenv("PORT", "8000"))

    # Start server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )
