"""Entry point for the recovered V2.29 full release."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.package_recovery_release import NAME, content, main
if __name__=='__main__':main()
