#!/usr/bin/env python3
"""Живі перевірки sync_api v4.1 на комп'ютері користувача (мережа України).

Автор: В'ячеслав Плескач.

Працює ЛИШЕ на копії архіву: знаходить тестову копію npa-redaktsii поруч (у теці, де лежить
ця тека), копіює її в kopiia_v41 і всі команди виконує там. Основний репозиторій і GitHub
не змінюються. Запити — лише до data.rada.gov.ua з User-Agent: OpenData, паузи 5–7 с,
локальний бюджет 150 MiB/добу.

Результат: rezultaty_v41.zip поруч із цією текою (журнали, коди виходу, звіти).
Запуск: run_v41.bat (або python live_v41.py).
"""
import datetime as dt
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
PKG = HERE.parent.parent if (HERE.parent.name == "tests") else HERE
BASE = PKG.parent                       # тека npa_probe
COPY = BASE / "kopiia_v41"
OUT = BASE / "out_v41"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
STEPS = []


def _is_archive(p: Path) -> bool:
    return (p / "perelik_aktiv.csv").exists() and (p / "akty").is_dir()


def find_test_copy():
    """Шукає повні копії архіву (perelik_aktiv.csv + akty/, ≥40 карток) поруч із пакетом, до глибини 4.

    Домашню теку й Google Диск не сканує. Копії з меншою кількістю карток не беруться.
    """
    roots = [(BASE, 4)]
    seen, cands = set(), []
    for root, depth in roots:
        stack = [(root, 0)]
        while stack:
            d, lvl = stack.pop()
            try:
                subs = [x for x in d.iterdir() if x.is_dir()]
            except OSError:
                continue
            for x in subs:
                if x in seen or x == COPY or x.name.startswith(".") or x == PKG:
                    continue
                seen.add(x)
                if _is_archive(x):
                    cards = list((x / "akty").glob("*/kartka.json"))
                    newest = max((c.stat().st_mtime for c in cards), default=0)
                    cands.append((newest, len(cards), x))
                elif lvl + 1 < depth and x.name not in ("akty", "red", "node_modules"):
                    stack.append((x, lvl + 1))
    cands = [c for c in cands if c[1] >= 40]
    cands.sort(reverse=True)   # найсвіжіші зміни карток першими
    return cands


REPO = "https://github.com/viacheslavpleskach-cpu/npa-redaktsii"
REPO_ZIP = "https://codeload.github.com/viacheslavpleskach-cpu/npa-redaktsii/zip/refs/heads/main"


def fetch_fresh_copy(info) -> None:
    """Тестової копії немає: свіжа копія публічного репозиторію з GitHub просто в kopiia_v41.

    Спершу git clone --depth 1 (якщо git є), інакше zip з codeload.github.com. Після клонування
    remote origin видаляється, щоб із тестової копії неможливо було випадково зробити push.
    Запити до порталу Ради тут не робляться.
    """
    import urllib.request
    git = shutil.which("git")
    if git:
        print(f"Тестової копії немає — клоную {REPO} у {COPY} (git, ~2 ГБ на диску; кілька хвилин)…")
        r = subprocess.run([git, "clone", "--depth", "1", REPO, str(COPY)], env=ENV)
        if r.returncode == 0:
            subprocess.run([git, "-C", str(COPY), "remote", "remove", "origin"], env=ENV)
            info["copied_from"] = f"git clone --depth 1 {REPO} (remote origin видалено)"
            return
        print("git clone не вдався; пробую zip…")
        shutil.rmtree(COPY, ignore_errors=True)
    tmp = BASE / "npa-redaktsii-main.zip"
    print(f"Тестової копії немає — завантажую {REPO_ZIP} (кілька сотень МБ; кілька хвилин)…")
    with urllib.request.urlopen(REPO_ZIP, timeout=120) as resp, tmp.open("wb") as f:
        shutil.copyfileobj(resp, f, length=1 << 20)
    print("Розпаковую…")
    with zipfile.ZipFile(tmp) as zf:
        top = zf.namelist()[0].split("/")[0]
        zf.extractall(BASE)
    (BASE / top).rename(COPY)
    tmp.unlink()
    info["copied_from"] = f"zip {REPO_ZIP}"


def show_tree():
    print(f"Вміст {BASE} (2 рівні):")
    for x in sorted(BASE.iterdir()):
        print("  " + x.name + ("/" if x.is_dir() else ""))
        if x.is_dir() and x != PKG:
            try:
                for y in sorted(x.iterdir())[:15]:
                    print("    " + y.name + ("/" if y.is_dir() else ""))
            except OSError:
                pass


