import re, sys
t = open("out/%s.html" % sys.argv[1], encoding="utf-8").read()
ws = [float(x) for x in re.findall(r'<svg[^>]*?width="([0-9.]+)"', t)]
hs = [float(x) for x in re.findall(r'<svg[^>]*?height="([0-9.]+)"', t)]
sys.stdout.write("%d %d" % (int(max(ws or [400])), int(sum(hs) + 90 * len(hs))))
