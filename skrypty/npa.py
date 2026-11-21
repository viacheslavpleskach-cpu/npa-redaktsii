#!/usr/bin/env python3
"""npa.py — тексти НПА та їхні редакції на дату з архіву npa-redaktsii.

Автор: В'ячеслав Плескач. Джерело даних: zakon.rada.gov.ua (© Верховна Рада України, CC BY 4.0).

Акт задається номером на сайті (2341-14), скороченням (КК, КПК, «Закон про ВРП») або словом із назви.
Дата — ДД.ММ.РРРР або РРРР-ММ-ДД; без дати — сьогодні.

  npa.py akty                                   перелік актів в архіві
  npa.py redaktsii КК                           усі редакції з датами й підставами
  npa.py stattia КК 375 --na 15.06.2020         текст статті в редакції, чинній на дату
  npa.py zminy ЦПК 189                          у яких редакціях змінювалася стаття
  npa.py porivniaty КАС 193 --z 01.01.2019 --po 01.01.2024   різниця між редакціями статті
  npa.py poshuk КПК "розумні строки" --na 01.03.2023          пошук у тексті редакції
  npa.py tekst "Закон про ВРП" --na 01.01.2020  шлях до файлу повного тексту редакції

Скрипт сам попереджає, якщо дата раніша за прийняття / набрання чинності, акт втратив
чинність, є редакції з умовною датою набрання чинності або дата пізніша за останню перевірку архіву.
"""
import argparse, csv, datetime as dt, difflib, glob, json, os, re, sys

KORIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIT = 'https://zakon.rada.gov.ua'


def dataz(s):
    if not s:
        return dt.date.today()
    s = s.strip()
    for f in ('%d.%m.%Y', '%Y-%m-%d', '%Y%m%d'):
        try:
            return dt.datetime.strptime(s, f).date()
        except ValueError:
            pass
    sys.exit(f'Не розпізнано дату: {s} (потрібно ДД.ММ.РРРР)')


def ed2d(ed):
    return None if ed.startswith('3000') or ed == 'bez_redaktsii' else dt.date(int(ed[:4]), int(ed[4:6]), int(ed[6:8]))


def ukr(d):
    return d.strftime('%d.%m.%Y') if d else ''


def perelik():
    with open(os.path.join(KORIN, 'perelik_aktiv.csv'), encoding='utf-8') as f:
        return list(csv.DictReader(f, delimiter=';'))


