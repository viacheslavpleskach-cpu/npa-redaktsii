#!/usr/bin/env python3
"""Коротка жива перевірка sync_api v4.1.5 на наявній копії kopiia_v41 (мережа України).

Автор: В'ячеслав Плескач.

Кроки (аудити v4.1.2 і v4.1.3): офлайн-тести; версія; скан хибних спрацювань HTML-евристики на всіх текстах копії;
probe (КАС 20230323, 2343-12 20191021, КАС 30000101); sync --changed двічі поспіль (другий має бути no-op);
verify; status; хеш картки 2343-12 безпосередньо до і після anomaly 2343-12 / 201301186 БЕЗ --record.
Наприкінці — check_live_results.py: якщо хоч одна умова успіху порушена, сценарій завершується з кодом 1.
Працює лише на копії kopiia_v41 (поруч із текою пакета; якщо її немає — створює з GitHub, як live_v41.py).
Основний репозиторій і GitHub не змінюються. Запити — лише data.rada.gov.ua, User-Agent: OpenData,
паузи 5–7 с, бюджет 150 MiB/добу. Очікуваний трафік — до ~10 МБ.

Результат: out_v41/v415/ (зокрема checks.json) і rezultaty_v415.zip поруч із текою пакета.
"""
import datetime as dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent.parent
BASE = PKG.parent
COPY = BASE / "kopiia_v41"
OUT = BASE / "out_v41" / "v415"   # підтека вже наданої Claude теки out_v41
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
STEPS = []

sys.path.insert(0, str(HERE))
import live_v41  # noqa: E402  (ensure_requests, fetch_fresh_copy, _is_archive)


def run(name, args, cwd=None, timeout=3600):
    started = time.time()
    log = OUT / f"{len(STEPS) + 1:02d}_{name}.txt"
    with log.open("w", encoding="utf-8") as f:
        f.write(f"$ {' '.join(map(str, args))}\n\n")
        f.flush()
        try:
            code = subprocess.run([str(a) for a in args], cwd=cwd or COPY, stdout=f, stderr=subprocess.STDOUT,
                                  env=ENV, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            code = "TIMEOUT"
        f.write(f"\n>> exit={code}\n")
    STEPS.append({"step": name, "cmd": " ".join(map(str, args)), "exit": code,
                  "seconds": int(time.time() - started), "log": log.name})
    print(f"[{len(STEPS):02d}] {name}: exit={code} ({STEPS[-1]['seconds']} с)")
    return code


def sync(*a):
    return [sys.executable, COPY / "skrypty" / "sync_api_v4_1.py", "--root", COPY,
            "--request-log", OUT / "http_requests.jsonl", *a]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""


def main():
    live_v41.ensure_requests()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.iterdir():
        old.unlink()
    info = {"started": dt.datetime.now().isoformat(timespec="seconds"), "python": sys.version,
            "platform": platform.platform()}
    if not (COPY.exists() and live_v41._is_archive(COPY)):
        shutil.rmtree(COPY, ignore_errors=True)
        live_v41.COPY, live_v41.BASE = COPY, BASE
        live_v41.fetch_fresh_copy(info)
        info["note"] = "kopiia_v41 не було — створено свіжу копію з GitHub (картки ще не v4.1)"
    else:
        info["copied_from"] = "наявна kopiia_v41 (після живого sync --all v4.1 від 23.11.2026)"
    shutil.copy2(PKG / "skrypty" / "sync_api_v4_1.py", COPY / "skrypty" / "sync_api_v4_1.py")
    card = COPY / "akty" / "2343-12" / "kartka.json"

    run("offline_tests", [sys.executable, "-m", "unittest", "discover", "-s", PKG / "tests", "-p", "test_*.py"],
        cwd=PKG / "tests")
    run("version", [sys.executable, "-c", "import sys; sys.path.insert(0, r'%s'); import sync_api_v4_1 as s; print(s.VERSION)"
                    % (COPY / "skrypty")])
    run("scan_html_fp", [sys.executable, HERE / "scan_html_fp.py", COPY, "--sync", COPY / "skrypty" / "sync_api_v4_1.py",
                         "--out", OUT / "scan_html_fp.json"])
    run("probe_2747-15_20230323", sync("probe", "--nreg", "2747-15", "--ed", "20230323"))
    run("probe_2343-12_20191021", sync("probe", "--nreg", "2343-12", "--ed", "20191021"))
    run("probe_2747-15_30000101", sync("probe", "--nreg", "2747-15", "--ed", "30000101"))
    run("sync_changed_1", sync("sync", "--changed"))
    run("sync_changed_2_noop", sync("sync", "--changed"))
    run("verify", sync("verify", "--json", OUT / "verify.json"))
    run("status", sync("status", "--out", OUT / "status.md"))
    # Хеш картки — безпосередньо перед anomaly (sync --changed вище може законно її оновити).
    info["kartka_2343_12_sha_before"] = sha(card)
    info["kartka_2343_12_mtime_ns_before"] = card.stat().st_mtime_ns if card.exists() else None
    run("anomaly_2343-12_no_record", sync("anomaly", "--nreg", "2343-12", "--raw", "201301186"))
    info["kartka_2343_12_sha_after"] = sha(card)
    info["kartka_2343_12_mtime_ns_after"] = card.stat().st_mtime_ns if card.exists() else None
    info["kartka_2343_12_unchanged"] = info["kartka_2343_12_sha_before"] == info["kartka_2343_12_sha_after"]
    print(f"[--] kartka 2343-12 незмінна після anomaly без --record: {info['kartka_2343_12_unchanged']}")

    for rel in ("dani/manual_only.json", "dani/perevirka.json", "akty/2343-12/kartka.json", ".npa_cache/state.json"):
        p = COPY / rel
        if p.exists():
            shutil.copy2(p, OUT / rel.replace("/", "__"))
    info["finished"] = dt.datetime.now().isoformat(timespec="seconds")
    (OUT / "env.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "steps.json").write_text(json.dumps(STEPS, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.path.insert(0, str(COPY / "skrypty"))
    import importlib
    expected = importlib.import_module("sync_api_v4_1").VERSION
    check_rc = subprocess.run([sys.executable, str(HERE / "check_live_results.py"), str(OUT), "--expect-version", expected],
                              env=ENV).returncode
    z = BASE / "rezultaty_v415.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in OUT.iterdir():
            zf.write(p, p.name)
    print(f"\nГотово. Результати: {OUT} і {z}")
    if check_rc != 0:
        print("ЖИВА ПЕРЕВІРКА НЕ ПРОЙДЕНА: порушено умови успіху (див. checks.json).")
    return check_rc


if __name__ == "__main__":
    sys.exit(main())
