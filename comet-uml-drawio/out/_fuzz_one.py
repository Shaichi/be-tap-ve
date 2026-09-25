import sys, traceback, xml.etree.ElementTree as ET
sys.path.insert(0, "scripts"); sys.path.insert(0, "tests")
from uml2drawio import generate
from fuzz_specs import GENERATORS
kind, seed = sys.argv[1], int(sys.argv[2])
spec = GENERATORS[kind](seed)
import json; json.dump(spec, open("out/_fuzz_%s_%d.json" % (kind, seed), "w"), indent=1)
try:
    generate([spec])
except Exception:
    traceback.print_exc()
