"""v4.1.6 (аудит v4.1.5): наскрізні тести кириличних позначень на початку тексту редакції.

Справжній текст, що починається з «<дата>», «<підпис>» чи «<ПІБ>», має проходити весь шлях:
fetch_verified_text → sync (запис verified) → verify → anomaly --record (дубль визнається, якщо тексти однакові).
"""
import argparse
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from helpers import S, FakeSession, act_card, card_url, http_date_for, make_archive, make_client, txt_url
from test_sync_integration import args_for
from test_v4_1_1_regressions import quiet, vargs, write_card

TEXTS = {
    "data": "<дата> народження ________\nСтаття 1. Форма заяви заповнюється заявником.\n",
    "pidpys": "<підпис> __________________\nСтаття 2. Заява підписується особисто.\n",
    "pib": "<ПІБ> заявника ________ <дата> ________\nСтаття 3. Дані вносяться друкованими літерами.\n",
}


class TestUnicodeEndToEnd(unittest.TestCase):
    def test_fetch_verified_text_accepts(self):
        for name, txt in TEXTS.items():
            with self.subTest(name):
                root = make_archive([("a-1", "А", "Акт", "povna")])
                sess = FakeSession()
                sess.route(txt_url("a-1", "20200101"), body=txt,
                           headers={"DocumentDate": http_date_for("20200101"), "Content-Type": "text/plain; charset=utf-8"})
                body, *_r, actual, _src = make_client(root, sess).fetch_verified_text("a-1", "20200101", "laws")
                self.assertEqual(actual, "20200101")
                self.assertTrue(body.startswith(txt.split()[0]), name)

    def test_sync_writes_verified_and_verify_clean(self):
        for name, txt in TEXTS.items():
            with self.subTest(name):
                root = make_archive([("a-1", "А", "Акт", "povna")])
                sess = FakeSession()
                from helpers import DOC_UPDATE_URL, PODIA_TXT, PODIA_URL, doc_update
                sess.route(PODIA_URL, body=PODIA_TXT)
                sess.route(DOC_UPDATE_URL, body=doc_update([("2026-11-20 09:00:00", "a-1", "20200101")]))
                sess.route(card_url("a-1"), body=act_card("a-1", ["20200101"]))
                sess.route(txt_url("a-1", "20200101"), body=txt,
                           headers={"DocumentDate": http_date_for("20200101"), "Content-Type": "text/plain"})
                sess.route(txt_url("a-1"), body=txt, headers={"DocumentDate": http_date_for("20200101")})
                client = make_client(root, sess)
                with mock.patch.object(S, "make_client", lambda a, r: client):
                    rc = quiet(S.run_sync, args_for(root, nreg="a-1"))
                self.assertEqual(rc, 0, name)
                k = json.loads((root / "akty" / "a-1" / "kartka.json").read_text(encoding="utf-8"))
                self.assertEqual(k["redaktsii"][0]["text_status"], "verified")
                self.assertEqual(quiet(S.run_verify, vargs(root)), 0)

    def test_anomaly_record_duplicate_for_identical_cyrillic_texts(self):
        for name, txt in TEXTS.items():
            with self.subTest(name):
                root = make_archive([("2343-12", "Б", "Банкрутство", "povna")])
                write_card(root, "2343-12", ["20130118", "20191021"])
                sess = FakeSession()
                sess.route(card_url("2343-12"), body=act_card("2343-12", ["20130118", "20191021"], edcnt=3))
                hdr = {"DocumentDate": http_date_for("20130118"), "Content-Type": "text/plain; charset=utf-8"}
                sess.route(txt_url("2343-12", "201301186"), body=txt, headers=hdr)
                sess.route(txt_url("2343-12", "20130118"), body=txt, headers=hdr)
                client = make_client(root, sess)
                a = argparse.Namespace(root=root, nreg="2343-12", raw="201301186", record=True, request_log=None,
                                       pause_min=5.0, pause_max=7.0, timeout=5.0, daily_budget_mb=150.0)
                with mock.patch.object(S, "make_client", lambda x, r: client):
                    buf = io.StringIO()
                    with redirect_stdout(buf):
                        S.run_anomaly(a)
                self.assertIn('"verdict": "duplicate_of:20130118"', buf.getvalue(), name)
                api = json.loads((root / "akty" / "2343-12" / "kartka.json").read_text(encoding="utf-8"))["api"]
                self.assertEqual(api["resolved_edition_ids"][0]["raw"], "201301186")

    def test_anomaly_cyrillic_vs_html_still_inconclusive(self):
        root = make_archive([("2343-12", "Б", "Банкрутство", "povna")])
        write_card(root, "2343-12", ["20130118", "20191021"])
        sess = FakeSession()
        sess.route(card_url("2343-12"), body=act_card("2343-12", ["20130118", "20191021"], edcnt=3))
        hdr = {"DocumentDate": http_date_for("20130118"), "Content-Type": "text/plain"}
        sess.route(txt_url("2343-12", "201301186"), body=TEXTS["data"], headers=hdr)
        sess.route(txt_url("2343-12", "20130118"), body="<div><p>Помилка</p></div>", headers=hdr)
        client = make_client(root, sess)
        a = argparse.Namespace(root=root, nreg="2343-12", raw="201301186", record=True, request_log=None,
                               pause_min=5.0, pause_max=7.0, timeout=5.0, daily_budget_mb=150.0)
        before = (root / "akty" / "2343-12" / "kartka.json").read_bytes()
        with mock.patch.object(S, "make_client", lambda x, r: client):
            buf = io.StringIO()
            with redirect_stdout(buf):
                S.run_anomaly(a)
        self.assertIn('"verdict": "inconclusive"', buf.getvalue())
        self.assertEqual((root / "akty" / "2343-12" / "kartka.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
