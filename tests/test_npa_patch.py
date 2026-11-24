"""C11–C12 і розд. 13 ТЗ: патч npa.py на копії (окремо від основного файла).

Потрібна копія чинного skrypty/npa.py: шлях у змінній NPA_PY або tests/fixtures/npa.py.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATCH = HERE.parent / "skrypty" / "patch_npa_v4_1.py"
NPA = Path(os.environ.get("NPA_PY", HERE / "fixtures" / "npa.py"))

LEG = "# Тест | редакція від {d} | Редакція\n# Підстава: —\n# Джерело: https://zakon.rada.gov.ua/laws/show/{n}/ed{e} (© Верховна Рада України, CC BY 4.0)\n\n"


def build(root: Path):
    (root / "skrypty").mkdir(parents=True)
    shutil.copy2(NPA, root / "skrypty" / "npa.py")
    (root / "dani").mkdir()
    (root / "perelik_aktiv.csv").write_text(
        "nreg;skorocheno;nazva;rezhym;aliasy;vysnovkiv;prymitka\n"
        "b-1;Банкр;Закон про банкрутство;povna;;0;\n"
        "o-1;Один;Положення;odyn;;0;\n"
        "k-1;КАС;Кодекс;povna;;0;\n", encoding="utf-8")

    def act(n, mode, eds, api=None, texts=None):
        d = root / "akty" / n / "red"
        d.mkdir(parents=True)
        red = []
        for e, txt in eds:
            red.append({"ed": e, "data": None, "data_na_saiti": "з дня припинення воєнного стану" if e.startswith("3000") else "",
                        "opys": "Редакція", "pidstava": ["1-IX"], "tekst": True,
                        **({"text_status": texts[e]} if texts and e in texts else {})})
            dd = "" if e.startswith("3000") else f"{e[6:8]}.{e[4:6]}.{e[:4]}"
            (d / f"{e}.txt").write_text(LEG.format(d=dd, n=n, e=e) + txt, encoding="utf-8")
        card = {"nreg": n, "nazva": f"Акт {n}", "stan": "Чинний", "rezhym": mode,
                "dzherelo": f"https://zakon.rada.gov.ua/laws/show/{n}", "perevireno": "2026-11-01T00:00:00+00:00",
                "redaktsii": red, "podii": [], "bez_redaktsii": False}
        if api:
            card["api"] = api
        (root / "akty" / n / "kartka.json").write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")

    act("b-1", "povna", [("20120101", "Стаття 1. Суд має п'ять днів.\n"), ("20200101", "Стаття 1. Суд має п’ять днів.\n")],
        api={"history_complete": False, "history_reason": "невирішені некоректні ідентифікатори редакцій: 201301186"},
        texts={"20200101": "corrupt"})
    act("o-1", "odyn", [("20240101", "Стаття 1. Знімок.\n")], api={"snapshot_only": True, "history_complete": False})
    act("k-1", "povna", [("20200101", "Стаття 1. А.\n"), ("30000101", "Стаття 1. Б.\n")], api={"history_complete": True})
    (root / "dani" / "perevirka.json").write_text(json.dumps({"b-1": {"checked_at": "2026-11-23T05:00:00+00:00"}}), encoding="utf-8")


def npa(root, *a):
    r = subprocess.run([sys.executable, str(root / "skrypty" / "npa.py"), *a], capture_output=True, text=True, encoding="utf-8")
    return r.stdout + r.stderr


@unittest.skipUnless(NPA.exists(), "немає копії npa.py (NPA_PY або tests/fixtures/npa.py)")
class TestNpaPatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="npa41p_"))
        build(cls.root)
        cls.before = {a: npa(cls.root, *a) for a in [("stattia", "k-1", "1", "--na", "01.06.2020")]}
        out = subprocess.run([sys.executable, str(PATCH), "--file", str(cls.root / "skrypty" / "npa.py")],
                             capture_output=True, text=True, encoding="utf-8")
        assert "Застосовано" in out.stdout, out.stdout + out.stderr

    def test_unresolved_history_warning(self):
        out = npa(self.root, "stattia", "b-1", "1", "--na", "01.06.2020")
        self.assertIn("повноту історії редакцій не підтверджено", out)
        self.assertIn("201301186", out)
        self.assertIn("не пройшов перевірку цілісності (corrupt)", out)

    def test_odyn_snapshot(self):
        out = npa(self.root, "stattia", "o-1", "1", "--na", "01.06.2025")
        self.assertIn("один знімок", out)
        out = npa(self.root, "stattia", "o-1", "1", "--na", "01.06.2020")
        self.assertIn("лише один знімок", out)
        self.assertNotIn("акта ще не було", out)

    def test_conditional_label(self):
        out = npa(self.root, "redaktsii", "k-1")
        self.assertIn("(умовна)", out)
        self.assertNotIn("(майбутня)", out)

    def test_apostrophe_only_diff(self):
        out = npa(self.root, "porivniaty", "b-1", "1", "--z", "01.06.2015", "--po", "01.06.2021")
        self.assertIn("лише в написанні апострофа", out)
        out = npa(self.root, "zminy", "b-1", "1")
        self.assertNotIn("змінено", out)
        txt = (self.root / "akty" / "b-1" / "red" / "20120101.txt").read_text(encoding="utf-8")
        self.assertIn("п'ять", txt)                                          # файл не змінено

    def test_perevirka_date(self):
        out = npa(self.root, "stattia", "b-1", "1", "--na", "01.06.2020")
        self.assertIn("Архів перевірено: 23.11.2026", out)

    def test_complete_history_unchanged_output(self):
        a = ("stattia", "k-1", "1", "--na", "01.06.2020")
        after = npa(self.root, *a)
        strip = lambda s: [l for l in s.splitlines() if not l.startswith("Перевірка тексту")]
        self.assertEqual(strip(after), strip(self.before[a]))

    def test_idempotent_and_revert(self):
        p = self.root / "skrypty" / "npa.py"
        out = subprocess.run([sys.executable, str(PATCH), "--file", str(p)], capture_output=True, text=True, encoding="utf-8")
        self.assertIn("уже застосовано", out.stdout)


if __name__ == "__main__":
    unittest.main()
