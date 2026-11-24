"""A7–A10: status=0, злиття подій, підстави редакцій, опис редакції."""
import unittest

from helpers import S, FakeSession, card_url, make_client, tmpdir


class TestStatus(unittest.TestCase):
    def test_explicit_zero_clears(self):
        stan, sid, warn = S.resolve_status({"status": 0}, {"stan": "Чинний"})
        self.assertEqual((stan, sid, warn), ("", "0", ""))

    def test_absent_keeps_old(self):
        stan, sid, warn = S.resolve_status({}, {"stan": "Чинний"})
        self.assertEqual(stan, "Чинний")
        self.assertIn("не передало", warn)

    def test_null_keeps_old_with_warning(self):
        stan, _sid, warn = S.resolve_status({"status": None}, {"stan": "Чинний"})
        self.assertEqual(stan, "Чинний")
        self.assertIn("null", warn)

    def test_known_and_unknown(self):
        self.assertEqual(S.resolve_status({"status": 1}, None)[0], "Втратив чинність")
        stan, sid, warn = S.resolve_status({"status": 42}, {"stan": "Чинний"})
        self.assertEqual((stan, sid), ("", "42"))
        self.assertIn("невідомий", warn)

    def test_in_normalized_card(self):
        root = tmpdir()
        data = {"result": "ok", "nreg": "a-1", "nazva": "А", "status": 0, "eds": [{"datred": "20200101"}],
                "datred": "20200101", "edcnt": 1}
        p = S.parse_json_card(data)
        c = S.normalized_card(root, "a-1", {"rezhym": "povna"}, p, "2026-11-23T00:00:00+00:00",
                              {"stan": "Чинний"}, data)
        self.assertEqual(c["stan"], "")
        self.assertEqual(c["api"]["status_id"], "0")


class TestEvents(unittest.TestCase):
    def test_no_edition_events_and_keep_legal(self):
        old = [
            {"data": "01.01.2020", "opys": "Редакція, підстава - 1-IX"},                       # старий помилковий
            {"data": "15.12.2017", "opys": "Набрання чинності"},
            {"data": "01.02.2021", "opys": "Тлумачення, підстава - v001p710-21"},
            {"data": "01.03.2022", "opys": "Визнання неконституційними окремих положень, підстава - 2-р/2022"},
        ]
        new = [
            {"data": "15.12.2017", "opys": "Набрання чинності", "podid": "1", "pidstava": []},
            {"data": "01.03.2022", "opys": "Визнання неконституційними окремих положень, підстава - v002p710-22",
             "podid": "25", "pidstava": ["v002p710-22"]},
            {"data": "05.05.2023", "opys": "Подія бази ВРУ (podid=77)", "podid": "77", "pidstava": []},
            {"data": "06.06.2023", "opys": "Нова редакція", "podid": "6", "pidstava": []},
        ]
        m = S.merge_events(new, old)
        opys = [e["opys"] for e in m]
        self.assertNotIn("Редакція, підстава - 1-IX", opys)
        self.assertEqual(sum(1 for o in opys if o.startswith("Набрання чинності")), 1)
        self.assertIn("Тлумачення, підстава - v001p710-21", opys)
        self.assertIn("Визнання неконституційними окремих положень, підстава - 2-р/2022", opys)   # старий підтверджений номер
        self.assertIn("Подія бази ВРУ (podid=77)", opys)
        self.assertFalse(any(o.startswith("Нова редакція") for o in opys))

    def test_podia_label_change_updates_without_duplicate(self):
        old = [{"data": "05.05.2023", "opys": "Подія бази ВРУ (podid=77), підстава - 5-IX", "podid": "77"}]
        new = [{"data": "05.05.2023", "opys": "Зупинення дії", "podid": "77", "pidstava": ["5-20"]}]
        m = S.merge_events(new, old)
        self.assertEqual(len(m), 1)
        self.assertEqual(m[0]["opys"], "Зупинення дії, підстава - 5-IX")

    def test_idempotent(self):
        new = [{"data": "15.12.2017", "opys": "Набрання чинності", "podid": "1", "pidstava": []}]
        once = S.merge_events(new, [])
        self.assertEqual(S.merge_events(new, once), once)


class TestBasis(unittest.TestCase):
    def setUp(self):
        self.root = tmpdir()
        self.sess = FakeSession()
        self.client = make_client(self.root, self.sess)

    def test_orgnum_and_nvlas(self):
        self.sess.route(card_url("2147-19"), body={"result": "ok", "nreg": "2147-19", "orgnum": "2147-VIII"})
        self.sess.route(card_url("v004p710-25"), body={"result": "ok", "nreg": "v004p710-25", "n_vlas": "4-р(II)/2025"})
        self.assertEqual(self.client.resolve_basis_display("2147-19"), ("2147-VIII", True))
        self.assertEqual(self.client.resolve_basis_display("v004p710-25"), ("4-р(II)/2025", True))
        calls = len(self.sess.calls)
        self.assertEqual(self.client.resolve_basis_display("2147-19"), ("2147-VIII", True))
        self.assertEqual(len(self.sess.calls), calls)              # з кешу

    def test_no_heuristic_roman(self):
        self.assertEqual(self.client.resolve_basis_display("1234-19"), ("1234-19", False))   # 404 → сирий nreg
        self.sess.route(card_url("9999-20"), body={"result": "ok", "nreg": "8888-20", "orgnum": "8888-IX"})
        self.assertEqual(self.client.resolve_basis_display("9999-20"), ("9999-20", False))   # чужа картка

    def test_enrich_keeps_old_and_desc(self):
        self.sess.route(card_url("2147-19"), body={"result": "ok", "nreg": "2147-19", "orgnum": "2147-VIII"})
        parsed = {"redaktsii": [
            {"ed": "20171215", "opys": "Нова редакція, підстава - 2147-19", "pidstava": ["2147-19"], "pidstava_nreg": ["2147-19"]},
            {"ed": "20100101", "opys": "Редакція, підстава - 1-17", "pidstava": ["1-17"], "pidstava_nreg": ["1-17"]},
        ], "podii": []}
        old = {"redaktsii": [{"ed": "20100101", "opys": "Редакція, підстава - 1-VI", "pidstava": ["1-VI"]}]}
        self.client.enrich_basis(parsed, old)
        r = {x["ed"]: x for x in parsed["redaktsii"]}
        self.assertEqual(r["20171215"]["pidstava"], ["2147-VIII"])
        self.assertEqual(r["20100101"]["pidstava"], ["1-VI"])                    # старе підтверджене
        self.assertEqual(S._desc_with_basis(r["20171215"]["opys"], r["20171215"]["pidstava"]),
                         "Нова редакція, підстава - 2147-VIII")                  # тип збережено, без сирого nreg

    def test_desc_noise_removed(self):
        self.assertEqual(S._desc_with_basis("попередня редакція 325 кб Стан: чинна", ["1-IX"]), "Редакція, підстава - 1-IX")
        self.assertEqual(S._desc_with_basis("Визнання конституційними окремих положень, підстава - v1", ["1-р/2020"]),
                         "Визнання конституційними окремих положень, підстава - 1-р/2020")


if __name__ == "__main__":
    unittest.main()
