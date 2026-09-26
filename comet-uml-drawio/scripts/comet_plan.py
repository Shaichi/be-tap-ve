#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tạo repair plan có cấu trúc từ comet_check + semantic model."""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from comet_check import check, load
from comet_model import build_model


RULE_ACTIONS = {
    "R1": "Tao it nhat mot communication/sequence diagram cho use case dang thieu.",
    "R2": "Kiem tra actor trong interaction va bo sung/doi chieu actor voi use case model.",
    "R3": "Dat boundary giua actor va control/entity; khong de actor goi truc tiep structural object.",
    "R4": "Sua stereotype ve mot COMET structural role hop le.",
    "R5": "Dong bo entity object voi entity class cung bundle.",
    "R6": "Kiem tra entity co dang phat message chu dong hay chi tra du lieu.",
    "R7": "Tao statechart cho state dependent control dang thieu.",
    "R8": "Dong bo event/action cua statechart voi message den/di control.",
    "R9": "Sua message reference/ten/seq de moi message co endpoint hop le va seq khong trung.",
    "R10": "Bo operations khoi entity class o pha analysis.",
    "R11": "Sua context diagram ve dung 1 software system va stereotype external hop le.",
    "R12": "Dong bo message va endpoint giua communication va sequence cua cung use case.",
    "R13": "Bao dam boundary/proxy co trao doi voi actor/external actor.",
    "R14": "Dong bo actor voi context external cung bundle.",
    "X1": "Sua useCase reference hoac them use case tuong ung trong cung bundle.",
    "X2": "Bo actor thieu vao interaction dung use case/bundle.",
    "X3": "Sua stateMachineOf hoac them state dependent control tuong ung trong interaction cung bundle.",
    "X4": "Dong bo tap entity giua ERD va entity class model cung bundle.",
    "X5": "Dong bo top-level component giua component va deployment cung bundle.",
    "X6": "Chon mot structural role nhat quan cho concept trong cung bundle.",
    "S1": "Sua initial pseudostate de chi co mot transition ra va khong co event/guard o transition khoi tao.",
    "S2": "Bo transition ra khoi final state.",
    "S3": "Them guard phan biet cho cac nhanh choice/junction.",
    "S4": "Noi state bi cut voi flow hop le hoac final state.",
    "S5": "Them guard phan biet cho cac transition cung event.",
    "A1": "Them guard cho cac nhanh decision va toi da mot nhanh else.",
    "A2": "Sua cardinality cua fork/join theo 1-in-many-out / many-in-1-out.",
    "A3": "Sua initial/final node theo quy tac activity.",
    "A4": "Dung merge de gop va decision de re nhanh, khong dung sai vai tro.",
    "A5": "Noi action voi luong vao/ra hop le.",
    "A6": "Tach join/fork ngam thanh node UML tuong ung.",
    "C1": "Them kieu cho moi attribute.",
    "C2": "Bo sung multiplicity va role/ten association khi can.",
    "E1": "Chi noi quan he ERD vao entity/relationship hop le.",
    "E2": "Bo sung cardinality o hai dau quan he.",
    "E3": "Dat ten cho quan he/hinh thoi.",
    "F1": "Noi moi man hinh tu root cua site map.",
    "F2": "Loai bo node/label khong hop le khoi screen flow.",
    "B1": "Chi de mot system trung tam trong business context.",
    "B2": "Dat ten cho flow va noi flow giua system va external.",
    "B3": "Bao dam moi external co it nhat mot flow.",
    "L1": "Doi text ve tieng Anh hoac dat lang explicit neu co chu co dau.",
}


def code_of(message):
    return str(message).split(" ", 1)[0] if message else "UNKNOWN"


def source_tokens(message):
    out = []
    for raw in re.findall(r"\[([^\]]+)\]", message):
        for token in re.split(r"\s*<>\s*|,\s*", raw):
            token = token.strip()
            if token and token not in out and token.lower() not in {"default"}:
                out.append(token)
    return out


def build_plan(specs):
    errors, warnings, infos = check(specs)
    model = build_model(specs)
    items = []
    for severity, messages in (("error", errors), ("warning", warnings), ("info", infos)):
        for message in messages:
            code = code_of(message)
            items.append({
                "id": "%s-%d" % (code, len(items) + 1),
                "rule": code,
                "severity": severity,
                "message": message,
                "action": RULE_ACTIONS.get(code, "Kiem tra spec va dong bo semantic model."),
                "sources": source_tokens(message),
            })

    # Impact map theo source: gom cac canonical concept nam trong cac spec bi anh huong.
    source_to_nodes = defaultdict(set)
    for nid, node in model["nodes"].items():
        for src in node.get("sources", []):
            source_to_nodes[src].add(nid)
    for item in items:
        affected = set()
        for src in item["sources"]:
            affected.update(source_to_nodes.get(src, set()))
        item["affectedNodeIds"] = sorted(affected)
        item["regenerateSources"] = sorted(set(item["sources"]))

    return {
        "schemaVersion": 1,
        "kind": "comet-repair-plan",
        "modelFingerprint": model["fingerprint"],
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "infos": len(infos),
            "steps": len(items),
        },
        "steps": items,
    }


def main():
    ap = argparse.ArgumentParser(description="Xuat repair plan machine-readable cho bo COMET")
    ap.add_argument("specs", nargs="+")
    ap.add_argument("-o", "--output", help="ghi JSON plan vao file")
    a = ap.parse_args()
    plan = build_plan(load(a.specs))
    text = json.dumps(plan, ensure_ascii=False, indent=2)
    if a.output:
        Path(a.output).parent.mkdir(parents=True, exist_ok=True)
        Path(a.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()