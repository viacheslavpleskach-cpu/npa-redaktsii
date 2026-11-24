"""C5–C10: sync --all / --changed на тимчасовому архіві з імітацією API."""
import argparse
import hashlib
import json
import unittest
from unittest import mock

from helpers import (S, DOC_UPDATE_URL, PODIA_TXT, PODIA_URL, FakeSession, act_card, card_url,
                     doc_update, http_date_for, make_archive, make_client, txt_url)

TEXT = "Стаття 1. Текст редакції {ed}.\n"


def args_for(root, **kw):
    base = dict(root=root, nreg=None, all=False, changed=False, ed=None, force=False, dry_run=False,
                refresh_doc_update=False, include_conditional=False, request_log=None,
                pause_min=5.0, pause_max=7.0, timeout=5.0, daily_budget_mb=150.0)
    base.update(kw)
    return argparse.Namespace(**base)


class World:
    """Імітація порталу: два акти в API, один поза API (302)."""

    def __init__(self):
        self.root = make_archive([("a-1", "А", "Акт А", "povna"), ("c-1", "Ц", "Акт Ц", "chynna"),
                                  ("n0001415-13", "КСЕ", "Кодекс суддівської етики", "povna")])
        self.sess = FakeSession()
        self.mod = {"a-1": "2026-11-20 09:00:00", "c-1": "2026-11-19 09:00:00"}
        self.status = 5
        self.publish()

    def publish(self):
        s = self.sess
        s.route(PODIA_URL, body=PODIA_TXT)
        s.route(DOC_UPDATE_URL, body=doc_update([
            (self.mod["a-1"], "a-1", "20200101"), (self.mod["a-1"], "a-1", "20210101"),
            (self.mod["c-1"], "c-1", "20190101"), (self.mod["c-1"], "c-1", "20220101")]))
        s.route(card_url("a-1"), body=act_card("a-1", ["20200101", "20210101"], status=self.status,
                                               hist=[{"poddat": "20200101", "podid": 1, "pidstava": ""}]))
        s.route(card_url("c-1"), body=act_card("c-1", ["20190101", "20220101"]))
        for n, eds in (("a-1", ["20200101", "20210101"]), ("c-1", ["20190101", "20220101"])):
            for ed in eds:
                s.route(txt_url(n, ed), body=TEXT.format(ed=ed), headers={"DocumentDate": http_date_for(ed)})
            s.route(txt_url(n), body=TEXT.format(ed=eds[-1]), headers={"DocumentDate": http_date_for(eds[-1])})
        for p in ("laws", "rada"):
            s.route(f"https://data.rada.gov.ua/{p}/card/n0001415-13.json", status=302,
                    headers={"Location": "https://zakon.rada.gov.ua/laws/show/n0001415-13"})

    def run(self, **kw):
        client = make_client(self.root, self.sess)
        with mock.patch.object(S, "make_client", lambda a, r: client):
            rc = S.run_sync(args_for(self.root, **kw))
        return rc, client

    def card(self, n):
        return json.loads((self.root / "akty" / n / "kartka.json").read_text(encoding="utf-8"))

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (self.root / "akty").rglob("*") if p.is_file()}


