import os
import sys
from pathlib import Path

# Add coe_sync directory to path
COE_SYNC_DIR = Path(__file__).resolve().parent / "coe_sync"
sys.path.insert(0, str(COE_SYNC_DIR))

from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
