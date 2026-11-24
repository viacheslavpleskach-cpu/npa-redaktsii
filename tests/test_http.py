"""B1–B12: HTTP-клієнт з імітацією сесії (без мережі й без реальних пауз)."""
import unittest

from helpers import (S, DOC_UPDATE_URL, FakeSession, conditional_stamp, doc_update,
                     http_date_for, make_client, make_response, tmpdir, txt_url)

TEXT = "Стаття 1. Тестовий текст редакції.\nСтаття 2. Ще текст.\n"


class TestHTTP(unittest.TestCase):
    def setUp(self):
        self.root = tmpdir()
        self.sess = FakeSession()
        self.client = make_client(self.root, self.sess)

    def test_user_agent_and_injected_pause(self):
        self.sess.route(txt_url("a-1", "20200101"), body=TEXT, headers={"DocumentDate": http_date_for("20200101")})
        self.client.fetch_verified_text("a-1", "20200101", "laws")
        self.client.fetch_verified_text("a-1", "20200101", "laws")
        self.assertTrue(all(ua == "OpenData" for ua in self.sess.ua_seen))
        self.assertEqual(len(self.client.sleeps), 1)
        self.assertTrue(5.0 <= self.client.sleeps[0] <= 7.0)

    def test_correct_date_accepted_wrong_rejected(self):
        self.sess.route(txt_url("a-1", "20200101"), body=TEXT, headers={"DocumentDate": http_date_for("20200101")})
        body, *_rest = self.client.fetch_verified_text("a-1", "20200101", "laws")
        self.assertIn("Стаття 1", body)
        self.sess.route(txt_url("a-1", "20190101"), body=TEXT, headers={"DocumentDate": http_date_for("20200101")})
        with self.assertRaises(S.EditionDateMismatch):
            self.client.fetch_verified_text("a-1", "20190101", "laws")

    def test_missing_or_bad_documentdate(self):
        self.sess.route(txt_url("a-1", "20200101"), body=TEXT)
        with self.assertRaises(S.EditionDateMismatch):
            self.client.fetch_verified_text("a-1", "20200101", "laws")
        self.sess.route(txt_url("a-1", "20200102"), body=TEXT, headers={"DocumentDate": "сміття"})
        with self.assertRaises(S.EditionDateMismatch):
            self.client.fetch_verified_text("a-1", "20200102", "laws")

    def test_conditional_exact_only(self):
        for ed in ("30000101", "30000102", "30000103", "30000104"):
            self.sess.route(txt_url("2747-15", ed), body=TEXT, headers={"DocumentDate": conditional_stamp(ed)})
            *_r, actual, _src = self.client.fetch_verified_text("2747-15", ed, "laws", allow_conditional=True)
            self.assertEqual(actual, ed)
        self.sess.route(txt_url("2747-15", "30000105"), body=TEXT, headers={"DocumentDate": conditional_stamp("30000105", 1)})
        with self.assertRaises(S.EditionDateMismatch):
            self.client.fetch_verified_text("2747-15", "30000105", "laws", allow_conditional=True)
        self.sess.route(txt_url("2747-15", "30000106"), body=TEXT, headers={"DocumentDate": "abc"})
        with self.assertRaises(S.EditionDateMismatch):
            self.client.fetch_verified_text("2747-15", "30000106", "laws", allow_conditional=True)
        self.sess.route(txt_url("2747-15", "30000107"), body=TEXT, headers={"DocumentDate": conditional_stamp("30000107")})
        with self.assertRaises(S.EditionDateMismatch):   # без allow_conditional — відмова
            self.client.fetch_verified_text("2747-15", "30000107", "laws")

    def test_redirect_is_manual_and_no_html(self):
        for p in ("laws", "rada"):
            self.sess.route(f"https://data.rada.gov.ua/{p}/card/n0001415-13.json", status=302,
                            headers={"Location": "https://zakon.rada.gov.ua/laws/show/n0001415-13"})
        with self.assertRaises(S.ManualOnlyError):
            self.client.fetch_card("n0001415-13")
        self.assertTrue(all("data.rada.gov.ua" in u for u, _h in self.sess.calls))
        self.assertEqual(len(self.client.manual_evidence["n0001415-13"]["http"]), 2)
        with self.assertRaises(S.SyncError):
            self.client.get("https://zakon.rada.gov.ua/laws/show/2747-15")   # не data.rada — відмова до запиту

    def test_403_429_stop_all(self):
        for code in (403, 429):
            sess = FakeSession()
            client = make_client(self.root, sess)
            sess.route(txt_url("a-1"), status=code)
            with self.assertRaises(S.SyncError):
                client.get(txt_url("a-1"))
            n = len(sess.calls)
            with self.assertRaises(S.SyncError):
                client.get(txt_url("a-2"))
            self.assertEqual(len(sess.calls), n, f"після {code} запит не мав піти")

    def test_content_length_over_budget_not_read(self):
        client = make_client(self.root, self.sess, budget=1000)
        body = b"x" * 5000
        resp = make_response(txt_url("big"), 200, body, {"DocumentDate": http_date_for("20200101")})
        self.sess.routes[txt_url("big")] = lambda h: resp
        with self.assertRaises(S.BudgetExceeded):
            client.get(txt_url("big"))
        self.assertEqual(resp.raw.reads, 0)

    def test_unknown_length_stream_stops(self):
        client = make_client(self.root, self.sess, budget=20000)
        resp = make_response(txt_url("big2"), 200, b"y" * 100000, {}, send_length=False)
        self.sess.routes[txt_url("big2")] = lambda h: resp
        with self.assertRaises(S.BudgetExceeded):
            client.get(txt_url("big2"))
        self.assertLess(resp.raw.max_pos, 100000)
        self.assertEqual(client.stats["interrupted"], 1)

    def test_304_uses_cache_without_rewrite(self):
        raw = doc_update([("2026-11-01 08:00:00", "a-1", "20200101")])
        self.sess.route(DOC_UPDATE_URL, body=raw, headers={"Last-Modified": "Sun, 22 Nov 2026 10:00:00 GMT"})
        self.client.fetch_doc_update()
        cache = self.root / ".npa_cache" / "doc-update.txt"
        mtime = cache.stat().st_mtime_ns
        self.sess.route(DOC_UPDATE_URL, status=304)
        by, st = self.client.fetch_doc_update()
        self.assertTrue(st["used_cache"])
        self.assertEqual(by["a-1"], {"20200101"})
        self.assertEqual(cache.stat().st_mtime_ns, mtime)
        self.assertEqual(self.sess.calls[-1][1].get("If-Modified-Since"), "Sun, 22 Nov 2026 10:00:00 GMT")

    def test_interrupted_stream_leaves_no_file(self):
        resp = make_response(txt_url("a-9", "20200101"), 200, TEXT.encode() * 2000,
                             {"DocumentDate": http_date_for("20200101")}, fail_after=8192)
        self.sess.routes[txt_url("a-9", "20200101")] = lambda h: resp
        with self.assertRaises(S.SyncError):
            self.client.fetch_verified_text("a-9", "20200101", "laws")
        self.assertFalse((self.root / "akty").exists())

    def test_podia_refresh_conditional(self):
        from helpers import PODIA_URL, PODIA_TXT
        self.sess.route(PODIA_URL, body=PODIA_TXT, headers={"Last-Modified": "Sat, 21 Nov 2026 00:00:00 GMT"})
        self.assertEqual(self.client.fetch_podia()["25"], "Визнання неконституційними окремих положень")
        n = len(self.sess.calls)
        self.client.fetch_podia()                                         # у межах запуску — без запиту
        self.assertEqual(len(self.sess.calls), n)
        c2 = make_client(self.root, self.sess)                             # той самий день — з кешу
        c2.fetch_podia()
        self.assertEqual(len(self.sess.calls), n)
        self.sess.route(PODIA_URL, status=304)
        c3 = make_client(self.root, self.sess)
        self.assertEqual(c3.fetch_podia(refresh=True)["0"], "Редакція")      # 304 → кеш
        self.assertEqual(self.sess.calls[-1][1].get("If-Modified-Since"), "Sat, 21 Nov 2026 00:00:00 GMT")
        self.assertEqual(c3.state["podia_entries"], 6)


if __name__ == "__main__":
    unittest.main()
