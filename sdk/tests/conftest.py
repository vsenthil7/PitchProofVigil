"""Make the SDK package importable as `pitchproof_vigil` during tests."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
