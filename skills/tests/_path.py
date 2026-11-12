"""Put the skill's scripts/ on sys.path for the tests."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent / "skills" / "prototype-to-backlog"
SCRIPTS = SKILL / "scripts"
FIXTURES = HERE / "fixtures"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
