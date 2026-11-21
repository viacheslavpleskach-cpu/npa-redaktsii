#!/usr/bin/env python3
"""Щотижневе оновлення архіву npa-redaktsii.

Автор: В'ячеслав Плескач. Джерело даних: zakon.rada.gov.ua (© Верховна Рада України, CC BY 4.0).

Порядок:
  1. python3 skrypty/onovlennia.py nregs
       → JSON-масив номерів актів для перевірки карток у браузері: zbirKartkyStart(<масив>)
  2. коли zbirKartkyStan() покаже «готово» — zbirKartkyZberehty() збереже файл npa_kartky_<дата>.json у «Завантаження»
  3. python3 skrypty/onovlennia.py porivniaty <шлях до npa_kartky_<дата>.json>
       → що змінилося (нові редакції, стан, події) і готовий виклик zbirStart(...) лише для змінених актів
  4. завантажені файли npa_*.json → skrypty/import.py, потім commit і push
"""
import csv, json, os, sys

KORIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def perelik():
    with open(os.path.join(KORIN, 'perelik_aktiv.csv'), encoding='utf-8') as f:
        return [r for r in csv.DictReader(f, delimiter=';') if r['nreg'] and r['rezhym'] != 'nemaie']


def kartka(nreg):
    p = os.path.join(KORIN, 'akty', nreg.replace('/', '_'), 'kartka.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


def cmd_nregs():
    print(json.dumps([r['nreg'] for r in perelik()], ensure_ascii=False))


def cmd_porivniaty(fail):
    nove = json.load(open(fail, encoding='utf-8'))
    zminy, vyklyk, vidomi, problemy = [], [], {}, []
    for r in perelik():
        n, k, s = r['nreg'], kartka(r['nreg']), nove.get(r['nreg'])
        if s in (None, 'помилка'):
            problemy.append(f'{n}: картку не отримано ({s})'); continue
        if not k:
            zminy.append(f'{n}: нового акта ще немає в архіві — повне завантаження')
            vyklyk.append({'nreg': n, 'rezhym': r['rezhym'], 'chastyna': 30}); continue
        stari = {x['ed'] for x in k['redaktsii']}
        z_tekstom = [x['ed'] for x in k['redaktsii'] if x['tekst']] + (['bez_redaktsii'] if k.get('bez_redaktsii') else [])
        novi = [e for e in s['eds'] if e not in stari]
        ye = set(z_tekstom)
        if r['rezhym'] == 'povna':
            tilky = [e for e in s['eds'] if e not in ye]
        else:  # chynna / odyn — лише редакція, чинна на сьогодні
            sohodni = __import__('datetime').date.today().strftime('%Y%m%d')
            realni = [e for e in s['eds'] if not e.startswith('3000') and e <= sohodni]
            tilky = [realni[-1]] if realni and realni[-1] not in ye else []
        znykli = [e for e in stari if e not in s['eds']]
        prychyny = []
        if novi: prychyny.append('нові редакції ' + ', '.join(novi))
        if znykli: prychyny.append('на сайті зникли редакції ' + ', '.join(sorted(znykli)))
        if s['stan'] != k['stan']: prychyny.append(f'стан: «{k["stan"]}» → «{s["stan"]}»')
        if s['podii'] != len(k.get('podii', [])): prychyny.append(f'подій у картці: {len(k.get("podii", []))} → {s["podii"]}')
        if prychyny:
            zminy.append(f'{n} ({r["skorocheno"]}): ' + '; '.join(prychyny))
            vyklyk.append({'nreg': n, 'rezhym': r['rezhym'], 'chastyna': 30, 'tilky': tilky})
    print('Змін не виявлено.' if not zminy else 'Зміни:\n  ' + '\n  '.join(zminy))
    if problemy:
        print('Проблеми:\n  ' + '\n  '.join(problemy))
    if vyklyk:
        print('\nВиклик у браузері:')
        print('zbirStart(' + json.dumps(vyklyk, ensure_ascii=False, separators=(',', ':')) + ')')
        print(f'\nРедакцій до завантаження: {sum(len(v.get("tilky") or []) for v in vyklyk)} (+ повні акти: '
              + ', '.join(v['nreg'] for v in vyklyk if 'tilky' not in v) + ')')


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'nregs':
        cmd_nregs()
    elif len(sys.argv) >= 3 and sys.argv[1] == 'porivniaty':
        cmd_porivniaty(sys.argv[2])
    else:
        print(__doc__); sys.exit(2)
