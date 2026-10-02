#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cai bo skill comet-uml-drawio + cac lenh ve tung loai so do (/uml-usecase, /uml-class, ..., /uml-comet).

Bo cuc sau khi cai (moi lenh la 1 skill anh em cua engine, giong quy uoc <dest>/sdd-*):
    <dest>/comet-uml-drawio/        engine: SKILL.md, scripts/, examples/, references/, tests/
    <dest>/uml-usecase/SKILL.md     lenh /uml-usecase - "<ENGINE>" da thay bang duong dan tuyet doi cua engine
    ...
<dest> mac dinh: ~/.claude/skills (Claude Code) va ~/.gemini/config/skills (Antigravity, neu co ~/.gemini/config).
Chi ghi de / xoa thu muc cua chinh bo skill nay (SKILL.md co 'name:' trung ten thu muc).

    python scripts/install.py                        # cai vao cac dest mac dinh
    python scripts/install.py --dest D:/skills       # cai vao thu muc khac (lap lai --dest duoc)
    python scripts/install.py --dry-run              # chi in viec se lam
    python scripts/install.py --uninstall            # go engine + cac lenh da cai
"""
import argparse
import os
import re
import shutil
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMANDS = ROOT / "commands"
PLACEHOLDER = "<ENGINE>"
MANIFEST = ".installed-commands"   # trong thu muc engine da cai: danh sach lenh da cai (de go lenh cu)
IGNORE = shutil.ignore_patterns("out", "__pycache__", "*.pyc", "commands", ".claude", ".git", ".idea", ".vscode")


def skill_name(skill_md):
    """Gia tri 'name:' trong frontmatter cua SKILL.md (None neu khong doc duoc)."""
    try:
        text = Path(skill_md).read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.match(r"---\s*\n(.*?)\n---", text, re.S)
    m = m and re.search(r"^name:\s*[\"']?([^\"'\s]+)[\"']?\s*$", m.group(1), re.M)
    return m.group(1) if m else None


def owned(target, name):
    """Thu muc dich chua ton tai, hoac la skill cua bo nay (SKILL.md co name trung)."""
    return not target.exists() or skill_name(target / "SKILL.md") == name


def plan():
    """[(ten skill, thu muc nguon)] - engine truoc, roi cac lenh trong commands/."""
    eng = skill_name(ROOT / "SKILL.md")
    if not eng:
        sys.exit("LOI: %s khong co frontmatter 'name:'" % (ROOT / "SKILL.md"))
    items = [(eng, ROOT)]
    for d in sorted(COMMANDS.iterdir()) if COMMANDS.is_dir() else []:
        if not (d / "SKILL.md").is_file():
            continue
        name = skill_name(d / "SKILL.md")
        if name != d.name:
            sys.exit("LOI: %s: 'name: %s' phai trung ten thu muc '%s'" % (d / "SKILL.md", name, d.name))
        items.append((name, d))
    return items


def rmtree(path):
    def fix(func, p, _exc):  # file chi-doc tren Windows
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=fix)
    else:
        shutil.rmtree(path, onerror=fix)


def copy_command(src, dst, engine_posix):
    """Chep thu muc lenh; file .md: thay <ENGINE> bang duong dan tuyet doi cua engine da cai."""
    dst.mkdir(parents=True)
    for f in sorted(src.rglob("*")):
        if "__pycache__" in f.parts or f.suffix == ".pyc":
            continue
        out = dst / f.relative_to(src)
        if f.is_dir():
            out.mkdir(parents=True, exist_ok=True)
        elif f.suffix.lower() == ".md":
            text = f.read_text(encoding="utf-8").replace(PLACEHOLDER, engine_posix)
            out.write_text(text, encoding="utf-8", newline="\n")
        else:
            shutil.copy2(f, out)


def replace_dir(target, build):
    """Dung ban moi o thu muc tam roi moi thay ban cu - loi giua chung khong de lai ban cai do dang."""
    tmp = target.with_name(target.name + ".installing")
    if tmp.exists():
        rmtree(tmp)
    build(tmp)
    if target.exists():
        rmtree(target)
    tmp.rename(target)


def install(dest, dry):
    items = plan()
    eng_name = items[0][0]
    bad = [str(dest / n) for n, _ in items if not owned(dest / n, n)]
    if bad:
        print("LOI [%s]: thu muc da ton tai nhung khong phai cua bo skill nay - khong ghi de:\n  %s"
              % (dest, "\n  ".join(bad)), file=sys.stderr)
        return False
    engine_dir = dest / eng_name
    engine_posix = engine_dir.absolute().as_posix()
    names = [n for n, _ in items[1:]]
    old = []
    if (engine_dir / MANIFEST).is_file():
        old = (engine_dir / MANIFEST).read_text(encoding="utf-8").split()
    stale = [n for n in old if n not in names and (dest / n).exists() and owned(dest / n, n)]
    print("[%s]" % dest)
    print("  engine  %s/  (<ENGINE> = %s)" % (eng_name, engine_posix))
    for n in names:
        print("  lenh    %s/SKILL.md  -> /%s" % (n, n))
    for n in stale:
        print("  go      %s/  (lenh cu khong con trong commands/)" % n)
    if dry:
        return True
    dest.mkdir(parents=True, exist_ok=True)

    def build_engine(tmp):
        shutil.copytree(ROOT, tmp, ignore=IGNORE)
        (tmp / MANIFEST).write_text("\n".join(names) + "\n", encoding="utf-8")
    replace_dir(engine_dir, build_engine)
    for name, src in items[1:]:
        replace_dir(dest / name, lambda tmp, src=src: copy_command(src, tmp, engine_posix))
    for n in stale:
        rmtree(dest / n)
    left = [str(dest / n / "SKILL.md") for n in names
            if PLACEHOLDER in (dest / n / "SKILL.md").read_text(encoding="utf-8")]
    if left:
        print("LOI: con placeholder %s trong:\n  %s" % (PLACEHOLDER, "\n  ".join(left)), file=sys.stderr)
        return False
    return True


def uninstall(dest, dry):
    items = plan()
    eng_name = items[0][0]
    names = [n for n, _ in items[1:]]
    if (dest / eng_name / MANIFEST).is_file():
        names += (dest / eng_name / MANIFEST).read_text(encoding="utf-8").split()
    ok = True
    print("[%s]" % dest)
    for n in dict.fromkeys(names + [eng_name]):   # engine sau cung, giu thu tu, bo trung
        target = dest / n
        if not target.exists():
            continue
        if not owned(target, n):
            print("  bo qua %s/ (khong phai cua bo skill nay)" % n, file=sys.stderr)
            ok = False
            continue
        print("  go     %s/" % n)
        if not dry:
            rmtree(target)
    return ok


def default_dests():
    home = Path.home()
    dests = [home / ".claude" / "skills"]
    if (home / ".gemini" / "config").is_dir():
        dests.append(home / ".gemini" / "config" / "skills")
    return dests


def main():
    ap = argparse.ArgumentParser(description="Cai skill comet-uml-drawio + lenh /uml-* vao thu muc skills")
    ap.add_argument("--dest", action="append", help="thu muc skills dich (lap lai duoc); mac dinh: "
                    "~/.claude/skills va ~/.gemini/config/skills (neu co ~/.gemini/config)")
    ap.add_argument("--dry-run", action="store_true", help="chi in viec se lam, khong ghi gi")
    ap.add_argument("--uninstall", action="store_true", help="go engine + cac lenh /uml-* da cai")
    a = ap.parse_args()
    dests = [Path(d).expanduser() for d in a.dest] if a.dest else default_dests()
    if any(d.resolve() == ROOT.parent.resolve() for d in dests):
        sys.exit("LOI: --dest trung thu muc chua ban nguon (%s)" % ROOT.parent)
    ok = True
    for d in dests:
        ok = (uninstall if a.uninstall else install)(d, a.dry_run) and ok
    if a.dry_run:
        print("(dry-run: chua ghi gi)")
    elif ok and a.uninstall:
        print("Da go.")
    elif ok:
        print("Xong. Mo phien moi cua Claude Code / Antigravity de nap skill + lenh.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
