# Звіт про виправлення v4.1.2 (за зауваженнями аудиту v4.1.1 від 23.11.2026)

Автор: В'ячеслав Плескач. 23.11.2026. Архітектуру не змінено; diff від v4.1.1 — `v4_1_1_to_v4_1_2.diff` (146 рядків).

| Розд. | Що змінено | Нові тести | На коді v4.1.1 |
|---|---|---|---|
| 2 | `anomaly`: функція `txt_response_problem()` перевіряє **обидві** відповіді (ed{raw} і контрольну ed{dd}) до обчислення SHA-256: саме HTTP 200; Content-Type без «html» (конкретний MIME не вимагається); непорожнє тіло; тіло не HTML. Інакше — `inconclusive` з причиною, `--record` нічого не пише. Запис доказу додатково вимагає збігу `sha256` і `reference_sha256`. | `test_raw_html_reference_txt`, `test_raw_txt_reference_html`, `test_both_identical_html` (сценарій аудиту), `test_html_body_with_text_mime`, `test_empty_bodies`; контроль — `test_identical_real_txt_still_duplicate` | 5 FAIL / контроль ok |
| 3 | `verify`: стан `missing_card` — окреме попередження з підказкою `sync --nreg`, кількість у підсумку, поле `missing_card` у JSON; ненульовий код, якщо хоч для одного акта з переліку немає `kartka.json` (зокрема коли в `red/` є сторонні файли); `verify --repair` для такого акта нічого не змінює і не повертає успіх. | `test_no_card_no_texts_nonzero`, `test_no_card_with_stray_text_nonzero`, `test_json_report_lists_missing_card`, `test_repair_without_card_no_targets_nonzero`, `test_repair_without_card_nonzero_and_no_changes`; контроль — `test_chynna_odyn_historical_missing_still_ok` | 3 FAIL, 1 ERROR / 2 ok |

**Результати.** Linux, Python 3.13 — 84/84; Windows 11, Python 3.12.10 (ПК користувача, окремий прогін) — 84/84, exit=0 (`offline_tests_v4_1_2_windows.txt`).
На коді v4.1.1 нові тести дають 8 FAIL і 1 ERROR; 3 проходять (контрольні, а також repair без картки з
пошкодженим файлом, який v4.1.1 уже завершував кодом 1).

**Пакет.** Збирається без `__pycache__` і `.pyc` (у ZIP v4.1.1 їх теж не було — `unzip -l` не показує жодного;
імовірно, байткод з'явився під час запуску тестів аудитором). `SHA256SUMS.txt` охоплює всі файли пакета, крім
самого себе.

**Живі перевірки.** LIVE_TEST_RESULTS.md описує прогін **v4.1**; v4.1.1 і v4.1.2 наживо не запускалися.

**Не змінювалося:** основний репозиторій `npa-redaktsii`, GitHub, планувальник Windows, локальний архів; commit/push не робився.

**Відкриті питання** (без змін): друга редакція 2343-12 від 18.01.2013; імпорт шести актів поза API без `zbir.js`;
вибіркова звірка 3 303 legacy-текстів; реакція `modified` на зміну картки без нового ed.
