# Звіт про виправлення v4.1.1 (за зауваженнями аудиту від 23.11.2026)

Автор: В'ячеслав Плескач. 23.11.2026. Архітектуру не змінено; diff від v4.1 — `v4_1_to_v4_1_1.diff` (169 рядків).

| П. | Що змінено | Нові тести | На коді v4.1 |
|---|---|---|---|
| 2 | `verify` без `--repair`: код 1, якщо є хоч один очікуваний missing / corrupt / date_mismatch; відсутні поза очікуваним набором режиму не рахуються | `test_verify_returns_nonzero_for_missing_expected_only`, `test_missing_outside_expected_set_not_counted` (контроль) | FAIL / ok |
| 3 | `verify --repair`: лічильники «відновлено / не вдалося / пропущено / залишилося», причина зупинки; код 0 лише якщо відновлено всі цілі | `test_verify_repair_budget_exceeded_returns_nonzero`, `test_verify_repair_conditional_skipped_returns_nonzero`, `test_verify_repair_all_targets_fixed_returns_zero` (контроль) | FAIL, FAIL / ok |
| 4 | будь-який нерозпізнаний `modified` у рядках акта → перевірка JSON-картки | `test_mixed_parsed_and_unparsed_modified_falls_back_to_card` (чинний `test_unparsed_modified_falls_back_to_card` лишився) | FAIL |
| 5 | каталог повний лише за `counted == edcnt`; `counted > edcnt` — розбіжність з причиною | `test_more_distinct_editions_than_edcnt_is_not_complete`, `test_more_than_edcnt_via_doc_update_is_not_complete`, `test_exact_edcnt_is_complete` (контроль); тести 2343-12 лишилися | FAIL, FAIL / ok |
| 6 | `SKILL.md`, розд. 7: що без дозволу; що лише за прямим дозволом (мережевий sync, `--force`, `verify --repair`, зміни файлів, commit/push); межі постійного дозволу власника (лише дані в npa-redaktsii); README посилається на нього; інших дозволів на автоматичний push у пакеті немає | перевірено пошуком по SKILL.md, README.md, reports/, CHANGELOG.md | — |
| 7 | `anomaly`: недоступні контрольна редакція чи ed{raw} (404 / 302 / помилка) → `inconclusive` з причиною, без запису в картку | `test_reference_404_inconclusive`, `test_reference_302_inconclusive` | ERROR, ERROR |

**Результати:** Linux, Python 3.13 — 72/72; Windows 11, Python 3.12.10 (ПК користувача) — 72/72, exit=0 (`offline_tests_v4_1_1_windows.txt`). Див. PLATFORMS.md.
На коді v4.1 нові тести дають 6 FAIL і 2 ERROR; 3 контрольні проходять, тобто тести ловлять саме описані вади.

**Перевірено додатково:** на живих даних 23.11.2026 у всіх 44 актах із повним каталогом counted = edcnt, тому
посилення п. 5 не змінює їхнього статусу; 2343-12 / `201301186` лишається невирішеною аномалією,
`history_complete = false`. Повторний live-запуск не проводився (за ТЗ, п. 8.4).

**Не змінювалося:** основний репозиторій `npa-redaktsii`, GitHub, планувальник Windows, дані архіву.

**Відкриті питання:** друга редакція 2343-12 від 18.01.2013 (зберігати чи ні і в якому форматі ID);
імпорт шести актів поза API без `zbir.js`; 3 303 legacy-тексти — вибіркова звірка; реакція `modified`
на зміну картки без нового ed — підтвердиться щотижневими запусками.
