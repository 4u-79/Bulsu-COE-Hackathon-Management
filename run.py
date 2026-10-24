import sys
from pathlib import Path

# Add coe_sync directory to path
COE_SYNC_DIR = Path(__file__).resolve().parent / "coe_sync"
sys.path.insert(0, str(COE_SYNC_DIR))

from app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
