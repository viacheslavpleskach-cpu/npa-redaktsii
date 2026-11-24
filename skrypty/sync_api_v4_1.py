#!/usr/bin/env python3
"""Безпечна безбраузерна синхронізація архіву npa-redaktsii (v4.1.5).

Автор: В'ячеслав Плескач.

Джерело: офіційний API data.rada.gov.ua (User-Agent: OpenData).
Формат архіву сумісний із skrypty/npa.py:
  akty/<nreg>/kartka.json
  akty/<nreg>/red/<YYYYMMDD>.txt

Ключові гарантії:
* кожен датований TXT перевіряється за HTTP-заголовком DocumentDate;
* поточний TXT перевіряється за datred з JSON-картки;
* відсутня/неправильна дата означає відмову від запису, а не підстановку іншої редакції;
* список редакцій доповнюється bulk-набором doc-update та верхньорівневим datred;
* умовні редакції 3000xxxx можна зберігати лише з явним --include-conditional
  та перевіркою спеціального DocumentDate (штучна дата 1100-MM-DD);
* старі метадані та події не втрачаються під час оновлення картки;
* інкрементальна синхронізація використовує повний набір doc-update, а не
  однодобовий список /laws/main/r.txt;
* локальний бюджет трафіку за замовчуванням обмежено 150 MiB/добу, залишаючи
  резерв від офіційного ліміту 200 MB/добу;
* лише офіційний API data.rada.gov.ua: robots.txt zakon.rada.gov.ua (User-Agent: *,
  Disallow: /) забороняє автоматичний доступ, тому HTML-сторінок скрипт не завантажує;
  акти поза API позначаються «оновлювати вручну»;
* старі офіційні номери підстав зберігаються; нові номери беруться з картки акта-підстави,
  а не виводяться евристично із суфікса nreg.

v4.1.8 (24.11.2026) додає:
* захист від неточних TXT API: у частині редакцій TXT API втрачає верхні індекси
  («Стаття 151» замість «Стаття 15-1», «пунктом 2581» замість «258-1»), а КПК ed20140302 містить
  главу, якої в редакції на сайті немає (звірено 24.11.2026);
* verify --repair --include-legacy замінює старий текст лише тоді, коли зміст збігається
  (після нормалізації: зміст сторінки, поле пошуку, апостроф, примітки у фігурних дужках) і
  немає втрати верхніх індексів; інакше старий текст лишається, у картці — api_text_issue і
  api_check, і повторно така редакція не завантажується (лише з --force);
* sync: новий текст порівнюється з попередньою редакцією; втрата верхніх індексів → api_text_issue
  (текст зберігається — іншого немає) і попередження; npa.py показує попередження.

v4.1.7 (24.11.2026) додає:
* окремі редакції того самого дня (9–10-значний ідентифікатор порталу, напр. 2343-12:
  201301186): записуються лише командою anomaly --record-separate після перевірки TXT API
  (DocumentDate = перші 8 цифр, текст відмінний від ed<дата>); порядок у межах дня задає
  власник за карткою сайту (--order before/after), поле poriadok_u_dni; сортування —
  за датою, порядком у дні, ідентифікатором;
* ручне виправлення опису й підстави редакції (команда pravka, без мережі): поле
  ruchna_pravka має перевагу над API і старою карткою під час наступних sync.

v4.1 (23.11.2026) додає:
* консервативну повноту історії: некоректні ідентифікатори редакцій (напр. 2343-12:
  201301186) зберігаються з походженням, не підсумовуються з коректними і лишають
  повноту непідтвердженою, доки аномалію не вирішено документовано (команда anomaly);
* окремі поля edition_catalog_complete / unresolved_edition_ids / all_texts_verified;
* per-document modified із doc-update для sync --changed (зміни картки без нової редакції);
* явний status=0 очищає старий стан; невідомий статус не підміняється відомим;
* перевірку цілісності наявних текстів (verify): verified / legacy_unverified / corrupt /
  date_mismatch / missing; без змін файлів, відновлення — лише з --repair;
* оновлення довідника podia.txt за If-Modified-Since (не частіше разу на добу);
* реєстр актів поза API (dani/manual_only.json) зі статусом, причиною й датою перевірки;
* журнал HTTP-запитів (--request-log) і розширений облік трафіку.

Приклади (команди виконувати з кореня npa-redaktsii):
  python skrypty/sync_api_v4_1.py probe --nreg 2747-15 --ed 20230323
  python skrypty/sync_api_v4_1.py probe --nreg 2747-15 --ed 30000101
  python skrypty/sync_api_v4_1.py sync --nreg 2747-15
  python skrypty/sync_api_v4_1.py sync --all
  python skrypty/sync_api_v4_1.py sync --changed
  python skrypty/sync_api_v4_1.py sync --nreg 2747-15 --ed 30000101 --include-conditional
  python skrypty/sync_api_v4_1.py verify                    # аудит текстів, нічого не змінює
  python skrypty/sync_api_v4_1.py verify --repair --nreg 2747-15
  python skrypty/sync_api_v4_1.py anomaly --nreg 2343-12 --raw 201301186
  python skrypty/sync_api_v4_1.py anomaly --nreg 2343-12 --raw 201301186 --record-separate \
         --order before --opys "Нова редакція" --pidstava "4212-VI"
  python skrypty/sync_api_v4_1.py pravka --nreg 2343-12 --ed 20130118 --opys "Редакція" \
         --pidstava "5405-VI, 5410-VI, 5518-VI" --prychyna "звірено з карткою сайту 24.11.2026"
  python skrypty/sync_api_v4_1.py status --out reports/stan.md

Цей скрипт не є офіційним джерелом. Перед юридичним цитуванням звіряйте текст
із посиланням на відповідну редакцію на порталі Верховної Ради.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import email.utils
import hashlib
import io
import json
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, urlparse

try:
    import requests
except ImportError as exc:  # pragma: no cover - runtime diagnostic
    raise SystemExit("Потрібен пакет requests: python -m pip install requests") from exc

DATA_HOST = "https://data.rada.gov.ua"
PUBLIC_HOST = "https://zakon.rada.gov.ua"
VERSION = "4.1.8"
USER_AGENT = "OpenData"
DOC_UPDATE_URL = f"{DATA_HOST}/ogd/zak/laws/data/csv/doc-update.txt"
PODIA_URL = f"{DATA_HOST}/ogd/zak/laws/data/csv/podia.txt"
DEFAULT_DAILY_BUDGET = 150 * 1024 * 1024  # резерв 50 MB від задекларованих 200 MB/добу
DATE_RE = re.compile(r"^\d{8}$")
CONDITIONAL_RE = re.compile(r"^3000\d{4}$")
SAME_DAY_RE = re.compile(r"^\d{9,10}$")   # окрема редакція того самого дня (ідентифікатор порталу)
MANUAL_ONLY_PATH = Path("dani") / "manual_only.json"
MANUAL_RECHECK_DAYS = 30
TEXT_STATES = ("verified", "legacy_unverified", "corrupt", "date_mismatch", "missing")
STATUS_BY_ID = {
    "0": "",  # «не визначено»: явний 0 очищає стан (див. resolve_status)
    "1": "Втратив чинність",
    "2": "Набирає чинності",
    "3": "Дію зупинено",
    "4": "Дію відновлено",
    "5": "Чинний",
    "6": "Не набрав чинності",
    "7": "Не застосовується",
    "8": "Частково набрав чинності",
    "9": "Втратив чинність крім окремих положень",
}
# Суфікси системного nreg, що позначають номер скликання ВРУ.
# Зберігаємо також сирий nreg, щоб не втрачати машинний ідентифікатор.
# Не виводимо офіційний номер із суфікса nreg: для старих документів це
# неоднозначно (напр., -14 може відповідати різним офіційним номерам).


def display_basis(value: str) -> str:
    """Безпечне відображення: без картки підстави повертаємо її nreg без вигадок."""
    return str(value).strip()



class SyncError(RuntimeError):
    """Загальна помилка синхронізації."""


class ManualOnlyError(SyncError):
    """Документ не підтримується потрібним JSON/TXT endpoint API."""


class BudgetExceeded(SyncError):
    """Досягнуто локальний обмежувач добового трафіку."""


class EditionDateMismatch(SyncError):
    """Сервер повернув текст редакції з іншою фактичною датою."""


def slug(nreg: str) -> str:
    return nreg.replace("/", "_").replace("\\", "_")


def encode_nreg(nreg: str) -> str:
    """Кодує кожен сегмент nreg окремо, залишаючи розділовий slash."""
    return "/".join(quote(part, safe="-_.~") for part in nreg.split("/"))


def parse_yyyymmdd(value: Any) -> str | None:
    if value is None or value == "":
        return None
    s = str(value).strip()
    if DATE_RE.fullmatch(s):
        try:
            dt.datetime.strptime(s, "%Y%m%d")
        except ValueError:
            return None
        return s
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return dt.datetime.strptime(s, fmt).strftime("%Y%m%d")
        except ValueError:
            pass
    return None


def valid_edition_id(value: Any) -> str | None:
    """Повертає звичайний YYYYMMDD або умовний 3000xxxx; інше відкидає."""
    s = str(value or "").strip()
    if CONDITIONAL_RE.fullmatch(s):
        return s
    return parse_yyyymmdd(s)


def edition_date(ed: Any) -> str | None:
    """Календарна дата редакції YYYYMMDD: для звичайної — сам ідентифікатор, для окремої
    редакції того самого дня (9–10 цифр) — перші 8 цифр; для умовної 3000xxxx — None."""
    s = str(ed or "").strip()
    if CONDITIONAL_RE.fullmatch(s):
        return None
    if DATE_RE.fullmatch(s):
        return parse_yyyymmdd(s)
    if SAME_DAY_RE.fullmatch(s):
        return parse_yyyymmdd(s[:8])
    return None


def edition_sort_key(item: dict[str, Any]) -> tuple[str, int, str]:
    """Порядок редакцій у картці: дата, порядок у межах дня (poriadok_u_dni), ідентифікатор.

    Умовні 3000xxxx ідуть після всіх календарних. npa.py бере останню редакцію з датою ≤ дати,
    тому для дня з кількома редакціями чинною на цей день вважається остання за порядком."""
    ed = str(item.get("ed", ""))
    try:
        order = int(item.get("poriadok_u_dni") or 0)
    except (TypeError, ValueError):
        order = 0
    return (ed[:8], order, ed)


def invalid_edition_reason(value: Any) -> str:
    """Пояснює, чому ідентифікатор редакції відхилено (для журналу аномалій)."""
    s = str(value or "").strip()
    if not s:
        return "порожнє значення"
    if not s.isdigit():
        return "містить нецифрові символи"
    if len(s) != 8:
        return f"{len(s)} цифр замість 8"
    return "неіснуюча календарна дата"


_MODIFIED_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M",
                     "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%Y%m%d%H%M%S", "%Y%m%d%H%M",
                     "%Y-%m-%d", "%d.%m.%Y", "%Y%m%d")


def parse_modified(value: Any) -> str | None:
    """Нормалізує поле modified із doc-update до 'YYYY-MM-DDTHH:MM:SS'.

    Невідомий формат повертає None: значення не вигадується (див. ТЗ v4.1, розд. 3.6).
    Unix-час (10 цифр) приймається лише в правдоподібному діапазоні 2000–2100 рр.
    """
    s = str(value or "").strip().strip('"')
    if not s:
        return None
    if re.fullmatch(r"\d{10}", s):
        stamp = int(s)
        if 946684800 <= stamp <= 4102444800:
            return dt.datetime.fromtimestamp(stamp, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        return None
    s2 = re.sub(r"(\.\d+)?([+-]\d{2}:?\d{2}|Z)?$", "", s)
    for fmt in _MODIFIED_FORMATS:
        try:
            return dt.datetime.strptime(s2, fmt).strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    return None


def date_display(ed: str | None) -> str:
    if not ed or ed.startswith("3000"):
        return ""
    return f"{ed[6:8]}.{ed[4:6]}.{ed[:4]}"




def split_pidstava(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        raw = [str(x).strip() for x in value]
    else:
        raw = re.split(r"\s*[|;,]\s*", str(value))
    return [x for x in raw if x]


def _records(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        record_keys = {"datred", "poddat", "ed", "date", "podid", "comment"}
        if record_keys.intersection(value):
            return [value]
        return list(value.values())
    return [value]


def _date_from_http_header(value: str | None) -> str | None:
    """Парсить DocumentDate; Last-Modified для цього не підходить."""
    if not value:
        return None
    value = value.strip()
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed:
            return parsed.date().strftime("%Y%m%d")
    except (TypeError, ValueError, OverflowError):
        pass
    for fmt in ("%a, %d %b %Y", "%d.%m.%Y", "%Y-%m-%d", "%Y%m%d"):
        try:
            return dt.datetime.strptime(value, fmt).strftime("%Y%m%d")
        except ValueError:
            continue
    return None


def header_value(headers: Any, name: str) -> str | None:
    wanted = name.lower()
    for key, value in (headers or {}).items():
        if str(key).lower() == wanted:
            return str(value)
    return None


def _conditional_header_matches(raw: str | None, requested_ed: str) -> bool:
    """Перевіряє штучний DocumentDate для умовних 3000xxxx.

    Портал повертає від'ємний Unix timestamp, який для 30000101 відповідає
    даті 1100-01-01 UTC. Валідація приймає лише точний штучний день 1100-MM-DD,
    що відповідає MMDD із запитаного ідентифікатора. Будь-яке інше значення
    відхиляється. Це окрема перевірка, не звичайна календарна дата.
    """
    if not raw or not re.fullmatch(r"-?\d+", raw.strip()):
        return False
    try:
        stamp = int(raw.strip())
        epoch = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
        actual = (epoch + dt.timedelta(seconds=stamp)).date()
        expected = dt.date(1100, int(requested_ed[4:6]), int(requested_ed[6:8]))
        return actual == expected
    except (ValueError, OverflowError, OSError):
        return False


def validate_document_date(headers: Any, *, requested_ed: str | None = None,
                           expected_current_ed: str | None = None,
                           allow_unversioned_current: bool = False,
                           allow_conditional: bool = False) -> str:
    """Перевіряє фактичну дату відповіді API до будь-якого запису файлу."""
    raw = header_value(headers, "DocumentDate")
    if requested_ed and requested_ed.startswith("3000"):
        if allow_conditional and _conditional_header_matches(raw, requested_ed):
            return requested_ed
        raise EditionDateMismatch(
            f"DocumentDate для умовної редакції {requested_ed} не підтверджує її штучний день 1100-MM-DD; "
            "текст не збережено."
        )
    actual = _date_from_http_header(raw)
    if not actual:
        raise EditionDateMismatch(
            "Сервер не надав коректного заголовка DocumentDate; текст не збережено."
        )
    if requested_ed:
        expected = edition_date(requested_ed) or requested_ed
    else:
        expected = expected_current_ed
        if not expected and allow_unversioned_current:
            return actual
        if not expected:
            raise EditionDateMismatch(
                "Немає datred у картці для перевірки поточного тексту; текст не збережено."
            )
    if actual != expected:
        raise EditionDateMismatch(
            f"Сервер повернув редакцію від {date_display(actual)}, "
            f"але було запитано/очікувалося {date_display(expected)}. Текст не збережено."
        )
    return actual


def decode_text(raw: bytes, *, preferred: str = "utf-8") -> str:
    # Спершу строгий UTF-8: байти cp1251 з кирилицею майже ніколи не є коректним UTF-8,
    # а навпаки декодування cp1251 «успішне» завжди (дає mojibake).
    for encoding in ("utf-8-sig", preferred, "cp1251"):
        try:
            return raw.decode(encoding).replace("\ufeff", "")
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace").replace("\ufeff", "")


def clean_plain_text(text: str) -> str:
    # Не нормалізуємо апострофи, пробіли чи юридичний текст; лише EOL/BOM.
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


# v4.1.8: перевірка тексту API відносно наявного тексту (старого імпорту або попередньої редакції).
_SUP_TOKEN_RE = re.compile(r"(?<![\d.\-/])(\d{1,4})-(\d{1,2})(?![\d\-])")
_VVR_RE = re.compile(r"\(Відомості[^()]*(?:\([^()]*\)[^()]*)*\)")
_PAGE_JUNK = {"×", "Знайти:", "Пошук", "закрити", "Мінімальна довжина слова — 3 символи, не більше 4 слів..."}


def superscript_loss(reference: str, new: str, limit: int = 20) -> list[str]:
    """Позначення з верхнім індексом (через дефіс, «15-1», «258-1»), які в новому тексті втратили дефіс.

    Позначення вважається втраченим, якщо в новому тексті немає «N-M», але є «NM» у тому самому
    контексті (10 символів перед ним, без пробілів, апостроф уніфіковано) хоча б для одного
    входження — так відсіюються збіги з іншими числами (напр. номер ВВР)."""
    def norm(x: str) -> str:
        return re.sub(r"\s+", "", re.sub(r"[’ʼ`´]", "'", x))
    lost: list[str] = []
    checked: set[str] = set()
    new_flat = norm(new)
    occurrences: dict[str, list[int]] = {}
    for m in _SUP_TOKEN_RE.finditer(reference):
        lst = occurrences.setdefault(m.group(0), [])
        if len(lst) < 50:
            lst.append(m.start())
    for tok, starts in occurrences.items():
        if tok in checked:
            continue
        checked.add(tok)
        if re.search(r"(?<![\d.\-/])" + re.escape(tok) + r"(?![\d\-])", new):
            continue
        joined = tok.replace("-", "")
        for st in starts:
            ctx = norm(reference[max(0, st - 30):st])[-10:]
            if ctx and (ctx + joined) in new_flat:
                lost.append(tok)
                break
        if len(lost) >= limit:
            break
    return lost


def _flat_content(text: str, drop_notes: bool = True) -> str:
    t = re.sub(r"[’ʼ`´]", "'", text.replace("\r\n", "\n")).replace("\u00a0", " ")
    t = t.replace("/*", " ").replace("*/", " ")
    lines = []
    for line in t.split("\n"):
        ln = " ".join(line.split())
        if not ln or ln in _PAGE_JUNK or ln.endswith("…"):
            continue
        lines.append(ln)
    flat = "".join(lines)
    if drop_notes:
        flat = re.sub(r"\{[^{}]*\}", "", flat)
    return flat.replace(" ", "")


def legacy_matches_api(old_body: str, new_body: str) -> tuple[bool, str]:
    """Чи збігається зміст старого тексту (браузерний імпорт) з текстом API.

    Ігноруються: зміст сторінки на початку старого тексту, поле пошуку, скорочені заголовки «…»,
    вид апострофа, позначки /* */ і примітки у фігурних дужках. Повертає (збіг, опис першої розбіжності)."""
    a, b = _VVR_RE.sub("", _flat_content(old_body)), _VVR_RE.sub("", _flat_content(new_body))
    if a == b:
        return True, ""
    # Вирівнювання за початком першої статті: у старому тексті перед ним — зміст сторінки.
    k = b.find("Стаття1.")
    if k >= 0:
        ia = a.rfind(b[k:k + 20], 0, 40000 + k)
        if ia >= 0:
            if a[ia:] == b[k:] and a[:ia].endswith(b[:k]):
                return True, ""
            a, b = a[ia:], b[k:]
    else:
        head = b[:30]
        i = a.find(head, 1) if head and a.startswith(head) else -1
        if 0 < i < 40000:
            if a[i:] == b:
                return True, ""
            a = a[i:]
    k = next((j for j in range(min(len(a), len(b))) if a[j] != b[j]), min(len(a), len(b)))
    return False, f"старий: …{a[max(0, k - 40):k + 60]}… / API: …{b[max(0, k - 40):k + 60]}…"


def previous_text(root: Path, nreg: str, editions: list[dict[str, Any]], ed: str) -> str | None:
    """Тіло тексту найближчої попередньої редакції, що є в архіві (для перевірки нового тексту)."""
    ids = [e.get("ed") for e in sorted(editions, key=edition_sort_key) if e.get("ed")]
    if ed not in ids:
        return None
    for prev in reversed(ids[:ids.index(ed)]):
        p = root / "akty" / slug(nreg) / "red" / f"{prev}.txt"
        if p.exists():
            try:
                return split_text_file(p.read_bytes().decode("utf-8"))[1]
            except (OSError, UnicodeDecodeError):
                return None
    return None


_HTML_TAG_RE = re.compile(
    r"<\s*/?\s*(?:html|head|body|title|meta|link|script|style|div|span|table|tbody|tr|td|th|p|br|a|"
    r"form|input|iframe|noscript|header|footer|nav|ul|ol|li|h[1-6]|img|section|article|main|aside|"
    r"figure|pre|code|strong|em|center|font|label|button|select|option|textarea|svg)\b[^<>]{0,500}>",
    re.I)
# Пара «відкривальний + закривальний тег з тим самим ім'ям» — будь-який елемент, напр. <main>…</main>.
_HTML_PAIR_RE = re.compile(r"<\s*([a-zA-Z][a-zA-Z0-9-]{0,30})\b[^<>]{0,500}>.{0,20000}?<\s*/\s*\1\s*>", re.S)


def looks_like_html(text: str) -> bool:
    """Чи є відповідь HTML-сторінкою, а не текстом редакції (v4.1.3 — посилена евристика).

    * ігнорує BOM, пробіли, XML-декларацію і HTML-коментарі перед першим тегом;
    * маркери <!doctype html, <html, <head, <body — у перших 4000 символах після них;
    * </html> або </body> у кінці відповіді;
    * щільність HTML-тегів: ≥ 5 структурних тегів у перших 50 000 символах;
    * v4.1.4: відповідь починається з тегу (`<` + ASCII-літера (v4.1.5), `!`, `/`, `?`) — короткі фрагменти на кшталт
      `<div><p>Помилка</p></div>`; пара відкривального й закривального тегу з тим самим ім'ям (`<main>…</main>`).
    Перевірено на всіх текстах архіву: жодного хибного спрацювання (tests/live/scan_html_fp.py).
    """
    if not text:
        return False
    s = text.lstrip("\ufeff \t\r\n")
    for _ in range(50):
        if s.startswith("<!--"):
            end = s.find("-->")
            s = s[end + 3:].lstrip("\ufeff \t\r\n") if end >= 0 else ""
        elif s[:5].lower() == "<?xml":
            end = s.find("?>")
            s = s[end + 2:].lstrip("\ufeff \t\r\n") if end >= 0 else ""
        else:
            break
    # Текст редакції ніколи не починається з тегу (у 3 304 текстах архіву немає жодного символу «<»).
    # v4.1.5: лише ASCII-літера — кириличні позначення на кшталт «<підпис>» на початку тексту не є тегом.
    if len(s) > 1 and s[0] == "<" and ((s[1].isascii() and s[1].isalpha()) or s[1] in "!/?"):
        return True
    head = s[:4000].lower()
    if head.startswith(("<!doctype html", "<html", "<head", "<body")):
        return True
    if any(m in head for m in ("<!doctype html", "<html", "<head>", "<head ", "<body")):
        return True
    tail = text.rstrip()[-2000:].lower()
    if "</html>" in tail or "</body>" in tail:
        return True
    if _HTML_PAIR_RE.search(text[:50000]):
        return True
    return len(_HTML_TAG_RE.findall(text[:50000])) >= 5


def parse_podia(raw: bytes) -> dict[str, str]:
    """Розбирає офіційний довідник подій podia.txt (TSV, Windows-1251)."""
    text = decode_text(raw, preferred="cp1251")
    mapping: dict[str, str] = {}
    for line in text.splitlines():
        cols = line.strip().split("\t")
        if len(cols) >= 2 and cols[0].strip().isdigit() and cols[1].strip():
            mapping[cols[0].strip()] = cols[1].strip()
    return mapping


def _event_from_hist(item: Any, podia: dict[str, str]) -> dict[str, Any] | None:
    if isinstance(item, dict):
        event_date = parse_yyyymmdd(item.get("poddat") or item.get("date"))
        podid = item.get("podid")
        raw_basis = split_pidstava(item.get("pidstava"))
    elif isinstance(item, (list, tuple)) and item:
        event_date = parse_yyyymmdd(item[0])
        podid = item[1] if len(item) > 1 else None
        raw_basis = split_pidstava(item[2] if len(item) > 2 else [])
    else:
        return None
    if not event_date or event_date.startswith("3000"):
        # 3000xxxx — технічний ідентифікатор умовної редакції, а не дата
        # юридичної події в календарному сенсі. У podii її не записуємо.
        return None
    podid_s = str(podid) if podid is not None else "?"
    label = podia.get(podid_s) or f"Подія бази ВРУ (podid={podid_s})"
    basis = [display_basis(x) for x in raw_basis]
    desc = label
    if basis:
        desc += ", підстава - " + ", ".join(basis)
    return {
        "data": date_display(event_date),
        "opys": desc,
        "podid": podid_s,
        "pidstava": basis,
        "pidstava_nreg": raw_basis,
    }


def _podid_label(podid: Any, podia: dict[str, str]) -> str:
    if podid is None or str(podid).strip() == "":
        return ""
    return podia.get(str(podid).strip(), "")


def _basis_from_description(description: str) -> list[str]:
    match = re.search(r"підстава\s*[-–—:]\s*(.+?)(?:\s+(?:поточна|наступна|попередня|остання|перша)\s+редакція.*)?$",
                      description or "", flags=re.I)
    if not match:
        return []
    return split_pidstava(match.group(1))


def parse_json_card(data: dict[str, Any], fallback_title: str = "",
                    podia: dict[str, str] | None = None,
                    bulk_editions: Iterable[str] = (),
                    bulk_invalid: Iterable[str] = (),
                    resolved_ids: Iterable[str] = ()) -> dict[str, Any]:
    """Парсить JSON-картку, зберігаючи типи подій через podia.txt та сирі nreg.

    resolved_ids — сирі некоректні ідентифікатори, які документовано вирішено
    (команда anomaly --record): лише вони не блокують підтвердження повноти.
    """
    bulk_invalid = list(dict.fromkeys(str(x).strip() for x in bulk_invalid if str(x).strip()))
    resolved = {str(x).strip() for x in resolved_ids if str(x).strip()}
    card_nreg = str(data.get("nreg") or "").strip()
    invalid_records: list[dict[str, str]] = []
    podia = podia or {}
    title = str(data.get("nazva") or fallback_title)
    status = "" if data.get("status") is None else str(data.get("status"))
    status_present = "status" in data
    raw_eds = _records(data.get("eds"))
    orgdat = parse_yyyymmdd(data.get("orgdat"))
    orgnum = str(data.get("orgnum") or data.get("n_vlas") or "").strip()
    editions_by_id: dict[str, dict[str, Any]] = {}

    invalid_eds = 0
    for item in raw_eds:
        if isinstance(item, dict):
            raw_date = (item.get("datred") or item.get("ed") or item.get("date")
                        or item.get("poddat"))
            comment = str(item.get("comment") or item.get("koment") or "").strip()
            raw_basis = split_pidstava(item.get("pidstava"))
            explicit_desc = str(item.get("opys") or item.get("description") or "").strip()
            display_raw = str(item.get("data_na_saiti") or "").strip()
            podid = item.get("podid")
        elif isinstance(item, (list, tuple)) and item:
            raw_date = item[0]
            raw_basis = split_pidstava(item[1] if len(item) > 1 else [])
            comment = explicit_desc = display_raw = ""
            podid = item[2] if len(item) > 2 else None
        else:
            raw_date, raw_basis, comment, explicit_desc, display_raw, podid = item, [], "", "", "", None
        ed = valid_edition_id(raw_date)
        if not ed:
            invalid_eds += 1  # напр. 9-значний ed у джерелі (2343-12: 201301186)
            invalid_records.append({"raw": str(raw_date or "").strip(), "source": "eds",
                                    "nreg": card_nreg, "reason": invalid_edition_reason(raw_date)})
            continue
        label = _podid_label(podid, podia)
        basis = [display_basis(x) for x in raw_basis]
        basis_text = ", ".join(basis)
        if ed.startswith("3000"):
            data_on_site = comment or display_raw or "дата залежить від події"
            # Умова набрання чинності зберігається в data_na_saiti/comment;
            # в описі її не дублюємо (сумісно з наявним архівом).
            desc = explicit_desc or label or "Редакція"
        else:
            data_on_site = display_raw or date_display(ed)
            if explicit_desc:
                desc = explicit_desc
            elif label:
                desc = label
            elif podid is not None:
                desc = f"Подія бази ВРУ (podid={podid})"
            else:
                desc = "Редакція"
        if basis_text and "підстава" not in desc.lower():
            desc += ", підстава - " + basis_text
        editions_by_id[ed] = {
            "ed": ed,
            "data_na_saiti": data_on_site,
            "opys": desc,
            "podid": str(podid) if podid is not None else "",
            "pidstava": basis,
            "pidstava_nreg": raw_basis,
            "comment": comment,
            "bez_posylannia": False,
        }

    top_datred = parse_yyyymmdd(data.get("datred"))
    if top_datred and top_datred not in editions_by_id:
        raw_basis = split_pidstava(data.get("pidstava"))
        basis = [display_basis(x) for x in raw_basis]
        desc = "Поточна редакція (datred із JSON-картки)"
        if basis:
            desc += ", підстава - " + ", ".join(basis)
        editions_by_id[top_datred] = {
            "ed": top_datred,
            "data_na_saiti": date_display(top_datred),
            "opys": desc,
            "podid": "",
            "pidstava": basis,
            "pidstava_nreg": raw_basis,
            "comment": "",
            "bez_posylannia": True,
        }

    # Bulk дати використовуються як пропуски лише тоді, коли API підтверджує
    # існування історії (eds/edcnt/datred). Для документів без історії вони
    # позначаються окремо як дата єдиного snapshot, а не як повна редакція.
    has_edition_history = bool(raw_eds or top_datred or (data.get("edcnt") not in (None, 0, "0", "")))
    bulk_only_dates: set[str] = set()
    if has_edition_history:
        for raw_ed in bulk_editions:
            ed = valid_edition_id(raw_ed)
            if not ed or ed.startswith("3000") or ed in editions_by_id:
                continue
            editions_by_id[ed] = {
                "ed": ed,
                "data_na_saiti": date_display(ed),
                "opys": "Редакція (за набором відкритих даних «Редакції нормативних документів»)",
                "podid": "",
                "pidstava": [],
                "pidstava_nreg": [],
                "comment": "",
                "bez_posylannia": True,
                "source": "doc-update",
            }
    else:
        today_str = dt.date.today().strftime("%Y%m%d")
        bulk_only_dates = {ed for raw_ed in bulk_editions
                           if (ed := valid_edition_id(raw_ed)) and not ed.startswith("3000") and ed <= today_str}

    editions = [editions_by_id[k] for k in sorted(editions_by_id)]
    json_valid = len({x["ed"] for x in editions if x.get("source") != "doc-update" and not x.get("bez_posylannia")})
    doc_update_added = sorted(x["ed"] for x in editions if x.get("source") == "doc-update")
    for raw in bulk_invalid:
        invalid_records.append({"raw": raw, "source": "doc-update", "nreg": card_nreg,
                                "reason": invalid_edition_reason(raw)})
    # Дедуплікація: та сама аномалія з двох джерел — один невирішений запис.
    seen_inv: set[tuple[str, str]] = set()
    uniq_records = []
    for rec in invalid_records:
        key = (rec["raw"], rec["source"])
        if key in seen_inv:
            continue
        seen_inv.add(key)
        uniq_records.append(rec)
    invalid_records = uniq_records
    anomaly_ids = list(dict.fromkeys(rec["raw"] for rec in invalid_records))
    unresolved_ids = [x for x in anomaly_ids if x not in resolved]
    edcnt_raw = data.get("edcnt")
    edcnt = int(edcnt_raw) if str(edcnt_raw or "").isdigit() else None
    # Повнота каталогу: лише коректні редакції (з eds, datred і doc-update) плюс
    # документовано вирішені аномалії. Невирішена аномалія завжди блокує підтвердження.
    counted = len(editions_by_id) + len([x for x in anomaly_ids if x in resolved])
    if not has_edition_history:
        catalog_complete, catalog_reason = False, "API не надає історії редакцій (eds/edcnt/datred)"
    elif edcnt is None or edcnt <= 0:
        catalog_complete, catalog_reason = False, "API не надав edcnt; повноту неможливо звірити"
    elif unresolved_ids:
        catalog_complete = False
        catalog_reason = ("невирішені некоректні ідентифікатори редакцій: " + ", ".join(unresolved_ids)
                          + f" (коректних {len(editions_by_id)} з edcnt={edcnt})")
    elif counted < edcnt:
        catalog_complete = False
        catalog_reason = f"знайдено {counted} редакцій із {edcnt} (edcnt)"
    elif counted > edcnt:
        # Більше редакцій, ніж заявив API, — розбіжність, а не підтвердження (v4.1.1).
        catalog_complete = False
        catalog_reason = (f"знайдено {counted} редакцій — більше, ніж edcnt={edcnt}; розбіжність джерел "
                          f"(з doc-update додано: {len(doc_update_added)})")
    else:
        catalog_complete = True
        catalog_reason = f"знайдено {counted} з edcnt={edcnt}" + (
            f"; вирішені аномалії: {', '.join(x for x in anomaly_ids if x in resolved)}"
            if any(x in resolved for x in anomaly_ids) else "")

    # podid 0 і 6 — записи про редакції/нові редакції; вони вже відображені
    # у redaktsii і не повинні вдруге потрапляти до юридичних podii.
    events: list[dict[str, Any]] = []
    for item in _records(data.get("hist")):
        if isinstance(item, dict):
            pid = item.get("podid")
        elif isinstance(item, (list, tuple)) and len(item) > 1:
            pid = item[1]
        else:
            pid = None
        if str(pid) in {"0", "6"}:
            continue
        event = _event_from_hist(item, podia)
        if event:
            events.append(event)
    events.sort(key=lambda x: (parse_yyyymmdd(x.get("data")) or "99999999", str(x.get("podid", ""))))

    return {
        "nazva": title,
        "stan": status,
        "redaktsii": editions,
        "podii": events,
        "datred": top_datred,
        "edcnt": data.get("edcnt"),
        "poddat": parse_yyyymmdd(data.get("poddat")),
        "pidstava_nreg": split_pidstava(data.get("pidstava")),
        "status_id": "" if data.get("status") is None else str(data.get("status")),
        "status_present": status_present,
        "prefiks": "laws",
        "bulk_only_dates": sorted(bulk_only_dates),
        "orgdat": orgdat,
        "orgnum": orgnum,
        # Сумісне поле: True лише за підтвердженої повноти каталогу (v4.1 — консервативно).
        "history_complete": catalog_complete,
        "edition_catalog_complete": catalog_complete,
        "catalog_reason": catalog_reason,
        "unresolved_edition_ids": unresolved_ids,
        "invalid_source_records": invalid_records,
        "invalid_source_ids": bulk_invalid,
        "invalid_eds": invalid_eds,
        "counts": {"edcnt": edcnt, "json_valid_dates": json_valid,
                   "doc_update_added": doc_update_added, "datred": top_datred,
                   "editions_total": len(editions_by_id), "invalid_unique": len(anomaly_ids)},
    }


def parse_doc_update(raw: bytes) -> tuple[dict[str, set[str]], dict[str, Any]]:
    """Парсить повний TSV doc-update (modified<TAB>nreg<TAB>ed).

    * некоректні ed (напр. 9 цифр) зберігаються без повторів для кожного nreg;
    * modified кожного рядка розбирається окремо від HTTP Last-Modified усього файла;
      для nreg береться максимум коректно розібраних значень;
    * nreg, у рядках якого modified не розібрано, позначається в modified_unparsed —
      для такого акта --changed перевіряє JSON-картку (безпечний fallback).
    """
    text = decode_text(raw, preferred="cp1251")
    rows = list(csv.reader(io.StringIO(text), delimiter="\t"))
    rows = [row for row in rows if row and any(x.strip() for x in row)]
    if not rows:
        raise SyncError("doc-update.txt порожній.")

    header_idx = None
    indexes: dict[str, int] = {}
    for i, row in enumerate(rows[:5]):
        normalized = [cell.strip().lstrip("\ufeff").lower() for cell in row]
        if "nreg" in normalized and "ed" in normalized:
            header_idx = i
            indexes = {name: normalized.index(name) for name in ("nreg", "ed")}
            if "modified" in normalized:
                indexes["modified"] = normalized.index("modified")
            break
    data_rows = rows[header_idx + 1:] if header_idx is not None else rows
    if header_idx is None:
        # Формат без заголовка, підтверджений на порталі: modified<TAB>nreg<TAB>ed.
        indexes = {"modified": 0, "nreg": 1, "ed": 2}

    by_nreg: dict[str, set[str]] = {}
    invalid_by_nreg: dict[str, list[str]] = {}
    modified_by_nreg: dict[str, str] = {}
    modified_unparsed: dict[str, list[str]] = {}
    modified_samples: list[str] = []
    invalid = 0
    invalid_modified = 0
    total = 0
    for row in data_rows:
        total += 1
        try:
            nreg = row[indexes["nreg"]].strip()
            raw_ed = row[indexes["ed"]].strip()
        except IndexError:
            invalid += 1
            continue
        if "modified" in indexes and nreg:
            raw_mod = row[indexes["modified"]].strip() if len(row) > indexes["modified"] else ""
            if len(modified_samples) < 5 and raw_mod:
                modified_samples.append(raw_mod)
            mod = parse_modified(raw_mod)
            if mod:
                if mod > modified_by_nreg.get(nreg, ""):
                    modified_by_nreg[nreg] = mod
            else:
                invalid_modified += 1
                lst = modified_unparsed.setdefault(nreg, [])
                if raw_mod not in lst and len(lst) < 5:
                    lst.append(raw_mod)
        ed = valid_edition_id(raw_ed)
        if not nreg or not ed:
            invalid += 1
            if nreg and raw_ed:
                lst = invalid_by_nreg.setdefault(nreg, [])
                if raw_ed not in lst:
                    lst.append(raw_ed)
            continue
        # Умовні 3000xxxx в bulk-список не додаємо: без коментаря з API
        # їхню умову неможливо достовірно відтворити.
        if ed.startswith("3000"):
            by_nreg.setdefault(nreg, set())
            continue
        by_nreg.setdefault(nreg, set()).add(ed)
    if not by_nreg:
        raise SyncError("doc-update.txt отримано, але не розпізнано рядків nreg/ed.")
    return by_nreg, {"rows": total, "documents": len(by_nreg), "invalid_rows": invalid,
                     "invalid_by_nreg": invalid_by_nreg, "modified_by_nreg": modified_by_nreg,
                     "modified_unparsed": modified_unparsed, "invalid_modified": invalid_modified,
                     "modified_samples": modified_samples}


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


class RadaHTTP:
    def __init__(self, root: Path, pause_min: float = 5.0, pause_max: float = 7.0,
                 timeout: float = 60.0, daily_budget: int = DEFAULT_DAILY_BUDGET,
                 session: requests.Session | None = None, sleep=time.sleep):
        self.root = root
        self.cache_dir = root / ".npa_cache"
        self.state_path = self.cache_dir / "state.json"
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
        self.pause_min = pause_min
        self.pause_max = pause_max
        self.timeout = timeout
        self.daily_budget = daily_budget
        self.sleep = sleep
        self.request_count = 0
        self.basis_lookups = 0
        self.basis_lookup_limit = 30
        self.bytes_today = 0
        self.blocked: str | None = None  # після 403/429 мережеві запити більше не робляться
        self.stats = {"requests": 0, "bytes_downloaded": 0, "responses_304": 0,
                      "cache_hits": 0, "interrupted": 0, "failed": 0}
        self.request_log: list[dict[str, Any]] = []
        self._podia: dict[str, str] | None = None
        self.manual_evidence: dict[str, dict[str, Any]] = {}
        self._load_usage()

    def _log(self, url: str, status: int | str, started: float, nbytes: int = 0,
             headers: Any = None, note: str = "") -> None:
        self.request_log.append({
            "time": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "url": url, "status": status, "bytes": nbytes,
            "ms": int((time.monotonic() - started) * 1000),
            "document_date": header_value(headers, "DocumentDate") or "",
            "last_modified": header_value(headers, "Last-Modified") or "",
            "content_length": header_value(headers, "Content-Length") or "",
            "location": header_value(headers, "Location") or "",
            "note": note,
        })

    def _load_usage(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        state = {}
        if self.state_path.exists():
            try:
                state = json.loads(self.state_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                state = {}
        today = dt.date.today().isoformat()
        if state.get("usage_date") != today:
            state["usage_date"] = today
            state["bytes_today"] = 0
        self.state = state
        self.bytes_today = int(state.get("bytes_today") or 0)

    def _save_state(self) -> None:
        atomic_write(self.state_path, (json.dumps(self.state, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    def _account_bytes(self, amount: int, url: str) -> None:
        if amount <= 0:
            return
        updated = self.bytes_today + amount
        if updated > self.daily_budget:
            raise BudgetExceeded(
                f"Локальний бюджет {self.daily_budget / 1024 / 1024:.0f} MiB/добу буде перевищено "
                f"запитом {url}; отримано ще {amount / 1024 / 1024:.2f} MiB. "
                "Зупиняюся, щоб залишити резерв до офіційного ліміту."
            )
        self.bytes_today = updated
        self.state["usage_date"] = dt.date.today().isoformat()
        self.state["bytes_today"] = updated
        self._save_state()

    def get(self, url: str, *, headers: dict[str, str] | None = None,
            allow_404: bool = False, allow_304: bool = False,
            allow_redirects: bool = False) -> requests.Response | None:
        if self.blocked:
            raise SyncError(f"Мережеві запити зупинено після {self.blocked}; {url} не запитано.")
        host = urlparse(url).hostname or ""
        if host != "data.rada.gov.ua":
            raise SyncError(f"Дозволено лише офіційний API data.rada.gov.ua; запит до {host} не виконано.")
        if self.request_count:
            self.sleep(random.uniform(self.pause_min, self.pause_max))
        self.request_count += 1
        self.stats["requests"] += 1
        started = time.monotonic()
        try:
            response = self.session.get(
                url, headers=headers or {}, timeout=self.timeout,
                allow_redirects=allow_redirects, stream=True,
            )
        except requests.RequestException as exc:
            self.stats["failed"] += 1
            self._log(url, "error", started, note=str(exc)[:200])
            raise SyncError(f"Мережева помилка для {url}: {exc}") from exc
        if response.status_code != 200:
            self._log(url, response.status_code, started, headers=response.headers)

        if allow_redirects:
            final_host = urlparse(response.url).hostname or ""
            if final_host not in {"zakon.rada.gov.ua", "data.rada.gov.ua"}:
                response.close()
                raise SyncError(f"Неприпустиме перенаправлення на сторонній домен: {response.url}")
        if response.status_code == 304 and allow_304:
            self.stats["responses_304"] += 1
            response.close()
            return response
        if response.status_code == 404 and allow_404:
            response.close()
            return None
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location", "")
            response.close()
            raise ManualOnlyError(f"HTTP {response.status_code} → {location}")
        if response.status_code in (401, 403):
            response.close()
            self.blocked = f"HTTP {response.status_code}"
            raise SyncError(
                f"HTTP {response.status_code} для {url}. Перевірте доступ із цієї мережі; "
                "синхронізацію зупинено без спроб обходу обмеження."
            )
        if response.status_code == 429:
            response.close()
            self.blocked = "HTTP 429"
            raise SyncError("HTTP 429: портал обмежив частоту запитів. Синхронізацію зупинено.")
        if response.status_code >= 400:
            code = response.status_code
            response.close()
            self.stats["failed"] += 1
            raise SyncError(f"HTTP {code} для {url}")

        # Потокове читання: якщо Content-Length відомий і не поміщається
        # у бюджет, не завантажуємо тіло. Для gzip-тіл облік консервативний
        # (після декомпресії), що краще за недооблік добового ліміту.
        remaining = max(0, self.daily_budget - self.bytes_today)
        raw_length = response.headers.get("Content-Length")
        if raw_length and raw_length.isdigit() and int(raw_length) > remaining:
            response.close()
            self.stats["interrupted"] += 1
            self._log(url, 200, started, headers=response.headers, note="тіло не читалося: бюджет")
            raise BudgetExceeded(
                f"Тіло {int(raw_length) / 1024 / 1024:.2f} MiB для {url} більше за залишок "
                f"локального бюджету {remaining / 1024 / 1024:.2f} MiB; запит перервано до читання тіла."
            )
        chunks: list[bytes] = []
        received = 0
        try:
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                if received + len(chunk) > remaining:
                    received += len(chunk)
                    self.bytes_today += received
                    self.state["usage_date"] = dt.date.today().isoformat()
                    self.state["bytes_today"] = self.bytes_today
                    self._save_state()
                    response.close()
                    self.stats["interrupted"] += 1
                    self.stats["bytes_downloaded"] += received
                    self._log(url, 200, started, received, response.headers, "потік перервано: бюджет")
                    raise BudgetExceeded(
                        f"Потік {url} перевищив локальний бюджет; отримано {received / 1024 / 1024:.2f} MiB."
                    )
                chunks.append(chunk)
                received += len(chunk)
        except BudgetExceeded:
            raise
        except requests.RequestException as exc:
            response.close()
            self.stats["interrupted"] += 1
            self.stats["bytes_downloaded"] += received
            self._log(url, 200, started, received, response.headers, f"обрив читання: {str(exc)[:120]}")
            if received:
                self._account_bytes(received, url)
            raise SyncError(f"Помилка читання відповіді {url}: {exc}") from exc
        self.stats["bytes_downloaded"] += received
        self._log(url, 200, started, received, response.headers)
        if received:
            self._account_bytes(received, url)
        response._content = b"".join(chunks)
        response._content_consumed = True
        response.close()
        return response

    def get_text(self, url: str, *, allow_404: bool = False) -> tuple[str, dict[str, str]] | None:
        response = self.get(url, allow_404=allow_404)
        if response is None:
            return None
        body = clean_plain_text(decode_text(response.content, preferred="utf-8"))
        if not body or looks_like_html(body):
            raise ManualOnlyError(f"Замість тексту API повернув порожню відповідь або HTML: {url}")
        return body, dict(response.headers)

    def get_json(self, url: str, *, allow_404: bool = False) -> tuple[dict[str, Any], dict[str, str]] | None:
        response = self.get(url, allow_404=allow_404)
        if response is None:
            return None
        ctype = str(response.headers.get("Content-Type", "")).lower()
        try:
            data = response.json()
        except ValueError as exc:
            if "html" in ctype or looks_like_html(response.text):
                raise ManualOnlyError(f"Замість JSON-картки сервер повернув HTML: {url}") from exc
            raise SyncError(f"Відповідь не є коректним JSON: {url}") from exc
        if not isinstance(data, dict):
            raise SyncError(f"Неочікувана структура JSON-картки: {url}")
        if data.get("result") not in (None, "ok"):
            raise ManualOnlyError(f"API не підтвердив картку {url}: result={data.get('result')!r}")
        return data, dict(response.headers)

    def fetch_card(self, nreg: str) -> tuple[dict[str, Any], dict[str, Any]]:
        encoded = encode_nreg(nreg)
        last_problem = None
        attempts: list[str] = []
        for prefix in ("laws", "rada"):
            url = f"{DATA_HOST}/{prefix}/card/{encoded}.json"
            try:
                result = self.get_json(url, allow_404=True)
            except ManualOnlyError as exc:
                last_problem = str(exc)
                attempts.append(f"{url}: {exc}")
                continue
            if result is None:
                last_problem = f"HTTP 404: {url}"
                attempts.append(f"{url}: HTTP 404")
                continue
            data, headers = result
            returned_nreg = str(data.get("nreg") or "").strip()
            if returned_nreg and returned_nreg != nreg:
                raise SyncError(f"JSON-картка для {nreg} містить інший nreg={returned_nreg}; дані не використано.")
            parsed = parse_json_card(data)
            if not parsed["nazva"] and not parsed["redaktsii"]:
                last_problem = f"Картка {url} не містить назви та редакцій."
                attempts.append(f"{url}: HTTP 200, порожня картка")
                continue
            meta = {
                "source": "json-card", "url": url,
                "last_modified": header_value(headers, "Last-Modified") or "",
                "document_date": header_value(headers, "DocumentDate") or "",
                "raw": data, "prefix": prefix,
            }
            parsed["prefiks"] = prefix
            return parsed, meta

        self.manual_evidence[nreg] = {"reason": last_problem or "endpoint недоступний", "http": attempts}
        raise ManualOnlyError(
            f"{nreg}: акт не обслуговується JSON API ({last_problem or 'endpoint недоступний'}). "
            "Оновлювати вручну: HTML-сторінки zakon.rada.gov.ua закриті для програм (robots.txt)."
        )

    def resolve_basis_display(self, basis_nreg: str) -> tuple[str, bool]:
        """Отримує офіційний номер документа-підстави з його JSON-картки.

        Невідомий номер повертається без змін і позначається unresolved; евристичної
        конвертації суфікса скликання немає. Результат кешується локально.
        """
        basis_nreg = str(basis_nreg).strip()
        cache_path = self.cache_dir / "basis_numbers.json"
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        except (OSError, ValueError):
            cache = {}
        if basis_nreg in cache:
            item = cache[basis_nreg]
            resolved_before = bool(item.get("resolved"))
            if resolved_before:
                return str(item.get("display") or basis_nreg), True
            checked = str(item.get("checked_at") or "")
            try:
                checked_date = dt.datetime.fromisoformat(checked.replace("Z", "+00:00")).date()
                retry_after = dt.date.today() - checked_date
            except ValueError:
                retry_after = dt.timedelta(days=31)
            if retry_after < dt.timedelta(days=30):
                return basis_nreg, False
        if self.basis_lookups >= self.basis_lookup_limit:
            return basis_nreg, False
        self.basis_lookups += 1
        encoded = encode_nreg(basis_nreg)
        resolved = ""
        for prefix in ("laws", "rada"):
            url = f"{DATA_HOST}/{prefix}/card/{encoded}.json"
            try:
                result = self.get_json(url, allow_404=True)
            except ManualOnlyError:
                continue
            if result is None:
                continue
            data, _headers = result
            if str(data.get("nreg") or basis_nreg) != basis_nreg:
                continue
            resolved = str(data.get("orgnum") or data.get("n_vlas") or "").strip()
            if resolved:
                break
        entry = {"display": resolved or basis_nreg, "resolved": bool(resolved),
                 "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        cache[basis_nreg] = entry
        atomic_write(cache_path, (json.dumps(cache, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        return entry["display"], entry["resolved"]

    def enrich_basis(self, parsed: dict[str, Any], old_card: dict[str, Any] | None = None) -> None:
        old_map = {x.get("ed"): x for x in (old_card or {}).get("redaktsii", []) if x.get("ed")}
        for item in parsed.get("redaktsii", []):
            old = old_map.get(item.get("ed")) or {}
            # Існуючий опис підстави з архіву — пріоритетне джерело для старих редакцій.
            if old.get("pidstava"):
                item["pidstava"] = list(old.get("pidstava") or [])
                if old.get("pidstava_nreg"):
                    item["pidstava_nreg"] = list(old.get("pidstava_nreg") or [])
                item["basis_unresolved"] = []
                continue
            raw_ids = list(item.get("pidstava_nreg") or item.get("pidstava") or [])
            display, unresolved = [], []
            for raw in raw_ids:
                val, ok = self.resolve_basis_display(raw)
                display.append(val)
                if not ok:
                    unresolved.append(raw)
            if display:
                item["pidstava"] = display
                item["pidstava_nreg"] = raw_ids
                item["basis_unresolved"] = unresolved
        old_events = list((old_card or {}).get("podii", []))
        for event in parsed.get("podii", []):
            raw_ids = list(event.get("pidstava_nreg") or event.get("pidstava") or [])
            # Події минулих років уже мають перевірені людиною описи в архіві.
            # Зіставляємо їх за датою та типом; не запускаємо сотні запитів за старими підставами.
            identity = (parse_yyyymmdd(event.get("data")), _event_label_core(event))
            old_match = next((old for old in old_events
                              if isinstance(old, dict)
                              and (parse_yyyymmdd(old.get("data")), _event_label_core(old)) == identity), None)
            if old_match:
                if old_match.get("pidstava"):
                    event["pidstava"] = list(old_match.get("pidstava") or [])
                old_basis = _basis_from_description(str(old_match.get("opys", "")))
                if old_basis and not event.get("pidstava"):
                    event["pidstava"] = old_basis
                if old_match.get("opys"):
                    event["opys"] = old_match["opys"]
                event["pidstava_nreg"] = list(old_match.get("pidstava_nreg") or raw_ids)
                event["basis_unresolved"] = []
                continue
            # Для нової події не вигадуємо римський номер. Зберігаємо raw nreg;
            # офіційний номер можна буде підтвердити окремим запитом за потреби.
            event["pidstava_nreg"] = raw_ids
            event["pidstava"] = raw_ids
            event["basis_unresolved"] = raw_ids[:] if raw_ids else []

    def fetch_edition_text(self, nreg: str, ed: str | None,
                           preferred_prefix: str = "laws") -> tuple[str, str, dict[str, str], int]:
        encoded = encode_nreg(nreg)
        suffix = f"/ed{ed}" if ed else ""
        prefixes = [preferred_prefix] + [p for p in ("laws", "rada") if p != preferred_prefix]
        last_error = None
        for prefix in prefixes:
            url = f"{DATA_HOST}/{prefix}/show/{encoded}{suffix}.txt"
            try:
                result = self.get_text(url, allow_404=True)
            except ManualOnlyError as exc:
                last_error = str(exc)
                continue
            if result is None:
                continue
            body, headers = result
            response_bytes = len(body.encode("utf-8"))
            return body, prefix, headers, response_bytes
        raise ManualOnlyError(
            f"TXT endpoint для {nreg} ({ed or 'поточна редакція'}) недоступний. {last_error or ''}"
        )

    def fetch_verified_text(self, nreg: str, ed: str | None, preferred_prefix: str,
                            *, expected_current_ed: str | None = None,
                            allow_unversioned_current: bool = False,
                            allow_conditional: bool = False) -> tuple[str, str, dict[str, str], str, str]:
        """Лише TXT API; повертає body, prefix, headers, actual_date, source."""
        source = "txt-api"
        body, prefix, headers, _size = self.fetch_edition_text(nreg, ed, preferred_prefix)
        actual = validate_document_date(
            headers, requested_ed=ed, expected_current_ed=expected_current_ed,
            allow_unversioned_current=allow_unversioned_current,
            allow_conditional=allow_conditional,
        )
        return body, prefix, headers, actual, source

    def fetch_doc_update(self, *, force: bool = False) -> tuple[dict[str, set[str]], dict[str, Any]]:
        """Завантажує/перевіряє кеш повного doc-update.txt через Last-Modified."""
        cache_path = self.cache_dir / "doc-update.txt"
        last_modified = "" if force else str(self.state.get("doc_update_last_modified") or "")
        headers = {"If-Modified-Since": last_modified} if last_modified and cache_path.exists() else {}
        response = self.get(DOC_UPDATE_URL, headers=headers, allow_404=True, allow_304=True)
        if response is None:
            raise SyncError(f"Не вдалося отримати офіційний набір редакцій: {DOC_UPDATE_URL}")
        if response.status_code == 304:
            if not cache_path.exists():
                # Без локального тіла 304 не допомагає; повтор без умови.
                response = self.get(DOC_UPDATE_URL, allow_404=True)
                if response is None:
                    raise SyncError("Сервер повернув 304, але локальний кеш doc-update відсутній.")
                raw = response.content
            else:
                raw = cache_path.read_bytes()
                self.stats["cache_hits"] += 1
            used_cache = True
        else:
            raw = response.content
            atomic_write(cache_path, raw)
            lm = header_value(response.headers, "Last-Modified") or ""
            if lm:
                self.state["doc_update_last_modified"] = lm
                self._save_state()
            used_cache = False
        mapping, stats = parse_doc_update(raw)
        stats.update({
            "last_modified": self.state.get("doc_update_last_modified", ""),
            "used_cache": used_cache,
            "bytes": len(raw),
        })
        return mapping, stats

    def fetch_podia(self, *, refresh: bool = False) -> dict[str, str]:
        """Офіційний довідник назв подій podia.txt (не podia.dat).

        Перевіряється на сервері через If-Modified-Since не частіше разу на добу
        (або щоразу з refresh=True); метадані — у state.json (podia_*). Якщо сервер
        недоступний, використовується кеш із попередженням у stats.
        """
        if self._podia is not None and not refresh:
            return self._podia
        cache_path = self.cache_dir / "podia.txt"
        today = dt.date.today().isoformat()
        cached = parse_podia(cache_path.read_bytes()) if cache_path.exists() else {}
        if cached and not refresh and self.state.get("podia_checked_on") == today:
            self.stats["cache_hits"] += 1
            self._podia = cached
            return cached
        lm = str(self.state.get("podia_last_modified") or "")
        headers = {"If-Modified-Since": lm} if lm and cached else {}
        try:
            response = self.get(PODIA_URL, headers=headers, allow_404=True, allow_304=True)
        except BudgetExceeded:
            raise
        except SyncError:
            if cached:
                self.stats["cache_hits"] += 1
                self._podia = cached
                return cached
            raise
        if response is None or response.status_code == 304:
            self.stats["cache_hits"] += 1
            parsed = cached
        else:
            parsed = parse_podia(response.content)
            if not parsed:
                raise SyncError("Офіційний podia.txt не вдалося розібрати; кеш не перезаписано.")
            atomic_write(cache_path, response.content)
            self.state["podia_last_modified"] = header_value(response.headers, "Last-Modified") or ""
            self.state["podia_sha256"] = hashlib.sha256(response.content).hexdigest()
            self.state["podia_fetched_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            self.state["podia_entries"] = len(parsed)
        self.state["podia_checked_on"] = today
        self._save_state()
        self._podia = parsed
        return parsed

    def save_request_log(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for rec in self.request_log:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")



def load_perelik(root: Path) -> list[dict[str, str]]:
    path = root / "perelik_aktiv.csv"
    if not path.exists():
        raise SyncError(f"Не знайдено {path}. Вкажіть --root на корінь репозиторію.")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def status_text(value: Any) -> str:
    numeric = "" if value is None else str(value).strip()
    return STATUS_BY_ID.get(numeric, numeric)


def resolve_status(raw_api: dict[str, Any] | None, existing: dict[str, Any] | None) -> tuple[str, str, str]:
    """Повертає (stan, status_id, попередження).

    * поля status немає у відповіді API → зберігається попередній stan (задокументований fallback);
    * status = null → так само попередній stan, з попередженням;
    * status = 0 → stan порожній («не визначено»), старий стан не успадковується;
    * відомий ID → назва зі STATUS_BY_ID;
    * невідомий ID → stan порожній, сирий ID у api.status_id і попередження.
    """
    raw_api = raw_api or {}
    old = str((existing or {}).get("stan") or "")
    if "status" not in raw_api:
        return old, "", "API не передало поле status; стан залишено з попередньої картки" if old else ""
    value = raw_api.get("status")
    if value is None:
        return old, "", "API передало status=null; стан залишено з попередньої картки" if old else ""
    sid = str(value).strip()
    if sid in STATUS_BY_ID:
        return STATUS_BY_ID[sid], sid, ""
    return "", sid, f"невідомий status={sid}; назву не приписано, сирий ID збережено в api.status_id"


def _event_key(event: dict[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    return (
        str(event.get("data", "")),
        str(event.get("podid", "")),
        tuple(sorted(str(x) for x in (event.get("pidstava") or []))),
    )


def _is_edition_event(event: dict[str, Any]) -> bool:
    podid = str(event.get("podid", ""))
    desc = str(event.get("opys", "")).strip().lower()
    return podid in {"0", "6"} or desc.startswith("редакція") or desc.startswith("нова редакція")


def _event_label_core(event: dict[str, Any]) -> str:
    desc = re.sub(r"\s+", " ", str(event.get("opys", "")).strip()).casefold()
    desc = re.sub(r"\s+стан:\s*.*$", "", desc)
    desc = re.sub(r",?\s*\d+\s*кб.*$", "", desc)
    desc = re.sub(r",\s*підстава\s*[-–—:].*$", "", desc)
    desc = re.sub(r"\s+(?:поточна|наступна|попередня|остання|перша) редакція.*$", "", desc)
    known = (
        "визнання неконституційними окремих положень",
        "визнання конституційними окремих положень",
        "набрання чинності", "втрата чинності", "введення в дію",
        "зупинення дії", "відновлення дії", "тлумачення", "прийняття",
    )
    for label in known:
        if desc.startswith(label):
            return label
    return desc.strip(" ;,:.-")


def _event_semantic_key(event: dict[str, Any]) -> tuple[Any, ...]:
    date = parse_yyyymmdd(event.get("data"))
    label = _event_label_core(event)
    if ", підстава" in str(event.get("opys", "")).lower():
        basis = _basis_from_description(str(event.get("opys", "")))
    else:
        basis = [str(x) for x in (event.get("pidstava") or [])]
    return date, label, tuple(sorted(basis))


def merge_events(new_events: list[dict[str, Any]], old_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Зберігає старі розгорнуті описи, не дублює записи про ті самі події."""
    merged: list[dict[str, Any]] = []
    seen_full: set[tuple[Any, ...]] = set()
    old_identity: set[tuple[str | None, str]] = set()
    # Події, збережені v4+ з API, мають podid: їх зіставляємо за (дата, podid), щоб
    # зміна назви в podia.txt оновлювала підпис, а не створювала дубль.
    new_by_podid = {}
    for ev in new_events or []:
        if isinstance(ev, dict) and str(ev.get("podid", "?")) not in ("", "?"):
            new_by_podid[(parse_yyyymmdd(ev.get("data")), str(ev.get("podid")))] = ev
    consumed: set[int] = set()
    for event in old_events or []:
        if isinstance(event, dict) and str(event.get("podid", "")) not in ("", "?") and not _is_edition_event(event):
            match = new_by_podid.get((parse_yyyymmdd(event.get("data")), str(event.get("podid"))))
            if match is not None:
                upd = dict(event)
                old_opys = str(event.get("opys", ""))
                tail = re.search(r",\s*підстава\s*[-–—:].*$", old_opys)
                upd["opys"] = _description_label(match.get("opys", "")) + (tail.group(0) if tail else "")
                key = _event_semantic_key(upd)
                if key not in seen_full:
                    seen_full.add(key)
                    old_identity.add((key[0], key[1]))
                    merged.append(upd)
                consumed.add(id(match))
                continue
        if not isinstance(event, dict) or _is_edition_event(event):
            continue
        event_date = parse_yyyymmdd(event.get("data"))
        if not event_date or event_date.startswith("3000"):
            continue
        key = _event_semantic_key(event)
        if key in seen_full:
            continue
        seen_full.add(key)
        old_identity.add((key[0], key[1]))
        merged.append(dict(event))
    for event in new_events or []:
        if not isinstance(event, dict) or _is_edition_event(event) or id(event) in consumed:
            continue
        date = parse_yyyymmdd(event.get("data"))
        if not date or date.startswith("3000"):
            continue
        key = _event_semantic_key(event)
        identity = (key[0], key[1])
        # Якщо для цієї дати й типу події вже є старий опис, залишаємо його:
        # зазвичай він має офіційний номер підстави та додаткові реквізити.
        if identity in old_identity:
            continue
        if key in seen_full:
            continue
        seen_full.add(key)
        merged.append(dict(event))
    return sorted(merged, key=lambda e: (parse_yyyymmdd(e.get("data")) or "99999999", str(e.get("podid", ""))))


