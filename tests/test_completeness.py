"""A6, розд. 2 і 6 ТЗ: повнота каталогу редакцій (2343-12 / 201301186)."""
import datetime as dt
import unittest

from helpers import S, act_card, make_archive


def eds_74():
    """74 різні коректні дати, серед них 20130118 (як у 2343-12)."""
    start = dt.date(1992, 7, 1)
    eds = sorted({(start + dt.timedelta(days=97 * i)).strftime("%Y%m%d") for i in range(73)} | {"20130118"})
    assert len(eds) == 74, len(eds)
    return eds


def old_v4_formula(parsed_valid: int, invalid_eds: int, bulk_invalid: int, edcnt: int) -> bool:
    return parsed_valid + invalid_eds + bulk_invalid >= edcnt


class Test2343_12(unittest.TestCase):
    def setUp(self):
        self.eds = eds_74()
        self.data = act_card("2343-12", self.eds, edcnt=75,
                             extra_eds=[{"datred": "201301186", "podid": 0, "pidstava": ""}])

    def test_no_double_count_and_unresolved(self):
        p = S.parse_json_card(self.data, bulk_editions=self.eds, bulk_invalid=["201301186", "201301186"])
        self.assertFalse(p["history_complete"])
        self.assertFalse(p["edition_catalog_complete"])
        self.assertEqual(p["unresolved_edition_ids"], ["201301186"])
        self.assertEqual(p["counts"]["invalid_unique"], 1)
        self.assertEqual(p["counts"]["edcnt"], 75)
        self.assertEqual(p["counts"]["json_valid_dates"], 74)
        srcs = sorted((r["source"], r["raw"]) for r in p["invalid_source_records"])
        self.assertEqual(srcs, [("doc-update", "201301186"), ("eds", "201301186")])   # походження збережено
        self.assertIn("201301186", p["catalog_reason"])
        # Регресія: формула v4 дала б «повно» (74 + 1 + 2 ≥ 75).
        self.assertTrue(old_v4_formula(74, 1, 2, 75))

    def test_only_in_doc_update(self):
        data = act_card("2343-12", self.eds, edcnt=75)
        p = S.parse_json_card(data, bulk_invalid=["201301186"])
        self.assertFalse(p["history_complete"])
        self.assertEqual(p["unresolved_edition_ids"], ["201301186"])

    def test_resolved_documented(self):
        p = S.parse_json_card(self.data, bulk_invalid=["201301186"], resolved_ids=["201301186"])
        self.assertTrue(p["edition_catalog_complete"])
        self.assertEqual(p["unresolved_edition_ids"], [])
        self.assertIn("вирішені аномалії", p["catalog_reason"])

    def test_missing_edition_is_incomplete(self):
        data = act_card("x-1", self.eds[:70], edcnt=74)
        p = S.parse_json_card(data)
        self.assertFalse(p["history_complete"])
        self.assertIn("70 редакцій із 74", p["catalog_reason"])

    def test_no_edcnt(self):
        data = act_card("x-2", self.eds[:3], edcnt=0)
        self.assertFalse(S.parse_json_card(data)["history_complete"])


class TestModesInCard(unittest.TestCase):
    def _card(self, mode, data, **kw):
        root = make_archive([(data["nreg"], "T", "Т", mode)])
        p = S.parse_json_card(data, **kw)
        return S.normalized_card(root, data["nreg"], {"nreg": data["nreg"], "rezhym": mode}, p, "2026-11-23T00:00:00+00:00")

    def test_povna_complete(self):
        c = self._card("povna", act_card("a-1", ["20200101", "20210101"]))
        self.assertTrue(c["api"]["history_complete"])
        self.assertFalse(c["api"]["all_texts_verified"])          # текстів ще немає
        self.assertEqual(c["api"]["texts"]["missing"], 2)

    def test_chynna_and_odyn_never_complete(self):
        for mode in ("chynna", "odyn"):
            c = self._card(mode, act_card("a-2", ["20200101", "20210101"]))
            self.assertFalse(c["api"]["history_complete"], mode)
            self.assertTrue(c["api"]["edition_catalog_complete"], mode)   # каталог окремо від режиму
            self.assertIn("режим", c["api"]["history_reason"])
            self.assertEqual(c["api"]["texts"]["expected"], 1)

    def test_snapshot_without_history(self):
        data = {"result": "ok", "nreg": "s-1", "nazva": "Знімок", "status": 5}
        c = self._card("povna", data, bulk_editions=["20240101"])
        self.assertTrue(c["api"]["snapshot_only"])
        self.assertFalse(c["api"]["history_complete"])
        self.assertEqual(len(c["redaktsii"]), 1)


if __name__ == "__main__":
    unittest.main()
