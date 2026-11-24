#!/usr/bin/env python3
"""Скан хибних спрацювань looks_like_html() на всіх текстах архіву (без мережі, нічого не змінює).

Автор: В'ячеслав Плескач.

Використання: python scan_html_fp.py <корінь архіву> [--sync <шлях до sync_api_v4_1.py>] [--out <json>]
Код виходу: 0 — жодного тексту не визнано HTML; 1 — є спрацювання (перелік у звіті).
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--sync", type=Path, default=Path(__file__).resolve().parents[2] / "skrypty" / "sync_api_v4_1.py")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    spec = importlib.util.spec_from_file_location("sync_api_v4_1", a.sync)
    S = importlib.util.module_from_spec(spec)
    sys.modules["sync_api_v4_1"] = S
    spec.loader.exec_module(S)
    files = sorted((a.root / "akty").glob("*/red/*.txt"))
    hits, with_lt, chars = [], 0, 0
    for f in files:
        data = f.read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")
        _, body = S.split_text_file(data)
        chars += len(body)
        if "<" in body:
            with_lt += 1
        if S.looks_like_html(body):
            hits.append(f.relative_to(a.root).as_posix())
    rep = {"version": S.VERSION, "files": len(files), "chars": chars, "files_with_lt": with_lt,
           "html_detected": len(hits), "hits": hits[:200]}
    print(json.dumps({k: v for k, v in rep.items() if k != "hits"}, ensure_ascii=False))
    for h in hits[:50]:
        print("  HTML?", h)
    if a.out:
        a.out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
