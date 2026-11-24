#!/usr/bin/env python3
"""Жива перевірка v4.1.7 і виправлення 2343-12 (окрема редакція 18.01.2013) на ПК в Україні.

Автор: В'ячеслав Плескач.

Що робить:
1. Створює мінімальну робочу копію kopiia_v417 з GitHub (main): perelik_aktiv.csv, skrypty/,
   tests/ і лише akty/2343-12 (картка й тексти; ~25 МБ). Повний архів не завантажується.
2. Офлайн-тести; версія синхронізатора (очікується 4.1.7).
3. anomaly --record-separate: ed201301186 → окрема редакція «Нова редакція, підстава - 4212-VI»
   перед ed20130118 (звірено з карткою сайту 24.11.2026).
4. pravka: підпис ed20130118 → «Редакція, підстава - 5405-VI, 5410-VI, 5518-VI».
5. sync --nreg 2343-12 (перерахунок повноти каталогу), verify, status.
6. npa.py: редакції й статті 1 на 17.01, 18.01 і 19.01.2013.
7. Автоперевірка умов успіху → checks.json; код 1, якщо хоч одна умова порушена.

Запити до порталу — лише data.rada.gov.ua, User-Agent: OpenData, паузи 5–7 с; очікуваний трафік —
кілька МБ. До GitHub — лише читання публічного репозиторію. Push сценарій не робить.
Результат: Downloads\\out_v41\\v417 і rezultaty_v417.zip.
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
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
COPY = BASE / "kopiia_v417"
OUT = BASE / "out_v41" / "v417"
NREG = "2343-12"
OWNER_REPO = "viacheslavpleskach-cpu/npa-redaktsii"
RAW = f"https://raw.githubusercontent.com/{OWNER_REPO}/main/"
API = f"https://api.github.com/repos/{OWNER_REPO}/contents/"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
STEPS = []

sys.path.insert(0, str(HERE))
import live_v41  # noqa: E402  (ensure_requests)


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "npa-redaktsii-live-v417"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def fetch_dir(rel: str) -> None:
    """Завантажує всі файли теки репозиторію (через GitHub contents API) у COPY/rel."""
    items = json.loads(get(API + rel + "?ref=main"))
    for it in items:
        if it["type"] == "dir":
            fetch_dir(it["path"])
        elif it["type"] == "file":
            dst = COPY / it["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(get(RAW + it["path"]))


def make_copy(info) -> None:
    shutil.rmtree(COPY, ignore_errors=True)
    COPY.mkdir(parents=True)
    print(f"Створюю робочу копію {COPY} з GitHub (лише {NREG}, скрипти й тести)…")
    for rel in ("perelik_aktiv.csv", "README.md"):
        (COPY / rel).write_bytes(get(RAW + rel))
    for rel in ("skrypty", "tests", f"akty/{NREG}"):
        fetch_dir(rel)
    (COPY / "dani").mkdir(exist_ok=True)
    info["copied_from"] = f"GitHub {OWNER_REPO}@main: perelik, skrypty, tests, akty/{NREG}"
    info["texts_2343_12"] = len(list((COPY / "akty" / NREG / "red").glob("*.txt")))


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
    return code, log.read_text(encoding="utf-8")


def sync(*a):
    return [sys.executable, COPY / "skrypty" / "sync_api_v4_1.py", "--root", COPY,
            "--request-log", OUT / "http_requests.jsonl", *a]


def npa(*a):
    return [sys.executable, COPY / "skrypty" / "npa.py", *a]


def body_sha(p: Path) -> str:
    data = p.read_bytes().decode("utf-8").replace("\r\n", "\n")
    lines = data.split("\n")
    k = 0
    while k < len(lines) and lines[k].startswith("# "):
        k += 1
    return hashlib.sha256("\n".join(lines[k:]).encode("utf-8")).hexdigest()


def main():
    live_v41.ensure_requests()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.iterdir():
        if old.is_file():
            old.unlink()
    info = {"started": dt.datetime.now().isoformat(timespec="seconds"), "python": sys.version,
            "platform": platform.platform()}
    make_copy(info)
    red = COPY / "akty" / NREG / "red"
    card_path = COPY / "akty" / NREG / "kartka.json"
    info["body_sha_20130118_before"] = body_sha(red / "20130118.txt")
    for rel in ("kartka.json", "red/20130118.txt"):
        shutil.copy2(COPY / "akty" / NREG / rel, OUT / ("before__" + rel.replace("/", "__")))

    checks = {}
    c, out = run("offline_tests", [sys.executable, "-m", "unittest", "discover", "-s", COPY / "tests", "-p", "test_*.py"],
                 cwd=COPY / "tests")
    checks["1_offline_tests_ok"] = c == 0 and "\nOK" in out
    c, out = run("version", [sys.executable, "-c",
                             "import sys; sys.path.insert(0, r'%s'); import sync_api_v4_1 as s; print(s.VERSION)"
                             % (COPY / "skrypty")])
    checks["2_version_4_1_7"] = "4.1.7" in out
    run("npa_redaktsii_before", npa("redaktsii", NREG))
    c, out = run("anomaly_record_separate", sync("anomaly", "--nreg", NREG, "--raw", "201301186",
                                                 "--record-separate", "--order", "before",
                                                 "--opys", "Нова редакція", "--pidstava", "4212-VI"))
    checks["3_anomaly_recorded"] = c == 0 and "Окрему редакцію записано" in out and (red / "201301186.txt").exists()
    c, out = run("pravka_20130118", sync("pravka", "--nreg", NREG, "--ed", "20130118", "--opys", "Редакція",
                                         "--pidstava", "5405-VI, 5410-VI, 5518-VI",
                                         "--prychyna", "звірено з карткою zakon.rada.gov.ua/laws/card/2343-12 24.11.2026"))
    checks["4_pravka_ok"] = c == 0
    info["body_sha_20130118_after"] = body_sha(red / "20130118.txt")
    checks["5_body_20130118_unchanged"] = info["body_sha_20130118_before"] == info["body_sha_20130118_after"]
    c, out = run("sync_nreg_2343-12", sync("sync", "--nreg", NREG))
    checks["6_sync_ok"] = c == 0
    card = json.loads(card_path.read_text(encoding="utf-8"))
    api = card.get("api") or {}
    eds = [x["ed"] for x in card.get("redaktsii", [])]
    checks["7_catalog_complete"] = (api.get("edition_catalog_complete") is True
                                    and not api.get("unresolved_edition_ids"))
    i = eds.index("201301186") if "201301186" in eds else -1
    checks["8_order_in_day"] = i >= 0 and i + 1 < len(eds) and eds[i + 1] == "20130118"
    e18 = next((x for x in card["redaktsii"] if x["ed"] == "20130118"), {})
    e186 = next((x for x in card["redaktsii"] if x["ed"] == "201301186"), {})
    checks["9_labels"] = (e18.get("pidstava") == ["5405-VI", "5410-VI", "5518-VI"]
                          and e186.get("pidstava") == ["4212-VI"] and e186.get("text_status") == "verified")
    c, out = run("verify_2343-12", sync("verify", "--nreg", NREG, "--json", OUT / "verify.json"))
    checks["10_verify_ok"] = c == 0
    run("status_2343-12", sync("status", "--nreg", NREG, "--out", OUT / "status.md"))
    run("npa_redaktsii_after", npa("redaktsii", NREG))
    _, o17 = run("npa_stattia1_17-01-2013", npa("stattia", NREG, "1", "--na", "17.01.2013"))
    _, o18 = run("npa_stattia1_18-01-2013", npa("stattia", NREG, "1", "--na", "18.01.2013"))
    _, o19 = run("npa_stattia1_19-01-2013", npa("stattia", NREG, "1", "--na", "19.01.2013"))
    checks["11_npa_17_01"] = "Редакція від 04.11.2012" in o17
    checks["12_npa_18_01"] = ("Редакція від 18.01.2013, Редакція, підстава - 5405-VI, 5410-VI, 5518-VI" in o18
                              and "набрали чинності 2 редакції" in o18 and "/ed20130118" in o18)
    checks["13_npa_19_01"] = "5405-VI, 5410-VI, 5518-VI" in o19 and "набрали чинності 2 редакції" not in o19

    for rel in ("kartka.json", "red/201301186.txt", "red/20130118.txt"):
        p = COPY / "akty" / NREG / rel
        if p.exists():
            shutil.copy2(p, OUT / ("after__" + rel.replace("/", "__")))
    info["finished"] = dt.datetime.now().isoformat(timespec="seconds")
    ok = all(checks.values())
    (OUT / "checks.json").write_text(json.dumps({"ok": ok, "checks": checks}, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    (OUT / "env.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "steps.json").write_text(json.dumps(STEPS, ensure_ascii=False, indent=1), encoding="utf-8")
    z = BASE / "rezultaty_v417.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in OUT.iterdir():
            zf.write(p, p.name)
    print("\nУмови успіху:")
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'НІ '} {k}")
    print(f"\nГотово. Результати: {OUT} і {z}")
    if not ok:
        print("ПЕРЕВІРКА НЕ ПРОЙДЕНА: див. checks.json і журнали кроків.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
