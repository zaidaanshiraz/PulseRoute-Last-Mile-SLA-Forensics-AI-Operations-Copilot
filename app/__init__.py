"""PulseRoute Application Package — Mohammed Zaidaan Shiraz"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from api_server import app

__all__ = ["app"]