class TestSyncFlow(unittest.TestCase):
    def test_full_flow(self):
        w = World()
        # Картка КСЕ з архіву (браузерний імпорт), без api.
        (w.root / "akty" / "n0001415-13").mkdir(parents=True)
        (w.root / "akty" / "n0001415-13" / "kartka.json").write_text(
            '{"nreg":"n0001415-13","nazva":"КСЕ","rezhym":"povna","perevireno":"2026-11-10","redaktsii":[],"podii":[]}',
            encoding="utf-8")

        rc, client = w.run(all=True)
        self.assertEqual(rc, 0)
        a = w.card("a-1")
        self.assertTrue(a["api"]["history_complete"])
        self.assertTrue(a["api"]["all_texts_verified"])
        self.assertEqual(a["api"]["doc_update_modified"], "2026-11-20T09:00:00")
        self.assertEqual(a["stan"], "Чинний")
        c = w.card("c-1")
        self.assertFalse(c["api"]["history_complete"])
        self.assertEqual(sorted(p.name for p in (w.root / "akty" / "c-1" / "red").iterdir()), ["20220101.txt"])
        manual = json.loads((w.root / "dani" / "manual_only.json").read_text(encoding="utf-8"))["akty"]
        self.assertIn("n0001415-13", manual)
        self.assertIn("302", " ".join(manual["n0001415-13"]["http"]))
        self.assertTrue(manual["n0001415-13"]["checked_at"])

        # C10: повторний --all — ідемпотентно (файли не змінюються).
        snap = w.snapshot()
        rc, _ = w.run(all=True)
        self.assertEqual(rc, 0)
        self.assertEqual(w.snapshot(), snap)

        # C6: --changed одразу — no-op; карток не запитує; ручний акт пропущено як нещодавно перевірений.
        n0 = len(w.sess.calls)
        rc, _ = w.run(changed=True)
        self.assertEqual(rc, 0)
        urls = [u for u, _h in w.sess.calls[n0:]]
        self.assertEqual(urls, [DOC_UPDATE_URL])
        self.assertEqual(w.snapshot(), snap)
        perev = json.loads((w.root / "dani" / "perevirka.json").read_text(encoding="utf-8"))
        self.assertIn("a-1", perev)

        # C7: modified змінився, ed ті самі → картку оновлено, тексти не завантажуються.
        w.mod["a-1"] = "2026-11-23 08:00:00"
        w.status = 1
        w.publish()
        n0 = len(w.sess.calls)
        rc, _ = w.run(changed=True)
        self.assertEqual(rc, 0)
        urls = [u for u, _h in w.sess.calls[n0:]]
        self.assertIn(card_url("a-1"), urls)
        self.assertFalse(any(u.endswith(".txt") and "/show/" in u for u in urls))
        a = w.card("a-1")
        self.assertEqual(a["api"]["doc_update_modified"], "2026-11-23T08:00:00")
        self.assertEqual(a["stan"], "Втратив чинність")                         # C8: статус оновлено

    def test_not_in_doc_update_is_not_manual(self):
        w = World()
        w.sess.route(card_url("n0001415-13"), body=act_card("n0001415-13", ["20240918"]))
        w.sess.route(txt_url("n0001415-13", "20240918"), body="Стаття 1. Текст.\n",
                     headers={"DocumentDate": http_date_for("20240918")})
        (w.root / "akty" / "n0001415-13").mkdir(parents=True)
        (w.root / "akty" / "n0001415-13" / "kartka.json").write_text(
            '{"nreg":"n0001415-13","nazva":"КСЕ","rezhym":"povna","perevireno":"2026-11-10","redaktsii":[],"podii":[]}',
            encoding="utf-8")
        ok, why = S._is_row_changed(w.root, {"nreg": "n0001415-13", "rezhym": "povna"}, set())
        self.assertTrue(ok)
        self.assertIn("перевіряю JSON-картку", why)
        rc, _ = w.run(nreg="n0001415-13")
        self.assertEqual(rc, 0)
        self.assertFalse((w.root / "dani" / "manual_only.json").exists())

    def test_wrong_documentdate_writes_nothing(self):
        w = World()
        w.sess.route(txt_url("a-1", "20200101"), body="підмінений текст", headers={"DocumentDate": http_date_for("20210101")})
        rc, _ = w.run(nreg="a-1")
        self.assertEqual(rc, 1)
        self.assertFalse((w.root / "akty" / "a-1" / "red" / "20200101.txt").exists())
        self.assertTrue((w.root / "akty" / "a-1" / "red" / "20210101.txt").exists())

    def test_existing_corrupt_not_hidden(self):
        w = World()
        w.run(nreg="a-1")
        p = w.root / "akty" / "a-1" / "red" / "20200101.txt"
        p.write_text(p.read_text(encoding="utf-8") + "зайвий рядок\n", encoding="utf-8")
        before = p.read_bytes()
        rc, _ = w.run(nreg="a-1")
        a = w.card("a-1")
        st = {x["ed"]: x["text_status"] for x in a["redaktsii"]}
        self.assertEqual(st["20200101"], "corrupt")
        self.assertFalse(a["api"]["all_texts_verified"])
        self.assertEqual(p.read_bytes(), before)                                  # не перезаписано

    def test_unparsed_modified_falls_back_to_card(self):
        w = World()
        w.run(all=True)
        w.sess.route(DOC_UPDATE_URL, body=doc_update([("???", "a-1", "20200101"), ("???", "a-1", "20210101"),
                                                       ("2026-11-19 09:00:00", "c-1", "20190101"),
                                                       ("2026-11-19 09:00:00", "c-1", "20220101")]))
        n0 = len(w.sess.calls)
        w.run(changed=True, refresh_doc_update=True)
        urls = [u for u, _h in w.sess.calls[n0:]]
        self.assertIn(card_url("a-1"), urls)
        self.assertNotIn(card_url("c-1"), urls)


if __name__ == "__main__":
    unittest.main()
