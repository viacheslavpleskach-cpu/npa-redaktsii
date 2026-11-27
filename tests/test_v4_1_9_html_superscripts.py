"""v4.1.9: відновлення верхніх індексів за HTML API (.htm) тієї самої редакції.

Автор: В'ячеслав Плескач.
"""
import argparse
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from helpers import (PODIA_TXT, PODIA_URL, S, FakeSession, act_card, card_url, http_date_for, make_archive,
                     make_client, txt_url)

NREG = "a-1"
OLD = ("ЗАКОН УКРАЇНИ\nПро тест\n(Відомості Верховної Ради (ВВР), 2016, № 31, ст. 545)\n"
       "Стаття 1. Визначення\n1. Суддя зобов’язаний діяти у строк 15-17 днів.\n"
       "Стаття 15-1. Система\n1. Доповнити пунктом 21-1 такого змісту.\n{Із змінами від 01.01.2020}\n")
SAME = OLD.replace("’", "'")
LOST = SAME.replace("Стаття 15-1.", "Стаття 151.").replace("пунктом 21-1", "пунктом 211")


def htm_url(nreg, ed, prefix="laws"):
    return f"https://data.rada.gov.ua/{prefix}/show/{S.encode_nreg(nreg)}/ed{ed}.htm"


def html_page(text, ed, nreg=NREG):
    """Сторінка у форматі HTML API: «15 - 1» з пробілами, апостроф ’, шапка й підвал."""
    t = text.replace("'", "’").replace("Стаття 15-1.", "Стаття 15 - 1 .").replace("пунктом 21-1", "пунктом 21 - 1")
    paras = "".join(f'<p><a name="n{i}"></a>\n{line}</p>\n' for i, line in enumerate(t.strip().split("\n")))
    d = f"{ed[6:8]}.{ed[4:6]}.{ed[:4]}"
    return (f'<html><head><meta name="Nreg" content="{nreg}"><title>Тест</title></head><body>\n'
            f"<h2>Верховна Рада України; Закон від 02.06.2016 № 1-VIII</h2>\n<h1>Тест</h1>\n<h4>Стан: Чинний</h4>\n"
            f"<h5>Ідентифікатор: {nreg}</h5>\n<hr>\n<h3>Текст документа від {d}:</h3>\n<div id=article>\n"
            f"<div><table><tr><td><p>[ image ]</p></td></tr></table></div>\n{paras}</div>\n"
            f"<p>© Офіційний вебпортал парламенту України</p>\n<p>https://www.rada.gov.ua/</p></body></html>")


def vargs(root, **kw):
    base = dict(root=root, nreg=NREG, json=None, repair=True, include_legacy=True, include_conditional=False,
                force=False, api_text_issue=False, request_log=None, pause_min=5.0, pause_max=7.0, timeout=5.0,
                daily_budget_mb=150.0)
    base.update(kw)
    return argparse.Namespace(**base)


def world(api_text, html_text=None, ed="20200101", html_ed=None):
    root = make_archive([(NREG, "А", "Акт", "povna")])
    d = root / "akty" / NREG
    (d / "red").mkdir(parents=True)
    card = {"nreg": NREG, "nazva": "Тест", "rezhym": "povna", "dzherelo": f"https://zakon.rada.gov.ua/laws/show/{NREG}",
            "perevireno": "2026-11-24T00:00:00+00:00", "podii": [],
            "redaktsii": [{"ed": ed, "data": f"{ed[6:8]}.{ed[4:6]}.{ed[:4]}", "opys": "Редакція", "pidstava": [],
                           "tekst": True}]}
    (d / "kartka.json").write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    (d / "red" / f"{ed}.txt").write_text(f"# Тест | редакція від {ed[6:8]}.{ed[4:6]}.{ed[:4]} | Редакція\n\n" + OLD,
                                         encoding="utf-8")
    sess = FakeSession()
    sess.route(txt_url(NREG, ed), body=api_text, headers={"DocumentDate": http_date_for(ed)})
    if html_text is not None:
        sess.route(htm_url(NREG, ed), body=html_page(html_text, html_ed or ed),
                   headers={"DocumentDate": http_date_for(html_ed or ed), "Content-Type": "text/html; charset=utf-8"})
    return root, sess, make_client(root, sess)


def repair(root, client, **kw):
    buf = io.StringIO()
    with mock.patch.object(S, "make_client", lambda a, r: client), redirect_stdout(buf):
        rc = S.run_verify(vargs(root, **kw))
    return rc, buf.getvalue()


def card(root):
    return json.loads((root / "akty" / NREG / "kartka.json").read_text(encoding="utf-8"))


def body_of(root, ed="20200101"):
    return S.split_text_file((root / "akty" / NREG / "red" / f"{ed}.txt").read_text(encoding="utf-8"))[1]