def kartka(nreg):
    p = os.path.join(KORIN, 'akty', nreg.replace('/', '_'), 'kartka.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


def znaity(zapyt, na=None):
    """Повертає nreg акта. Кілька документів під одним скороченням (КУпАП) — обирає за датою."""
    q = zapyt.strip().lower()
    rows = perelik()
    tochni = [r for r in rows if r['nreg'].lower() == q]
    if not tochni:
        tochni = [r for r in rows if q == r['skorocheno'].lower() or q in [a.lower() for a in r['aliasy'].split('|') if a]]
    if not tochni:
        tochni = [r for r in rows if q in r['nazva'].lower() or q in r['skorocheno'].lower()]
    if not tochni:
        sys.exit(f'Акт «{zapyt}» не знайдено в архіві. Перелік: npa.py akty. '
                 'Якщо акт потрібен, його можна додати до архіву (perelik_aktiv.csv) або взяти текст із zakon.rada.gov.ua.')
    vidsutni = [r for r in tochni if not r['nreg'] or r['rezhym'] == 'nemaie']
    tochni = [r for r in tochni if r['nreg'] and r['rezhym'] != 'nemaie']
    if not tochni:
        r = vidsutni[0]
        sys.exit(f'«{r["nazva"]}»: {r["prymitka"] or "в архіві немає"}.')
    if len(tochni) == 1:
        return tochni[0]['nreg']
    nazvy = {r['skorocheno'].split(' (')[0] for r in tochni}
    if len(nazvy) == 1:  # один акт, поділений на кілька документів
        na = na or dt.date.today()
        naikr, best = None, None
        for r in tochni:
            k = kartka(r['nreg'])
            if not k:
                continue
            ds = [ed2d(x['ed']) for x in k['redaktsii'] if ed2d(x['ed']) and ed2d(x['ed']) <= na]
            if ds and (naikr is None or max(ds) > naikr):
                naikr, best = max(ds), r['nreg']
        if best:
            return best
    sys.exit('Неоднозначно, уточніть: ' + '; '.join(f"{r['nreg']} — {r['skorocheno']}" for r in tochni))


def podiia(k, slovo):
    for p in k.get('podii', []):
        if slovo in p['opys']:
            try:
                return dt.datetime.strptime(p['data'], '%d.%m.%Y').date()
            except ValueError:
                return None
    return None


def redaktsiia_na(k, na):
    """(редакція, попередження) — редакція, чинна на дату na."""
    pop = []
    realni = [r for r in k['redaktsii'] if ed2d(r['ed'])]
    pered = [r for r in realni if ed2d(r['ed']) <= na]
    if not k['redaktsii'] and k.get('bez_redaktsii'):
        pop.append('документ на сайті не має переліку редакцій: в архіві один текст, без історії змін')
        return {'ed': 'bez_redaktsii', 'data': None, 'opys': '', 'pidstava': [], 'tekst': True}, pop
    if not pered:
        pop.append(f'на {ukr(na)} акта ще не було: перша редакція від {ukr(ed2d(realni[0]["ed"])) if realni else "?"} '
                   '(сайт у такому разі показує чинну редакцію — не використовувати її)')
        return None, pop
    r = pered[-1]
    nch = podiia(k, 'Набрання чинності')
    if nch and na < nch:
        pop.append(f'на {ukr(na)} акт прийнято, але він ще не набрав чинності (набрання чинності — {ukr(nch)})')
    vtr = podiia(k, 'Втрата чинності')
    if vtr and na >= vtr:
        pop.append(f'акт втратив чинність {ukr(vtr)}')
    elif 'Втратив' in (k.get('stan') or ''):
        pop.append(f'стан акта: {k["stan"]}')
    umovni = [x for x in k['redaktsii'] if x['ed'].startswith('3000')]
    if umovni:
        pop.append('є редакції з умовною датою набрання чинності: '
                   + '; '.join(f"{x['data_na_saiti']} (підстава {', '.join(x['pidstava'])})" for x in umovni))
    pizni = [x for x in realni if ed2d(x['ed']) > na]
    if pizni and ed2d(pizni[0]['ed']) > dt.date.today():
        pop.append(f'є редакція, що набирає чинності {ukr(ed2d(pizni[0]["ed"]))} (підстава {", ".join(pizni[0]["pidstava"])})')
    perev = dt.date.fromisoformat(k['perevireno'][:10])
    if na > perev:
        pop.append(f'архів перевірено станом на {ukr(perev)}; зміни після цієї дати можуть бути не враховані')
    return r, pop


def tekst(nreg, ed):
    p = os.path.join(KORIN, 'akty', nreg.replace('/', '_'), 'red', f'{ed}.txt')
    if not os.path.exists(p):
        return None, p
    radky = open(p, encoding='utf-8').read().split('\n')
    return [x for x in radky if not x.startswith('# ')], p


MEZHA = re.compile(r'^(Стаття\s+\d|Розділ\s|РОЗДІЛ\s|Глава\s|ГЛАВА\s|Параграф\s|§\s*\d|Книга\s|КНИГА\s)')


def stattia_z(radky, n):
    rx = re.compile(r'^Стаття\s+' + re.escape(n) + r'\.(\s|$)')
    idx = [i for i, l in enumerate(radky) if rx.match(l)]
    idx = [i for i in idx if not radky[i].rstrip().endswith('…')] or idx  # пропускаємо зміст
    if not idx:
        return None
    i = idx[-1]
    j = i + 1
    while j < len(radky) and not MEZHA.match(radky[j]):
        j += 1
    return radky[i:j]


def shapka(k, r, na, pop):
    url = f"{k['dzherelo']}/ed{r['ed']}" if r['ed'] != 'bez_redaktsii' else k['dzherelo']
    s = [f"Акт: {k['nazva']} ({k['nreg']})"]
    if r['ed'] != 'bez_redaktsii':
        s.append(f"Редакція від {ukr(ed2d(r['ed']))}, {r['opys']}  [чинна на {ukr(na)}]")
    s.append(f'Джерело: {url}')
    s.append(f"Архів перевірено: {ukr(dt.date.fromisoformat(k['perevireno'][:10]))}")
    s += ['⚠ ' + p for p in pop]
    return '\n'.join(s)


def potribna_kartka(akt, na=None):
    nreg = znaity(akt, na)
    k = kartka(nreg)
    if not k:
        sys.exit(f'{nreg}: акт є в переліку, але ще не завантажений в архів.')
    return k


def cmd_akty(a):
    for r in perelik():
        k = kartka(r['nreg']) if r['nreg'] else None
        st = (f"{sum(1 for x in k['redaktsii'] if x['tekst'])}/{len(k['redaktsii'])} ред., перевірено {k['perevireno'][:10]}"
              if k else ('немає на сайті' if r['rezhym'] == 'nemaie' else 'ще не завантажено'))
        print(f"{r['nreg'] or '—':14} {r['skorocheno'][:45]:45} {r['rezhym']:7} {st}")


def cmd_redaktsii(a):
    k = potribna_kartka(a.akt)
    print(f"{k['nazva']} ({k['nreg']}), стан: {k['stan'] or '—'}; перевірено {k['perevireno'][:10]}")
    sohodni = dt.date.today()
    chynna = [r for r in k['redaktsii'] if ed2d(r['ed']) and ed2d(r['ed']) <= sohodni]
    chynna = chynna[-1]['ed'] if chynna else None
    for r in k['redaktsii']:
        d = ukr(ed2d(r['ed'])) or r['data_na_saiti']
        poz = ' ← чинна' if r['ed'] == chynna else (' (майбутня)' if not ed2d(r['ed']) or ed2d(r['ed']) > sohodni else '')
        print(f"{d:12} {r['opys'][:90]}{'' if r['tekst'] else '  [тексту в архіві немає]'}{poz}")
    for p in k.get('podii', []):
        print(f"  подія {p['data']}: {p['opys'][:100]}")


def cmd_stattia(a):
    na = dataz(a.na)
    k = potribna_kartka(a.akt, na)
    r, pop = redaktsiia_na(k, na)
    if not r:
        sys.exit('\n'.join('⚠ ' + p for p in pop))
    radky, p = tekst(k['nreg'], r['ed'])
    if radky is None:
        sys.exit(shapka(k, r, na, pop) + f'\nТексту цієї редакції в архіві немає (режим «{k["rezhym"]}»). '
                 f'Отримати з сайту: {k["dzherelo"]}/ed{r["ed"]}')
    st = stattia_z(radky, a.stattia)
    print(shapka(k, r, na, pop))
    print('—' * 40)
    print('\n'.join(st) if st else f'Статтю {a.stattia} в тексті цієї редакції не знайдено (можливо, її тоді ще не було).')


def cmd_tekst(a):
    na = dataz(a.na)
    k = potribna_kartka(a.akt, na)
    r, pop = redaktsiia_na(k, na)
    if not r:
        sys.exit('\n'.join('⚠ ' + p for p in pop))
    radky, p = tekst(k['nreg'], r['ed'])
    print(shapka(k, r, na, pop))
    print('Файл: ' + (p if radky is not None else 'немає в архіві'))


def cmd_zminy(a):
    k = potribna_kartka(a.akt)
    prev, bulo = None, False
    for r in k['redaktsii']:
        if not r['tekst']:
            continue
        radky, _ = tekst(k['nreg'], r['ed'])
        st = stattia_z(radky, a.stattia)
        cur = '\n'.join(st) if st else None
        d = ukr(ed2d(r['ed'])) or r['data_na_saiti']
        if cur != prev:
            if cur is None:
                print(f'{d:12} статті немає в тексті')
            elif prev is None:
                print(f'{d:12} стаття є в тексті ({"перша поява" if bulo else "перша редакція в архіві"}), підстава {", ".join(r["pidstava"]) or "—"}')
            else:
                print(f'{d:12} змінено, підстава {", ".join(r["pidstava"]) or "—"}')
            bulo = bulo or cur is not None
        prev = cur
    if k['rezhym'] != 'povna':
        print(f'⚠ в архіві не всі редакції (режим «{k["rezhym"]}»)')


def cmd_porivniaty(a):
    d1, d2 = dataz(a.z), dataz(a.po)
    k = potribna_kartka(a.akt, d2)
    r1, p1 = redaktsiia_na(k, d1)
    r2, p2 = redaktsiia_na(k, d2)
    if not r1 or not r2:
        sys.exit('\n'.join('⚠ ' + p for p in p1 + p2))
    print(f"{k['nazva']}, стаття {a.stattia}: редакція від {ukr(ed2d(r1['ed']))} → від {ukr(ed2d(r2['ed']))}")
    if r1['ed'] == r2['ed']:
        print('Між цими датами редакція не змінювалася.'); return
    t1, _ = tekst(k['nreg'], r1['ed']); t2, _ = tekst(k['nreg'], r2['ed'])
    if t1 is None or t2 is None:
        sys.exit('Тексту однієї з редакцій в архіві немає.')
    s1, s2 = stattia_z(t1, a.stattia) or [], stattia_z(t2, a.stattia) or []
    if s1 == s2:
        print('Текст статті не змінився.'); return
    for l in difflib.unified_diff(s1, s2, f'від {ukr(ed2d(r1["ed"]))}', f'від {ukr(ed2d(r2["ed"]))}', lineterm='', n=0):
        print(l)


def cmd_poshuk(a):
    na = dataz(a.na)
    k = potribna_kartka(a.akt, na)
    r, pop = redaktsiia_na(k, na)
    if not r:
        sys.exit('\n'.join('⚠ ' + p for p in pop))
    radky, _ = tekst(k['nreg'], r['ed'])
    if radky is None:
        sys.exit('Тексту цієї редакції в архіві немає.')
    print(shapka(k, r, na, pop)); print('—' * 40)
    rx = re.compile(re.escape(a.fraza), re.I)
    st, n = '', 0
    for l in radky:
        if re.match(r'^Стаття\s+\d', l) and not l.rstrip().endswith('…'):
            st = l.split('.')[0]
        if rx.search(l):
            n += 1
            if n <= a.max:
                print(f'[{st or "—"}] {l[:400]}')
    print(f'Знайдено рядків: {n}' + (f' (показано {a.max})' if n > a.max else ''))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    sp.add_parser('akty').set_defaults(f=cmd_akty)
    p = sp.add_parser('redaktsii'); p.add_argument('akt'); p.set_defaults(f=cmd_redaktsii)
    p = sp.add_parser('stattia'); p.add_argument('akt'); p.add_argument('stattia'); p.add_argument('--na'); p.set_defaults(f=cmd_stattia)
    p = sp.add_parser('tekst'); p.add_argument('akt'); p.add_argument('--na'); p.set_defaults(f=cmd_tekst)
    p = sp.add_parser('zminy'); p.add_argument('akt'); p.add_argument('stattia'); p.set_defaults(f=cmd_zminy)
    p = sp.add_parser('porivniaty'); p.add_argument('akt'); p.add_argument('stattia'); p.add_argument('--z', required=True); p.add_argument('--po', required=True); p.set_defaults(f=cmd_porivniaty)
    p = sp.add_parser('poshuk'); p.add_argument('akt'); p.add_argument('fraza'); p.add_argument('--na'); p.add_argument('--max', type=int, default=30); p.set_defaults(f=cmd_poshuk)
    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