def run(name, args, cwd=None, timeout=3600):
    started = time.time()
    log = OUT / f"{len(STEPS) + 1:02d}_{name}.txt"
    with log.open("w", encoding="utf-8") as f:
        f.write(f"$ {' '.join(map(str, args))}\n\n")
        f.flush()
        try:
            r = subprocess.run([str(a) for a in args], cwd=cwd or COPY, stdout=f, stderr=subprocess.STDOUT,
                               env=ENV, timeout=timeout)
            code = r.returncode
        except subprocess.TimeoutExpired:
            code = "TIMEOUT"
        f.write(f"\n>> exit={code}\n")
    sec = int(time.time() - started)
    STEPS.append({"step": name, "cmd": " ".join(map(str, args)), "exit": code, "seconds": sec, "log": log.name})
    print(f"[{len(STEPS):02d}] {name}: exit={code} ({sec} с)")
    return code


def sync(*a):
    return [sys.executable, COPY / "skrypty" / "sync_api_v4_1.py", "--root", COPY,
            "--request-log", OUT / "http_requests.jsonl", *a]


def npa(*a):
    return [sys.executable, COPY / "skrypty" / "npa.py", *a]


def doc_update_analysis():
    """Формат поля modified на живому doc-update (з кешу, без нового запиту)."""
    sys.path.insert(0, str(COPY / "skrypty"))
    import importlib
    mod = importlib.import_module("sync_api_v4_1")
    raw = (COPY / ".npa_cache" / "doc-update.txt").read_bytes()
    text = mod.decode_text(raw, preferred="cp1251")
    lines = text.splitlines()
    by, st = mod.parse_doc_update(raw)
    rows = {n: [l for l in lines if f"\t{n}\t" in l][:200] for n in ("2343-12", "2747-15", "1618-15", "5076-17")}
    rep = {
        "bytes": len(raw), "rows": st["rows"], "documents": st["documents"],
        "first_lines": lines[:8], "modified_samples": st["modified_samples"],
        "invalid_modified": st["invalid_modified"], "invalid_rows": st["invalid_rows"],
        "invalid_by_nreg_ours": {n: st["invalid_by_nreg"].get(n) for n in rows},
        "modified_by_nreg_ours": {n: st["modified_by_nreg"].get(n) for n in rows},
        "rows_ours": {n: v[-15:] for n, v in rows.items()},
        "rows_count_ours": {n: len(v) for n, v in rows.items()},
    }
    (OUT / "doc_update_analysis.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[--] doc-update проаналізовано: doc_update_analysis.json")


def ensure_requests():
    """sync_api потребує пакета requests; якщо його немає — ставить у профіль користувача (pip --user)."""
    try:
        import requests  # noqa: F401
        return
    except ImportError:
        pass
    print("Немає пакета requests — встановлюю: python -m pip install --user requests …")
    subprocess.run([sys.executable, "-m", "pip", "install", "--user", "requests"], env=ENV)
    r = subprocess.run([sys.executable, "-c", "import requests; print(requests.__version__)"],
                       capture_output=True, text=True, env=ENV)
    if r.returncode != 0:
        sys.exit("Не вдалося встановити requests. Виконайте вручну: python -m pip install --user requests "
                 "і запустіть run_v41.bat ще раз.")
    print(f"requests {r.stdout.strip()} встановлено.")
    import importlib
    import site
    # Тека user site могла з'явитися лише щойно: додаємо її до sys.path цього процесу.
    site.addsitedir(site.getusersitepackages())
    importlib.invalidate_caches()


