import os
import sys

# make `custom_components` importable from the repo root for the unit tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
