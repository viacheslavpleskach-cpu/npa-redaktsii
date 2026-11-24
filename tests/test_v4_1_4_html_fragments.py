"""Короткі HTML-фрагменти (v4.1.4, аудит v4.1.3, розд. 3.1): не можуть стати текстом редакції чи «дублем»."""
import argparse
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from helpers import S, FakeSession, act_card, card_url, http_date_for, make_archive, make_client, make_response, txt_url
from test_v4_1_1_regressions import write_card

FRAGMENTS = {
    "div_p": "<div><p>Помилка</p></div>",                                   # приклади аудиту
    "section_h1": "<section><h1>Помилка</h1></section>",
    "main_h1_p": "<main><h1>Помилка</h1><p>Немає даних</p></main>",
    "single_p": "<p>Немає даних</p>",
    "h1_404": "<h1>404 Not Found</h1>",
    "comment_then_main": "<!-- err --><main>Немає даних</main>",
    "xml_error": "<?xml version=\"1.0\"?><error><code>500</code></error>",
    "text_then_pair": "Помилка сервера: <main>Немає даних</main> спробуйте пізніше",
    "custom_tag_pair": "Відповідь: <error-message>Документ не знайдено</error-message>",
}

LEGAL = {
    "inequality": "Стаття 7. Ставка становить < 5 відсотків і > 2 відсотків від суми.",
    "no_space_ineq": "Умова x<y та y>z застосовується, якщо інше не встановлено законом.",
    "cyrillic_placeholder": "У формі зазначається «<підпис>» і «<дата>» особи, яка подає заяву.",
    "double_angle": "Назва <<Про судоустрій>> у документі взята в подвійні кутові дужки.",
    "word_html": "Сторінка у форматі html або body-текст згадується як приклад. " * 10,
    # v4.1.5 (аудит v4.1.4): кириличне позначення на початку тексту — не тег.
    "cyrillic_placeholder_at_start": "<підпис> __________________",
    "cyrillic_upper_at_start": "<ПІБ> заявника ________ <дата> ________",
    "cyrillic_at_start_long": "<підпис керівника>\nСтаття 1. Порядок застосовується до всіх судів. " * 5,
}


class TestShortFragments(unittest.TestCase):
    def test_fragments_detected(self):
        for name, body in FRAGMENTS.items():
            with self.subTest(name):
                self.assertTrue(S.looks_like_html(body), name)
                r = make_response("https://data.rada.gov.ua/x.txt", 200, body.encode("utf-8"),
                                  {"Content-Type": "text/plain; charset=utf-8"})
                self.assertTrue(S.txt_response_problem(r), name)

    def test_legal_texts_not_detected(self):
        for name, body in LEGAL.items():
            with self.subTest(name):
                self.assertFalse(S.looks_like_html(body), name)

    def test_fetch_verified_text_rejects_fragments(self):
        for name, body in FRAGMENTS.items():
            with self.subTest(name):
                root = make_archive([("a-1", "А", "Акт", "povna")])
                sess = FakeSession()
                sess.route(txt_url("a-1", "20200101"), body=body,
                           headers={"DocumentDate": http_date_for("20200101"), "Content-Type": "text/plain"})
                with self.assertRaises(S.SyncError):
                    make_client(root, sess).fetch_verified_text("a-1", "20200101", "laws")

    def test_anomaly_never_duplicate_for_fragments(self):
        for name, body in FRAGMENTS.items():
            with self.subTest(name):
                root = make_archive([("2343-12", "Б", "Банкрутство", "povna")])
                write_card(root, "2343-12", ["20130118", "20191021"])
                sess = FakeSession()
                sess.route(card_url("2343-12"), body=act_card("2343-12", ["20130118", "20191021"], edcnt=3))
                hdr = {"DocumentDate": http_date_for("20130118"), "Content-Type": "text/plain"}
                sess.route(txt_url("2343-12", "201301186"), body=body, headers=hdr)
                sess.route(txt_url("2343-12", "20130118"), body=body, headers=hdr)
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
                self.assertNotIn("resolved_edition_ids", json.loads(before.decode("utf-8")).get("api", {}))


if __name__ == "__main__":
    unittest.main()
