"""A12 і розд. 5 ТЗ: перевірка цілісності наявних текстів (verify)."""
import argparse
import hashlib
import unittest

from helpers import S, make_archive

TEXT = "Стаття 1. Текст редакції.\nСтаття 2. Інший текст.\n"


def write_v41(root, nreg, ed, text=TEXT):
    card = {"nazva": "Тест", "dzherelo": f"https://zakon.rada.gov.ua/laws/show/{nreg}"}
    body = S.clean_plain_text(text)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return S.write_text_file(root, nreg, card, ed, body, {"opys": "Редакція"}, ed, digest)


def write_legacy(root, nreg, ed, header_date):
    p = root / "akty" / nreg / "red" / f"{ed}.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"# Тест | редакція від {header_date} | Редакція\n# Підстава: —\n"
                 f"# Джерело: https://zakon.rada.gov.ua/laws/show/{nreg}/ed{ed} (© Верховна Рада України, CC BY 4.0)\n\n"
                 + TEXT, encoding="utf-8")
    return p


class TestClassify(unittest.TestCase):
    def setUp(self):
        self.root = make_archive([("a-1", "А", "Акт", "povna")])

    def test_verified(self):
        p = write_v41(self.root, "a-1", "20200101")
        self.assertEqual(S.classify_text_file(p, "20200101", "a-1")[0], "verified")

    def test_crlf_checkout_still_verified(self):
        p = write_v41(self.root, "a-1", "20200101")
        p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))   # як після git checkout з autocrlf
        self.assertEqual(S.classify_text_file(p, "20200101", "a-1")[0], "verified")

    def test_one_byte_changed_is_corrupt(self):
        p = write_v41(self.root, "a-1", "20200101")
        data = bytearray(p.read_bytes())
        data[-5] ^= 1
        p.write_bytes(bytes(data))
        self.assertEqual(S.classify_text_file(p, "20200101", "a-1")[0], "corrupt")

    def test_wrong_documentdate(self):
        p = write_v41(self.root, "a-1", "20200101")
        target = p.with_name("20200202.txt")
        target.write_bytes(p.read_bytes().replace(b"/ed20200101", b"/ed20200202"))
        st, detail = S.classify_text_file(target, "20200202", "a-1")
        self.assertEqual(st, "date_mismatch", detail)

    def test_legacy(self):
        p = write_legacy(self.root, "a-1", "20200101", "01.01.2020")
        self.assertEqual(S.classify_text_file(p, "20200101", "a-1")[0], "legacy_unverified")
        q = write_legacy(self.root, "a-1", "20200303", "01.01.2020")
        self.assertEqual(S.classify_text_file(q, "20200303", "a-1")[0], "date_mismatch")

    def test_missing_and_empty(self):
        self.assertEqual(S.classify_text_file(self.root / "nema.txt", "20200101")[0], "missing")
        e = self.root / "akty" / "a-1" / "red" / "20210101.txt"
        e.parent.mkdir(parents=True, exist_ok=True)
        e.write_text("# шапка\n\n", encoding="utf-8")
        self.assertEqual(S.classify_text_file(e, "20210101")[0], "corrupt")

    def test_verify_changes_nothing(self):
        write_v41(self.root, "a-1", "20200101")
        write_legacy(self.root, "a-1", "20190101", "01.01.2019")
        bad = write_v41(self.root, "a-1", "20180101")
        bad.write_text(bad.read_text(encoding="utf-8") + "зайве\n", encoding="utf-8")
        (self.root / "akty" / "a-1" / "kartka.json").write_text(
            '{"nreg":"a-1","nazva":"Т","rezhym":"povna","redaktsii":[{"ed":"20170101"},{"ed":"20180101"},'
            '{"ed":"20190101"},{"ed":"20200101"}],"podii":[]}', encoding="utf-8")
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob("*") if p.is_file()}
        args = argparse.Namespace(root=self.root, nreg=None, json=str(self.root / "out" / "v.json"), repair=False,
                                  include_legacy=False, include_conditional=False, request_log=None,
                                  pause_min=5.0, pause_max=7.0, timeout=5.0, daily_budget_mb=1.0)
        rc = S.run_verify(args)
        self.assertEqual(rc, 1)   # є corrupt
        after = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}
        self.assertEqual(before, after)
        import json
        rep = json.loads((self.root / "out" / "v.json").read_text(encoding="utf-8"))
        self.assertEqual(rep["total"], {"verified": 1, "legacy_unverified": 1, "corrupt": 1, "date_mismatch": 0, "missing": 1})


if __name__ == "__main__":
    unittest.main()