def _description_label(value: Any) -> str:
    text = re.sub(r"\s+стан:\s*.*$", "", str(value or "").strip(), flags=re.I)
    text = re.sub(r",?\s*\d+\s*кб.*$", "", text, flags=re.I)
    text = re.sub(r",\s*підстава\s*[-–—:].*$", "", text, flags=re.I)
    text = re.sub(r"\s+(?:поточна|наступна|попередня|остання|перша) редакція.*$", "", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def _is_generic_edition_description(value: Any) -> bool:
    label = _description_label(value).casefold()
    return label in {"редакція", "поточна редакція (datred із json-картки)", "редакція (за набором відкритих даних «редакції нормативних документів»)"}


def _merge_edition_metadata(new_item: dict[str, Any], old_item: dict[str, Any] | None) -> dict[str, Any]:
    item = dict(new_item)
    if not old_item:
        return item
    # Старі офіційні підстави з архіву переважають технічні nreg з API.
    old_basis = list(old_item.get("pidstava") or [])
    if old_basis:
        item["pidstava"] = old_basis
    if old_item.get("pidstava_nreg"):
        item["pidstava_nreg"] = list(old_item.get("pidstava_nreg") or [])

    old_desc = str(old_item.get("opys") or "").strip()
    new_desc = str(item.get("opys") or "").strip()
    if old_desc:
        old_label = _description_label(old_desc).casefold()
        new_label = _description_label(new_desc).casefold()
        if not new_desc or _is_generic_edition_description(new_desc):
            # API не дала типу редакції: залишаємо старий повний опис.
            item["opys"] = old_desc
        elif old_label and new_label and old_label.startswith(new_label) and len(old_label) > len(new_label):
            # Старий запис має розширену назву (орган, вид акта, реквізити).
            item["opys"] = old_desc
        elif old_basis and "підстава" not in new_desc.lower():
            # Новий podid точніший за старий загальний «Редакція», але підставу
            # беремо зі старої картки, не змінюючи її написання.
            item["opys"] = new_desc + ", підстава - " + ", ".join(old_basis)
    if not item.get("comment") and old_item.get("comment"):
        item["comment"] = old_item["comment"]
    # Метадані завантаження тексту (SHA-256, DocumentDate, джерело) не губимо між запусками.
    for key in ("sha256", "document_date", "text_source"):
        if old_item.get(key) and not item.get(key):
            item[key] = old_item[key]
    if item.get("ed", "").startswith("3000") and old_item.get("data_na_saiti") and not item.get("comment"):
        item["data_na_saiti"] = old_item["data_na_saiti"]
    return item


def _desc_with_basis(desc: str, basis: list[str]) -> str:
    """Збирає опис з мітки події та остаточних (офіційних) номерів підстав.

    Прибирає з опису стару частину «, підстава - …» (у т. ч. сирі nreg з API)
    і хвости на кшталт «Стан: …», «NN кб», «поточна редакція».
    """
    label = _description_label(desc) or "Редакція"
    if label.casefold().startswith(("попередня редакція", "поточна редакція", "наступна редакція")):
        label = "Редакція"  # артефакт старої HTML-картки (zbir.js), а не тип редакції
    return label + (", підстава - " + ", ".join(basis) if basis else "")


def _is_informative_description(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and not _is_generic_edition_description(text)


_SHA_RE = re.compile(r"SHA-256:\s*([0-9a-f]{64})")
_DOCDATE_RE = re.compile(r"^# DocumentDate:\s*([^|]+?)\s*(?:\||$)", re.M)
_LEGACY_DATE_RE = re.compile(r"\|\s*редакція від (\d{2}\.\d{2}\.\d{4})\s*\|")
_SOURCE_RE = re.compile(r"^# Джерело:\s*(\S+)", re.M)


def split_text_file(data: str) -> tuple[list[str], str]:
    """Розділяє файл редакції на рядки шапки ('# ...') і тіло (як у npa.py)."""
    lines = data.split("\n")
    k = 0
    while k < len(lines) and lines[k].startswith("# "):
        k += 1
    rest = lines[k:]
    if rest and rest[0] == "":
        rest = rest[1:]
    if rest and rest[-1] == "":
        rest = rest[:-1]
    return lines[:k], "\n".join(rest)


def classify_text_file(path: Path, ed: str | None, nreg: str | None = None) -> tuple[str, str]:
    """Перевіряє цілісність і походження наявного файла редакції. Нічого не змінює.

    verified — шапка v4/v4.1 з SHA-256, хеш тіла збігається, DocumentDate і джерело
    відповідають редакції. SHA-256 підтверджує лише незмінність після збереження;
    походження — сукупність endpoint (джерело в шапці), DocumentDate і журналу.
    legacy_unverified — старий файл (браузерний імпорт) без SHA/DocumentDate; дата
    в шапці не суперечить імені. corrupt / date_mismatch / missing — див. ТЗ v4.1, розд. 5.
    """
    if not path.exists():
        return "missing", "файла немає"
    try:
        # CRLF → LF: git на Windows (core.autocrlf) міняє лише закінчення рядків, не зміст;
        # SHA-256 у шапці рахується від тіла з LF (як його повертає clean_plain_text).
        data = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
    except UnicodeDecodeError:
        return "corrupt", "файл не є коректним UTF-8"
    except OSError as exc:
        return "corrupt", f"не читається: {exc}"
    header_lines, body = split_text_file(data)
    header = "\n".join(header_lines)
    if not body.strip():
        return "corrupt", "порожнє тіло тексту"
    if looks_like_html(body):
        return "corrupt", "тіло схоже на HTML"
    src = _SOURCE_RE.search(header)
    src_url = src.group(1) if src else ""
    if ed and src_url:
        if not src_url.rstrip("/").endswith(f"/ed{ed}"):
            return "date_mismatch", f"джерело в шапці {src_url} не відповідає редакції {ed}"
    if nreg and src_url and f"/show/{nreg}" not in src_url:
        return "corrupt", f"джерело в шапці {src_url} не відповідає акту {nreg}"
    sha = _SHA_RE.search(header)
    if sha:
        actual = hashlib.sha256(body.encode("utf-8")).hexdigest()
        if actual != sha.group(1):
            return "corrupt", "SHA-256 тіла не збігається із записаним у шапці"
        dd = _DOCDATE_RE.search(header)
        label = dd.group(1).strip() if dd else ""
        if not label:
            return "corrupt", "у шапці з SHA-256 немає DocumentDate"
        if ed and ed.startswith("3000"):
            if f"умовна редакція {ed}" not in label:
                return "date_mismatch", f"DocumentDate «{label}» не підтверджує умовну редакцію {ed}"
        elif ed:
            if parse_yyyymmdd(label) != (edition_date(ed) or ed):
                return "date_mismatch", f"DocumentDate {label} ≠ редакція {date_display(ed)}"
        return "verified", "SHA-256 і DocumentDate збігаються"
    legacy = _LEGACY_DATE_RE.search(header_lines[0] if header_lines else "")
    if ed and legacy and not ed.startswith("3000") and parse_yyyymmdd(legacy.group(1)) != (edition_date(ed) or ed):
        return "date_mismatch", f"у шапці «редакція від {legacy.group(1)}», а файл {ed}"
    return "legacy_unverified", "старий файл без SHA-256/DocumentDate"


def text_counts(editions: list[dict[str, Any]], expected: Iterable[str]) -> dict[str, Any]:
    expected = [e for e in expected if e]
    by_ed = {x.get("ed"): x for x in editions}
    counts = {state: 0 for state in TEXT_STATES}
    for ed in expected:
        st = (by_ed.get(ed) or {}).get("text_status") or "missing"
        counts[st] = counts.get(st, 0) + 1
    counts["expected"] = len(expected)
    return counts


def normalized_card(root: Path, nreg: str, row: dict[str, str], parsed: dict[str, Any],
                    retrieved_at: str, existing: dict[str, Any] | None = None,
                    raw_api: dict[str, Any] | None = None,
                    source: str = "json-card",
                    warnings: list[str] | None = None,
                    doc_update_modified: str | None = None) -> dict[str, Any]:
    existing = existing or {}
    name = parsed.get("nazva") or existing.get("nazva") or row.get("nazva") or nreg
    if any(x in name for x in ("�", "Ð", "Ñ")):
        name = existing.get("nazva") or row.get("nazva") or name
    status, status_id, status_warning = resolve_status(raw_api, existing)
    if status_warning and warnings is not None:
        warnings.append(status_warning)
    old_editions = {x.get("ed"): x for x in existing.get("redaktsii", []) if x.get("ed")}
    red_dir = root / "akty" / slug(nreg) / "red"
    existing_files = {p.stem for p in red_dir.glob("*.txt")} if red_dir.exists() else set()
    editions: list[dict[str, Any]] = []
    for incoming in parsed.get("redaktsii", []):
        ed = incoming.get("ed")
        if not ed:
            continue
        merged = _merge_edition_metadata(incoming, old_editions.get(ed))
        conditional = ed.startswith("3000")
        editions.append({
            "ed": ed,
            "data": None if conditional else date_display(ed),
            "umovna": conditional,
            "data_na_saiti": merged.get("data_na_saiti") or (merged.get("comment") if conditional else date_display(ed)) or "дата залежить від події",
            "opys": (_desc_with_basis(merged.get("opys") or "Редакція", list(merged.get("pidstava") or []))
                     if merged.get("pidstava") else (merged.get("opys") or "Редакція")),
            "podid": str(merged.get("podid") or ""),
            "pidstava": list(merged.get("pidstava") or []),
            "pidstava_nreg": list(merged.get("pidstava_nreg") or []),
            "basis_unresolved": list(merged.get("basis_unresolved") or []),
            "comment": merged.get("comment") or "",
            "tekst": ed in existing_files,
            "text_status": (classify_text_file(red_dir / f"{ed}.txt", ed, nreg)[0]
                            if ed in existing_files else "missing"),
            "bez_posylannia": bool(merged.get("bez_posylannia")),
            "source": merged.get("source", "api"),
            "snapshot_only": bool(merged.get("snapshot_only")),
            **{k: merged[k] for k in ("sha256", "document_date", "text_source") if merged.get(k)},
        })
        _apply_manual(editions[-1], old_editions.get(ed))
    # Bulk дати для документів без історії залишаються єдиним snapshot, а не редакціями.
    bulk_only = list(parsed.get("bulk_only_dates") or [])
    if not editions and bulk_only:
        date = max(bulk_only)
        if date not in {x["ed"] for x in editions}:
            editions.append({
                "ed": date, "data": date_display(date), "umovna": False,
                "data_na_saiti": date_display(date),
                "opys": "Єдиний збережений текст (дата з doc-update; повна історія редакцій відсутня)",
                "podid": "", "pidstava": [], "pidstava_nreg": [],
                "basis_unresolved": [], "comment": "", "tekst": date in existing_files,
                "text_status": (classify_text_file(red_dir / f"{date}.txt", date, nreg)[0]
                                if date in existing_files else "missing"),
                "bez_posylannia": True, "source": "doc-update-single-snapshot",
                "snapshot_only": True,
            })
    # Старі дати не видаляємо, навіть якщо нова картка/набір тимчасово їх не повернув.
    present = {x["ed"] for x in editions}
    for ed, old in old_editions.items():
        if ed in present:
            continue
        old_copy = dict(old)
        old_copy["tekst"] = (ed in existing_files)
        old_copy["text_status"] = (classify_text_file(red_dir / f"{ed}.txt", ed, nreg)[0]
                                   if ed in existing_files else "missing")
        old_copy["source"] = old_copy.get("source") or "archive-only"
        _apply_manual(old_copy, old)
        editions.append(old_copy)
    editions.sort(key=edition_sort_key)

    prefix = str(parsed.get("prefiks") or "laws")
    # Посилання лишається читабельним; URL-кодування використовується лише в HTTP-запитах.
    dzherelo = f"{PUBLIC_HOST}/{prefix}/show/{nreg}"
    mode = row.get("rezhym", existing.get("rezhym", "povna"))
    catalog_complete = bool(parsed.get("edition_catalog_complete", parsed.get("history_complete", False)))
    snapshot = any(x.get("snapshot_only") for x in editions)
    # Сумісне поле для npa.py: історію редакцій підтверджено (каталог повний, режим povna, не snapshot).
    history_complete = catalog_complete and mode == "povna" and not snapshot
    if mode != "povna":
        history_reason = f"режим «{mode}»: зберігається не вся історія редакцій"
    elif snapshot:
        history_reason = "єдиний snapshot без історії редакцій"
    else:
        history_reason = parsed.get("catalog_reason") or ""
    expected_texts = [e for e in choose_editions(mode, editions) if e]
    tcounts = text_counts(editions, expected_texts)
    all_texts_verified = bool(expected_texts) and tcounts["verified"] == tcounts["expected"]
    old_api = existing.get("api") or {}
    card = {
        "nreg": nreg, "nazva": name, "stan": status,
        "rezhym": row.get("rezhym", existing.get("rezhym", "povna")),
        "dzherelo": dzherelo,
        "perevireno": retrieved_at,
        "redaktsii": editions,
        "podii": merge_events(parsed.get("podii", []), existing.get("podii", [])),
        "bez_redaktsii": not bool(editions),
        "api": {
            "datred": parsed.get("datred"), "edcnt": parsed.get("edcnt"),
            "orgdat": parse_yyyymmdd((raw_api or {}).get("orgdat") or parsed.get("orgdat")),
            "orgnum": str((raw_api or {}).get("orgnum") or parsed.get("orgnum") or ""),
            "poddat": parsed.get("poddat"), "status_id": status_id,
            "pidstava_nreg": parsed.get("pidstava_nreg", []),
            "source": source, "history_complete": history_complete,
            "history_reason": history_reason,
            "edition_catalog_complete": catalog_complete,
            "unresolved_edition_ids": list(parsed.get("unresolved_edition_ids") or []),
            "invalid_source_records": list(parsed.get("invalid_source_records") or []),
            "resolved_edition_ids": list(old_api.get("resolved_edition_ids") or []),
            "separate_edition_ids": list(old_api.get("separate_edition_ids") or []),
            "counts": dict(parsed.get("counts") or {}),
            "texts": tcounts,
            "all_texts_verified": all_texts_verified,
            "doc_update_modified": doc_update_modified or old_api.get("doc_update_modified") or "",
            "sync_version": VERSION,
            "checked_at": retrieved_at,
            "snapshot_only": snapshot,
        },
    }
    return card


def _apply_manual(item: dict[str, Any], old: dict[str, Any] | None) -> None:
    """Переносить порядок у межах дня і ручну правку (pravka) зі старої картки.

    Ручна правка має перевагу над описом і підставою з API та старої картки: її вносить
    власник після звірки з карткою сайту, коли API змішує дані (2343-12, 18.01.2013)."""
    if not old:
        return
    if old.get("poriadok_u_dni") not in (None, "", 0):
        item["poriadok_u_dni"] = old["poriadok_u_dni"]
    for key in ("api_text_issue", "api_check"):
        if old.get(key) and not item.get(key):
            item[key] = old[key]
    pr = old.get("ruchna_pravka")
    if isinstance(pr, dict) and (pr.get("opys") or pr.get("pidstava") is not None):
        basis = list(pr.get("pidstava") or [])
        item["pidstava"] = basis
        item["opys"] = _desc_with_basis(pr.get("opys") or item.get("opys") or "Редакція", basis)
        item["ruchna_pravka"] = pr


def choose_editions(mode: str, editions: list[dict[str, Any]], today: dt.date | None = None,
                    include_conditional: bool = False) -> list[str | None]:
    today = today or dt.date.today()
    real_ids = [x["ed"] for x in editions if x.get("ed") and not x["ed"].startswith("3000")]
    conditional_ids = [x["ed"] for x in editions if x.get("ed", "").startswith("3000")]
    if mode == "povna":
        selected: list[str | None] = real_ids if real_ids else [None]
        return selected + (conditional_ids if include_conditional else [])
    eligible = [ed for ed in real_ids if dt.datetime.strptime(edition_date(ed) or ed[:8], "%Y%m%d").date() <= today]
    if mode in ("chynna", "odyn"):
        return [eligible[-1]] if eligible else ([None] if not real_ids else [])
    return []


def existing_text_editions(root: Path, nreg: str) -> set[str]:
    red_dir = root / "akty" / slug(nreg) / "red"
    if not red_dir.exists():
        return set()
    return {p.stem for p in red_dir.glob("*.txt")}


def write_text_file(root: Path, nreg: str, card: dict[str, Any], ed: str | None,
                    text: str, info: dict[str, Any] | None, actual_date: str,
                    digest: str) -> Path:
    folder = root / "akty" / slug(nreg) / "red"
    folder.mkdir(parents=True, exist_ok=True)
    key = ed or "bez_redaktsii"
    path = folder / f"{key}.txt"
    if ed:
        display = date_display(ed) or (info or {}).get("data_na_saiti") or "дата залежить від події"
        desc = (info or {}).get("opys", "Редакція")
        bases = ", ".join((info or {}).get("pidstava") or []) or "—"
        doc_date_label = f"умовна редакція {ed} (штучний DocumentDate перевірено)" if ed.startswith("3000") else date_display(actual_date)
        header = (
            f"# {card['nazva']} | {desc} | {display}\n"
            f"# Підстава: {bases}\n"
            f"# Джерело: {card['dzherelo']}/ed{ed} (© Верховна Рада України; data.rada.gov.ua)\n"
            f"# DocumentDate: {doc_date_label} | SHA-256: {digest}\n"
        )
    else:
        header = (
            f"# {card['nazva']} | поточний текст від {date_display(actual_date)}\n"
            f"# Джерело: {card['dzherelo']} (© Верховна Рада України; data.rada.gov.ua)\n"
            f"# DocumentDate: {date_display(actual_date)} | SHA-256: {digest}\n"
        )
    payload = (header + "\n" + text.rstrip() + "\n").encode("utf-8")
    atomic_write(path, payload)
    return path


def _load_old_card(root: Path, nreg: str) -> dict[str, Any] | None:
    path = root / "akty" / slug(nreg) / "kartka.json"
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SyncError(f"Стара картка {path} пошкоджена; її не перезаписано: {exc}") from exc
    return value if isinstance(value, dict) else None


def sync_one(client: RadaHTTP, root: Path, row: dict[str, str],
             bulk_editions: Iterable[str] = (), *, bulk_invalid: Iterable[str] = (), force: bool = False,
             only_ed: str | None = None, dry_run: bool = False,
             include_conditional: bool = False,
             doc_update_modified: str | None = None) -> dict[str, Any]:
    nreg = str(row.get("nreg", "")).strip()
    mode = str(row.get("rezhym", "povna")).strip()
    if not nreg or mode == "nemaie":
        return {"nreg": nreg, "status": "пропущено", "reason": "немає номера або режим nemaie"}
    if mode not in {"povna", "chynna", "odyn"}:
        raise SyncError(f"Невідомий режим зберігання {mode!r} для {nreg}.")

    old_card = _load_old_card(root, nreg)
    podia = client.fetch_podia()
    parsed, card_meta = client.fetch_card(nreg)
    old_api_meta = (old_card or {}).get("api") or {}
    resolved_ids = [str(x.get("raw")) for x in (list(old_api_meta.get("resolved_edition_ids") or [])
                                                + list(old_api_meta.get("separate_edition_ids") or []))
                    if isinstance(x, dict) and x.get("raw")]
    parsed = parse_json_card(card_meta["raw"], fallback_title=(row.get("nazva") or nreg),
                             podia=podia, bulk_editions=bulk_editions, bulk_invalid=bulk_invalid,
                             resolved_ids=resolved_ids)
    parsed["prefiks"] = card_meta.get("prefix", "laws")
    client.enrich_basis(parsed, old_card)
    if old_card and old_card.get("redaktsii") and not parsed.get("redaktsii"):
        raise SyncError("Нова картка не містить редакцій, хоча стара їх мала; картку не перезаписано.")

    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    info_messages: list[str] = []
    card = normalized_card(root, nreg, row, parsed, retrieved_at, old_card,
                           card_meta.get("raw"), source=card_meta.get("source", "json-card"),
                           warnings=info_messages, doc_update_modified=doc_update_modified)
    editions = card.get("redaktsii", [])
    if parsed.get("unresolved_edition_ids"):
        info_messages.append("повноту історії НЕ підтверджено: " + str(parsed.get("catalog_reason")))

    if only_ed:
        requested = valid_edition_id(only_ed)
        if not requested:
            raise SyncError(f"Некоректна дата редакції {only_ed}; очікується YYYYMMDD або YYYY-MM-DD.")
        if requested.startswith("3000") and not include_conditional:
            raise SyncError("Для умовної редакції додайте --include-conditional; за замовчуванням вони не зберігаються.")
        if requested not in {x["ed"] for x in editions}:
            raise SyncError(f"Редакції {requested} немає в картці або наборі відкритих даних.")
        selected: list[str | None] = [requested]
    else:
        selected = choose_editions(mode, editions, include_conditional=include_conditional)

    if parsed.get("invalid_source_ids"):
        info_messages.append("у наборі doc-update пропущено записи з некоректною датою редакції: "
                             + ", ".join(parsed["invalid_source_ids"]))
    conditional = [x["ed"] for x in editions if str(x.get("ed", "")).startswith("3000")]
    if conditional and mode == "povna" and not include_conditional:
        info_messages.append(
            "умовні редакції не включено до звичайної синхронізації: " + ", ".join(conditional) +
            "; їхні умови збережено в kartka.json"
        )

    written: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    for ed in selected:
        info = next((x for x in editions if x.get("ed") == ed), None) if ed else None
        key = ed or "bez_redaktsii"
        target = root / "akty" / slug(nreg) / "red" / f"{key}.txt"
        if target.exists() and not force:
            skipped.append(key)
            state = (info or {}).get("text_status") or classify_text_file(target, ed, nreg)[0]
            if info is not None:
                info["tekst"] = True
                info["text_status"] = state
            if state in ("corrupt", "date_mismatch"):
                detail = classify_text_file(target, ed, nreg)[1]
                info_messages.append(f"{key}: наявний текст {state} ({detail}); не перезаписано — "
                                     "перевірте verify і відновіть через verify --repair")
            continue
        if dry_run:
            written.append(key)
            continue
        try:
            expected_current = parsed.get("datred") if ed is None else None
            body, actual_prefix, headers, actual_date, text_source = client.fetch_verified_text(
                nreg, ed, parsed.get("prefiks", "laws"),
                expected_current_ed=expected_current,
                allow_unversioned_current=(ed is None),
                allow_conditional=bool(include_conditional),
            )
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            if len(body.strip()) < 20:
                info_messages.append(f"{key}: короткий текст ({len(body)} символів); перевірте його окремо")
            if actual_prefix != card_meta.get("prefix", "laws"):
                card["dzherelo"] = f"{PUBLIC_HOST}/{actual_prefix}/show/{nreg}"
            lost: list[str] = []
            if ed:
                prev_body = previous_text(root, nreg, editions, ed)
                if prev_body:
                    lost = superscript_loss(prev_body, body)
            path = write_text_file(root, nreg, card, ed, body, info, actual_date, digest)
            written.append(str(path.relative_to(root)))
            if info is not None:
                info["tekst"] = True
                info["text_status"] = "verified"
                info["sha256"] = digest
                info["document_date"] = actual_date
                info["text_source"] = text_source
                if lost:
                    info["api_text_issue"] = ("TXT API втрачає верхні індекси (" + ", ".join(lost[:5])
                                              + " у попередній редакції записані через дефіс); номери з верхніми "
                                              "індексами звіряти із сайтом")
            if lost:
                info_messages.append(f"{key}: [УВАГА] у тексті API втрачено верхні індекси ({', '.join(lost[:5])}) — "
                                     "збережено з позначкою api_text_issue; звірити із сайтом")
        except BudgetExceeded:
            raise
        except (SyncError, requests.RequestException) as exc:
            failed.append(key)
            info_messages.append(f"{key}: НЕ збережено — {exc}")

    expected_texts = [e for e in choose_editions(mode, editions) if e]
    card["api"]["texts"] = text_counts(editions, expected_texts)
    card["api"]["all_texts_verified"] = (bool(expected_texts)
                                         and card["api"]["texts"]["verified"] == card["api"]["texts"]["expected"])
    if not dry_run:
        # Для snapshot-only документа зберігаємо саме один датований текст;
        # старий bez_redaktsii.txt не видаляємо автоматично.
        path = root / "akty" / slug(nreg) / "kartka.json"
        payload = (json.dumps(card, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
        if not (path.exists() and _same_card_except_times(path, card)):
            atomic_write(path, payload)

    basis_unresolved = sorted({x for e in editions for x in e.get("basis_unresolved", [])})
    return {
        "nreg": nreg, "title": card.get("nazva", nreg), "mode": mode,
        "editions_in_card": len(editions), "selected": len(selected),
        "written": written, "skipped": skipped, "failed": failed,
        "warnings": info_messages, "basis_unresolved": basis_unresolved,
        "card_source": card_meta.get("source"), "datred": parsed.get("datred"),
        "status": "ok" if not failed else "частково",
        "catalog_complete": parsed.get("edition_catalog_complete"),
        "texts": card["api"]["texts"],
    }


def _strip_times(card: dict[str, Any]) -> dict[str, Any]:
    c = json.loads(json.dumps(card, ensure_ascii=False))
    c.pop("perevireno", None)
    (c.get("api") or {}).pop("checked_at", None)
    return c


def _same_card_except_times(path: Path, card: dict[str, Any]) -> bool:
    """Ідемпотентність: картку не перезаписуємо, якщо змінилися лише часові мітки.

    Виняток: якщо перевірка старіша за 7 днів, мітку «perevireno» оновлюємо, бо npa.py
    за нею попереджає про застарілість архіву.
    """
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    try:
        old_checked = dt.datetime.fromisoformat(str(old.get("perevireno", ""))[:19])
        if (dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - old_checked).days >= 7:
            return False
    except ValueError:
        return False
    return _strip_times(old) == _strip_times(card)


def do_probe(client: RadaHTTP, root: Path, nreg: str, ed: str | None,
             save: bool = False) -> int:
    print(f"Перевірка JSON/TXT API для {nreg}")
    podia = client.fetch_podia()
    parsed, meta = client.fetch_card(nreg)
    parsed = parse_json_card(meta["raw"], podia=podia)
    print(f"[OK] Картка: {meta['source']} ({meta['url']})")
    print(f"     Назва: {parsed.get('nazva') or '—'}")
    print(f"     Редакцій: {len(parsed['redaktsii'])}; юридичних подій: {len(parsed['podii'])}")
    print(f"     datred: {date_display(parsed.get('datred')) or 'не надано'}; edcnt: {parsed.get('edcnt')}")

    expected_current = parsed.get("datred")
    current_body, current_prefix, current_headers, current_actual, current_source = client.fetch_verified_text(
        nreg, None, parsed.get("prefiks", "laws"), expected_current_ed=expected_current,
        allow_unversioned_current=not bool(expected_current),
    )
    print(f"[OK] Поточний текст через {current_source}: DocumentDate={date_display(current_actual)}; "
          f"символів={len(current_body):,}")

    if ed is None:
        normal_ids = [x["ed"] for x in parsed["redaktsii"] if not x["ed"].startswith("3000")]
        historical = [x for x in normal_ids if x != parsed.get("datred")]
        if not historical:
            print("[ІНФО] Історичної редакції в картці не виявлено; перевірено лише поточний текст/snapshot.")
            return 0
        ed = historical[-1]
    requested = valid_edition_id(ed)
    if not requested:
        raise SyncError(f"Некоректна дата редакції: {ed}")
    if requested not in {x["ed"] for x in parsed["redaktsii"]}:
        raise SyncError(f"Редакції {requested} немає в отриманій картці.")

    historical_body, hist_prefix, hist_headers, historical_actual, hist_source = client.fetch_verified_text(
        nreg, requested, parsed.get("prefiks", "laws"),
        allow_conditional=requested.startswith("3000"),
    )
    if requested.startswith("3000"):
        print(f"[OK] Умовна редакція: {requested}; штучний DocumentDate підтверджує 1100-{requested[4:6]}-{requested[6:8]}; "
              f"джерело={hist_source}; символів={len(historical_body):,}. Звичайним запуском не зберігається.")
    else:
        print(f"[OK] Історичний текст через {hist_source}: DocumentDate={date_display(historical_actual)}; "
              f"символів={len(historical_body):,}")
    same = hashlib.sha256(current_body.encode("utf-8")).digest() == hashlib.sha256(historical_body.encode("utf-8")).digest()
    print("[ІНФО] Поточний та запитаний тексти однакові (це очікувано, якщо ed є поточним)." if same else
          "[OK] Поточний та історичний тексти відрізняються.")

    if save:
        out = root / "tests" / "probe-output-v4_1"
        out.mkdir(parents=True, exist_ok=True)
        prefix = slug(nreg)
        (out / f"{prefix}-current.txt").write_text(current_body, encoding="utf-8")
        (out / f"{prefix}-{requested}.txt").write_text(historical_body, encoding="utf-8")
        (out / f"{prefix}-card.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        report = [
            f"nreg: {nreg}", f"edition: {requested}", f"card_source: {meta['source']}",
            f"card_url: {meta['url']}", f"current_document_date: {current_actual}",
            f"historical_document_date: {historical_actual}",
            f"current_source: {current_source}", f"historical_source: {hist_source}",
            f"current_chars: {len(current_body)}", f"historical_chars: {len(historical_body)}",
            f"same_text: {same}", "verification: exact DocumentDate/banner date validated",
        ]
        (out / f"{prefix}-probe.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
        print(f"[OK] Відповіді збережено в {out}")
    return 0


def _card_dates_from_metadata(root: Path, nreg: str) -> tuple[set[str], str | None, dict[str, Any] | None]:
    card = _load_old_card(root, nreg)
    if not card:
        return set(), None, None
    dates = {x.get("ed") for x in card.get("redaktsii", [])
             if x.get("ed") and valid_edition_id(x.get("ed")) and not str(x.get("ed")).startswith("3000")}
    today = dt.date.today().strftime("%Y%m%d")
    dated = sorted(x for x in dates if x <= today)
    datred_api = parse_yyyymmdd((card.get("api") or {}).get("datred"))
    # Не вважаємо майбутній datred чинним станом на сьогодні.
    datred = datred_api if datred_api and datred_api <= today else (dated[-1] if dated else None)
    return dates, datred, card


def _local_dates(root: Path, nreg: str) -> set[str]:
    return existing_text_editions(root, nreg) - {"bez_redaktsii"}


def load_manual_only(root: Path) -> dict[str, dict[str, Any]]:
    path = root / MANUAL_ONLY_PATH
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    items = data.get("akty", data) if isinstance(data, dict) else {}
    return {k: v for k, v in items.items() if isinstance(v, dict)} if isinstance(items, dict) else {}


def save_manual_only(root: Path, items: dict[str, dict[str, Any]]) -> None:
    payload = {
        "opys": ("Акти поза JSON/TXT API data.rada.gov.ua. Статус встановлено фактичною відповіддю API "
                 "(HTTP 302/404 або картка без даних), а не відсутністю в doc-update. "
                 "Оновлюються вручну власником архіву; автоматичне сканування zakon.rada.gov.ua "
                 "заборонене robots.txt і не виконується."),
        "akty": dict(sorted(items.items())),
    }
    atomic_write(root / MANUAL_ONLY_PATH, (json.dumps(payload, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def _manual_recent(entry: dict[str, Any] | None, days: int = MANUAL_RECHECK_DAYS) -> bool:
    if not entry:
        return False
    try:
        checked = dt.datetime.fromisoformat(str(entry.get("checked_at", ""))[:19])
    except ValueError:
        return False
    return (dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - checked).days < days


def record_check(root: Path, nregs: Iterable[str], how: str) -> None:
    """dani/perevirka.json: коли кожен акт востаннє звірено з API/doc-update.

    --changed звіряє незмінені акти за doc-update, не запитуючи їхніх карток, тому
    kartka.json/perevireno для них не оновлюється; дата звірки — тут (її читає npa.py v4.1).
    """
    path = root / "dani" / "perevirka.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError):
        data = {}
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    for n in nregs:
        data[n] = {"checked_at": now, "how": how}
    atomic_write(path, (json.dumps(dict(sorted(data.items())), ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def _is_row_changed(root: Path, row: dict[str, str], bulk_dates: set[str],
                    modified: str | None = None, modified_unparsed: bool = False,
                    manual_entry: dict[str, Any] | None = None) -> tuple[bool, str]:
    nreg = row["nreg"].strip()
    known_dates, old_datred, card = _card_dates_from_metadata(root, nreg)
    files = _local_dates(root, nreg)
    mode = row.get("rezhym", "povna")
    if card is None:
        return True, "картки ще немає"
    if manual_entry and _manual_recent(manual_entry):
        return False, (f"оновлювати вручну: {manual_entry.get('reason', 'API не обслуговує акт')} "
                       f"(перевірено {str(manual_entry.get('checked_at', ''))[:10]})")
    if not bulk_dates and not modified:
        # Відсутність у doc-update не доводить непідтримки API: перевіряємо JSON-картку.
        return True, ("немає в doc-update; перевіряю JSON-картку"
                      + ("" if not manual_entry else " (ручний статус застарів)"))
    api = card.get("api") or {}
    old_mod = str(api.get("doc_update_modified") or "")
    if modified_unparsed:
        # Будь-який нерозпізнаний modified у рядках акта — перевіряємо картку, навіть якщо інші
        # значення розпізнано: невідомий рядок міг бути саме зміною (v4.1.1).
        return True, ("modified у doc-update частково невідомого формату; перевіряю JSON-картку"
                      if modified else "modified у doc-update невідомого формату; перевіряю JSON-картку")
    if modified and not old_mod:
        return True, "у картці ще немає базового modified (перший запуск v4.1)"
    if modified and old_mod and modified != old_mod:
        return True, f"modified змінився: {old_mod} → {modified}"
    today_str = dt.date.today().strftime("%Y%m%d")
    eligible_bulk = {d for d in bulk_dates if d <= today_str}
    latest_bulk = max(eligible_bulk) if eligible_bulk else None
    if mode == "chynna":
        # Для chynna важлива лише остання редакція, яка вже настала.
        # Майбутні редакції в doc-update не повинні робити акт зміненим сьогодні.
        target = latest_bulk or (old_datred if old_datred and old_datred <= today_str else None)
        if target and old_datred != target:
            return True, f"datred змінилася: {old_datred or '—'} → {target}"
        if target and target not in files:
            return True, f"немає тексту чинної редакції {target}"
        return False, "чинна редакція не змінилася; майбутні редакції та історичні файли не враховуються"
    if mode == "odyn":
        target = latest_bulk or old_datred
        if target and old_datred != target:
            return True, f"оновилася дата єдиного snapshot: {old_datred or '—'} → {target}"
        return (bool(target) and target not in files), ("відсутній файл єдиного snapshot" if target and target not in files else "snapshot актуальний")
    missing_metadata = bulk_dates - known_dates
    missing_text = known_dates - files
    if missing_metadata or missing_text:
        why = []
        if missing_metadata:
            why.append(f"{len(missing_metadata)} дат не описано в kartka.json")
        if missing_text:
            why.append(f"{len(missing_text)} текстів відсутні")
        return True, "; ".join(why)
    # Незмінений modified не доводить цілісності старих файлів (див. verify).
    return False, "modified і редакції не змінилися"


def make_client(args: argparse.Namespace, root: Path) -> RadaHTTP:
    return RadaHTTP(root, pause_min=args.pause_min, pause_max=args.pause_max,
                    timeout=args.timeout, daily_budget=int(args.daily_budget_mb * 1024 * 1024))


def print_traffic(client: RadaHTTP, budget_mb: float) -> None:
    st = client.stats
    print(f"  HTTP-запитів: {st['requests']}; завантажено {st['bytes_downloaded'] / 1024 / 1024:.2f} MiB "
          f"(після декомпресії; може відрізнятися від обліку сервера); 304: {st['responses_304']}; "
          f"з кешу: {st['cache_hits']}; перервано: {st['interrupted']}; невдалих: {st['failed']}")
    print(f"  використано локального бюджету за добу: {client.bytes_today / 1024 / 1024:.2f} / {budget_mb:.0f} MiB")


def run_sync(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    rows = load_perelik(root)
    rows = [r for r in rows if r.get("nreg", "").strip() and r.get("rezhym") != "nemaie"]
    if args.nreg:
        rows = [r for r in rows if r.get("nreg", "").strip() == args.nreg]
        if not rows:
            raise SyncError(f"{args.nreg} відсутній у perelik_aktiv.csv або має режим nemaie.")

    client = make_client(args, root)
    try:
        return _run_sync(args, root, rows, client)
    finally:
        if getattr(args, "request_log", None):
            client.save_request_log(Path(args.request_log))


def _run_sync(args: argparse.Namespace, root: Path, rows: list[dict[str, str]], client: RadaHTTP) -> int:
    bulk_map: dict[str, set[str]] = {}
    bulk_invalid_map: dict[str, list[str]] = {}
    modified_map: dict[str, str] = {}
    modified_unparsed: dict[str, list[str]] = {}
    try:
        bulk_map, bulk_stats = client.fetch_doc_update(force=args.refresh_doc_update)
        bulk_invalid_map = bulk_stats.get("invalid_by_nreg", {})
        modified_map = bulk_stats.get("modified_by_nreg", {})
        modified_unparsed = bulk_stats.get("modified_unparsed", {})
        print(f"doc-update: {bulk_stats['documents']:,} документів, {bulk_stats['rows']:,} рядків, "
              f"{bulk_stats['invalid_rows']:,} некоректних ed, {bulk_stats.get('invalid_modified', 0):,} нерозібраних modified; "
              f"Last-Modified файла={bulk_stats['last_modified'] or 'не надано'}; "
              f"кеш={'так' if bulk_stats['used_cache'] else 'ні'}.")
        if bulk_stats.get("modified_samples"):
            print("  зразки modified: " + " | ".join(bulk_stats["modified_samples"][:3]))
    except BudgetExceeded:
        raise
    except SyncError as exc:
        if client.blocked:
            raise
        if args.changed:
            raise SyncError(f"Для --changed потрібен повний набір doc-update; {exc}") from exc
        print(f"[УВАГА] doc-update недоступний; використаю лише JSON-картки: {exc}", file=sys.stderr)

    manual_reg = load_manual_only(root)
    unchanged: list[str] = []
    if args.changed:
        changed_rows = []
        for row in rows:
            nreg = row["nreg"].strip()
            changed, why = _is_row_changed(root, row, bulk_map.get(nreg, set()),
                                           modified=modified_map.get(nreg),
                                           modified_unparsed=bool(modified_unparsed.get(nreg)),
                                           manual_entry=manual_reg.get(nreg))
            if changed:
                changed_rows.append(row)
                print(f"{nreg}: перевірити — {why}")
            elif "вручну" in why:
                print(f"{nreg}: {why}")
            else:
                unchanged.append(nreg)
        print(f"Актів для перевірки: {len(changed_rows)} із {len(rows)}.")
        if unchanged and not args.dry_run:
            record_check(root, unchanged, "doc-update: без змін")
        rows = changed_rows
        if not rows:
            print("Нових редакцій, змін карток і відсутніх текстів не виявлено.")
            print_traffic(client, args.daily_budget_mb)
            return 0

    total_written = total_skipped = total_failed = 0
    total_warnings = 0
    manual: list[str] = []
    hard_errors = 0
    stopped = False
    checked_ok: list[str] = []
    for row in rows:
        nreg = row.get("nreg", "").strip()
        try:
            result = sync_one(client, root, row, bulk_map.get(nreg, set()),
                              bulk_invalid=bulk_invalid_map.get(nreg, []), force=args.force, only_ed=args.ed,
                              dry_run=args.dry_run, include_conditional=args.include_conditional,
                              doc_update_modified=modified_map.get(nreg))
            t = result.get("texts") or {}
            print(f"{nreg}: {result['status']} — {result.get('title', result.get('reason', ''))} "
                  f"[картка: {result.get('card_source', '—')}; каталог {'повний' if result.get('catalog_complete') else 'НЕ підтверджено'}; "
                  f"тексти: {t.get('verified', 0)} перевірено, {t.get('legacy_unverified', 0)} legacy, "
                  f"{t.get('corrupt', 0) + t.get('date_mismatch', 0)} проблемних, {t.get('missing', 0)} відсутніх з {t.get('expected', 0)}]")
            if result.get("written"):
                print("  записано/до запису: " + ", ".join(result["written"][:12]))
                total_written += len(result["written"])
            total_skipped += len(result.get("skipped", []))
            total_failed += len(result.get("failed", []))
            for warning in result.get("warnings", []):
                print("  [ІНФО] " + warning)
                total_warnings += 1
            if result.get("basis_unresolved"):
                print("  [УВАГА] не вдалося підтвердити офіційний номер підстави редакції; збережено сирий nreg: "
                      + ", ".join(result["basis_unresolved"][:12]))
            if nreg in manual_reg and not args.dry_run:
                manual_reg.pop(nreg, None)
                save_manual_only(root, manual_reg)
                print(f"  [ІНФО] {nreg} тепер обслуговується API; знято з реєстру ручних актів")
            if result.get("status") == "ok":
                checked_ok.append(nreg)
        except ManualOnlyError as exc:
            manual.append(nreg)
            print(f"{nreg}: ОНОВЛЮВАТИ ВРУЧНУ — {exc}")
            if not args.dry_run and client.manual_evidence.get(nreg):
                ev = client.manual_evidence[nreg]
                manual_reg[nreg] = {
                    "nazva": row.get("nazva") or row.get("skorocheno") or nreg,
                    "reason": ev.get("reason", str(exc)),
                    "http": ev.get("http", []),
                    "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                    "dzherelo": ((_load_old_card(root, nreg) or {}).get("dzherelo")
                                 or f"{PUBLIC_HOST}/laws/show/{nreg}"),
                }
                save_manual_only(root, manual_reg)
        except BudgetExceeded as exc:
            print(f"ЗУПИНКА ЗА БЮДЖЕТОМ ТРАФІКУ: {exc}", file=sys.stderr)
            stopped = True
            break
        except SyncError as exc:
            print(f"{nreg}: ПОМИЛКА — {exc}", file=sys.stderr)
            hard_errors += 1
            if client.blocked:
                print("Подальші запити зупинено.", file=sys.stderr)
                stopped = True
                break
    if checked_ok and not args.dry_run:
        record_check(root, checked_ok, "JSON-картка")

    print("\nПідсумок:")
    print(f"  нових/планових файлів: {total_written}")
    print(f"  вже наявних файлів: {total_skipped}")
    print(f"  текстів, які не вдалося зберегти: {total_failed}")
    print(f"  інформаційних повідомлень: {total_warnings}")
    print(f"  справжніх помилок: {hard_errors + total_failed}")
    print(f"  документів, які потребують ручної перевірки: {len(manual)}" + (f" ({', '.join(manual)})" if manual else ""))
    print_traffic(client, args.daily_budget_mb)
    # Штатні попередження та документи поза API не роблять запуск помилковим.
    return 1 if hard_errors or total_failed or stopped else 0


def _rows_for(root: Path, nreg: str | None) -> list[dict[str, str]]:
    rows = [r for r in load_perelik(root) if r.get("nreg", "").strip() and r.get("rezhym") != "nemaie"]
    if nreg:
        rows = [r for r in rows if r["nreg"].strip() == nreg]
        if not rows:
            raise SyncError(f"{nreg} відсутній у perelik_aktiv.csv або має режим nemaie.")
    return rows


def audit_act(root: Path, row: dict[str, str]) -> dict[str, Any]:
    """Класифікує всі файли редакцій акта й очікувані, але відсутні тексти."""
    nreg = row["nreg"].strip()
    mode = row.get("rezhym", "povna")
    card = _load_old_card(root, nreg) or {}
    editions = card.get("redaktsii", [])
    red_dir = root / "akty" / slug(nreg) / "red"
    files = {p.stem for p in red_dir.glob("*.txt")} if red_dir.exists() else set()
    expected = [e for e in choose_editions(mode, editions) if e] if editions else []
    items: list[dict[str, str]] = []
    for ed in sorted(files | set(expected)):
        e = None if ed == "bez_redaktsii" else ed
        state, detail = classify_text_file(red_dir / f"{ed}.txt", e, nreg)
        items.append({"ed": ed, "state": state, "detail": detail, "expected": ed in expected})
    counts = {state: sum(1 for x in items if x["state"] == state) for state in TEXT_STATES}
    return {"nreg": nreg, "mode": mode, "items": items, "counts": counts, "card": bool(card),
            "missing_card": not bool(card)}


def run_verify(args: argparse.Namespace) -> int:
    """Аудит цілісності текстів. Без --repair нічого не змінює й мережі не використовує."""
    root = args.root.resolve()
    rows = _rows_for(root, args.nreg)
    total = {state: 0 for state in TEXT_STATES}
    report: list[dict[str, Any]] = []
    problems: list[tuple[str, dict[str, str]]] = []
    missing_cards: list[str] = []
    for row in rows:
        res = audit_act(root, row)
        report.append(res)
        for k, v in res["counts"].items():
            total[k] += v
        line = ", ".join(f"{k} {v}" for k, v in res["counts"].items() if v)
        print(f"{res['nreg']:14} {res['mode']:6} {line or 'файлів немає'}")
        if res["missing_card"]:
            missing_cards.append(res["nreg"])
            print(f"    ⚠ missing_card: немає akty/{slug(res['nreg'])}/kartka.json — очікуваний набір редакцій "
                  f"неможливо перевірити; спершу sync --nreg {res['nreg']}")
        for it in res["items"]:
            if it["state"] in ("corrupt", "date_mismatch") or (it["state"] == "missing" and it["expected"]):
                problems.append((res["nreg"], it))
                print(f"    {it['ed']}: {it['state']} — {it['detail']}")
    print("\nРазом: " + ", ".join(f"{k} {v}" for k, v in total.items())
          + f"; актів без картки (missing_card): {len(missing_cards)}"
          + (f" ({', '.join(missing_cards)})" if missing_cards else ""))
    print("legacy_unverified — старі файли браузерного імпорту без SHA-256/DocumentDate: їх не видалено й не "
          "перезаписано; для цитування звіряти з офіційним джерелом за посиланням у шапці файла.")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps({"version": VERSION, "total": total, "missing_card": missing_cards,
                                               "akty": report},
                                              ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"Звіт: {args.json}")
    if not args.repair:
        # Ненульовий код, якщо є хоч один очікуваний відсутній, пошкоджений або з невірною датою текст,
        # або для акта з переліку немає kartka.json (v4.1.2). Відсутні файли поза очікуваним набором
        # режиму до problems не потрапляють.
        return 1 if problems or missing_cards else 0
    if missing_cards:
        print("Відновлення неможливе для актів без kartka.json: " + ", ".join(missing_cards)
              + ". Спершу sync --nreg <номер>; інші цілі відновлюються як звичайно.")

    # --repair: лише явний запит; завантаження з перевіркою DocumentDate, атомарний запис.
    targets = [(n, it) for n, it in problems if it["state"] in ("corrupt", "date_mismatch", "missing")]
    if args.include_legacy:
        targets += [(r["nreg"], it) for r in report for it in r["items"] if it["state"] == "legacy_unverified"]
    if not targets:
        print("Відновлювати нічого.")
        return 1 if missing_cards else 0
    client = make_client(args, root)
    fixed = failed = skipped = kept = 0
    stopped = ""
    done: set[tuple[str, str]] = set()
    try:
        for nreg, it in targets:
            if stopped:
                break
            ed = None if it["ed"] == "bez_redaktsii" else it["ed"]
            card = _load_old_card(root, nreg)
            if not card:
                print(f"{nreg} {it['ed']}: немає kartka.json — пропущено")
                skipped += 1
                continue
            info = next((x for x in card.get("redaktsii", []) if x.get("ed") == ed), None)
            if ed and ed.startswith("3000") and not args.include_conditional:
                print(f"{nreg} {ed}: умовна редакція — потрібен --include-conditional; пропущено")
                skipped += 1
                continue
            if (it["state"] == "legacy_unverified" and info is not None and info.get("api_text_issue")
                    and not getattr(args, "force", False)):
                print(f"{nreg} {it['ed']}: текст API раніше визнано неточним ({info['api_text_issue'][:80]}…); "
                      "пропущено (повторно — лише з --force)")
                skipped += 1
                continue
            try:
                body, prefix, headers, actual, source = client.fetch_verified_text(
                    nreg, ed, (re.search(r"/(laws|rada)/show/", card.get("dzherelo", "")) or [None, "laws"])[1],
                    expected_current_ed=(card.get("api") or {}).get("datred") if ed is None else None,
                    allow_unversioned_current=(ed is None), allow_conditional=bool(args.include_conditional))
            except BudgetExceeded as exc:
                print(f"ЗУПИНКА ЗА БЮДЖЕТОМ: {exc}")
                stopped = "бюджет трафіку"
                break
            except SyncError as exc:
                print(f"{nreg} {it['ed']}: НЕ відновлено — {exc}")
                failed += 1
                if client.blocked:
                    stopped = client.blocked
                continue
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            text_path = root / "akty" / slug(nreg) / "red" / f"{it['ed']}.txt"
            if it["state"] == "legacy_unverified" and text_path.exists():
                # v4.1.8: старий текст замінюється лише за збігу змісту і без втрати верхніх індексів.
                old_body = split_text_file(text_path.read_bytes().decode("utf-8"))[1]
                same, why = legacy_matches_api(old_body, body)
                lost = superscript_loss(old_body, body)
                if lost or not same:
                    issue = ("TXT API втрачає верхні індекси (" + ", ".join(lost[:5]) + ")") if lost else \
                            "зміст TXT API відрізняється від тексту браузерного імпорту"
                    print(f"{nreg} {it['ed']}: залишено старий текст — {issue}" + (f"; {why[:220]}" if why else ""))
                    if info is not None:
                        info["api_text_issue"] = issue + "; залишено текст браузерного імпорту, звірити із сайтом"
                        info["api_check"] = {"checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                                             "api_sha256": digest, "zbih_zmistu": same,
                                             "vtracheni_indeksy": lost[:10], "rozbizhnist": why[:400]}
                        atomic_write(root / "akty" / slug(nreg) / "kartka.json",
                                     (json.dumps(card, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
                    kept += 1
                    continue
            elif ed and info is not None:
                prev_body = previous_text(root, nreg, card.get("redaktsii", []), ed)
                lost = superscript_loss(prev_body, body) if prev_body else []
                if lost:
                    info["api_text_issue"] = ("TXT API втрачає верхні індекси (" + ", ".join(lost[:5])
                                              + "); номери з верхніми індексами звіряти із сайтом")
                    print(f"{nreg} {it['ed']}: [УВАГА] у тексті API втрачено верхні індекси ({', '.join(lost[:5])})")
            write_text_file(root, nreg, card, ed, body, info, actual, digest)
            if info is not None:
                info.update({"tekst": True, "text_status": "verified", "sha256": digest,
                             "document_date": actual, "text_source": source})
                atomic_write(root / "akty" / slug(nreg) / "kartka.json",
                             (json.dumps(card, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
            fixed += 1
            done.add((nreg, it["ed"]))
            print(f"{nreg} {it['ed']}: відновлено ({it['state']} → verified)")
    finally:
        if args.request_log:
            client.save_request_log(Path(args.request_log))
    remaining = len(targets) - fixed - kept
    print(f"Ціль: {len(targets)}; відновлено: {fixed}; залишено старий текст: {kept}; не вдалося: {failed}; "
          f"пропущено: {skipped}; "
          f"залишилося невідновленими: {remaining}" + (f" (зупинка: {stopped})" if stopped else ""))
    print_traffic(client, args.daily_budget_mb)
    # Повний успіх — лише якщо відновлено всі цілі (v4.1.1) і немає актів без картки (v4.1.2).
    return 0 if remaining == 0 and not missing_cards else 1


def txt_response_problem(resp: Any) -> str:
    """Причина, з якої відповідь TXT API не можна вважати текстом редакції ('' — придатна).

    Вимоги (v4.1.2): саме HTTP 200; Content-Type, якщо наданий, без «html»; тіло непорожнє і не HTML.
    Конкретного MIME-типу (text/plain) не вимагаємо: офіційний API може віддавати TXT з іншим.
    """
    if resp is None:
        return "немає відповіді"
    if getattr(resp, "status_code", None) != 200:
        return f"HTTP {getattr(resp, 'status_code', '?')} замість 200"
    ctype = str(header_value(resp.headers, "Content-Type") or "").lower()
    if "html" in ctype:
        return f"Content-Type {ctype} — HTML, а не текст"
    body = clean_plain_text(decode_text(resp.content))
    if not body.strip():
        return "порожнє тіло відповіді"
    if looks_like_html(body):
        return "тіло відповіді — HTML-сторінка"
    return ""


def run_anomaly(args: argparse.Namespace) -> int:
    """Перевіряє некоректний ідентифікатор редакції через офіційний TXT API.

    Висновок «duplicate_of» робиться лише тоді, коли сервер повертає для ed{raw} текст
    з DocumentDate D, D — коректна редакція з картки, raw починається з D, D не є поточною
    редакцією (тобто це не «мовчазна підміна» чинним текстом) і SHA-256 тексту збігається
    з текстом ed{D}. В інших випадках — inconclusive; повнота лишається непідтвердженою.
    З --record доказ записується в kartka.json (api.resolved_edition_ids).
    """
    root = args.root.resolve()
    nreg, raw = args.nreg, str(args.raw).strip()
    card = _load_old_card(root, nreg)
    if not card:
        raise SyncError(f"Немає kartka.json для {nreg}.")
    record_separate = bool(getattr(args, "record_separate", False))
    if record_separate:
        if getattr(args, "record", False):
            raise SyncError("--record і --record-separate взаємовиключні.")
        if getattr(args, "order", None) not in ("before", "after"):
            raise SyncError("Для --record-separate вкажіть --order before або --order after "
                            "(місце редакції серед редакцій того самого дня за карткою сайту).")
        if not SAME_DAY_RE.fullmatch(raw) or not edition_date(raw):
            raise SyncError(f"{raw}: окрема редакція того самого дня має 9–10 цифр, перші 8 — дата.")
    client = make_client(args, root)
    evidence: dict[str, Any] = {"raw": raw, "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    body: str | None = None
    try:
        parsed, meta = client.fetch_card(nreg)
        raw_eds = [str(x.get("datred") if isinstance(x, dict) else x) for x in _records(meta["raw"].get("eds"))]
        evidence["in_json_eds"] = raw in raw_eds
        evidence["edcnt"] = meta["raw"].get("edcnt")
        evidence["datred"] = parse_yyyymmdd(meta["raw"].get("datred"))
        valid = {x["ed"] for x in parsed["redaktsii"]}
        url = f"{DATA_HOST}/laws/show/{encode_nreg(nreg)}/ed{raw}.txt"
        try:
            resp = client.get(url, allow_404=True)
        except BudgetExceeded:
            raise
        except SyncError as exc:
            resp = False
            evidence.update({"http": "error", "verdict": "inconclusive", "why": f"запит ed{raw} не вдався: {str(exc)[:200]}"})
        if resp is False:
            pass
        elif resp is None:
            evidence.update({"http": 404, "verdict": "inconclusive", "why": "TXT API повертає 404"})
        elif txt_response_problem(resp):
            evidence.update({"http": resp.status_code, "verdict": "inconclusive",
                             "why": f"відповідь на ed{raw} не є текстом редакції: {txt_response_problem(resp)}"})
        else:
            dd = _date_from_http_header(header_value(resp.headers, "DocumentDate"))
            body = clean_plain_text(decode_text(resp.content))
            sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
            evidence.update({"http": resp.status_code, "document_date": dd or "", "sha256": sha,
                             "chars": len(body)})
            if not dd:
                evidence.update({"verdict": "inconclusive", "why": "немає коректного DocumentDate"})
            elif dd == evidence["datred"]:
                evidence.update({"verdict": "inconclusive",
                                 "why": "сервер повернув поточну редакцію (ймовірна мовчазна підміна)"})
            elif dd in valid and raw.startswith(dd):
                evidence["reference_ed"] = dd
                try:
                    ref = client.get(f"{DATA_HOST}/laws/show/{encode_nreg(nreg)}/ed{dd}.txt", allow_404=True)
                except BudgetExceeded:
                    raise
                except SyncError as exc:   # напр. 302 → ManualOnlyError: висновок контрольований
                    ref = None
                    evidence["reference_error"] = str(exc)[:200]
                if ref is not None and txt_response_problem(ref):
                    evidence["reference_error"] = "контрольна відповідь не є текстом редакції: " + txt_response_problem(ref)
                    ref = None
                if ref is None:
                    evidence.update({"verdict": "inconclusive",
                                     "why": "контрольна редакція ed{0} недоступна: {1}".format(
                                         dd, evidence.get("reference_error", "HTTP 404"))})
                    ref_dd = ref_sha = None
                else:
                    ref_dd = _date_from_http_header(header_value(ref.headers, "DocumentDate"))
                    ref_sha = hashlib.sha256(clean_plain_text(decode_text(ref.content)).encode("utf-8")).hexdigest()
                    evidence.update({"reference_document_date": ref_dd or "", "reference_sha256": ref_sha})
                if ref is None:
                    pass
                elif ref_dd == dd and ref_sha == sha:
                    evidence.update({"verdict": f"duplicate_of:{dd}",
                                     "why": f"ed{raw} і ed{dd} повертають той самий текст редакції від {date_display(dd)}"})
                else:
                    evidence.update({"verdict": "inconclusive", "why": f"тексти ed{raw} і ed{dd} відрізняються"})
            else:
                evidence.update({"verdict": "inconclusive",
                                 "why": f"DocumentDate {dd} не є префіксом {raw} або не входить до каталогу"})
    finally:
        if args.request_log:
            client.save_request_log(Path(args.request_log))
    print(json.dumps(evidence, ensure_ascii=False, indent=1))
    if args.record and str(evidence.get("verdict", "")).startswith("duplicate_of:") \
            and evidence.get("sha256") and evidence.get("sha256") == evidence.get("reference_sha256"):
        api = card.setdefault("api", {})
        lst = [x for x in api.get("resolved_edition_ids", []) if isinstance(x, dict) and x.get("raw") != raw]
        lst.append(evidence)
        api["resolved_edition_ids"] = lst
        atomic_write(root / "akty" / slug(nreg) / "kartka.json",
                     (json.dumps(card, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
        print("Доказ записано в kartka.json (api.resolved_edition_ids); повноту перерахує наступний sync.")
    elif args.record:
        print("Висновок не є доказом дубліката — у картку нічого не записано.")
    if record_separate:
        problem = _separate_problem(evidence, raw, body)
        if problem:
            print(f"Окрему редакцію НЕ записано: {problem}")
            print_traffic(client, args.daily_budget_mb)
            return 1
        _record_separate(root, nreg, card, raw, body or "", evidence, args)
    print_traffic(client, args.daily_budget_mb)
    return 0


def _separate_problem(evidence: dict[str, Any], raw: str, body: str | None) -> str:
    """'' — доказ окремої редакції того самого дня достатній; інакше причина відмови."""
    day = edition_date(raw)
    if body is None or not evidence.get("sha256"):
        return "текст ed{0} не отримано ({1})".format(raw, evidence.get("why", "немає відповіді"))
    if evidence.get("document_date") != day:
        return f"DocumentDate {evidence.get('document_date') or '—'} не збігається з датою {day} у ідентифікаторі"
    if evidence.get("reference_ed") != day:
        return evidence.get("why") or f"дата {day} відсутня серед коректних редакцій картки"
    if not evidence.get("reference_sha256"):
        return "контрольний текст ed{0} недоступний: {1}".format(day, evidence.get("reference_error", "—"))
    if evidence.get("reference_document_date") != day:
        return f"контрольний текст має DocumentDate {evidence.get('reference_document_date') or '—'}"
    if evidence["reference_sha256"] == evidence["sha256"]:
        return "тексти однакові — це дублікат; використайте --record"
    return ""


def _record_separate(root: Path, nreg: str, card: dict[str, Any], raw: str, body: str,
                     evidence: dict[str, Any], args: argparse.Namespace) -> None:
    """Записує окрему редакцію того самого дня: текст, рядок у картці, доказ у api."""
    day = edition_date(raw) or raw[:8]
    basis = split_pidstava(getattr(args, "pidstava", None) or "")
    label = str(getattr(args, "opys", None) or "Редакція").strip()
    order = -1 if args.order == "before" else 1
    info = {"opys": _desc_with_basis(label, basis), "pidstava": basis}
    write_text_file(root, nreg, card, raw, body, info, day, evidence["sha256"])
    item = {
        "ed": raw, "data": date_display(day), "umovna": False, "data_na_saiti": date_display(day),
        "opys": info["opys"], "podid": "", "pidstava": basis, "pidstava_nreg": [],
        "basis_unresolved": [],
        "comment": (f"окрема редакція того самого дня; ідентифікатор порталу {raw}; "
                    f"{'перед' if order < 0 else 'після'} ed{day} за карткою сайту"),
        "tekst": True, "text_status": "verified", "bez_posylannia": False,
        "source": "api-separate", "snapshot_only": False, "poriadok_u_dni": order,
        "sha256": evidence["sha256"], "document_date": day,
        "text_source": f"{DATA_HOST}/laws/show/{encode_nreg(nreg)}/ed{raw}.txt",
    }
    eds = [x for x in card.get("redaktsii", []) if x.get("ed") != raw]
    eds.append(item)
    eds.sort(key=edition_sort_key)
    card["redaktsii"] = eds
    api = card.setdefault("api", {})
    rec = dict(evidence)
    rec.update({"order": args.order, "opys": label, "pidstava": basis,
                "verdict": f"separate_same_day:{day}"})
    api["separate_edition_ids"] = [x for x in api.get("separate_edition_ids", [])
                                   if isinstance(x, dict) and x.get("raw") != raw] + [rec]
    api["unresolved_edition_ids"] = [x for x in api.get("unresolved_edition_ids", []) if x != raw]
    atomic_write(root / "akty" / slug(nreg) / "kartka.json",
                 (json.dumps(card, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(f"Окрему редакцію записано: akty/{slug(nreg)}/red/{raw}.txt і kartka.json "
          f"({'перед' if order < 0 else 'після'} {day}); повноту каталогу перерахує наступний sync.")


def run_pravka(args: argparse.Namespace) -> int:
    """Ручне виправлення опису й підстави редакції в kartka.json (без мережі).

    Тіло тексту не змінюється (SHA-256 лишається чинним); у шапці файла замінюється
    лише старий опис і рядок «# Підстава:». Правка зберігається в ruchna_pravka і має
    перевагу під час наступних sync."""
    root = args.root.resolve()
    nreg, ed = args.nreg, str(args.ed).strip()
    card = _load_old_card(root, nreg)
    if not card:
        raise SyncError(f"Немає kartka.json для {nreg}.")
    item = next((x for x in card.get("redaktsii", []) if x.get("ed") == ed), None)
    if item is None:
        raise SyncError(f"Редакції {ed} немає в картці {nreg}.")
    prychyna = str(args.prychyna or "").strip()
    if not prychyna:
        raise SyncError("Вкажіть --prychyna (звідки взято виправлення).")
    basis = split_pidstava(args.pidstava) if args.pidstava is not None else list(item.get("pidstava") or [])
    label = _description_label(args.opys) if args.opys else (_description_label(item.get("opys")) or "Редакція")
    old_opys = str(item.get("opys") or "")
    old_basis = list(item.get("pidstava") or [])
    new_opys = _desc_with_basis(label, basis)
    item["ruchna_pravka"] = {"opys": label, "pidstava": basis, "prychyna": prychyna,
                             "zapysano": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                             "bulo": {"opys": old_opys, "pidstava": old_basis}}
    item["opys"], item["pidstava"] = new_opys, basis
    path = root / "akty" / slug(nreg) / "red" / f"{ed}.txt"
    header_note = "файла тексту немає"
    if path.exists():
        data = path.read_bytes().decode("utf-8")
        nl = "\r\n" if "\r\n" in data else "\n"
        lines = data.split(nl)
        k = 0
        changed = False
        while k < len(lines) and lines[k].startswith("# "):
            if k == 0 and old_opys and old_opys in lines[0]:
                lines[0] = lines[0].replace(old_opys, new_opys)
                changed = True
            elif lines[k].startswith("# Підстава:"):
                lines[k] = "# Підстава: " + (", ".join(basis) or "—")
                changed = True
            k += 1
        if changed:
            atomic_write(path, nl.join(lines).encode("utf-8"))
            header_note = "шапку файла оновлено (тіло без змін)"
        else:
            header_note = "шапку файла не змінено (старий опис у ній не знайдено)"
    atomic_write(root / "akty" / slug(nreg) / "kartka.json",
                 (json.dumps(card, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(f"{nreg} {ed}: «{old_opys}» → «{new_opys}»; {header_note}.")
    return 0


def run_status(args: argparse.Namespace) -> int:
    """Таблиця стану всіх актів: API / вручну, повнота каталогу, тексти (без мережі)."""
    root = args.root.resolve()
    manual = load_manual_only(root)
    lines = ["| nreg | Акт | Режим | Доступ | edcnt | Редакцій у картці | Каталог | Невирішені ID | "
             "Тексти: перевірено / legacy / проблемні / відсутні з очікуваних |",
             "|---|---|---|---|---|---|---|---|---|"]
    tot = {"api": 0, "manual": 0, "unknown": 0}
    for row in _rows_for(root, args.nreg):
        nreg = row["nreg"].strip()
        card = _load_old_card(root, nreg) or {}
        api = card.get("api") or {}
        if nreg in manual:
            access = "вручну"; tot["manual"] += 1
        elif api.get("sync_version") or api.get("source") == "json-card":
            access = "API"; tot["api"] += 1
        else:
            access = "не перевірено"; tot["unknown"] += 1
        res = audit_act(root, row)
        c = res["counts"]
        exp = [x for x in res["items"] if x["expected"]]
        ce = {st: sum(1 for x in exp if x["state"] == st) for st in TEXT_STATES}
        if access == "вручну":
            catalog = "—"
        elif api.get("edition_catalog_complete") is True:
            catalog = "повний"
        elif api.get("edition_catalog_complete") is False:
            catalog = "НЕ підтверджено: " + str(api.get("history_reason") or "")[:60]
        else:
            catalog = "невідомо (картка до v4.1)"
        lines.append(
            f"| {nreg} | {(row.get('skorocheno') or row.get('nazva') or '')[:40]} | {row.get('rezhym')} | {access} | "
            f"{api.get('edcnt', '—')} | {len(card.get('redaktsii', []))} | {catalog} | "
            f"{', '.join(api.get('unresolved_edition_ids') or []) or '—'} | "
            f"{ce['verified']} / {ce['legacy_unverified']} / {ce['corrupt'] + ce['date_mismatch']} / {ce['missing']} з {len(exp)}"
            f"{' (+' + str(c['verified'] + c['legacy_unverified'] - ce['verified'] - ce['legacy_unverified']) + ' інших файлів)' if (c['verified'] + c['legacy_unverified']) > (ce['verified'] + ce['legacy_unverified']) else ''} |")
    head = (f"Стан архіву (sync_api v{VERSION}): API — {tot['api']}, вручну — {tot['manual']}, "
            f"не перевірено — {tot['unknown']}.\n\n")
    out = head + "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"Записано: {args.out}")
    else:
        print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"Безпечна синхронізація npa-redaktsii через офіційний JSON/TXT API (v{VERSION})")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="корінь npa-redaktsii")
    parser.add_argument("--pause-min", type=float, default=5.0, help="мінімальна пауза між запитами")
    parser.add_argument("--pause-max", type=float, default=7.0, help="максимальна пауза між запитами")
    parser.add_argument("--timeout", type=float, default=60.0, help="тайм-аут HTTP-запиту")
    parser.add_argument("--daily-budget-mb", type=float, default=150.0, help="локальний денний бюджет MiB")
    parser.add_argument("--request-log", help="дописати журнал HTTP-запитів (JSONL) у цей файл")
    sub = parser.add_subparsers(dest="command", required=True)
    probe = sub.add_parser("probe", help="перевірити JSON/TXT API для акта")
    probe.add_argument("--nreg", default="2747-15")
    probe.add_argument("--ed", help="історична дата YYYYMMDD або умовна 3000xxxx")
    probe.add_argument("--save", action="store_true", help="зберегти тестові відповіді поза основним архівом")
    sync = sub.add_parser("sync", help="синхронізувати акти з perelik_aktiv.csv")
    sync.add_argument("--nreg", help="один акт")
    sync.add_argument("--all", action="store_true", help="перевірити всі акти")
    sync.add_argument("--changed", action="store_true", help="лише зміни: нові редакції, modified картки, відсутні тексти")
    sync.add_argument("--ed", help="завантажити одну редакцію YYYYMMDD або 3000xxxx")
    sync.add_argument("--force", action="store_true", help="перезаписати вже наявний текст після валідації")
    sync.add_argument("--dry-run", action="store_true", help="показати план без запису")
    sync.add_argument("--refresh-doc-update", action="store_true", help="оновити повний кеш doc-update")
    sync.add_argument("--include-conditional", action="store_true", help="дозволити умовні редакції 3000xxxx з перевіркою штучного DocumentDate")
    ver = sub.add_parser("verify", help="аудит цілісності наявних текстів (без змін; --repair — відновити)")
    ver.add_argument("--nreg", help="один акт")
    ver.add_argument("--json", help="записати повний звіт у JSON")
    ver.add_argument("--repair", action="store_true", help="заново завантажити corrupt/date_mismatch/відсутні тексти з перевіркою DocumentDate")
    ver.add_argument("--include-legacy", action="store_true", help="з --repair: також замінити legacy_unverified (лише явним рішенням власника)")
    ver.add_argument("--include-conditional", action="store_true", help="з --repair: дозволити умовні 3000xxxx")
    ver.add_argument("--force", action="store_true",
                     help="з --repair --include-legacy: повторно перевірити редакції з позначкою api_text_issue")
    an = sub.add_parser("anomaly", help="перевірити некоректний ідентифікатор редакції через TXT API")
    an.add_argument("--nreg", required=True)
    an.add_argument("--raw", required=True, help="сирий ідентифікатор, напр. 201301186")
    an.add_argument("--record", action="store_true", help="записати доказ дубліката в kartka.json")
    an.add_argument("--record-separate", action="store_true",
                    help="записати як окрему редакцію того самого дня (текст відмінний від ed<дата>)")
    an.add_argument("--order", choices=("before", "after"),
                    help="з --record-separate: місце серед редакцій того самого дня за карткою сайту")
    an.add_argument("--opys", help="з --record-separate: вид редакції з картки сайту, напр. «Нова редакція»")
    an.add_argument("--pidstava", help="з --record-separate: підстава з картки сайту, напр. «4212-VI»")
    pr = sub.add_parser("pravka", help="виправити опис і підставу редакції в kartka.json (без мережі)")
    pr.add_argument("--nreg", required=True)
    pr.add_argument("--ed", required=True, help="ідентифікатор редакції, напр. 20130118")
    pr.add_argument("--opys", help="вид редакції, напр. «Редакція» або «Нова редакція»")
    pr.add_argument("--pidstava", help="підстава через кому, напр. «5405-VI, 5410-VI, 5518-VI»")
    pr.add_argument("--prychyna", required=True, help="звідки взято виправлення")
    stt = sub.add_parser("status", help="таблиця стану всіх актів (без мережі)")
    stt.add_argument("--nreg", help="один акт")
    stt.add_argument("--out", help="записати Markdown у файл")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.pause_min < 0 or args.pause_max < args.pause_min:
        raise SystemExit("Некоректні --pause-min / --pause-max")
    if args.daily_budget_mb <= 0:
        raise SystemExit("--daily-budget-mb має бути додатним")
    try:
        if args.command == "probe":
            client = make_client(args, args.root.resolve())
            try:
                return do_probe(client, args.root.resolve(), args.nreg, args.ed, args.save)
            finally:
                if args.request_log:
                    client.save_request_log(Path(args.request_log))
        if args.command == "sync":
            if not (args.nreg or args.all or args.changed):
                raise SystemExit("Вкажіть --nreg НОМЕР, --all або --changed")
            if sum(bool(x) for x in (args.all, args.changed)) > 1:
                raise SystemExit("Не поєднуйте --all і --changed")
            if args.all and args.nreg:
                raise SystemExit("Не поєднуйте --all і --nreg; для одного акта використовуйте лише --nreg")
            return run_sync(args)
        if args.command == "verify":
            return run_verify(args)
        if args.command == "anomaly":
            return run_anomaly(args)
        if args.command == "status":
            return run_status(args)
        if args.command == "pravka":
            return run_pravka(args)
    except SyncError as exc:
        print(f"ПОМИЛКА: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
