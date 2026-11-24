# npa_api_v4_1_6_candidate — кандидат пакета v4.1.6 (синхронізатор 4.1.5) для npa-redaktsii

Автор: В'ячеслав Плескач. 23.11.2026.

Синхронізація архіву редакцій НПА лише через офіційний JSON/TXT API data.rada.gov.ua
(`User-Agent: OpenData`). Основа — v4; архітектуру не змінено, HTML fallback не повернуто.
Основний репозиторій і GitHub цим пакетом не змінюються. Дозволи на запуск синхронізації, commit і push — `SKILL.md`, розд. 7.

## Склад

| Шлях | Що це |
|---|---|
| `skrypty/sync_api_v4_1.py` | синхронізатор (версія 4.1.5): `probe`, `sync`, `verify`, `anomaly`, `status` |
| `skrypty/patch_npa_v4_1.py` | необов'язковий патч `npa.py` (резервна копія, `--check`, `--revert`) |
| `tests/test_*.py`, `tests/helpers.py` | 103 офлайн-тести (unittest, без мережі); `tests/run_offline_tests.bat` — запуск на Windows |
| `tests/fixtures/npa.py` | копія чинного `npa.py` для тестів патча |
| `tests/live/run_v41.bat`, `live_v41.py` | повні живі перевірки на ПК в Україні — лише на копії архіву |
| `tests/live/run_v414.bat`, `live_v414.py` | коротка жива перевірка v4.1.4 (скан HTML, probe, sync --changed ×2, verify, status, anomaly без --record з хешем картки до/після) |
| `tests/live/run_v415.bat`, `live_v415.py` | коротка жива перевірка v4.1.5 з автоперевіркою умов успіху (код 1 за порушення) |
| `tests/live/check_live_results.py` | 9 умов успіху живої перевірки (зокрема повнота сценарію) → `checks.json` або `--out-json` |
| `tests/live/scan_html_fp.py` | скан хибних спрацювань HTML-евристики на всіх текстах архіву |
| `reports/` | ZVIT_v4_1_6, ZVIT_v4_1_5, ZVIT_v4_1_4, ZVIT_v4_1_3, ZVIT_v4_1_2, ZVIT_v4_1_1, TEST_RESULTS, PLATFORMS, LIVE_TEST_RESULTS (повний живий прогін v4.1 і короткі живі перевірки v4.1.3–v4.1.5; журнали — `live_logs/`, `live_logs_v413/`, `live_logs_v414/`, `live_logs_v415/`), SYNC_AUDIT_REPORT, MANUAL_ONLY, `npa_v4_1.diff` |
| `SKILL.md` | запропонована редакція скіла `npa-redaktsii` після інтеграції v4.1 |
| `v4_to_v4_1_5.diff`, `v4_1_to_v4_1_1.diff` … `v4_1_4_to_v4_1_5.diff`, `v4_1_5_to_v4_1_6_checker.diff`, `CHANGELOG.md`, `SHA256SUMS.txt` | зміни й контрольні суми |

## Команди (з кореня npa-redaktsii)

```bat
python skrypty\sync_api_v4_1.py sync --changed            :: щотижня
python skrypty\sync_api_v4_1.py sync --nreg 2343-12        :: один акт
python skrypty\sync_api_v4_1.py verify --json verify.json  :: аудит текстів, нічого не змінює
python skrypty\sync_api_v4_1.py anomaly --nreg 2343-12 --raw 201301186
python skrypty\sync_api_v4_1.py status --out stan.md       :: таблиця стану актів
```

Офлайн-тести: `cd tests && python -m unittest discover -s . -p "test_*.py" -v`.

## Що пропонується перенести до репозиторію (після аудиту й дозволу власника)

`skrypty/sync_api_v4_1.py`; патч `npa.py` (застосувати `patch_npa_v4_1.py`); `tests/` (за бажанням —
у `skrypty/tests/`); нові файли даних, які створює v4.1: `dani/manual_only.json`, `dani/perevirka.json`;
`.npa_cache/` — до `.gitignore`. Старі `zbir.js`/`onovlennia.py` для оновлення не використовуються.
