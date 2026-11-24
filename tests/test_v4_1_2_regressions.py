"""Регресійні тести v4.1.2 за зауваженнями аудиту v4.1.1 від 23.11.2026 (розд. 2 і 3)."""
import argparse
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from helpers import S, FakeSession, act_card, card_url, http_date_for, make_archive, make_client, txt_url
from test_v4_1_1_regressions import quiet, vargs, write_card, write_v41

HTML = "<!doctype html><html><head><title>Законодавство</title></head><body>сторінка</body></html>"
TXT = "Стаття 1. Текст редакції від 18.01.2013.\n"


class TestAnomalyHtml(unittest.TestCase):
    def _run(self, raw_body, raw_ctype, ref_body, ref_ctype):
        root = make_archive([("2343-12", "Б", "Банкрутство", "povna")])
        write_card(root, "2343-12", ["20130118", "20191021"])
        sess = FakeSession()
        sess.route(card_url("2343-12"), body=act_card("2343-12", ["20130118", "20191021"], edcnt=3))
        dd = http_date_for("20130118")
        sess.route(txt_url("2343-12", "201301186"), body=raw_body, headers={"DocumentDate": dd, "Content-Type": raw_ctype})
        sess.route(txt_url("2343-12", "20130118"), body=ref_body, headers={"DocumentDate": dd, "Content-Type": ref_ctype})
        client = make_client(root, sess)
        a = argparse.Namespace(root=root, nreg="2343-12", raw="201301186", record=True, request_log=None,
                               pause_min=5.0, pause_max=7.0, timeout=5.0, daily_budget_mb=150.0)
        before = (root / "akty" / "2343-12" / "kartka.json").read_bytes()
        with mock.patch.object(S, "make_client", lambda x, r: client):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = S.run_anomaly(a)
        after = (root / "akty" / "2343-12" / "kartka.json").read_bytes()
        return rc, buf.getvalue(), before, after

    def assert_inconclusive_unrecorded(self, rc, out, before, after):
        self.assertEqual(rc, 0)
        self.assertIn('"verdict": "inconclusive"', out)
        self.assertNotIn("duplicate_of", out)
        self.assertEqual(before, after)                                  # картку не змінено
        self.assertNotIn("resolved_edition_ids", json.loads(after.decode("utf-8")).get("api", {}))

    def test_raw_html_reference_txt(self):
        r = self._run(HTML, "text/html; charset=utf-8", TXT, "text/plain; charset=utf-8")
        self.assert_inconclusive_unrecorded(*r)
        self.assertIn("не є текстом редакції", r[1])

    def test_raw_txt_reference_html(self):
        r = self._run(TXT, "text/plain; charset=utf-8", HTML, "text/html")
        self.assert_inconclusive_unrecorded(*r)
        self.assertIn("контрольна відповідь не є текстом редакції", r[1])

    def test_both_identical_html(self):
        r = self._run(HTML, "text/html", HTML, "text/html")              # відтворений аудитом сценарій
        self.assert_inconclusive_unrecorded(*r)

    def test_html_body_with_text_mime(self):
        r = self._run(HTML, "text/plain", HTML, "text/plain")             # MIME бреше, тіло — HTML
        self.assert_inconclusive_unrecorded(*r)

    def test_empty_bodies(self):
        r = self._run("   \n", "text/plain", "   \n", "text/plain")
        self.assert_inconclusive_unrecorded(*r)

    def test_identical_real_txt_still_duplicate(self):
        rc, out, before, after = self._run(TXT, "text/plain; charset=utf-8", TXT, "application/octet-stream")
        self.assertEqual(rc, 0)
        self.assertIn('"verdict": "duplicate_of:20130118"', out)
        api = json.loads(after.decode("utf-8"))["api"]
        self.assertEqual(api["resolved_edition_ids"][0]["raw"], "201301186")


class TestVerifyMissingCard(unittest.TestCase):
    def _root(self):
        return make_archive([("a-1", "А", "Акт", "povna")])

    def test_no_card_no_texts_nonzero(self):
        root = self._root()
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = S.run_verify(vargs(root))
        self.assertNotEqual(rc, 0)
        self.assertIn("missing_card", buf.getvalue())

    def test_no_card_with_stray_text_nonzero(self):
        root = self._root()
        write_v41(root, "a-1", "20200101")
        self.assertNotEqual(quiet(S.run_verify, vargs(root)), 0)

    def test_json_report_lists_missing_card(self):
        root = self._root()
        out = root / "v.json"
        quiet(S.run_verify, vargs(root, json=str(out)))
        rep = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(rep["missing_card"], ["a-1"])

    def test_chynna_odyn_historical_missing_still_ok(self):
        root = make_archive([("c-1", "Ц", "Акт", "chynna"), ("o-1", "О", "Знімок", "odyn")])
        write_card(root, "c-1", ["20190101", "20220101"], mode="chynna")
        write_v41(root, "c-1", "20220101")
        write_card(root, "o-1", ["20180101", "20240101"], mode="odyn")
        write_v41(root, "o-1", "20240101")
        self.assertEqual(quiet(S.run_verify, vargs(root)), 0)

    def test_repair_without_card_nonzero_and_no_changes(self):
        root = self._root()
        p = write_v41(root, "a-1", "20200101")
        p.write_text(p.read_text(encoding="utf-8") + "пошкодження\n", encoding="utf-8")
        snap = {q: q.read_bytes() for q in root.rglob("*") if q.is_file()}
        sess = FakeSession()
        client = make_client(root, sess)
        with mock.patch.object(S, "make_client", lambda a, r: client):
            rc = quiet(S.run_verify, vargs(root, repair=True))
        self.assertNotEqual(rc, 0)
        self.assertEqual(sess.calls, [])                                  # мережі не торкалися
        after = {q: q.read_bytes() for q in root.rglob("*") if q.is_file() and ".npa_cache" not in q.parts}
        self.assertEqual({k: v for k, v in snap.items() if ".npa_cache" not in k.parts}, after)

    def test_repair_without_card_no_targets_nonzero(self):
        root = self._root()
        self.assertNotEqual(quiet(S.run_verify, vargs(root, repair=True)), 0)


if __name__ == "__main__":
    unittest.main()
