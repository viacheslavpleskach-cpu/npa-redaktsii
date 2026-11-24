#!/usr/bin/env python3
"""Автоматична перевірка умов успіху короткої живої перевірки (v4.1.5; посилено у v4.1.6).

Автор: В'ячеслав Плескач.

Використання: python check_live_results.py <тека з журналами> [--expect-version 4.1.5] [--out-json <файл>]
Пише checks.json у ту саму теку (або в --out-json, щоб не перезаписати журнал прогону). Код виходу: 0 — усі умови виконано; 1 — хоч одна порушена; 2 — бракує файлів.

Умови:
  0. (v4.1.6) кожен обов'язковий крок сценарію є в steps.json рівно один раз, його журнал існує, непорожній і
     закінчується рядком «>> exit=<код>», що збігається з кодом у steps.json; є env.json, scan_html_fp.json,
     http_requests.jsonl; неповний сценарій НЕ може дати успіх;
  1. усі кроки steps.json завершилися з кодом 0;
  2. версія синхронізатора (крок version) збігається з очікуваною (якщо задано);
  3. скан HTML на текстах копії: html_detected = 0;
  4. другий sync --changed поспіль: «Актів для перевірки: 0 із N», рівно 1 HTTP-запит, і це 304;
  5. картка 2343-12 під час anomaly без --record не змінилася: SHA-256 і mtime до = після;
  6. anomaly для 201301186: verdict не duplicate_of (очікувано inconclusive);
  7. verify: corrupt = date_mismatch = missing = 0 і жодного акта без картки;
  8. журнал HTTP: усі запити лише до data.rada.gov.ua, жодної відповіді 403/429.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


REQUIRED_STEPS = (
    "offline_tests", "version", "scan_html_fp",
    "probe_2747-15_20230323", "probe_2343-12_20191021", "probe_2747-15_30000101",
    "sync_changed_1", "sync_changed_2_noop", "verify", "status", "anomaly_2343-12_no_record",
)
REQUIRED_FILES = ("env.json", "steps.json", "scan_html_fp.json", "http_requests.jsonl")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--expect-version")
    ap.add_argument("--out-json", type=Path, help="куди записати результат (типово <тека>/checks.json)")
    a = ap.parse_args()
    out = a.out
    if not (out / "steps.json").exists() or not (out / "env.json").exists():
        print(f"Бракує steps.json / env.json у {out}")
        return 2
    steps = json.loads(read(out / "steps.json"))
    env = json.loads(read(out / "env.json"))
    by = {s["step"]: s for s in steps}
    checks = []

    def check(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    names = [s.get("step") for s in steps]
    problems0 = []
    for req in REQUIRED_STEPS:
        n = names.count(req)
        if n == 0:
            problems0.append(f"немає кроку {req}")
        elif n > 1:
            problems0.append(f"крок {req} повторюється {n} рази")
    dups = sorted({x for x in names if names.count(x) > 1 and x not in REQUIRED_STEPS})
    problems0 += [f"крок {x} повторюється" for x in dups]
    for st in steps:
        log = out / str(st.get("log", ""))
        txt = read(log) if st.get("log") else ""
        if not txt.strip():
            problems0.append(f"журнал кроку {st.get('step')} відсутній або порожній")
            continue
        m_exit = re.findall(r"^>> exit=(\S+)\s*$", txt, re.M)
        if not m_exit or m_exit[-1] != str(st.get("exit")):
            problems0.append(f"журнал {st.get('step')}: «>> exit=» {m_exit[-1] if m_exit else 'немає'} ≠ steps.json {st.get('exit')}")
    for f in REQUIRED_FILES:
        if not (out / f).exists() or not read(out / f).strip():
            problems0.append(f"немає файла {f}")
    check("0_scenario_complete", not problems0, "усі 11 кроків по одному разу, журнали й файли на місці"
          if not problems0 else "; ".join(problems0[:8]) + (f" (+{len(problems0) - 8})" if len(problems0) > 8 else ""))

    bad = [f"{s['step']}={s['exit']}" for s in steps if s["exit"] != 0]
    check("1_all_steps_exit_0", not bad, "усі 0" if not bad else ", ".join(bad))

    ver = read(out / by.get("version", {}).get("log", "_")).split("\n")
    ver_val = next((l.strip() for l in ver[2:] if re.fullmatch(r"\d+\.\d+(\.\d+)?", l.strip())), "")
    check("2_version", (not a.expect_version) or ver_val == a.expect_version,
          f"скрипт {ver_val or '?'}" + (f", очікувано {a.expect_version}" if a.expect_version else ""))

    try:
        scan = json.loads(read(out / "scan_html_fp.json") or "{}")
    except ValueError:
        scan = {}
    check("3_scan_html_no_false_positives", scan.get("html_detected") == 0 and scan.get("files", 0) > 0,
          f"файлів {scan.get('files')}, визнано HTML {scan.get('html_detected')}")

    noop = next((s for s in steps if "noop" in s["step"]), None)
    t = read(out / noop["log"]) if noop else ""
    m = re.search(r"Актів для перевірки: (\d+) із (\d+)", t)
    r = re.search(r"HTTP-запитів: (\d+);.*?304: (\d+)", t)
    ok4 = bool(m and m.group(1) == "0" and r and r.group(1) == "1" and r.group(2) == "1")
    check("4_second_changed_is_noop", ok4,
          (f"актів {m.group(1)} із {m.group(2)}" if m else "немає рядка «Актів для перевірки»")
          + (f"; запитів {r.group(1)}, 304: {r.group(2)}" if r else "; немає підсумку HTTP"))

    same = (env.get("kartka_2343_12_sha_before") and env.get("kartka_2343_12_sha_before") == env.get("kartka_2343_12_sha_after")
            and env.get("kartka_2343_12_mtime_ns_before") == env.get("kartka_2343_12_mtime_ns_after")
            and env.get("kartka_2343_12_unchanged") is True)
    check("5_card_unchanged_by_anomaly", same,
          f"sha {str(env.get('kartka_2343_12_sha_before'))[:12]}… → {str(env.get('kartka_2343_12_sha_after'))[:12]}…, "
          f"mtime {env.get('kartka_2343_12_mtime_ns_before')} → {env.get('kartka_2343_12_mtime_ns_after')}")

    an = next((s for s in steps if s["step"].startswith("anomaly")), None)
    at = read(out / an["log"]) if an else ""
    v = re.search(r'"verdict": "([^"]+)"', at)
    check("6_anomaly_not_duplicate", bool(v) and not v.group(1).startswith("duplicate_of"),
          f"verdict {v.group(1) if v else '?'}")

    vt = read(out / by.get("verify", {}).get("log", "_"))
    tot = re.search(r"Разом: verified (\d+), legacy_unverified (\d+), corrupt (\d+), date_mismatch (\d+), missing (\d+)"
                    r"(?:; актів без картки \(missing_card\): (\d+))?", vt)
    ok7 = bool(tot and tot.group(3) == tot.group(4) == tot.group(5) == "0" and (tot.group(6) in (None, "0")))
    check("7_verify_clean", ok7, tot.group(0) if tot else "немає підсумку verify")

    hosts, bad_codes, n = set(), [], 0
    for line in read(out / "http_requests.jsonl").splitlines():
        if line.strip():
            try:
                rec = json.loads(line)
            except ValueError:
                bad_codes.append("невалідний рядок журналу")
                continue
            n += 1
            hosts.add(urlparse(rec["url"]).hostname)
            if rec.get("status") in (403, 429):
                bad_codes.append(rec["status"])
    check("8_http_only_official_no_403_429", n > 0 and hosts == {"data.rada.gov.ua"} and not bad_codes,
          f"запитів {n}, хости {sorted(hosts)}, 403/429: {len(bad_codes)}")

    failed = [c["check"] for c in checks if not c["ok"]]
    (a.out_json or (out / "checks.json")).write_text(json.dumps({"passed": not failed, "failed": failed, "checks": checks},
                                                ensure_ascii=False, indent=1), encoding="utf-8")
    for c in checks:
        print(("[OK]   " if c["ok"] else "[FAIL] ") + c["check"] + " — " + c["detail"])
    print("УСІ УМОВИ ВИКОНАНО" if not failed else f"ПОРУШЕНО УМОВ: {len(failed)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
