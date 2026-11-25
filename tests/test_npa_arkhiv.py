# -*- coding: utf-8 -*-
"""Перевірка skrypty/npa.py на самому архіві (решта тестів перевіряє patch_npa_v4_1.py на копії tests/fixtures/npa.py).
Запуск: python -m pytest tests/test_npa_arkhiv.py  або  python -m unittest tests.test_npa_arkhiv"""
import datetime as dt
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'skrypty'))
import npa  # noqa: E402


def out(f, **kw):
    buf = io.StringIO()
    with redirect_stdout(buf):
        f(SimpleNamespace(**kw))
    return buf.getvalue()


class Arkhiv(unittest.TestCase):
    def test_kupap_chastyny_do_2017(self):
        """До 10.06.2017 КУпАП — два документи (статті 1–212 і 213–330): пошук без номера статті бере обидва."""
        d = dt.date(2003, 1, 1)
        while d < dt.date(2017, 6, 10):
            self.assertEqual(sorted(npa.znaity('КУпАП', d, vsi=True)), ['80731-10', '80732-10'], d)
            d += dt.timedelta(days=30)

    def test_kupap_pislia_2017(self):
        for d in (dt.date(2017, 6, 10), dt.date(2020, 1, 1), dt.date(2026, 11, 1)):
            self.assertEqual(npa.znaity('КУпАП', d, vsi=True), ['8073-10'], d)
            self.assertEqual(npa.znaity('КУпАП', d), '8073-10', d)

    def test_kupap_stattia_v_potribnii_chastyni(self):
        self.assertEqual(npa.znaity('КУпАП', dt.date(2015, 1, 1), '130'), '80731-10')
        self.assertEqual(npa.znaity('КУпАП', dt.date(2015, 1, 1), '255'), '80732-10')
        self.assertEqual(npa.znaity('КУпАП', dt.date(2015, 1, 1), '185-3'), '80731-10')

    def test_poshuk_apostrof(self):
        """Апостроф будь-якого коду у фразі дає той самий результат."""
        a = out(npa.cmd_poshuk, akt='КПК', fraza="обов'язок", na='01.03.2023', max=0)
        b = out(npa.cmd_poshuk, akt='КПК', fraza='обов’язок', na='01.03.2023', max=0)
        self.assertEqual(a, b)
        self.assertRegex(a, r'Знайдено рядків: [1-9]')

    def test_stattia_na_datu(self):
        t = out(npa.cmd_stattia, akt='КК', stattia='375', na='15.06.2020')
        self.assertIn('Редакція від 11.06.2020', t)
        self.assertIn('Стаття 375.', t)

    def test_rizni_akty_ne_zlyvaiutsia(self):
        """Два різні закони з однаковим початком скорочення — «Неоднозначно», а не вибір за датою."""
        rows = [r for r in npa.perelik() if r['skorocheno'].startswith('Закон про зміни до КПК')]
        if len(rows) > 1:
            with self.assertRaises(SystemExit):
                npa.znaity('Закон про зміни до КПК', dt.date(2026, 1, 1))


if __name__ == '__main__':
    unittest.main()
