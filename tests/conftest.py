import sys
from pathlib import Path

# Test against src/, not against whatever mfpandas happens to be installed.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
