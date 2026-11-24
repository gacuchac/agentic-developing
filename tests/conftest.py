"""Put scripts/workflow on sys.path so tests import its modules by name."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "workflow"))
