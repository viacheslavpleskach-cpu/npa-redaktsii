"""v4.1.8: захист від неточних TXT API (втрата верхніх індексів, інший зміст).

Автор: В'ячеслав Плескач.
"""
import argparse
import io
import json
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

from helpers import (PODIA_TXT, PODIA_URL, S, SKRYPTY, FakeSession, act_card, card_url, http_date_for,
                     make_archive, make_client, txt_url)

NREG = "a-1"
OLD = ("ЗАКОН УКРАЇНИ\nПро тест\nРозділ I ЗАГАЛЬНІ\nСтаття 1. Визначення…\nСтаття 15-1. Система…\n×\nЗнайти:\nПошук\n"
       "ЗАКОН УКРАЇНИ\nПро тест\n(Відомості Верховної Ради (ВВР), 2016, № 31, ст. 545)\n"
       "Стаття 1. Визначення\n1. Суддя зобов’язаний діяти.\n"
       "Стаття 15-1. Система\n1. Доповнити пунктом 21-1 такого змісту.\n{Із змінами від 01.01.2020, ВВР, 2020, № 1}\n")
SAME = ("ЗАКОН УКРАЇНИ\nПро тест\n(Відомості Верховної Ради (ВВР), 2016, № 31, ст. 545)\n"
        "Стаття 1. Визначення\n1. Суддя зобов'язаний діяти.\n"
        "Стаття 15-1. Система\n1. Доповнити пунктом 21-1 такого змісту.\n{Із змінами від 01.01.2020}\n")
LOST = SAME.replace("Стаття 15-1.", "Стаття 151.").replace("пунктом 21-1", "пунктом 211")
OTHER = SAME.replace("Суддя зобов'язаний діяти.", "Суддя має право діяти.")


def vargs(root, **kw):
    base = dict(root=root, nreg=NREG, json=None, repair=True, include_legacy=True, include_conditional=False,
                force=False, request_log=None, pause_min=5.0, pause_max=7.0, timeout=5.0, daily_budget_mb=150.0)
    base.update(kw)
    return argparse.Namespace(**base)


def world(api_text, eds=("20200101",)):
    root = make_archive([(NREG, "А", "Акт", "povna")])
    d = root / "akty" / NREG
    (d / "red").mkdir(parents=True)
    card = {"nreg": NREG, "nazva": "Тест", "rezhym": "povna", "dzherelo": f"https://zakon.rada.gov.ua/laws/show/{NREG}",
            "perevireno": "2026-11-24T00:00:00+00:00", "podii": [],
            "redaktsii": [{"ed": e, "data": f"{e[6:8]}.{e[4:6]}.{e[:4]}", "opys": "Редакція", "pidstava": [],
                           "tekst": True} for e in eds]}
    (d / "kartka.json").write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    for e in eds:
        (d / "red" / f"{e}.txt").write_text(f"# Тест | редакція від {e[6:8]}.{e[4:6]}.{e[:4]} | Редакція\n\n" + OLD,
                                            encoding="utf-8")
    sess = FakeSession()
    for e in eds:
        sess.route(txt_url(NREG, e), body=api_text, headers={"DocumentDate": http_date_for(e)})
    return root, sess, make_client(root, sess)


def repair(root, client, **kw):
    buf = io.StringIO()
    with mock.patch.object(S, "make_client", lambda a, r: client), redirect_stdout(buf):
        rc = S.run_verify(vargs(root, **kw))
    return rc, buf.getvalue()


def card(root):
    return json.loads((root / "akty" / NREG / "kartka.json").read_text(encoding="utf-8"))


class TestHelpers(unittest.TestCase):
    def test_superscript_loss(self):
        self.assertEqual(sorted(S.superscript_loss(SAME, LOST)), ["15-1", "21-1"])
        self.assertEqual(S.superscript_loss(SAME, SAME), [])

    def test_superscript_loss_needs_same_context(self):
        # стаття 3-1 зникла, але «31» є лише в іншому контексті (номер ВВР) — це не втрата індексу
        old = "Стаття 3-1. Арбітражний керуючий\nтекст"
        new = "(Відомості Верховної Ради, 1992, № 31, ст. 440)\nСтаття 4. Інше"
        self.assertEqual(S.superscript_loss(old, new), [])

    def test_legacy_matches_api(self):
        self.assertTrue(S.legacy_matches_api(OLD, SAME)[0])
        same, why = S.legacy_matches_api(OLD, OTHER)
        self.assertFalse(same)
        self.assertIn("маєправо", why)

    def test_previous_text(self):
        root, _, _ = world(SAME, eds=("20190101", "20200101"))
        eds = card(root)["redaktsii"]
        self.assertIn("Стаття 15-1", S.previous_text(root, NREG, eds, "20200101"))
        self.assertIsNone(S.previous_text(root, NREG, eds, "20190101"))


