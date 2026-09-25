import sys, os, time, xml.etree.ElementTree as ET
sys.path.insert(0, "scripts"); sys.path.insert(0, "tests")
from uml2drawio import generate
from validate_drawio import validate_file
from fuzz_specs import GENERATORS
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
bad = 0
t0 = time.time()
for kind, gen in GENERATORS.items():
    for seed in range(N):
        spec = gen(seed)
        try:
            mx, models, warns = generate([spec])
            rep = validate_file(ET.tostring(mx, encoding="unicode"))
        except Exception as ex:
            print("CRASH", kind, seed, repr(ex)); bad += 1; continue
        for p in rep:
            if p["errors"] or p["warnings"]:
                bad += 1
                print("%s seed=%d: %d E, %d W" % (kind, seed, len(p["errors"]), len(p["warnings"])))
                for x in (p["errors"] + p["warnings"])[:4]:
                    print("    ", x)
print("bad=%d  time=%.1fs" % (bad, time.time() - t0))
