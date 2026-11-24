"""v4.1.5 (аудит v4.1.4, розд. 2): check_live_results.py позначає живу перевірку невдалою за порушення умов."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CHECK = Path(__file__).resolve().parent / "live" / "check_live_results.py"


def make_out(**over):
    d = Path(tempfile.mkdtemp(prefix="chk_"))
    steps = [("offline_tests", 0), ("version", 0), ("scan_html_fp", 0), ("probe_2747-15_20230323", 0),
             ("probe_2343-12_20191021", 0), ("probe_2747-15_30000101", 0), ("sync_changed_1", 0),
             ("sync_changed_2_noop", 0), ("verify", 0), ("status", 0), ("anomaly_2343-12_no_record", 0)]
    steps = over.get("steps", steps)
    logs = {
        "version": "$ x\n\n4.1.5\n\n>> exit=0\n",
        "sync_changed_2_noop": over.get("noop", "Актів для перевірки: 0 із 51.\n  HTTP-запитів: 1; завантажено 0.00 MiB; 304: 1; з кешу: 1\n"),
        "verify": over.get("verify", "Разом: verified 7, legacy_unverified 3303, corrupt 0, date_mismatch 0, missing 0; "
                                     "актів без картки (missing_card): 0\n"),
        "anomaly_2343-12_no_record": over.get("anomaly", '{\n "verdict": "inconclusive"\n}\n'),
    }
    rec = []
    for i, (name, code) in enumerate(steps, 1):
        log = f"{i:02d}_{name}.txt"
        body = logs.get(name, "ok\n")
        if name not in over.get("no_exit_line", ()):
            body += f"\n>> exit={over.get('log_exit', {}).get(name, code)}\n"
        if name not in over.get("missing_logs", ()):
            (d / log).write_text(body, encoding="utf-8")
        rec.append({"step": name, "exit": code, "log": log})
    (d / "steps.json").write_text(json.dumps(rec), encoding="utf-8")
    env = {"kartka_2343_12_sha_before": "a" * 64, "kartka_2343_12_sha_after": "a" * 64,
           "kartka_2343_12_mtime_ns_before": 1, "kartka_2343_12_mtime_ns_after": 1, "kartka_2343_12_unchanged": True}
    env.update(over.get("env", {}))
    (d / "env.json").write_text(json.dumps(env), encoding="utf-8")
    (d / "scan_html_fp.json").write_text(json.dumps(over.get("scan", {"files": 3303, "html_detected": 0})), encoding="utf-8")
    http = over.get("http", [{"url": "https://data.rada.gov.ua/x", "status": 304}])
    (d / "http_requests.jsonl").write_text("\n".join(json.dumps(x) for x in http) + "\n", encoding="utf-8")
    for f in over.get("drop_files", ()):
        (d / f).unlink()
    return d


def run(d, *extra):
    return subprocess.run([sys.executable, str(CHECK), str(d), "--expect-version", "4.1.5", *extra],
                          capture_output=True, text=True, encoding="utf-8").returncode


class TestLiveChecker(unittest.TestCase):
    def test_all_good_passes(self):
        d = make_out()
        self.assertEqual(run(d), 0)
        self.assertTrue(json.loads((d / "checks.json").read_text(encoding="utf-8"))["passed"])

    def test_each_violation_fails(self):
        cases = {
            "card_changed": {"env": {"kartka_2343_12_sha_after": "b" * 64, "kartka_2343_12_unchanged": False}},
            "card_mtime_changed": {"env": {"kartka_2343_12_mtime_ns_after": 2}},
            "second_changed_not_noop": {"noop": "Актів для перевірки: 3 із 51.\n  HTTP-запитів: 7; завантажено 1 MiB; 304: 1\n"},
            "second_changed_no_304": {"noop": "Актів для перевірки: 0 із 51.\n  HTTP-запитів: 1; завантажено 17 MiB; 304: 0\n"},
            "step_failed": {"log_exit": {}, "steps": [("offline_tests", 0), ("version", 0), ("scan_html_fp", 0),
                            ("probe_2747-15_20230323", 0), ("probe_2343-12_20191021", 0), ("probe_2747-15_30000101", 0),
                            ("sync_changed_1", 0), ("sync_changed_2_noop", 0), ("verify", 1), ("status", 0),
                            ("anomaly_2343-12_no_record", 0)]},
            "html_false_positive": {"scan": {"files": 3303, "html_detected": 1}},
            "anomaly_duplicate": {"anomaly": '{"verdict": "duplicate_of:20130118"}'},
            "verify_missing_card": {"verify": "Разом: verified 7, legacy_unverified 3303, corrupt 0, date_mismatch 0, missing 0; "
                                              "актів без картки (missing_card): 1\n"},
            "foreign_host": {"http": [{"url": "https://zakon.rada.gov.ua/laws/show/x", "status": 200}]},
            "rate_limited": {"http": [{"url": "https://data.rada.gov.ua/x", "status": 429}]},
        }
        for name, over in cases.items():
            with self.subTest(name):
                self.assertEqual(run(make_out(**over)), 1, name)

    def test_incomplete_scenario_fails(self):
        """v4.1.6 (аудит v4.1.5): неповний сценарій не може дати успіх."""
        full = [("offline_tests", 0), ("version", 0), ("scan_html_fp", 0), ("probe_2747-15_20230323", 0),
                ("probe_2343-12_20191021", 0), ("probe_2747-15_30000101", 0), ("sync_changed_1", 0),
                ("sync_changed_2_noop", 0), ("verify", 0), ("status", 0), ("anomaly_2343-12_no_record", 0)]
        keep = {"version", "sync_changed_2_noop", "verify", "anomaly_2343-12_no_record"}
        cases = {
            "seven_required_steps_removed": {"steps": [x for x in full if x[0] in keep]},   # експеримент аудиту
            "one_step_removed": {"steps": [x for x in full if x[0] != "status"]},
            "duplicate_step": {"steps": full + [("verify", 0)]},
            "unknown_duplicate_step": {"steps": full + [("extra", 0), ("extra", 0)]},
            "log_missing": {"missing_logs": ("probe_2343-12_20191021",)},
            "log_without_exit_line": {"no_exit_line": ("status",)},
            "log_exit_mismatch": {"log_exit": {"verify": 1}},
            "no_scan_json": {"drop_files": ("scan_html_fp.json",)},
            "no_http_log": {"drop_files": ("http_requests.jsonl",)},
            "empty_steps": {"steps": []},
        }
        for name, over in cases.items():
            with self.subTest(name):
                d = make_out(**over)
                self.assertEqual(run(d), 1, name)
                res = json.loads((d / "checks.json").read_text(encoding="utf-8"))
                self.assertFalse(res["passed"], name)
                self.assertIn("0_scenario_complete", res["failed"], name)

    def test_out_json_does_not_overwrite_run_checks(self):
        d = make_out()
        (d / "checks.json").write_text('{"original": true}', encoding="utf-8")
        alt = d / "posthoc.json"
        self.assertEqual(run(d, "--out-json", str(alt)), 0)
        self.assertEqual((d / "checks.json").read_text(encoding="utf-8"), '{"original": true}')
        self.assertTrue(json.loads(alt.read_text(encoding="utf-8"))["passed"])

    def test_wrong_version_fails(self):
        self.assertEqual(subprocess.run([sys.executable, str(CHECK), str(make_out()), "--expect-version", "9.9.9"],
                                        capture_output=True).returncode, 1)

    def test_missing_files(self):
        self.assertEqual(run(Path(tempfile.mkdtemp())), 2)


if __name__ == "__main__":
    unittest.main()
