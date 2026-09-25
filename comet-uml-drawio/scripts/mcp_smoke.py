#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_smoke.py - Goi truc tiep draw.io MCP server (stdio, JSON-RPC) de kiem tra khi phien AI chua nap tool.

  python mcp_smoke.py --list                       # liet ke tool cua server
  python mcp_smoke.py file.drawio [--tool open_drawio_xml] [--arg content]
  python mcp_smoke.py - --tool list_pages --args '{"path": "out/atm_all.drawio"}'
"""
import argparse
import json
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def rpc(proc, mid, method, params=None):
    msg = {"jsonrpc": "2.0", "method": method}
    if mid is not None:
        msg["id"] = mid
    if params is not None:
        msg["params"] = params
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    if mid is None:
        return None
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("server dong ket noi")
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("id") == mid:
            return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--tool", default="open_drawio_xml")
    ap.add_argument("--arg", default="content", help="ten tham so chua XML")
    ap.add_argument("--args", help="JSON tham so them, vd '{\"path\": \"x.drawio\"}'")
    ap.add_argument("--save", help="ghi noi dung text tra ve vao file")
    ap.add_argument("--cmd", default="npx -y @drawio/mcp")
    a = ap.parse_args()
    proc = subprocess.Popen(a.cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            text=True, encoding="utf-8")
    try:
        r = rpc(proc, 1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                        "clientInfo": {"name": "mcp_smoke", "version": "1"}})
        print("server:", json.dumps(r.get("result", {}).get("serverInfo")))
        rpc(proc, None, "notifications/initialized")
        tools = rpc(proc, 2, "tools/list", {})["result"]["tools"]
        if a.list or not a.file:
            for t in tools:
                print("-", t["name"], ":", (t.get("description") or "").split("\n")[0][:160])
                print("   params:", json.dumps(t.get("inputSchema", {}).get("properties", {}), ensure_ascii=False)[:400])
            return
        args = json.loads(a.args) if a.args else {}
        if a.file != "-":
            with open(a.file, encoding="utf-8") as f:
                args[a.arg] = f.read()
        r = rpc(proc, 3, "tools/call", {"name": a.tool, "arguments": args})
        res = r.get("result") or r.get("error")
        for c in (res.get("content") or []) if isinstance(res, dict) else []:
            if c.get("type") == "text":
                t = c["text"]
                if a.save:
                    with open(a.save, "w", encoding="utf-8") as f:
                        f.write(t)
                    print("Da luu ket qua vao", a.save)
                print(t if len(t) < 400 else t[:200] + " ... (%d ky tu)" % len(t))
        if isinstance(res, dict) and (res.get("isError") or "code" in res):
            print("LOI:", json.dumps(res, ensure_ascii=False)[:500])
            sys.exit(1)
    finally:
        proc.stdin.close()
        proc.terminate()


if __name__ == "__main__":
    main()
