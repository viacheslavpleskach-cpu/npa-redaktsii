"""v4.1.7: окремі редакції того самого дня (2343-12: 201301186) і ручна правка опису.

Автор: В'ячеслав Плескач.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from helpers import (PODIA_TXT, PODIA_URL, S, SKRYPTY, FakeSession, act_card, card_url, http_date_for, make_archive,
                     make_client, txt_url)

NREG = "2343-12"
TEXT_A = "ЗАКОН УКРАЇНИ\nСтаття 1. Нова редакція 4212-VI.\n"
TEXT_B = "ЗАКОН УКРАЇНИ\nСтаття 1. Редакція зі змінами 5405-VI, 5410-VI, 5518-VI.\n"
LEGACY_HEAD = ("# Тест | редакція від 18.01.2013 | Нова редакція, підстава - 4212-VI\n"
               "# Підстава: 4212-VI\n"
               "# Джерело: https://zakon.rada.gov.ua/laws/show/2343-12/ed20130118 (© Верховна Рада України, CC BY 4.0)\n\n")


def world(*, sep_text=TEXT_A, ref_text=TEXT_B, sep_date="20130118"):
    root = make_archive([(NREG, "Б", "Банкрутство", "povna")])
    d = root / "akty" / NREG
    (d / "red").mkdir(parents=True)
    card = {"nreg": NREG, "nazva": "Тест", "rezhym": "povna", "stan": "Втратив чинність",
            "dzherelo": f"https://zakon.rada.gov.ua/laws/show/{NREG}",
            "perevireno": "2026-11-24T00:00:00+00:00", "podii": [],
            "redaktsii": [
                {"ed": "20121104", "data": "04.11.2012", "umovna": False, "data_na_saiti": "04.11.2012",
                 "opys": "Редакція, підстава - 5405-VI", "pidstava": ["5405-VI"], "tekst": True},
                {"ed": "20130118", "data": "18.01.2013", "umovna": False, "data_na_saiti": "18.01.2013",
                 "opys": "Нова редакція, підстава - 4212-VI", "pidstava": ["4212-VI"], "tekst": True},
                {"ed": "20130411", "data": "11.04.2013", "umovna": False, "data_na_saiti": "11.04.2013",
                 "opys": "Редакція, підстава - 155-VII", "pidstava": ["155-VII"], "tekst": True}],
            "api": {"unresolved_edition_ids": ["201301186"], "history_complete": False,
                    "history_reason": "невирішені некоректні ідентифікатори редакцій: 201301186"}}
    (d / "kartka.json").write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    (d / "red" / "20121104.txt").write_text(
        "# Тест | редакція від 04.11.2012 | Редакція\n\nСтаття 1. Стара.\n", encoding="utf-8")
    (d / "red" / "20130118.txt").write_text(LEGACY_HEAD + TEXT_B, encoding="utf-8")
    (d / "red" / "20130411.txt").write_text(
        "# Тест | редакція від 11.04.2013 | Редакція\n\nСтаття 1. Пізніша.\n", encoding="utf-8")
    sess = FakeSession()
    sess.route(card_url(NREG), body=act_card(NREG, ["20121104", "20130118", "20130411"],
                                             datred="20130411", edcnt=4, status=1))
    sess.route(txt_url(NREG, "201301186"), body=sep_text, headers={"DocumentDate": http_date_for(sep_date)})
    sess.route(txt_url(NREG, "20130118"), body=ref_text, headers={"DocumentDate": http_date_for("20130118")})
    return root, make_client(root, sess)


def anomaly_args(root, **kw):
    base = dict(root=root, nreg=NREG, raw="201301186", record=False, record_separate=True,
                order="before", opys="Нова редакція", pidstava="4212-VI", request_log=None,
                pause_min=5.0, pause_max=7.0, timeout=5.0, daily_budget_mb=150.0)
    base.update(kw)
    return argparse.Namespace(**base)


def run_anomaly(root, client, **kw):
    with mock.patch.object(S, "make_client", lambda a, r: client):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = S.run_anomaly(anomaly_args(root, **kw))
    return rc, buf.getvalue()


def load_card(root):
    return json.loads((root / "akty" / NREG / "kartka.json").read_text(encoding="utf-8"))


class TestEditionDate(unittest.TestCase):
    def test_edition_date(self):
        self.assertEqual(S.edition_date("20130118"), "20130118")
        self.assertEqual(S.edition_date("201301186"), "20130118")
        self.assertEqual(S.edition_date("2013011812"), "20130118")
        self.assertIsNone(S.edition_date("30000101"))
        self.assertIsNone(S.edition_date("201313186"))     # неіснуюча дата
        self.assertIsNone(S.edition_date("20130118123"))   # 11 цифр

    def test_sort_key_orders_within_day(self):
        items = [{"ed": "20130411"}, {"ed": "20130118"}, {"ed": "201301186", "poriadok_u_dni": -1},
                 {"ed": "30000101"}, {"ed": "20121104"}]
        self.assertEqual([x["ed"] for x in sorted(items, key=S.edition_sort_key)],
                         ["20121104", "201301186", "20130118", "20130411", "30000101"])
        items[2]["poriadok_u_dni"] = 1
        self.assertEqual([x["ed"] for x in sorted(items, key=S.edition_sort_key)][1:3],
                         ["20130118", "201301186"])

    def test_document_date_validation_uses_day_prefix(self):
        h = {"DocumentDate": http_date_for("20130118")}
        self.assertEqual(S.validate_document_date(h, requested_ed="201301186"), "20130118")
        with self.assertRaises(S.EditionDateMismatch):
            S.validate_document_date({"DocumentDate": http_date_for("20130119")}, requested_ed="201301186")

    def test_choose_editions_chynna_with_same_day_id(self):
        import datetime as dt
        eds = [{"ed": "201301186", "poriadok_u_dni": -1}, {"ed": "20130118"}]
        self.assertEqual(S.choose_editions("chynna", eds, today=dt.date(2014, 1, 1)), ["20130118"])


class TestRecordSeparate(unittest.TestCase):
    def test_records_text_card_and_order(self):
        root, client = world()
        rc, out = run_anomaly(root, client)
        self.assertEqual(rc, 0, out)
        self.assertIn("Окрему редакцію записано", out)
        card = load_card(root)
        self.assertEqual([x["ed"] for x in card["redaktsii"]],
                         ["20121104", "201301186", "20130118", "20130411"])
        sep = card["redaktsii"][1]
        self.assertEqual(sep["poriadok_u_dni"], -1)
        self.assertEqual(sep["opys"], "Нова редакція, підстава - 4212-VI")
        self.assertEqual(sep["text_status"], "verified")
        self.assertEqual(card["api"]["unresolved_edition_ids"], [])
        self.assertEqual(card["api"]["separate_edition_ids"][0]["raw"], "201301186")
        path = root / "akty" / NREG / "red" / "201301186.txt"
        self.assertEqual(S.classify_text_file(path, "201301186", NREG)[0], "verified")
        self.assertIn("/ed201301186", path.read_text(encoding="utf-8").split("\n")[2])

    def test_same_text_is_refused(self):
        root, client = world(sep_text=TEXT_B)
        rc, out = run_anomaly(root, client)
        self.assertEqual(rc, 1)
        self.assertIn("дублікат", out)
        self.assertFalse((root / "akty" / NREG / "red" / "201301186.txt").exists())
        self.assertEqual(load_card(root)["api"]["unresolved_edition_ids"], ["201301186"])

    def test_wrong_document_date_is_refused(self):
        root, client = world(sep_date="20130119")
        rc, out = run_anomaly(root, client)
        self.assertEqual(rc, 1)
        self.assertIn("НЕ записано", out)
        self.assertNotIn("separate_edition_ids", load_card(root)["api"])

    def test_order_is_required(self):
        root, client = world()
        with self.assertRaises(S.SyncError):
            run_anomaly(root, client, order=None)

    def test_record_and_separate_exclusive(self):
        root, client = world()
        with self.assertRaises(S.SyncError):
            run_anomaly(root, client, record=True)

    def test_html_body_is_refused(self):
        root, client = world(sep_text="<!DOCTYPE html><html><body>Сторінка</body></html>")
        rc, out = run_anomaly(root, client)
        self.assertEqual(rc, 1)
        self.assertFalse((root / "akty" / NREG / "red" / "201301186.txt").exists())


class TestSyncKeepsSeparateAndManual(unittest.TestCase):
    def test_catalog_complete_after_record(self):
        p = S.parse_json_card(act_card(NREG, ["20121104", "20130118", "20130411"], edcnt=4),
                              bulk_invalid=["201301186"], resolved_ids=["201301186"])
        self.assertTrue(p["edition_catalog_complete"], p["catalog_reason"])
        p2 = S.parse_json_card(act_card(NREG, ["20121104", "20130118", "20130411"], edcnt=4),
                               bulk_invalid=["201301186"])
        self.assertFalse(p2["edition_catalog_complete"])

    def test_normalized_card_keeps_order_and_manual_correction(self):
        root, client = world()
        run_anomaly(root, client)
        with redirect_stdout(io.StringIO()):
            S.run_pravka(argparse.Namespace(root=root, nreg=NREG, ed="20130118", opys="Редакція",
                                            pidstava="5405-VI, 5410-VI, 5518-VI",
                                            prychyna="звірено з карткою сайту"))
        old = load_card(root)
        # API знову дає старий опис і інші підстави — ручна правка має перевагу.
        parsed = S.parse_json_card(act_card(NREG, ["20121104", "20130118", "20130411"], edcnt=4,
                                            extra_eds=[]), bulk_invalid=["201301186"],
                                   resolved_ids=["201301186"])
        for e in parsed["redaktsii"]:
            if e["ed"] == "20130118":
                e["opys"], e["pidstava"] = "Нова редакція, підстава - 4212-VI", ["4212-VI"]
        card = S.normalized_card(root, NREG, {"nreg": NREG, "rezhym": "povna"}, parsed,
                                 "2026-11-24T00:00:00+00:00", old)
        eds = [x["ed"] for x in card["redaktsii"]]
        self.assertEqual(eds, ["20121104", "201301186", "20130118", "20130411"])
        e = card["redaktsii"][2]
        self.assertEqual(e["opys"], "Редакція, підстава - 5405-VI, 5410-VI, 5518-VI")
        self.assertEqual(e["pidstava"], ["5405-VI", "5410-VI", "5518-VI"])
        self.assertIn("ruchna_pravka", e)
        self.assertEqual(card["redaktsii"][1]["text_status"], "verified")
        self.assertTrue(card["api"]["edition_catalog_complete"])
        self.assertEqual(card["api"]["separate_edition_ids"][0]["raw"], "201301186")

    def test_sync_one_end_to_end(self):
        root, client = world()
        run_anomaly(root, client)
        with redirect_stdout(io.StringIO()):
            S.run_pravka(argparse.Namespace(root=root, nreg=NREG, ed="20130118", opys="Редакція",
                                            pidstava="5405-VI, 5410-VI, 5518-VI",
                                            prychyna="звірено з карткою сайту"))
        client.session.route(PODIA_URL, body=PODIA_TXT)
        res = S.sync_one(client, root, {"nreg": NREG, "rezhym": "povna", "nazva": "Тест"},
                         bulk_invalid=["201301186"])
        self.assertEqual(res["failed"], [], res)
        self.assertTrue(res["catalog_complete"])
        card = load_card(root)
        self.assertEqual([x["ed"] for x in card["redaktsii"]],
                         ["20121104", "201301186", "20130118", "20130411"])
        self.assertEqual(card["redaktsii"][2]["pidstava"], ["5405-VI", "5410-VI", "5518-VI"])
        self.assertIn("201301186", res["skipped"])


class TestPravka(unittest.TestCase):
    def test_header_rewritten_body_untouched(self):
        root, _ = world()
        path = root / "akty" / NREG / "red" / "20130118.txt"
        body_before = S.split_text_file(path.read_text(encoding="utf-8"))[1]
        with redirect_stdout(io.StringIO()):
            rc = S.run_pravka(argparse.Namespace(root=root, nreg=NREG, ed="20130118", opys="Редакція",
                                                 pidstava="5405-VI, 5410-VI, 5518-VI",
                                                 prychyna="звірено з карткою сайту"))
        self.assertEqual(rc, 0)
        head, body = S.split_text_file(path.read_text(encoding="utf-8"))
        self.assertEqual(body, body_before)
        self.assertIn("| редакція від 18.01.2013 | Редакція, підстава - 5405-VI, 5410-VI, 5518-VI", head[0])
        self.assertEqual(head[1], "# Підстава: 5405-VI, 5410-VI, 5518-VI")
        self.assertEqual(S.classify_text_file(path, "20130118", NREG)[0], "legacy_unverified")
        e = load_card(root)["redaktsii"][1]
        self.assertEqual(e["ruchna_pravka"]["bulo"]["pidstava"], ["4212-VI"])

    def test_verified_sha_survives_pravka(self):
        root, _ = world()
        body = S.clean_plain_text(TEXT_B)
        card = {"nazva": "Тест", "dzherelo": f"https://zakon.rada.gov.ua/laws/show/{NREG}"}
        S.write_text_file(root, NREG, card, "20130118", body,
                          {"opys": "Нова редакція, підстава - 4212-VI", "pidstava": ["4212-VI"]},
                          "20130118", hashlib.sha256(body.encode("utf-8")).hexdigest())
        with redirect_stdout(io.StringIO()):
            S.run_pravka(argparse.Namespace(root=root, nreg=NREG, ed="20130118", opys="Редакція",
                                            pidstava="5405-VI", prychyna="тест"))
        path = root / "akty" / NREG / "red" / "20130118.txt"
        self.assertEqual(S.classify_text_file(path, "20130118", NREG)[0], "verified")

    def test_unknown_edition(self):
        root, _ = world()
        with self.assertRaises(S.SyncError):
            S.run_pravka(argparse.Namespace(root=root, nreg=NREG, ed="20990101", opys="Редакція",
                                            pidstava="1-I", prychyna="тест"))


class TestNpaSameDay(unittest.TestCase):
    """npa.py з репозиторію на тимчасовому архіві: вибір редакції на дату з двома редакціями дня."""

    def setUp(self):
        self.root, client = world()
        run_anomaly(self.root, client)
        with redirect_stdout(io.StringIO()):
            S.run_pravka(argparse.Namespace(root=self.root, nreg=NREG, ed="20130118", opys="Редакція",
                                            pidstava="5405-VI, 5410-VI, 5518-VI", prychyna="тест"))
        (self.root / "skrypty").mkdir()
        shutil.copy(SKRYPTY / "npa.py", self.root / "skrypty" / "npa.py")

    def npa(self, *args):
        r = subprocess.run([sys.executable, str(self.root / "skrypty" / "npa.py"), *args],
                           capture_output=True, text=True, encoding="utf-8")
        return r.stdout + r.stderr

    def test_day_of_two_editions(self):
        out = self.npa("stattia", NREG, "1", "--na", "18.01.2013")
        self.assertIn("5405-VI, 5410-VI, 5518-VI", out)
        self.assertIn("зі змінами 5405-VI", out)
        self.assertIn("набрали чинності 2 редакції", out)
        self.assertIn("/ed20130118", out)

    def test_next_day_no_extra_warning(self):
        out = self.npa("stattia", NREG, "1", "--na", "19.01.2013")
        self.assertIn("зі змінами 5405-VI", out)
        self.assertNotIn("набрали чинності 2 редакції", out)

    def test_redaktsii_lists_both(self):
        out = self.npa("redaktsii", NREG)
        self.assertIn("18.01.2013 [ed201301186] Нова редакція, підстава - 4212-VI", out)
        self.assertIn("18.01.2013   Редакція, підстава - 5405-VI, 5410-VI, 5518-VI", out)


if __name__ == "__main__":
    unittest.main()
