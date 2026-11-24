"""Регресійні тести v4.1.1 за зауваженнями аудиту від 23.11.2026 (пп. 2–5, 7)."""
import argparse
import hashlib
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from helpers import (S, FakeSession, act_card, card_url, http_date_for, make_archive, make_client,
                     make_response, txt_url)

TEXT = "Стаття 1. Текст редакції {ed}.\n"


def vargs(root, **kw):
    base = dict(root=root, nreg=None, json=None, repair=False, include_legacy=False, include_conditional=False,
                request_log=None, pause_min=5.0, pause_max=7.0, timeout=5.0, daily_budget_mb=150.0)
    base.update(kw)
    return argparse.Namespace(**base)


def write_card(root, nreg, eds, mode="povna"):
    d = root / "akty" / nreg
    (d / "red").mkdir(parents=True, exist_ok=True)
    card = {"nreg": nreg, "nazva": "Т", "rezhym": mode, "dzherelo": f"https://zakon.rada.gov.ua/laws/show/{nreg}",
            "perevireno": "2026-11-23T00:00:00+00:00", "redaktsii": [{"ed": e, "pidstava": []} for e in eds], "podii": []}
    (d / "kartka.json").write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    return card


def write_v41(root, nreg, ed, text=None):
    body = S.clean_plain_text(text or TEXT.format(ed=ed))
    card = {"nazva": "Т", "dzherelo": f"https://zakon.rada.gov.ua/laws/show/{nreg}"}
    return S.write_text_file(root, nreg, card, ed, body, {"opys": "Редакція"}, ed,
                             hashlib.sha256(body.encode("utf-8")).hexdigest())


def quiet(fn, *a, **kw):
    with redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class TestVerifyCodes(unittest.TestCase):
    def test_verify_returns_nonzero_for_missing_expected_only(self):
        root = make_archive([("a-1", "А", "Акт", "povna")])
        write_card(root, "a-1", ["20200101", "20210101"])
        write_v41(root, "a-1", "20200101")                      # 20210101 відсутній
        self.assertNotEqual(quiet(S.run_verify, vargs(root)), 0)

    def test_missing_outside_expected_set_not_counted(self):
        root = make_archive([("c-1", "Ц", "Акт", "chynna")])
        write_card(root, "c-1", ["20190101", "20220101"], mode="chynna")
        write_v41(root, "c-1", "20220101")                      # 20190101 у режимі chynna не очікується
        self.assertEqual(quiet(S.run_verify, vargs(root)), 0)

    def _repair_world(self, budget=150 * 1024 * 1024):
        root = make_archive([("a-1", "А", "Акт", "povna")])
        write_card(root, "a-1", ["20200101", "20210101", "20220101"])
        sess = FakeSession()
        client = make_client(root, sess, budget=budget)
        return root, sess, client

    def test_verify_repair_all_targets_fixed_returns_zero(self):
        root, sess, client = self._repair_world()
        for ed in ("20200101", "20210101", "20220101"):
            sess.route(txt_url("a-1", ed), body=TEXT.format(ed=ed), headers={"DocumentDate": http_date_for(ed)})
        with mock.patch.object(S, "make_client", lambda a, r: client):
            self.assertEqual(quiet(S.run_verify, vargs(root, repair=True)), 0)
        self.assertEqual(quiet(S.run_verify, vargs(root)), 0)

    def test_verify_repair_budget_exceeded_returns_nonzero(self):
        root, sess, client = self._repair_world(budget=2000)
        sess.route(txt_url("a-1", "20200101"), body=TEXT.format(ed="20200101"),
                   headers={"DocumentDate": http_date_for("20200101")})
        big = make_response(txt_url("a-1", "20210101"), 200, b"x" * 5000, {"DocumentDate": http_date_for("20210101")})
        sess.routes[txt_url("a-1", "20210101")] = lambda h: big
        with mock.patch.object(S, "make_client", lambda a, r: client):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = S.run_verify(vargs(root, repair=True))
        self.assertNotEqual(rc, 0)
        self.assertTrue((root / "akty" / "a-1" / "red" / "20200101.txt").exists())   # перший відновлено
        self.assertIn("залишилося невідновленими: 2", buf.getvalue())
        self.assertIn("зупинка: бюджет трафіку", buf.getvalue())

    def test_verify_repair_conditional_skipped_returns_nonzero(self):
        root = make_archive([("k-1", "К", "Кодекс", "povna")])
        write_card(root, "k-1", ["20200101", "30000101"])
        write_v41(root, "k-1", "20200101")
        p = write_v41(root, "k-1", "30000101")
        p.write_text(p.read_text(encoding="utf-8") + "пошкодження\n", encoding="utf-8")   # corrupt
        client = make_client(root, FakeSession())
        with mock.patch.object(S, "make_client", lambda a, r: client):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = S.run_verify(vargs(root, repair=True))
        self.assertNotEqual(rc, 0)
        self.assertIn("пропущено: 1", buf.getvalue())


