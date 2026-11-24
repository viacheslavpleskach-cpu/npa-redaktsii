#!/usr/bin/env python3
"""Повне оновлення архіву npa-redaktsii через API data.rada.gov.ua на ПК власника (Україна).

Автор: В'ячеслав Плескач.

1. Робочий архів — Downloads\\npa-arkhiv. Якщо його немає, створюється з GitHub (zip останнього
   commit main, кілька сотень МБ). Якщо є (позначка .npa_arkhiv.json) — використовується наявний,
   скрипти й тести оновлюються з того самого commit GitHub.
2. Версія синхронізатора, офлайн-тести.
3. Хеші всіх файлів akty/ і dani/ → sync --all → verify → status → npa.py akty.
4. Змінені й нові файли даних копіюються в Downloads\\out_v41\\full\\zmineni\\ (зі збереженням шляхів)
   разом із manifest.json — їх Claude забирає й надсилає в репозиторій як дані.
5. Автоперевірка умов успіху → checks.json; код 1, якщо хоч одна умова порушена.

Запити до порталу — лише data.rada.gov.ua (User-Agent: OpenData, паузи 5–7 с, бюджет 150 MiB/добу;
очікувано ~35 MiB). До GitHub — лише читання. Push сценарій не робить.
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
BASE = HERE.parent                      # Downloads
ARCH = BASE / "npa-arkhiv"
MARK = ARCH / ".npa_arkhiv.json"
OUT = BASE / "out_v41" / "full"
OWNER_REPO = "viacheslavpleskach-cpu/npa-redaktsii"
API = f"https://api.github.com/repos/{OWNER_REPO}/"
RAW_ROOT = f"https://raw.githubusercontent.com/{OWNER_REPO}/"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
STEPS = []
DATA_DIRS = ("akty", "dani")

sys.path.insert(0, str(HERE))
import live_v41  # noqa: E402  (ensure_requests)


def get(url: str, dst: Path | None = None):
    req = urllib.request.Request(url, headers={"User-Agent": "npa-redaktsii-full-sync"})
    with urllib.request.urlopen(req, timeout=300) as r:
        if dst is None:
            return r.read()
        with dst.open("wb") as f:
            shutil.copyfileobj(r, f, length=1 << 20)
    return None


def fetch_dir(sha: str, rel: str) -> None:
    for it in json.loads(get(API + "contents/" + rel + "?ref=" + sha)):
        if it["type"] == "dir":
            fetch_dir(sha, it["path"])
        elif it["type"] == "file":
            dst = ARCH / it["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(get(RAW_ROOT + sha + "/" + it["path"]))


def prepare(info) -> None:
    sha = json.loads(get(API + "commits/main"))["sha"]
    info["commit"] = sha
    if ARCH.exists() and MARK.exists():
        info["arkhiv"] = "наявний Downloads\\npa-arkhiv; скрипти й тести оновлено з GitHub"
        for rel in ("skrypty", "tests"):
            shutil.rmtree(ARCH / rel, ignore_errors=True)
            fetch_dir(sha, rel)
        return
    if ARCH.exists():
        raise SystemExit(f"{ARCH} існує, але без позначки .npa_arkhiv.json — перейменуйте або видаліть теку й запустіть знову.")
    tmp = BASE / "npa-redaktsii-full.zip"
    print(f"Завантажую архів з GitHub (commit {sha[:7]}, кілька сотень МБ; кілька хвилин)…")
    get(f"https://codeload.github.com/{OWNER_REPO}/zip/{sha}", tmp)
    print("Розпаковую…")
    with zipfile.ZipFile(tmp) as zf:
        top = zf.namelist()[0].split("/")[0]
        zf.extractall(BASE)
    (BASE / top).rename(ARCH)
    tmp.unlink()
    MARK.write_text(json.dumps({"created": dt.datetime.now().isoformat(timespec="seconds"), "commit": sha},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    info["arkhiv"] = f"створено з GitHub zip {sha[:7]}"


def run(name, args, cwd=None, timeout=4 * 3600):
    started = time.time()
    log = OUT / f"{len(STEPS) + 1:02d}_{name}.txt"
    with log.open("w", encoding="utf-8") as f:
        f.write(f"$ {' '.join(map(str, args))}\n\n")
        f.flush()
        try:
            code = subprocess.run([str(a) for a in args], cwd=cwd or ARCH, stdout=f, stderr=subprocess.STDOUT,
                                  env=ENV, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            code = "TIMEOUT"
        f.write(f"\n>> exit={code}\n")
    STEPS.append({"step": name, "cmd": " ".join(map(str, args)), "exit": code,
                  "seconds": int(time.time() - started), "log": log.name})
    print(f"[{len(STEPS):02d}] {name}: exit={code} ({STEPS[-1]['seconds']} с)")
    return code, log.read_text(encoding="utf-8")


def sync(*a):
    return [sys.executable, ARCH / "skrypty" / "sync_api_v4_1.py", "--root", ARCH,
            "--request-log", OUT / "http_requests.jsonl", *a]


def snapshot() -> dict:
    res = {}
    for d in DATA_DIRS:
        for p in (ARCH / d).rglob("*"):
            if p.is_file():
                res[p.relative_to(ARCH).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return res


def main():
    live_v41.ensure_requests()
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(OUT / "zmineni", ignore_errors=True)
    for old in OUT.iterdir():
        if old.is_file():
            old.unlink()
    info = {"started": dt.datetime.now().isoformat(timespec="seconds"), "python": sys.version,
            "platform": platform.platform()}
    prepare(info)
    checks = {}
    c, out = run("version", [sys.executable, "-c",
                             "import sys; sys.path.insert(0, r'%s'); import sync_api_v4_1 as s; print(s.VERSION)"
                             % (ARCH / "skrypty")])
    checks["1_version_4_1_7"] = "4.1.7" in out
    c, out = run("offline_tests", [sys.executable, "-m", "unittest", "discover", "-s", ARCH / "tests", "-p", "test_*.py"],
                 cwd=ARCH / "tests")
    checks["2_offline_tests_ok"] = c == 0 and "\nOK" in out
    print("Рахую контрольні суми файлів даних…")
    before = snapshot()
    info["files_before"] = len(before)
    c, out = run("sync_all", sync("sync", "--all"))
    checks["3_sync_all_ok"] = c == 0
    c, out = run("verify", sync("verify", "--json", OUT / "verify.json"))
    v = json.loads((OUT / "verify.json").read_text(encoding="utf-8")) if (OUT / "verify.json").exists() else {}
    tot = v.get("total") or {}
    checks["4_verify_ok"] = c == 0 and tot.get("corrupt", 1) == 0 and tot.get("date_mismatch", 1) == 0
    info["verify_total"] = tot
    run("status", sync("status", "--out", OUT / "status.md"))
    c, _ = run("npa_akty", [sys.executable, ARCH / "skrypty" / "npa.py", "akty"])
    checks["5_npa_akty_ok"] = c == 0
    after = snapshot()
    changed = sorted(k for k in after if before.get(k) != after[k])
    deleted = sorted(k for k in before if k not in after)
    checks["6_no_deleted_files"] = not deleted
    zm = OUT / "zmineni"
    for rel in changed:
        dst = zm / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ARCH / rel, dst)
    unresolved = {}
    for card in (ARCH / "akty").glob("*/kartka.json"):
        try:
            api = json.loads(card.read_text(encoding="utf-8")).get("api") or {}
        except ValueError:
            continue
        if api.get("unresolved_edition_ids"):
            unresolved[card.parent.name] = api["unresolved_edition_ids"]
    manifest = {"commit": info["commit"], "changed": [{"path": k, "sha256": after[k], "new": k not in before}
                                                      for k in changed],
                "deleted": deleted, "unresolved_edition_ids": unresolved}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    info["changed"] = len(changed)
    info["new"] = sum(1 for k in changed if k not in before)
    info["unresolved"] = unresolved
    info["finished"] = dt.datetime.now().isoformat(timespec="seconds")
    ok = all(checks.values())
    (OUT / "checks.json").write_text(json.dumps({"ok": ok, "checks": checks}, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    (OUT / "env.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "steps.json").write_text(json.dumps(STEPS, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nУмови успіху:")
    for k, val in checks.items():
        print(f"  {'OK ' if val else 'НІ '} {k}")
    print(f"\nЗмінено файлів даних: {len(changed)} (нових {info['new']}); невирішені аномалії: {unresolved or 'немає'}")
    print(f"Результати: {OUT}")
    if not ok:
        print("ПЕРЕВІРКА НЕ ПРОЙДЕНА: див. checks.json і журнали кроків.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
