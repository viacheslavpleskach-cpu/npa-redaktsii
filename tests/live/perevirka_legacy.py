#!/usr/bin/env python3
"""Перевірка й заміна старих текстів браузерного імпорту (legacy_unverified) текстами API.

Автор: В'ячеслав Плескач.

Запуск щодня (порція в межах денного бюджету 150 MiB); кожен наступний запуск продовжує з місця
зупинки, бо замінені тексти вже мають статус verified.

1. Знаходить робочий архів (позначка .npa_arkhiv.json): змінна NPA_ARKHIV, тека поруч із цим
   скриптом, Documents\\npa_full\\npa-arkhiv, Downloads\\npa_full\\npa-arkhiv, Downloads\\npa-arkhiv, %USERPROFILE%\\npa-arkhiv.
2. Оновлює з GitHub (main) скрипти, усі kartka.json і тексти редакцій із позначкою api_text_issue
   (у репозиторії для них залишено текст браузерного імпорту) — щоб робоча копія збігалася з репозиторієм.
3. Видаляє 4 застарілі bez_redaktsii.txt (995_j67, 2201-20, 3604-20, v0011740-14) — їх замінено
   датованими текстами; у репозиторії вони вже видалені.
4. Для актів у порядку perelik_aktiv.csv (найчастіше цитовані — першими):
   verify --nreg <акт> --repair --include-legacy. Кожен текст завантажується з API, перевіряється
   DocumentDate; старий файл замінюється перевіреним (SHA-256) лише за збігу змісту й без втрати
   верхніх індексів (v4.1.8), інакше лишається з позначкою api_text_issue. Зупинка — за бюджетом.
5. Змінені файли → out_v41\\legacy\\zmineni.zip + manifest.json; підсумок verify → verify.json.

Запити — лише data.rada.gov.ua (User-Agent: OpenData, паузи 5–7 с). Push сценарій не робить.
"""
import csv
import datetime as dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import re
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
OLD_COPIES = ["995_j67", "2201-20", "3604-20", "v0011740-14"]
STEPS = []


def find_archive() -> Path:
    home = Path.home()
    cands = [os.environ.get("NPA_ARKHIV")] if os.environ.get("NPA_ARKHIV") else []
    cands += [HERE.parent / "npa-arkhiv", HERE.parent.parent / "npa-arkhiv",
              home / "Documents" / "npa_full" / "npa-arkhiv",
              home / "Downloads" / "npa_full" / "npa-arkhiv", home / "Downloads" / "npa-arkhiv",
              home / "npa-arkhiv"]
    for c in cands:
        p = Path(c)
        if (p / ".npa_arkhiv.json").exists() and (p / "skrypty" / "sync_api_v4_1.py").exists():
            return p
    raise SystemExit("Не знайдено робочий архів npa-arkhiv (з позначкою .npa_arkhiv.json). "
                     "Вкажіть шлях: set NPA_ARKHIV=<тека> і запустіть знову.")


ARCH = find_archive()
OUT = ARCH.parent / "out_v41" / "legacy"


OWNER_REPO = "viacheslavpleskach-cpu/npa-redaktsii"
GH_API = f"https://api.github.com/repos/{OWNER_REPO}/"
GH_RAW = f"https://raw.githubusercontent.com/{OWNER_REPO}/"


def gh_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "npa-redaktsii-legacy"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def pull_from_github(info) -> None:
    """Скрипти, картки і тексти з api_text_issue — з останнього commit main (лише читання)."""
    sha = json.loads(gh_get(GH_API + "commits/main"))["sha"]
    info["github_commit"] = sha
    for it in json.loads(gh_get(GH_API + "contents/skrypty?ref=" + sha)):
        if it["type"] == "file":
            (ARCH / it["path"]).write_bytes(gh_get(GH_RAW + sha + "/" + it["path"]))
    restored = []
    for d in sorted((ARCH / "akty").iterdir()):
        if not d.is_dir():
            continue
        rel = f"akty/{d.name}/kartka.json"
        try:
            data = gh_get(GH_RAW + sha + "/" + urllib.request.quote(rel))
        except Exception as exc:  # noqa: BLE001 — акт може бути відсутній у репозиторії
            print(f"  {rel}: не отримано з GitHub ({exc}); залишено локальну")
            continue
        (ARCH / rel).write_bytes(data)
        for e in json.loads(data.decode("utf-8")).get("redaktsii", []):
            if e.get("api_text_issue") and e.get("text_status") != "verified":
                trel = f"akty/{d.name}/red/{e['ed']}.txt"
                (ARCH / trel).write_bytes(gh_get(GH_RAW + sha + "/" + urllib.request.quote(trel)))
                restored.append(trel)
    info["restored_from_github"] = restored
    print(f"З GitHub ({sha[:7]}): скрипти, картки; повернуто текстів браузерного імпорту: {len(restored)}")


