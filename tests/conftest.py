import os
import sys

# Make the src/ layout importable without requiring an editable install,
# so `pytest` works straight out of a fresh clone too.
_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, os.path.abspath(_SRC))