def main():
    ensure_requests()
    OUT.mkdir(exist_ok=True)
    for old in OUT.iterdir():
        old.unlink()
    info = {"started": dt.datetime.now().isoformat(timespec="seconds"), "python": sys.version,
            "platform": platform.platform(), "windows": platform.win32_ver() if os.name == "nt" else None}
    cands = find_test_copy()
    info["candidates"] = [(dt.datetime.fromtimestamp(t).isoformat(timespec="seconds"), n, str(p)) for t, n, p in cands]
    explicit = Path(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].strip() else None
    if explicit and not _is_archive(explicit):
        sys.exit(f"У {explicit} немає perelik_aktiv.csv і теки akty.")
    for t, n, p in cands[:10]:
        print(f"  знайдено копію: {p} — карток {n}, остання зміна {dt.datetime.fromtimestamp(t):%d.%m.%Y %H:%M}")
    if not COPY.exists() or not _is_archive(COPY):
        shutil.rmtree(COPY, ignore_errors=True)
        if not cands and not explicit:
            try:
                fetch_fresh_copy(info)
            except Exception as exc:
                show_tree()
                sys.exit(f"Не вдалося отримати копію архіву з GitHub ({exc}). Вкажіть шлях: run_v41.bat \"шлях\"")
        else:
            src = explicit or cands[0][2]
            print(f"Копіюю тестову копію {src} → {COPY} (кілька хвилин)…")
            shutil.copytree(src, COPY)
            info["copied_from"] = str(src)
    else:
        info["copied_from"] = "kopiia_v41 уже існувала — використано її"
    (COPY / "skrypty").mkdir(exist_ok=True)
    if not (COPY / "skrypty" / "npa.py").exists():
        shutil.copy2(PKG / "tests" / "fixtures" / "npa.py", COPY / "skrypty" / "npa.py")
        info["npa_py"] = "у копії не було skrypty/npa.py — узято чинний npa.py з пакета"
    for f in ("sync_api_v4_1.py", "patch_npa_v4_1.py"):
        shutil.copy2(PKG / "skrypty" / f, COPY / "skrypty" / f)
    shutil.copy2(COPY / "skrypty" / "npa.py", OUT / "npa_original.py")
    (OUT / "env.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")

    # 0. Офлайн-тести на Windows
    run("offline_tests", [sys.executable, "-m", "unittest", "discover", "-s", PKG / "tests", "-p", "test_*.py"],
        cwd=PKG / "tests")
    # 1. probe основних актів
    run("probe_2747-15_20230323", sync("probe", "--nreg", "2747-15", "--ed", "20230323"))
    run("probe_5076-17_20250910", sync("probe", "--nreg", "5076-17", "--ed", "20250910"))
    run("probe_2343-12_20191021", sync("probe", "--nreg", "2343-12", "--ed", "20191021"))
    # 2. Умовні редакції
    for ed in ("30000101", "30000102", "30000103", "30000104"):
        run(f"probe_2747-15_{ed}", sync("probe", "--nreg", "2747-15", "--ed", ed))
    # 3. Контрольна синхронізація одного акта
    run("sync_nreg_1618-15", sync("sync", "--nreg", "1618-15"))
    # 4–5. Повна синхронізація копії і --changed одразу
    run("sync_all", sync("sync", "--all"))
    try:
        doc_update_analysis()
    except BaseException as exc:  # аналіз не повинен зупиняти решту
        print(f"[--] аналіз doc-update не вдався: {exc}")
    run("sync_changed", sync("sync", "--changed"))
    # 6. Аномалія 2343-12
    run("anomaly_2343-12", sync("anomaly", "--nreg", "2343-12", "--raw", "201301186", "--record"))
    run("sync_nreg_2343-12_after", sync("sync", "--nreg", "2343-12"))
    # 7. Аудит текстів і таблиця стану (без мережі)
    run("verify", sync("verify", "--json", OUT / "verify.json"))
    run("status", sync("status", "--out", OUT / "status.md"))
    # 8. npa.py до і після патча (на копії)
    checks = [("stattia", "КАС", "193", "--na", "01.03.2019"), ("stattia", "ЦПК", "189", "--na", "01.03.2019"),
              ("stattia", "5076-17", "6", "--na", "01.06.2024"), ("stattia", "2343-12", "1", "--na", "01.06.2015"),
              ("stattia", "2755-17", "1", "--na", "01.06.2024"), ("stattia", "2201-20", "1", "--na", "01.06.2024"),
              ("redaktsii", "КАС"), ("redaktsii", "2343-12"), ("porivniaty", "КАС", "193", "--z", "01.01.2019", "--po", "23.11.2026")]
    for i, c in enumerate(checks):
        run(f"npa_before_{i}", npa(*c))
    run("patch_npa", [sys.executable, COPY / "skrypty" / "patch_npa_v4_1.py"])
    for i, c in enumerate(checks):
        run(f"npa_after_{i}", npa(*c))

    for rel in ("dani/manual_only.json", "dani/perevirka.json", "akty/2343-12/kartka.json",
                "akty/2747-15/kartka.json", "akty/1618-15/kartka.json", ".npa_cache/state.json"):
        p = COPY / rel
        if p.exists():
            shutil.copy2(p, OUT / rel.replace("/", "__"))
    info["finished"] = dt.datetime.now().isoformat(timespec="seconds")
    (OUT / "env.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "steps.json").write_text(json.dumps(STEPS, ensure_ascii=False, indent=1), encoding="utf-8")
    z = BASE / "rezultaty_v41.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in OUT.iterdir():
            zf.write(p, p.name)
    print(f"\nГотово. Результати: {z}\nПрикріпіть цей файл у чат.")


if __name__ == "__main__":
    main()
