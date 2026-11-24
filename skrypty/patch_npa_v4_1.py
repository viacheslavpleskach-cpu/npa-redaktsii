#!/usr/bin/env python3
"""Необов'язковий патч skrypty/npa.py під метадані sync_api v4.1.

Автор: В'ячеслав Плескач.

Що додає (попередня поведінка для актів із підтвердженою історією не змінюється):
* попередження, якщо повноту історії редакцій не підтверджено (api.history_complete = false),
  з причиною (напр. «невирішені некоректні ідентифікатори редакцій: 201301186»);
* попередження для режимів chynna / odyn і snapshot: збережений текст не доводить,
  що саме він діяв на довільну дату;
* попередження, якщо текст редакції не пройшов перевірку цілісності (corrupt / date_mismatch);
  рядок «Перевірка тексту» в шапці виводу;
* умовні редакції 3000xxxx у `redaktsii` позначаються «(умовна)», а не «(майбутня)»;
* дата звірки архіву — пізніша з kartka.json/perevireno і dani/perevirka.json (sync --changed);
* `porivniaty` і `zminy` порівнюють тексти з нормалізованими апострофами (' ʼ ` ‘ → ’)
  лише в пам'яті: файли не змінюються, а відмінність тільки в апострофі не вважається зміною.

Використання (з кореня npa-redaktsii; спершу на копії):
  python skrypty/patch_npa_v4_1.py            # застосувати; резервна копія npa.py.bak-v4_1
  python skrypty/patch_npa_v4_1.py --check    # лише перевірити, чи патч застосовний
  python skrypty/patch_npa_v4_1.py --revert   # відновити з резервної копії
"""
import argparse
import os
import shutil
import sys

MARKER = "# patch v4.1 (sync_api_v4_1)"

