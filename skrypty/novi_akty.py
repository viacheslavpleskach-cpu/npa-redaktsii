#!/usr/bin/env python3
"""Пошук НПА, які згадуються у висновках, але яких немає в архіві.

Автор: В'ячеслав Плескач.

    python3 skrypty/novi_akty.py <тека з висновками .docx> [--porih 2] [--zapysaty]

Рахує, у скількох висновках (файл = один висновок; версії одного номера — один висновок)
згадано кожен закон («Закон … «Про …»») і кодекс. Друкує ті, яких немає в perelik_aktiv.csv
і які згадано не менше ніж у --porih висновках (з урахуванням попередніх запусків —
dani/zghadky.csv). З --zapysaty оновлює dani/zghadky.csv і dani/vysnovky_opratsovani.txt.
Акти до архіву не додає: це робить власник репозиторію після підтвердження.
"""
import argparse, collections, csv, html, os, re, sys, zipfile

KORIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DANI = os.path.join(KORIN, 'dani')


def tekst_docx(p):
    out = []
    with zipfile.ZipFile(p) as z:
        for n in ('word/document.xml', 'word/footnotes.xml', 'word/endnotes.xml'):
            if n in z.namelist():
                x = z.read(n).decode('utf-8', 'replace')
                x = re.sub(r'</w:p>', '\n', x)
                out.append(html.unescape(re.sub(r'<[^>]+>', '', x)))
    t = ' '.join(out)
    return re.sub(r'[ \s]+', ' ', t.replace('“', '«').replace('”', '»').replace('"', '«').replace('’', "'"))


def zghadky(t):
    z = set()
    for m in re.finditer(r'Закон\w*\s+(?:України\s+)?(?:від\s+[\d.]+\s+(?:року\s+)?(?:№\s*[\w/-]+\s+)?)?«\s*(Про[^»]{3,200})»', t):
        z.add('Закон «' + re.sub(r'\s+', ' ', m.group(1)).strip().rstrip('.,') + '»')
    for m in re.finditer(r'\b([А-ЯІЇЄҐ][а-яіїєґ\'-]+(?:\s+[а-яіїєґ\'-]+){0,3}\s+[Кк]одекс\w*\s+України)', t):
        z.add(m.group(1))
    return z


STOP = {'і', 'та', 'й', 'про', 'україни', 'україні', 'в', 'у', 'з', 'із', 'на', 'щодо', 'закон', 'закону', 'кодекс', 'кодексу',
        'кодексі', 'кодексом', 'від', 'для', 'до', 'або', 'а', 'як'}


def osnovy(s):
    """Основи значущих слів (перші 5 літер) — для порівняння назв у різних відмінках."""
    return {w[:5] for w in re.findall(r"[а-яіїєґ']+", s.lower()) if w not in STOP and len(w) > 2}


def vidomyi(akt, vidomi):
    o = osnovy(akt)
    if not o:
        return True
    return any(len(o & v) / len(o | v) >= 0.75 for v in vidomi)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('teka'); ap.add_argument('--porih', type=int, default=2); ap.add_argument('--zapysaty', action='store_true')
    a = ap.parse_args()
    with open(os.path.join(KORIN, 'perelik_aktiv.csv'), encoding='utf-8') as f:
        vidomi = [osnovy(re.sub(r'\(.*?\)', '', r['nazva'])) for r in csv.DictReader(f, delimiter=';')]
    zp = os.path.join(DANI, 'zghadky.csv'); op = os.path.join(DANI, 'vysnovky_opratsovani.txt')
    lich = collections.Counter()
    if os.path.exists(zp):
        for r in csv.DictReader(open(zp, encoding='utf-8')):
            lich[r['akt']] = int(r['vysnovkiv'])
    oprats = set(open(op, encoding='utf-8').read().split('\n')) if os.path.exists(op) else set()
    novi_nomery = {}
    for dp, _, fs in os.walk(a.teka):
        for f in fs:
            m = re.match(r'^!?\s*(\d{4,6})', re.sub(r'^[A-Za-z0-9_-]{25,}__', '', f))
            if not f.lower().endswith('.docx') or not m or m.group(1) in oprats:
                continue
            try:
                novi_nomery.setdefault(m.group(1), set()).update(zghadky(tekst_docx(os.path.join(dp, f))))
            except Exception as e:
                print('пропущено', f, e, file=sys.stderr)
    for z in novi_nomery.values():
        lich.update(z)
    poza = [(n, akt) for akt, n in lich.items() if n >= a.porih and not vidomyi(akt, vidomi)]
    print(f'Нових висновків опрацьовано: {len(novi_nomery)}')
    if poza:
        print('Акти поза архівом, згадані щонайменше в', a.porih, 'висновках:')
        for n, akt in sorted(poza, reverse=True):
            print(f'  {n:4}  {akt}')
    else:
        print('Нових актів для архіву не виявлено.')
    if a.zapysaty:
        os.makedirs(DANI, exist_ok=True)
        with open(zp, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f); w.writerow(['akt', 'vysnovkiv'])
            for akt, n in lich.most_common():
                w.writerow([akt, n])
        with open(op, 'w', encoding='utf-8') as f:
            f.write('\n'.join(sorted(oprats | set(novi_nomery))))


if __name__ == '__main__':
    main()