class TestRestore(unittest.TestCase):
    def test_restores_only_superscripts(self):
        fixed, n, why = S.restore_superscripts_from_html(LOST, html_page(SAME, "20200101"), nreg=NREG, ed="20200101")
        self.assertEqual(why, "")
        self.assertEqual(n, 2)
        self.assertEqual(fixed, SAME)  # апостроф і рядки — як у TXT; діапазон 15-17 не зачеплено

    def test_txt_dash_already_present(self):
        fixed, n, why = S.restore_superscripts_from_html(SAME, html_page(SAME, "20200101"))
        self.assertIsNone(fixed)
        self.assertIn("немає верхніх індексів", why)

    def test_content_difference_rejected(self):
        other = LOST.replace("Суддя", "Особа")
        fixed, _, why = S.restore_superscripts_from_html(other, html_page(SAME, "20200101"))
        self.assertIsNone(fixed)
        self.assertIn("відрізняється", why)

    def test_wrong_date_or_act_rejected(self):
        self.assertIn("не 01.01.2020", S.restore_superscripts_from_html(
            LOST, html_page(SAME, "20210101"), ed="20200101")[2])
        self.assertIn("іншому акту", S.restore_superscripts_from_html(
            LOST, html_page(SAME, "20200101", nreg="b-2"), nreg=NREG)[2])


class TestRepairWithHtml(unittest.TestCase):
    def test_legacy_replaced_with_restored_text(self):
        root, sess, client = world(LOST, SAME)
        rc, out = repair(root, client)
        self.assertEqual(rc, 0, out)
        self.assertIn("верхні індекси відновлено за HTML API (2)", out)
        e = card(root)["redaktsii"][0]
        self.assertEqual(e["text_status"], "verified")
        self.assertEqual(e["text_source"], "txt-api+html-api")
        self.assertNotIn("api_text_issue", e)
        self.assertEqual(e["api_text_fix"]["vidnovleno_indeksiv"], 2)
        self.assertEqual(body_of(root), SAME.strip())
        p = root / "akty" / NREG / "red" / "20200101.txt"
        self.assertEqual(S.classify_text_file(p, "20200101", NREG)[0], "verified")

    def test_html_missing_keeps_old_text(self):
        root, _, client = world(LOST)  # .htm → 404
        p = root / "akty" / NREG / "red" / "20200101.txt"
        before = p.read_bytes()
        rc, out = repair(root, client)
        self.assertIn("залишено старий текст", out)
        self.assertIn("HTML API:", out)
        self.assertEqual(p.read_bytes(), before)
        e = card(root)["redaktsii"][0]
        self.assertIn("верхні індекси", e["api_text_issue"])
        self.assertIn("html", e["api_check"])

    def test_html_wrong_document_date_keeps_old_text(self):
        root, _, client = world(LOST, SAME, html_ed="20210101")
        p = root / "akty" / NREG / "red" / "20200101.txt"
        before = p.read_bytes()
        repair(root, client)
        self.assertEqual(p.read_bytes(), before)
        self.assertIn("api_text_issue", card(root)["redaktsii"][0])

    def test_recheck_flagged(self):
        root, sess, client = world(LOST)  # перший прохід: HTML недоступний → позначка
        repair(root, client)
        self.assertIn("api_text_issue", card(root)["redaktsii"][0])
        sess.route(htm_url(NREG, "20200101"), body=html_page(SAME, "20200101"),
                   headers={"DocumentDate": http_date_for("20200101")})
        rc, out = repair(root, client)  # без прапорця — пропущено
        self.assertIn("пропущено", out)
        rc, out = repair(root, client, api_text_issue=True, include_legacy=False)
        self.assertEqual(rc, 0, out)
        e = card(root)["redaktsii"][0]
        self.assertEqual(e["text_status"], "verified")
        self.assertNotIn("api_text_issue", e)
        self.assertEqual(body_of(root), SAME.strip())


class TestSyncNewEditionHtml(unittest.TestCase):
    def test_flagged_verified_edition_fixed_later(self):
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
        client = make_client(root, sess)
        res = S.sync_one(client, root, {"nreg": NREG, "rezhym": "povna", "nazva": "Тест"})
        self.assertTrue(any("втрачено верхні індекси" in w for w in res["warnings"]), res["warnings"])
        self.assertIn("api_text_issue", next(x for x in card(root)["redaktsii"] if x["ed"] == "20210101"))
        sess.route(htm_url(NREG, "20210101"), body=html_page(SAME, "20210101"),
                   headers={"DocumentDate": http_date_for("20210101")})
        rc, out = repair(root, client, api_text_issue=True, include_legacy=False)
        e = next(x for x in card(root)["redaktsii"] if x["ed"] == "20210101")
        self.assertNotIn("api_text_issue", e, out)
        self.assertEqual(e["text_status"], "verified")
        self.assertIn("Стаття 15-1.", body_of(root, "20210101"))

    def test_new_edition_restored(self):
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
        sess.route(htm_url(NREG, "20210101"), body=html_page(SAME, "20210101"),
                   headers={"DocumentDate": http_date_for("20210101")})
        sess.route(txt_url(NREG, "20200101"), body=SAME, headers={"DocumentDate": http_date_for("20200101")})
        client = make_client(root, sess)
        res = S.sync_one(client, root, {"nreg": NREG, "rezhym": "povna", "nazva": "Тест"})
        self.assertFalse(any("втрачено верхні індекси" in w for w in res["warnings"]), res["warnings"])
        new = json.loads((d.parent / "kartka.json").read_text(encoding="utf-8"))
        e = next(x for x in new["redaktsii"] if x["ed"] == "20210101")
        self.assertNotIn("api_text_issue", e)
        self.assertEqual(e["api_text_fix"]["vidnovleno_indeksiv"], 2)
        self.assertIn("Стаття 15-1.", body_of(root, "20210101"))


if __name__ == "__main__":
    unittest.main()