REPLACEMENTS = [
    # 1. Нормалізація апострофів і дата звірки з dani/perevirka.json
    (
        "def ed2d(ed):\n",
        "APOS = str.maketrans({\"'\": '’', 'ʼ': '’', '`': '’', '‘': '’'})  " + MARKER + "\n\n\n"
        "def norm_apos(radky):\n"
        "    \"\"\"Лише для порівняння: апострофи різних кодів вважаються однаковими.\"\"\"\n"
        "    return [l.translate(APOS) for l in radky] if radky is not None else None\n\n\n"
        "def data_perevirky(k):\n"
        "    \"\"\"Пізніша з дат: картка (perevireno) і dani/perevirka.json (sync --changed).\"\"\"\n"
        "    d = dt.date.fromisoformat(k['perevireno'][:10])\n"
        "    p = os.path.join(KORIN, 'dani', 'perevirka.json')\n"
        "    if os.path.exists(p):\n"
        "        try:\n"
        "            z = json.load(open(p, encoding='utf-8')).get(k['nreg'], {})\n"
        "            d = max(d, dt.date.fromisoformat(str(z.get('checked_at', ''))[:10]))\n"
        "        except (ValueError, OSError):\n"
        "            pass\n"
        "    return d\n\n\n"
        "def ed2d(ed):\n",
    ),
    # 2. Snapshot/odyn: інше повідомлення, якщо на дату немає редакції
    (
        "    if not pered:\n"
        "        pop.append(f'на {ukr(na)} акта ще не було: перша редакція від {ukr(ed2d(realni[0][\"ed\"])) if realni else \"?\"} '\n"
        "                   '(сайт у такому разі показує чинну редакцію — не використовувати її)')\n"
        "        return None, pop\n",
        "    api = k.get('api') or {}\n"
        "    znimok = k.get('rezhym') == 'odyn' or bool(api.get('snapshot_only'))\n"
        "    if not pered:\n"
        "        if znimok and realni:\n"
        "            pop.append(f'в архіві лише один знімок тексту від {ukr(ed2d(realni[0][\"ed\"]))} без історії редакцій; '\n"
        "                       f'редакції на {ukr(na)} в архіві немає — взяти з сайту')\n"
        "            return None, pop\n"
        "        pop.append(f'на {ukr(na)} акта ще не було: перша редакція від {ukr(ed2d(realni[0][\"ed\"])) if realni else \"?\"} '\n"
        "                   '(сайт у такому разі показує чинну редакцію — не використовувати її)')\n"
        "        return None, pop\n",
    ),
    # 3. Попередження про повноту, режим і цілісність тексту; дата звірки
    (
        "    perev = dt.date.fromisoformat(k['perevireno'][:10])\n"
        "    if na > perev:\n",
        "    if k.get('rezhym') == 'povna' and api and api.get('history_complete') is False:\n"
        "        pop.append('повноту історії редакцій не підтверджено'\n"
        "                   + (f\": {api.get('history_reason')}\" if api.get('history_reason') else '')\n"
        "                   + ' — між редакціями архіву може бути пропущена')\n"
        "    if znimok:\n"
        "        pop.append(f'режим «{k.get(\"rezhym\")}»: в архіві один знімок тексту (від {ukr(ed2d(r[\"ed\"]))}); '\n"
        "                   f'що саме він діяв на {ukr(na)}, архівом не підтверджено')\n"
        "    elif k.get('rezhym') == 'chynna':\n"
        "        pop.append('режим «chynna»: в архіві зберігається лише чинний текст, не вся історія редакцій')\n"
        "    if r.get('text_status') in ('corrupt', 'date_mismatch'):\n"
        "        pop.append(f'текст цієї редакції не пройшов перевірку цілісності ({r[\"text_status\"]}) — звірити із сайтом')\n"
        "    perev = data_perevirky(k)\n"
        "    if na > perev:\n",
    ),
    # 4. Шапка: рядок перевірки тексту і дата звірки
    (
        "    s.append(f\"Архів перевірено: {ukr(dt.date.fromisoformat(k['perevireno'][:10]))}\")\n",
        "    s.append(f\"Архів перевірено: {ukr(data_perevirky(k))}\")\n"
        "    st = {'verified': 'перевірено (SHA-256 і DocumentDate з API)',\n"
        "          'legacy_unverified': 'старий імпорт без контрольної суми — для цитування звірити із сайтом',\n"
        "          'corrupt': 'ПОШКОДЖЕНО', 'date_mismatch': 'ДАТА НЕ ЗБІГАЄТЬСЯ'}.get(r.get('text_status'))\n"
        "    if st:\n"
        "        s.append(f'Перевірка тексту: {st}')\n",
    ),
    # 5. redaktsii: умовні не «майбутні»; рядок про повноту
    (
        "        poz = ' ← чинна' if r['ed'] == chynna else (' (майбутня)' if not ed2d(r['ed']) or ed2d(r['ed']) > sohodni else '')\n",
        "        poz = ' ← чинна' if r['ed'] == chynna else (' (умовна)' if not ed2d(r['ed']) else (' (майбутня)' if ed2d(r['ed']) > sohodni else ''))\n",
    ),
    (
        "    print(f\"{k['nazva']} ({k['nreg']}), стан: {k['stan'] or '—'}; перевірено {k['perevireno'][:10]}\")\n",
        "    print(f\"{k['nazva']} ({k['nreg']}), стан: {k['stan'] or '—'}; перевірено {data_perevirky(k).isoformat()}\")\n"
        "    api = k.get('api') or {}\n"
        "    if api.get('history_complete') is False and k.get('rezhym') == 'povna':\n"
        "        print('⚠ повноту історії редакцій не підтверджено: ' + str(api.get('history_reason') or ''))\n"
        "    elif k.get('rezhym') != 'povna':\n"
        "        print(f'⚠ режим «{k.get(\"rezhym\")}»: в архіві не вся історія редакцій')\n",
    ),
    # 6. zminy: апострофи не дають хибної «зміни»
    (
        "        cur = '\\n'.join(st) if st else None\n",
        "        cur = '\\n'.join(norm_apos(st)) if st else None\n",
    ),
    # 7. porivniaty: порівняння з нормалізованими апострофами
    (
        "    s1, s2 = stattia_z(t1, a.stattia) or [], stattia_z(t2, a.stattia) or []\n"
        "    if s1 == s2:\n"
        "        print('Текст статті не змінився.'); return\n"
        "    for l in difflib.unified_diff(s1, s2,",
        "    s1, s2 = stattia_z(t1, a.stattia) or [], stattia_z(t2, a.stattia) or []\n"
        "    if s1 == s2:\n"
        "        print('Текст статті не змінився.'); return\n"
        "    s1, s2 = norm_apos(s1), norm_apos(s2)\n"
        "    if s1 == s2:\n"
        "        print('Текст статті не змінився (різниця лише в написанні апострофа).'); return\n"
        "    for l in difflib.unified_diff(s1, s2,",
    ),
]


def main():
    ap = argparse.ArgumentParser(description="Патч npa.py v4.1")
    ap.add_argument("--file", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "npa.py"))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    backup = a.file + ".bak-v4_1"
    if a.revert:
        if not os.path.exists(backup):
            sys.exit(f"Резервної копії {backup} немає.")
        shutil.copy2(backup, a.file)
        print(f"Відновлено {a.file} з {backup}")
        return
    src = open(a.file, encoding="utf-8").read()
    if MARKER in src:
        print("Патч уже застосовано — нічого не змінено.")
        return
    out = src
    missing = []
    for i, (old, new) in enumerate(REPLACEMENTS, 1):
        if out.count(old) != 1:
            missing.append(i)
            continue
        out = out.replace(old, new, 1)
    if missing:
        sys.exit(f"Патч не застосовний: фрагменти {missing} не знайдено рівно один раз (npa.py змінено?). Файл не змінено.")
    compile(out, a.file, "exec")
    if a.check:
        print(f"Патч застосовний ({len(REPLACEMENTS)} фрагментів). Файл не змінено.")
        return
    shutil.copy2(a.file, backup)
    with open(a.file + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    os.replace(a.file + ".tmp", a.file)
    print(f"Застосовано до {a.file}; резервна копія {backup}")


if __name__ == "__main__":
    main()