def run(name, args, timeout=6 * 3600):
    started = time.time()
    log = OUT / f"{len(STEPS) + 1:03d}_{name}.txt"
    with log.open("w", encoding="utf-8") as f:
        f.write(f"$ {' '.join(map(str, args))}\n\n")
        f.flush()
        try:
            code = subprocess.run([str(a) for a in args], cwd=ARCH, stdout=f, stderr=subprocess.STDOUT,
                                  env=ENV, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            code = "TIMEOUT"
        f.write(f"\n>> exit={code}\n")
    STEPS.append({"step": name, "exit": code, "seconds": int(time.time() - started), "log": log.name})
    print(f"[{len(STEPS):03d}] {name}: exit={code} ({STEPS[-1]['seconds']} с)")
    return code, log.read_text(encoding="utf-8")


def sync(*a):
    return [sys.executable, ARCH / "skrypty" / "sync_api_v4_1.py", "--root", ARCH,
            "--request-log", OUT / f"http_{len(STEPS) + 1:03d}.jsonl", *a]


def snapshot() -> dict:
    res = {}
    for d in ("akty", "dani"):
        for p in (ARCH / d).rglob("*"):
            if p.is_file():
                res[p.relative_to(ARCH).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return res


def acts_in_order() -> list[str]:
    manual = set()
    mo = ARCH / "dani" / "manual_only.json"
    if mo.exists():
        try:
            data = json.loads(mo.read_text(encoding="utf-8"))
            manual = set(data.get("akty", data) if isinstance(data, dict) else data)
        except ValueError:
            pass
    rows = list(csv.DictReader((ARCH / "perelik_aktiv.csv").open(encoding="utf-8"), delimiter=";"))
    return [r["nreg"] for r in rows if r.get("nreg") and r.get("rezhym") != "nemaie" and r["nreg"] not in manual]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.iterdir():
        if old.is_file():
            old.unlink()
    info = {"started": dt.datetime.now().isoformat(timespec="seconds"), "arkhiv": str(ARCH),
            "python": sys.version, "platform": platform.platform()}
    print(f"Архів: {ARCH}")
    pull_from_github(info)
    c, out = run("version", [sys.executable, "-c",
                             "import sys; sys.path.insert(0, r'%s'); import sync_api_v4_1 as s; print(s.VERSION)"
                             % (ARCH / "skrypty")])
    if not re.search(r"4\.1\.(8|9)|4\.[2-9]", out):
        raise SystemExit("Очікувалася версія синхронізатора 4.1.8 або новіша — див. 001_version.txt")
    before = snapshot()
    removed = []
    for a in OLD_COPIES:
        p = ARCH / "akty" / a / "red" / "bez_redaktsii.txt"
        if p.exists():
            p.unlink()
            removed.append(p.relative_to(ARCH).as_posix())
    info["removed_old_copies"] = removed
    stopped = ""
    done_acts = []
    for nreg in acts_in_order():
        c, out = run(f"repair_{nreg.replace('/', '_')}",
                     sync("verify", "--nreg", nreg, "--repair", "--include-legacy"))
        done_acts.append({"nreg": nreg, "exit": c,
                          "fixed": out.count("→ verified)"), "kept": out.count("залишено старий текст"),
                          "failed": out.count("НЕ відновлено")})
        if "ЗУПИНКА ЗА БЮДЖЕТОМ" in out:
            stopped = f"бюджет трафіку (на акті {nreg})"
            break
        if "(зупинка: HTTP" in out or "HTTP 429" in out:
            stopped = f"портал обмежив доступ (на акті {nreg})"
            break
    info["stopped"] = stopped or "усі акти оброблено"
    run("verify_all", sync("verify", "--json", OUT / "verify.json"))
    v = json.loads((OUT / "verify.json").read_text(encoding="utf-8")) if (OUT / "verify.json").exists() else {}
    info["verify_total"] = v.get("total")
    after = snapshot()
    changed = sorted(k for k in after if before.get(k) != after[k])
    deleted = sorted(k for k in before if k not in after)
    with zipfile.ZipFile(OUT / "zmineni.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in changed:
            zf.write(ARCH / rel, rel)
    manifest = {"changed": [{"path": k, "sha256": after[k], "new": k not in before} for k in changed],
                "deleted": deleted, "acts": done_acts, "stopped": info["stopped"]}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    checks = {
        "1_only_expected_deletions": set(deleted) <= set(removed),
        "2_no_corrupt_or_date_mismatch": bool(v) and (v.get("total") or {}).get("corrupt", 1) == 0
                                         and (v.get("total") or {}).get("date_mismatch", 1) == 0,
        "3_no_failed_repairs": all(a["failed"] == 0 for a in done_acts),
    }
    info["changed_files"] = len(changed)
    info["fixed_texts"] = sum(a["fixed"] for a in done_acts)
    info["kept_old_texts"] = sum(a["kept"] for a in done_acts)
    info["finished"] = dt.datetime.now().isoformat(timespec="seconds")
    (OUT / "checks.json").write_text(json.dumps({"ok": all(checks.values()), "checks": checks},
                                                ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "env.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "steps.json").write_text(json.dumps(STEPS, ensure_ascii=False, indent=1), encoding="utf-8")
    tot = v.get("total") or {}
    print(f"\nЗамінено текстів: {info['fixed_texts']}; залишено старих (текст API неточний): "
          f"{info['kept_old_texts']}; зупинка: {info['stopped']}")
    print(f"Залишилось legacy_unverified: {tot.get('legacy_unverified')}; verified: {tot.get('verified')}")
    for k, val in checks.items():
        print(f"  {'OK ' if val else 'НІ '} {k}")
    print(f"Результати: {OUT}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
