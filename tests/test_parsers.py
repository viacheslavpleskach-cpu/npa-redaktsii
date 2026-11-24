"""A1–A5: парсери дат, ідентифікаторів, doc-update, podia, JSON-картки."""
import unittest

from helpers import S, PODIA_TXT, doc_update


class TestDates(unittest.TestCase):
    def test_parse_yyyymmdd(self):
        self.assertEqual(S.parse_yyyymmdd("20240229"), "20240229")      # високосний
        self.assertIsNone(S.parse_yyyymmdd("20230229"))                  # невисокосний
        self.assertEqual(S.parse_yyyymmdd("2019-10-21"), "20191021")
        self.assertEqual(S.parse_yyyymmdd("21.10.2019"), "20191021")
        self.assertIsNone(S.parse_yyyymmdd("20191321"))
        self.assertIsNone(S.parse_yyyymmdd(""))
        self.assertIsNone(S.parse_yyyymmdd(None))

    def test_valid_edition_id(self):
        self.assertEqual(S.valid_edition_id("20191021"), "20191021")
        self.assertEqual(S.valid_edition_id("30000101"), "30000101")
        self.assertIsNone(S.valid_edition_id("201301186"))               # 9 цифр (2343-12)
        self.assertIsNone(S.valid_edition_id("2013011"))
        self.assertIsNone(S.valid_edition_id("300001011"))

    def test_invalid_reason(self):
        self.assertEqual(S.invalid_edition_reason("201301186"), "9 цифр замість 8")
        self.assertEqual(S.invalid_edition_reason("20130230"), "неіснуюча календарна дата")
        self.assertEqual(S.invalid_edition_reason("2013-x"), "містить нецифрові символи")

    def test_parse_modified(self):
        self.assertEqual(S.parse_modified("2026-11-21 10:15:00"), "2026-11-21T10:15:00")
        self.assertEqual(S.parse_modified("20261121101500"), "2026-11-21T10:15:00")
        self.assertEqual(S.parse_modified("21.11.2026 10:15"), "2026-11-21T10:15:00")
        self.assertEqual(S.parse_modified("2026-11-21T10:15:00.123+02:00"), "2026-11-21T10:15:00")
        self.assertEqual(S.parse_modified("1763720100"), "2025-11-21T10:15:00")
        self.assertIsNone(S.parse_modified("вчора"))
        self.assertIsNone(S.parse_modified("12"))
        self.assertIsNone(S.parse_modified(""))


class TestDocUpdate(unittest.TestCase):
    def test_real_format_multi_rows_and_max_modified(self):
        raw = doc_update([
            ("2026-11-01 08:00:00", "2343-12", "20191021"),
            ("2026-11-20 09:30:00", "2343-12", "20180404"),
            ("2026-11-05 12:00:00", "2343-12", "201301186"),
            ("2026-11-05 12:00:00", "2343-12", "201301186"),   # дубль аномалії
            ("2026-10-01 00:00:00", "2747-15", "30000101"),
        ])
        by, st = S.parse_doc_update(raw)
        self.assertEqual(by["2343-12"], {"20191021", "20180404"})
        self.assertEqual(st["invalid_by_nreg"]["2343-12"], ["201301186"])   # без повтору
        self.assertEqual(st["modified_by_nreg"]["2343-12"], "2026-11-20T09:30:00")
        self.assertEqual(by["2747-15"], set())                              # умовні в bulk не йдуть
        self.assertEqual(st["invalid_modified"], 0)

    def test_header_row_and_unknown_modified(self):
        raw = ("modified\tnreg\ted\n" "незрозуміло\t1618-15\t20240101\n" "2026-01-02 00:00:00\t1618-15\t20240201\n").encode("cp1251")
        by, st = S.parse_doc_update(raw)
        self.assertEqual(by["1618-15"], {"20240101", "20240201"})
        self.assertEqual(st["modified_by_nreg"]["1618-15"], "2026-01-02T00:00:00")
        self.assertEqual(st["modified_unparsed"]["1618-15"], ["незрозуміло"])
        self.assertEqual(st["invalid_modified"], 1)

    def test_empty_raises(self):
        with self.assertRaises(S.SyncError):
            S.parse_doc_update(b"")

    def test_cp1251_and_utf8(self):
        raw = "2026-01-02 00:00:00\t254к/96-вр\t20200101\n"
        for enc in ("cp1251", "utf-8"):
            by, _ = S.parse_doc_update(raw.encode(enc))
            self.assertIn("254к/96-вр", by)


class TestPodia(unittest.TestCase):
    def test_parse_podia(self):
        m = S.parse_podia(PODIA_TXT)
        self.assertEqual(m["25"], "Визнання неконституційними окремих положень")
        self.assertEqual(m["0"], "Редакція")

    def test_empty_unknown_dup(self):
        raw = "x\tнезрозуміле\n7\t\n8\tПерше\n8\tДруге\n".encode("cp1251")
        m = S.parse_podia(raw)
        self.assertNotIn("x", m)
        self.assertNotIn("7", m)
        self.assertEqual(m["8"], "Друге")   # останнє значення; дубль ID не ламає розбір


class TestJsonCard(unittest.TestCase):
    def test_fields(self):
        podia = S.parse_podia(PODIA_TXT)
        data = {"nreg": "2747-15", "nazva": "КАС", "status": 5, "edcnt": 3, "datred": "20230323",
                "orgdat": "20050706", "orgnum": "2747-IV",
                "eds": [{"datred": "20050706", "podid": 4, "pidstava": ""},
                        {"datred": "20230323", "podid": 0, "pidstava": "2147-19"},
                        {"datred": "30000101", "podid": 0, "pidstava": "4840-20",
                         "comment": "вводиться в дію з дня припинення воєнного стану"}],
                "hist": [{"poddat": "20230323", "podid": 0, "pidstava": "2147-19"},
                         {"poddat": "20200101", "podid": 25, "pidstava": "v001p710-20"},
                         {"poddat": "20200101", "podid": 99, "pidstava": ""}]}
        p = S.parse_json_card(data, podia=podia)
        eds = {x["ed"]: x for x in p["redaktsii"]}
        self.assertEqual(set(eds), {"20050706", "20230323", "30000101"})
        self.assertEqual(eds["30000101"]["comment"], "вводиться в дію з дня припинення воєнного стану")
        self.assertEqual(eds["20050706"]["opys"], "Прийняття")
        self.assertEqual(eds["20230323"]["pidstava_nreg"], ["2147-19"])
        self.assertEqual([e["podid"] for e in p["podii"]], ["25", "99"])           # podid 0 не дублюється
        self.assertEqual(p["podii"][1]["opys"], "Подія бази ВРУ (podid=99)")       # невідомий не відкинуто
        self.assertEqual(p["orgdat"], "20050706")
        self.assertEqual(p["status_id"], "5")
        self.assertTrue(p["edition_catalog_complete"])


if __name__ == "__main__":
    unittest.main()
