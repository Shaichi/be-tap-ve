# usage: out/_shot.sh name   (expects out/name.drawio) -> out/name.png
n=$1
python scripts/preview_svg.py out/$n.drawio -o out/$n.html >/dev/null
set -- $(python out/_size.py "$n" | tr -d '\r')
W=$1; H=$2
mkdir -p /tmp/chr_prof
"/c/Program Files/Google/Chrome/Application/chrome.exe" --headless=new --disable-gpu --hide-scrollbars --user-data-dir="$(cygpath -w /tmp/chr_prof)" --window-size=$((W+60)),$((H+120)) --screenshot="$(cygpath -w $PWD/out/$n.png)" "file:///$(cygpath -m $PWD/out/$n.html)" 2>/dev/null
echo "$n ${W}x${H}"
