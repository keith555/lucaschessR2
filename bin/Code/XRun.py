# Codex 06/09/2025
# I updated bin/Code/XRun.py so kibitzer subprocesses use the same interpreter as your main app (sys.executable).
#  This ensures they run inside your active venv and see installed packages.

import subprocess
import sys

import Code


def run_lucas(*args):
    li = []
    if sys.argv[0].endswith(".py"):
        # Use the current interpreter to preserve the active venv
        li.append(sys.executable)
        li.append("./LucasR.py")
    else:
        li.append("LucasR.exe" if Code.is_windows else "./LucasR")
    li.extend(args)

    return subprocess.Popen(li)
