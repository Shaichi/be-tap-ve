"""Dong bo skill tu thu muc du an sang cac ban cai dat (bo out/, __pycache__, .claude/)."""
import os, shutil, sys
SRC = os.path.abspath(".")
PARTS = ["SKILL.md", "scripts", "references", "examples", "tests"]
STALE = ["out", "scripts/__pycache__", "tests/__pycache__"]
ign = shutil.ignore_patterns("__pycache__", "*.pyc", "out", ".claude")
for dst in sys.argv[1:]:
    dst = os.path.expanduser(dst)
    for p in PARTS + STALE:
        q = os.path.join(dst, p)
        if os.path.isdir(q):
            shutil.rmtree(q)
        elif os.path.isfile(q):
            os.remove(q)
    for p in PARTS:
        s = os.path.join(SRC, p)
        if os.path.isdir(s):
            shutil.copytree(s, os.path.join(dst, p), ignore=ign)
        elif os.path.isfile(s):
            shutil.copy2(s, os.path.join(dst, p))
    n = sum(len(fs) for _, _, fs in os.walk(dst))
    print("synced ->", dst, "(%d files)" % n)