class TestRepairLegacy(unittest.TestCase):
    def test_equal_content_is_replaced(self):
        root, _, client = world(SAME)
        rc, out = repair(root, client)
        self.assertEqual(rc, 0, out)
        e = card(root)["redaktsii"][0]
        self.assertEqual(e["text_status"], "verified")
        self.assertNotIn("api_text_issue", e)
        p = root / "akty" / NREG / "red" / "20200101.txt"
        self.assertEqual(S.classify_text_file(p, "20200101", NREG)[0], "verified")

    def test_superscript_loss_keeps_old_text(self):
        root, sess, client = world(LOST)
        p = root / "akty" / NREG / "red" / "20200101.txt"
        before = p.read_bytes()
        rc, out = repair(root, client)
        self.assertEqual(rc, 0, out)
        self.assertIn("залишено старий текст", out)
        self.assertEqual(p.read_bytes(), before)
        e = card(root)["redaktsii"][0]
        self.assertIn("верхні індекси", e["api_text_issue"])
        self.assertEqual(sorted(e["api_check"]["vtracheni_indeksy"]), ["15-1", "21-1"])
        self.assertNotEqual(e.get("text_status"), "verified")
        # повторний запуск не завантажує текст удруге
        n = len(sess.calls)
        rc, out = repair(root, client)
        self.assertEqual(len(sess.calls), n)
        self.assertIn("пропущено (повторно — лише з --force)", out)
        # з --force — завантажує знову
        repair(root, client, force=True)
        self.assertGreater(len(sess.calls), n)

    def test_other_content_keeps_old_text(self):
        root, _, client = world(OTHER)
        p = root / "akty" / NREG / "red" / "20200101.txt"
        before = p.read_bytes()
        rc, out = repair(root, client)
        self.assertEqual(p.read_bytes(), before)
        e = card(root)["redaktsii"][0]
        self.assertIn("зміст TXT API відрізняється", e["api_text_issue"])
        self.assertFalse(e["api_check"]["zbih_zmistu"])


class TestSyncNewEdition(unittest.TestCase):
    def test_new_edition_with_loss_is_flagged(self):
        root = make_archive([(NREG, "А", "Акт", "povna")])
        d = root / "akty" / NREG / "red"
        d.mkdir(parents=True)
        (d / "20200101.txt").write_text("# Тест | редакція від 01.01.2020 | Редакція\n\n" + SAME, encoding="utf-8")
        old_card = {"nreg": NREG, "nazva": "Тест", "rezhym": "povna", "podii": [],
                    "dzherelo": f"https://zakon.rada.gov.ua/laws/show/{NREG}",
                    "redaktsii": [{"ed": "20200101", "opys": "Редакція", "pidstava": [], "tekst": True}]}
        (d.parent / "kartka.json").write_text(json.dumps(old_card, ensure_ascii=False), encoding="utf-8")
        sess = FakeSession()
        sess.route(card_url(NREG), body=act_card(NREG, ["20200101", "20210101"], datred="20210101", edcnt=2))
        sess.route(PODIA_URL, body=PODIA_TXT)
        sess.route(txt_url(NREG, "20210101"), body=LOST, headers={"DocumentDate": http_date_for("20210101")})
        sess.route(txt_url(NREG, "20200101"), body=SAME, headers={"DocumentDate": http_date_for("20200101")})
        client = make_client(root, sess)
        res = S.sync_one(client, root, {"nreg": NREG, "rezhym": "povna", "nazva": "Тест"})
        self.assertTrue(any("верхні індекси" in w for w in res["warnings"]), res["warnings"])
        k = card(root)
        e = next(x for x in k["redaktsii"] if x["ed"] == "20210101")
        self.assertIn("верхні індекси", e["api_text_issue"])
        self.assertEqual(e["text_status"], "verified")
        # наступний sync зберігає позначку
        S.sync_one(client, root, {"nreg": NREG, "rezhym": "povna", "nazva": "Тест"})
        e = next(x for x in card(root)["redaktsii"] if x["ed"] == "20210101")
        self.assertIn("api_text_issue", e)


class TestNpaWarning(unittest.TestCase):
    def test_npa_shows_api_text_issue(self):
        root, _, client = world(LOST)
        repair(root, client)
        (root / "skrypty").mkdir()
        shutil.copy(SKRYPTY / "npa.py", root / "skrypty" / "npa.py")
        r = subprocess.run([sys.executable, str(root / "skrypty" / "npa.py"), "stattia", NREG, "1", "--na", "01.06.2020"],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertIn("текст редакції: TXT API втрачає верхні індекси", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
