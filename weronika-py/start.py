#!/usr/bin/env python3
"""
Weronika — same-browser launcher (no chrome test).

Just delegates to weronika_launcher.py so any start method does the same thing.
"""
import weronika_launcher
import sys
if __name__ == "__main__":
    # Forward CLI args
    sys.argv[0] = "weronika_launcher.py"
    weronika_launcher.main()
