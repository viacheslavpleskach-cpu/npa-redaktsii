"""Граничні випадки розпізнавання HTML (v4.1.3, рекомендація аудиту v4.1.2, розд. 4).

Мета: жодна HTML-відповідь не може стати текстом редакції або доказом дубля в anomaly.
"""
import argparse
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from helpers import S, FakeSession, act_card, card_url, http_date_for, make_archive, make_client, txt_url
from test_v4_1_1_regressions import write_card

FILLER = "Стаття 1. Звичайний текст закону без розмітки. " * 30          # > 500 символів

HTML_CASES = {
    "comment_before_html": "<!-- згенеровано сервером -->\n<!-- ще коментар -->\n<html><head><title>Т</title></head><body>x</body></html>",
    "head_without_body": "<head><title>Законодавство України</title><meta charset=\"utf-8\"></head>\nТекст без body",
    "bom_doctype": "﻿<!DOCTYPE html>\n<html><body>сторінка</body></html>",
    "bom_and_spaces_html": "﻿ \r\n\t<HTML><BODY>сторінка</BODY></HTML>",
    "xml_declaration": "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<html xmlns=\"http://www.w3.org/1999/xhtml\"><body>x</body></html>",
    "markers_after_500": FILLER + "\n<html><body>далі сторінка</body></html>",
    "markers_only_at_end": FILLER * 5 + "\n</div></body></html>",
    "fragment_no_markers_dense_tags": FILLER * 10 + "<div><p>а</p><p>б</p><span>в</span><table><tr><td>г</td></tr></table></div>",
    "uppercase_doctype": "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01//EN\">\n<HTML>",
}

NOT_HTML = {
    "plain_law": "Стаття 5. Розмір штрафу становить < 10 і > 3 неоподатковуваних мінімумів.\nСтаття 6. Текст.",
    "angle_brackets_in_text": "Порівняння: a<b, b>c; формула <x> позначає змінну. " * 20,
    "word_html_in_text": "Сторінка у форматі html або body-текст згадується у статті як приклад. " * 10,
}


class TestLooksLikeHtml(unittest.TestCase):
    def test_html_cases_detected(self):
        for name, body in HTML_CASES.items():
            with self.subTest(name):
                self.assertTrue(S.looks_like_html(body), name)

    def test_plain_text_not_detected(self):
        for name, body in NOT_HTML.items():
            with self.subTest(name):
                self.assertFalse(S.looks_like_html(body), name)

    def test_txt_response_problem_for_each_html_case(self):
        for name, body in HTML_CASES.items():
            with self.subTest(name):
                from helpers import make_response
                r = make_response("https://data.rada.gov.ua/x.txt", 200, body.encode("utf-8"),
                                  {"Content-Type": "text/plain; charset=utf-8"})
                self.assertTrue(S.txt_response_problem(r), name)


class TestHtmlNeverBecomesEdition(unittest.TestCase):
    def test_fetch_verified_text_rejects_html(self):
        for name, body in HTML_CASES.items():
            with self.subTest(name):
                root = make_archive([("a-1", "А", "Акт", "povna")])
                sess = FakeSession()
                sess.route(txt_url("a-1", "20200101"), body=body,
                           headers={"DocumentDate": http_date_for("20200101"), "Content-Type": "text/plain"})
                client = make_client(root, sess)
                with self.assertRaises(S.SyncError):
                    client.fetch_verified_text("a-1", "20200101", "laws")

    def test_anomaly_never_duplicate_for_html(self):
        for name, body in HTML_CASES.items():
            with self.subTest(name):
                root = make_archive([("2343-12", "Б", "Банкрутство", "povna")])
                write_card(root, "2343-12", ["20130118", "20191021"])
                sess = FakeSession()
                sess.route(card_url("2343-12"), body=act_card("2343-12", ["20130118", "20191021"], edcnt=3))
                hdr = {"DocumentDate": http_date_for("20130118"), "Content-Type": "text/plain"}
                sess.route(txt_url("2343-12", "201301186"), body=body, headers=hdr)
                sess.route(txt_url("2343-12", "20130118"), body=body, headers=hdr)     # однакові сторінки
                client = make_client(root, sess)
                a = argparse.Namespace(root=root, nreg="2343-12", raw="201301186", record=True, request_log=None,
                                       pause_min=5.0, pause_max=7.0, timeout=5.0, daily_budget_mb=150.0)
                before = (root / "akty" / "2343-12" / "kartka.json").read_bytes()
                with mock.patch.object(S, "make_client", lambda x, r: client):
                    buf = io.StringIO()
                    with redirect_stdout(buf):
                        S.run_anomaly(a)
                self.assertNotIn("duplicate_of", buf.getvalue(), name)
                self.assertEqual((root / "akty" / "2343-12" / "kartka.json").read_bytes(), before, name)
                self.assertNotIn("resolved_edition_ids",
                                 json.loads(before.decode("utf-8")).get("api", {}))


if __name__ == "__main__":
    unittest.main()
