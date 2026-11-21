#!/usr/bin/env python3
"""Імпорт файлів npa_<nreg>_pNN.json (зібраних zbir.js) в архів.

Автор: В'ячеслав Плескач. Джерело даних: zakon.rada.gov.ua (© Верховна Рада України, CC BY 4.0).

    python3 skrypty/import.py <файл.json> [<файл.json> ...]

Для кожного акта пише akty/<nreg>/kartka.json і akty/<nreg>/red/<ЕД>.txt,
де <ЕД> — дата редакції на сайті (РРРРММДД; 3000xxxx — редакції, дата набрання
чинності яких залежить від події). Друкує звіт перевірок.
"""
import csv, json, os, sys, glob

KORIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def slug(nreg):
    return nreg.replace('/', '_')


def data_ed(ed):
    if ed.startswith('3000'):
        return None
    return f'{ed[6:8]}.{ed[4:6]}.{ed[0:4]}'


def perelik():
    with open(os.path.join(KORIN, 'perelik_aktiv.csv'), encoding='utf-8') as f:
        return {r['nreg']: r for r in csv.DictReader(f, delimiter=';') if r['nreg']}


def main(faily):
    akty = {}
    for p in faily:
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
        a = akty.setdefault(d['nreg'], {'meta': None, 'teksty': {}, 'chastyny': set(), 'ostannia': False})
        if d.get('ostannia') or a['meta'] is None:
            a['meta'] = d
        a['teksty'].update(d.get('teksty') or {})
        a['chastyny'].add(d.get('chastyna'))
        a['ostannia'] = a['ostannia'] or bool(d.get('ostannia'))

    spysok = perelik()
    zvit, problemy = [], 0
    for nreg, a in akty.items():
        m = a['meta']
        k = m['kartka']
        d = os.path.join(KORIN, 'akty', slug(nreg))
        os.makedirs(os.path.join(d, 'red'), exist_ok=True)
        kp = os.path.join(d, 'kartka.json')
        stara = json.load(open(kp, encoding='utf-8')) if os.path.exists(kp) else {}
        url = f"https://zakon.rada.gov.ua/{m['prefiks']}/show/{nreg}"
        zapysano, poperedzhennia = 0, []
        for ed, radky in sorted(a['teksty'].items()):
            if radky is None:
                poperedzhennia.append(f'ed{ed}: сайт не віддав текст'); continue
            tekst = '\n'.join(radky).strip()
            if len(tekst) < 200:
                poperedzhennia.append(f'ed{ed}: підозріло короткий текст ({len(tekst)} симв.)')
            r = next((x for x in k['redaktsii'] if x['ed'] == ed), None)
            if ed == 'bez_redaktsii':
                zag = f"# {k['nazva']} | текст без переліку редакцій, отримано {m['zibrano'][:10]}\n# Джерело: {url} (© Верховна Рада України, CC BY 4.0)\n"
            else:
                koly = data_ed(ed) or (r or {}).get('data_na_saiti', 'дата залежить від події')
                pidst = ', '.join((r or {}).get('pidstava') or []) or '—'
                zag = (f"# {k['nazva']} | редакція від {koly} | {(r or {}).get('opys', '')}\n"
                       f"# Підстава: {pidst}\n# Джерело: {url}/ed{ed} (© Верховна Рада України, CC BY 4.0)\n")
            with open(os.path.join(d, 'red', f'{ed}.txt'), 'w', encoding='utf-8') as f:
                f.write(zag + '\n' + tekst + '\n')
            zapysano += 1
        # справжні редакції з'явилися — тимчасовий текст без переліку редакцій більше не потрібен
        bez = os.path.join(d, 'red', 'bez_redaktsii.txt')
        if k['redaktsii'] and os.path.exists(bez) and 'bez_redaktsii' not in a['teksty']:
            os.remove(bez)
        # перевірка: однакові тексти сусідніх редакцій (буває законно: зміна стосувалася
        # іншої частини акта, поділеного на кілька документів, або лише додатків)
        fs = sorted(glob.glob(os.path.join(d, 'red', '[0-9]*.txt')))
        prev = None
        for fp in fs:
            body = open(fp, encoding='utf-8').read().split('\n', 4)[-1]
            if prev is not None and body == prev[1]:
                poperedzhennia.append(f'{os.path.basename(fp)} збігається з {os.path.basename(prev[0])}')
            prev = (fp, body)
        # картка
        rezhym = spysok.get(nreg, {}).get('rezhym', '')
        ye = {os.path.basename(x)[:-4] for x in glob.glob(os.path.join(d, 'red', '*.txt'))}
        redaktsii = []
        for r in k['redaktsii']:
            redaktsii.append({'ed': r['ed'], 'data': data_ed(r['ed']), 'umovna': r['ed'].startswith('3000'),
                              'data_na_saiti': r['data_na_saiti'], 'opys': r['opys'], 'pidstava': r['pidstava'],
                              'tekst': r['ed'] in ye, 'bez_posylannia': bool(r.get('bez_posylannia'))})
        nova = {'nreg': nreg, 'nazva': k['nazva'], 'stan': k['stan'], 'rezhym': rezhym, 'dzherelo': url,
                'perevireno': m['zibrano'], 'redaktsii': redaktsii, 'podii': k['podii'],
                'bez_redaktsii': 'bez_redaktsii' in ye}
        with open(kp, 'w', encoding='utf-8') as f:
            json.dump(nova, f, ensure_ascii=False, indent=1)
        if rezhym == 'povna':
            brak = [r['ed'] for r in redaktsii if not r['tekst']]
            if brak:
                poperedzhennia.append(f'немає текстів {len(brak)} редакцій: {", ".join(brak[:6])}{"…" if len(brak) > 6 else ""}')
        novi = len({r['ed'] for r in redaktsii} - {r['ed'] for r in stara.get('redaktsii', [])}) if stara else 0
        problemy += len(poperedzhennia)
        zvit.append(f"{nreg} — {k['nazva'][:60]}: записано {zapysano}, редакцій у картці {len(redaktsii)}"
                    + (f", нових у картці {novi}" if stara else '')
                    + (f", частин {len(a['chastyny'])}" + ('' if a['ostannia'] else ' (НЕМАЄ ОСТАННЬОЇ ЧАСТИНИ)'))
                    + ''.join('\n   ⚠ ' + p for p in poperedzhennia))
    print('\n'.join(zvit))
    print(f'\nАктів: {len(akty)}; попереджень: {problemy}')
    return 1 if problemy else 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    sys.exit(main(sys.argv[1:]))