class TestMixedModified(unittest.TestCase):
    def test_mixed_parsed_and_unparsed_modified_falls_back_to_card(self):
        root = make_archive([("a-1", "А", "Акт", "povna")])
        write_card(root, "a-1", ["20200101"])
        write_v41(root, "a-1", "20200101")
        k = json.loads((root / "akty" / "a-1" / "kartka.json").read_text(encoding="utf-8"))
        k["api"] = {"doc_update_modified": "2026-11-20T09:00:00"}
        (root / "akty" / "a-1" / "kartka.json").write_text(json.dumps(k), encoding="utf-8")
        raw = "2026-11-20 09:00:00\ta-1\t20200101\n???\ta-1\t20200101\n".encode("cp1251")
        by, st = S.parse_doc_update(raw)
        self.assertEqual(st["modified_by_nreg"]["a-1"], "2026-11-20T09:00:00")
        changed, why = S._is_row_changed(root, {"nreg": "a-1", "rezhym": "povna"}, by["a-1"],
                                         modified=st["modified_by_nreg"].get("a-1"),
                                         modified_unparsed=bool(st["modified_unparsed"].get("a-1")))
        self.assertTrue(changed)
        self.assertIn("частково невідомого формату", why)


class TestEdcntExact(unittest.TestCase):
    def test_more_distinct_editions_than_edcnt_is_not_complete(self):
        p = S.parse_json_card(act_card("x-1", ["20200101", "20210101"], edcnt=1))
        self.assertFalse(p["edition_catalog_complete"])
        self.assertFalse(p["history_complete"])
        self.assertIn("більше, ніж edcnt=1", p["catalog_reason"])

    def test_more_than_edcnt_via_doc_update_is_not_complete(self):
        p = S.parse_json_card(act_card("x-2", ["20200101"], edcnt=1), bulk_editions=["20250101"])
        self.assertFalse(p["edition_catalog_complete"])
        self.assertIn("з doc-update додано: 1", p["catalog_reason"])

    def test_exact_edcnt_is_complete(self):
        p = S.parse_json_card(act_card("x-3", ["20200101", "20210101"], edcnt=2))
        self.assertTrue(p["edition_catalog_complete"])


class TestAnomalyReference(unittest.TestCase):
    def _world(self, ref_status):
        root = make_archive([("2343-12", "Б", "Банкрутство", "povna")])
        write_card(root, "2343-12", ["20130118", "20191021"])
        sess = FakeSession()
        sess.route(card_url("2343-12"), body=act_card("2343-12", ["20130118", "20191021"], edcnt=3))
        sess.route(txt_url("2343-12", "201301186"), body="Стаття 1. Інший текст.\n",
                   headers={"DocumentDate": http_date_for("20130118")})
        if ref_status == 302:
            sess.route(txt_url("2343-12", "20130118"), status=302, headers={"Location": "/laws/show/2343-12"})
        else:
            sess.route(txt_url("2343-12", "20130118"), status=ref_status)
        return root, make_client(root, sess)

    def _run(self, root, client):
        a = argparse.Namespace(root=root, nreg="2343-12", raw="201301186", record=True, request_log=None,
                               pause_min=5.0, pause_max=7.0, timeout=5.0, daily_budget_mb=150.0)
        with mock.patch.object(S, "make_client", lambda x, r: client):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = S.run_anomaly(a)
        return rc, buf.getvalue()

    def test_reference_404_inconclusive(self):
        root, client = self._world(404)
        rc, out = self._run(root, client)
        self.assertEqual(rc, 0)
        self.assertIn('"verdict": "inconclusive"', out)
        self.assertIn("недоступна", out)
        card = json.loads((root / "akty" / "2343-12" / "kartka.json").read_text(encoding="utf-8"))
        self.assertNotIn("resolved_edition_ids", card.get("api", {}))       # нічого не записано

    def test_reference_302_inconclusive(self):
        root, client = self._world(302)
        rc, out = self._run(root, client)
        self.assertEqual(rc, 0)
        self.assertIn('"verdict": "inconclusive"', out)
        self.assertNotIn("duplicate_of", out)


if __name__ == "__main__":
    unittest.main()
