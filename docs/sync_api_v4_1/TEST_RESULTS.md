# TEST_RESULTS — офлайн-тести пакета v4.1.6 (синхронізатор 4.1.5)

Автор: В'ячеслав Плескач. Дата: 23.11.2026. Платформи — див. PLATFORMS.md.

Запуск однією командою (з кореня пакета):

```
cd tests
python -m unittest discover -s . -p "test_*.py" -v
```

Результат на Linux (Python 3.13): **103 тести, усі пройшли** (0 пропущених): 97 — v4.1.5; +2 у `test_live_checker.py` (неповний сценарій — 10 варіантів, зокрема контрольний експеримент аудиту з вилученням семи кроків; `--out-json` не перезаписує журнал прогону; на перевіряльнику v4.1.5 усі 11 subTest FAIL); +4 у `test_v4_1_6_unicode_e2e.py` (тексти, що починаються з `<дата>`, `<підпис>`, `<ПІБ>`: прийом `fetch_verified_text`, запис verified у sync і чистий verify, `anomaly --record` визнає дубль однакових текстів, кириличний текст проти HTML — inconclusive; на коді v4.1.4 дев'ять subTest FAIL, на 4.1.5 — проходять).

Хибних спрацювань HTML-евристики на реальних текстах немає: `tests/live/scan_html_fp.py` — 3 304 тексти хмарної копії, 0; на копії користувача (жива перевірка v4.1.5) — 3 310, 0.

Windows 11 (10.0.26300), Python 3.12.10, 24.11.2026: **103 тести, усі пройшли**, exit=0 — окремий прогін на ПК користувача (`offline_tests_v4_1_6_windows.txt`).

Мережа в тестах не використовується: HTTP імітується (`tests/helpers.py`, справжні `requests.Response`), паузи — через впроваджену функцію sleep.

| Файл | Клас | Тест | Результат (Linux) |
|---|---|---|---|
| test_completeness | Test2343_12 | test_missing_edition_is_incomplete | ok |
| test_completeness | Test2343_12 | test_no_double_count_and_unresolved | ok |
| test_completeness | Test2343_12 | test_no_edcnt | ok |
| test_completeness | Test2343_12 | test_only_in_doc_update | ok |
| test_completeness | Test2343_12 | test_resolved_documented | ok |
| test_completeness | TestModesInCard | test_chynna_and_odyn_never_complete | ok |
| test_completeness | TestModesInCard | test_povna_complete | ok |
| test_completeness | TestModesInCard | test_snapshot_without_history | ok |
| test_http | TestHTTP | test_304_uses_cache_without_rewrite | ok |
| test_http | TestHTTP | test_403_429_stop_all | ok |
| test_http | TestHTTP | test_conditional_exact_only | ok |
| test_http | TestHTTP | test_content_length_over_budget_not_read | ok |
| test_http | TestHTTP | test_correct_date_accepted_wrong_rejected | ok |
| test_http | TestHTTP | test_interrupted_stream_leaves_no_file | ok |
| test_http | TestHTTP | test_missing_or_bad_documentdate | ok |
| test_http | TestHTTP | test_podia_refresh_conditional | ok |
| test_http | TestHTTP | test_redirect_is_manual_and_no_html | ok |
| test_http | TestHTTP | test_unknown_length_stream_stops | ok |
| test_http | TestHTTP | test_user_agent_and_injected_pause | ok |
| test_live_checker | TestLiveChecker | test_all_good_passes | ok |
| test_live_checker | TestLiveChecker | test_each_violation_fails | ok |
| test_live_checker | TestLiveChecker | test_incomplete_scenario_fails | ok |
| test_live_checker | TestLiveChecker | test_missing_files | ok |
| test_live_checker | TestLiveChecker | test_out_json_does_not_overwrite_run_checks | ok |
| test_live_checker | TestLiveChecker | test_wrong_version_fails | ok |
| test_npa_patch | TestNpaPatch | test_apostrophe_only_diff | ok |
| test_npa_patch | TestNpaPatch | test_complete_history_unchanged_output | ok |
| test_npa_patch | TestNpaPatch | test_conditional_label | ok |
| test_npa_patch | TestNpaPatch | test_idempotent_and_revert | ok |
| test_npa_patch | TestNpaPatch | test_odyn_snapshot | ok |
| test_npa_patch | TestNpaPatch | test_perevirka_date | ok |
| test_npa_patch | TestNpaPatch | test_unresolved_history_warning | ok |
| test_parsers | TestDates | test_invalid_reason | ok |
| test_parsers | TestDates | test_parse_modified | ok |
| test_parsers | TestDates | test_parse_yyyymmdd | ok |
| test_parsers | TestDates | test_valid_edition_id | ok |
| test_parsers | TestDocUpdate | test_cp1251_and_utf8 | ok |
| test_parsers | TestDocUpdate | test_empty_raises | ok |
| test_parsers | TestDocUpdate | test_header_row_and_unknown_modified | ok |
| test_parsers | TestDocUpdate | test_real_format_multi_rows_and_max_modified | ok |
| test_parsers | TestJsonCard | test_fields | ok |
| test_parsers | TestPodia | test_empty_unknown_dup | ok |
| test_parsers | TestPodia | test_parse_podia | ok |
| test_status_events_basis | TestBasis | test_desc_noise_removed | ok |
| test_status_events_basis | TestBasis | test_enrich_keeps_old_and_desc | ok |
| test_status_events_basis | TestBasis | test_no_heuristic_roman | ok |
| test_status_events_basis | TestBasis | test_orgnum_and_nvlas | ok |
| test_status_events_basis | TestEvents | test_idempotent | ok |
| test_status_events_basis | TestEvents | test_no_edition_events_and_keep_legal | ok |
| test_status_events_basis | TestEvents | test_podia_label_change_updates_without_duplicate | ok |
| test_status_events_basis | TestStatus | test_absent_keeps_old | ok |
| test_status_events_basis | TestStatus | test_explicit_zero_clears | ok |
| test_status_events_basis | TestStatus | test_in_normalized_card | ok |
| test_status_events_basis | TestStatus | test_known_and_unknown | ok |
| test_status_events_basis | TestStatus | test_null_keeps_old_with_warning | ok |
| test_sync_integration | TestSyncFlow | test_existing_corrupt_not_hidden | ok |
| test_sync_integration | TestSyncFlow | test_full_flow | ok |
| test_sync_integration | TestSyncFlow | test_not_in_doc_update_is_not_manual | ok |
| test_sync_integration | TestSyncFlow | test_unparsed_modified_falls_back_to_card | ok |
| test_sync_integration | TestSyncFlow | test_wrong_documentdate_writes_nothing | ok |
| test_text_audit | TestClassify | test_crlf_checkout_still_verified | ok |
| test_text_audit | TestClassify | test_legacy | ok |
| test_text_audit | TestClassify | test_missing_and_empty | ok |
| test_text_audit | TestClassify | test_one_byte_changed_is_corrupt | ok |
| test_text_audit | TestClassify | test_verified | ok |
| test_text_audit | TestClassify | test_verify_changes_nothing | ok |
| test_text_audit | TestClassify | test_wrong_documentdate | ok |
| test_v4_1_1_regressions | TestAnomalyReference | test_reference_302_inconclusive | ok |
| test_v4_1_1_regressions | TestAnomalyReference | test_reference_404_inconclusive | ok |
| test_v4_1_1_regressions | TestEdcntExact | test_exact_edcnt_is_complete | ok |
| test_v4_1_1_regressions | TestEdcntExact | test_more_distinct_editions_than_edcnt_is_not_complete | ok |
| test_v4_1_1_regressions | TestEdcntExact | test_more_than_edcnt_via_doc_update_is_not_complete | ok |
| test_v4_1_1_regressions | TestMixedModified | test_mixed_parsed_and_unparsed_modified_falls_back_to_card | ok |
| test_v4_1_1_regressions | TestVerifyCodes | test_missing_outside_expected_set_not_counted | ok |
| test_v4_1_1_regressions | TestVerifyCodes | test_verify_repair_all_targets_fixed_returns_zero | ok |
| test_v4_1_1_regressions | TestVerifyCodes | test_verify_repair_budget_exceeded_returns_nonzero | ok |
| test_v4_1_1_regressions | TestVerifyCodes | test_verify_repair_conditional_skipped_returns_nonzero | ok |
| test_v4_1_1_regressions | TestVerifyCodes | test_verify_returns_nonzero_for_missing_expected_only | ok |
| test_v4_1_2_regressions | TestAnomalyHtml | test_both_identical_html | ok |
| test_v4_1_2_regressions | TestAnomalyHtml | test_empty_bodies | ok |
| test_v4_1_2_regressions | TestAnomalyHtml | test_html_body_with_text_mime | ok |
| test_v4_1_2_regressions | TestAnomalyHtml | test_identical_real_txt_still_duplicate | ok |
| test_v4_1_2_regressions | TestAnomalyHtml | test_raw_html_reference_txt | ok |
| test_v4_1_2_regressions | TestAnomalyHtml | test_raw_txt_reference_html | ok |
| test_v4_1_2_regressions | TestVerifyMissingCard | test_chynna_odyn_historical_missing_still_ok | ok |
| test_v4_1_2_regressions | TestVerifyMissingCard | test_json_report_lists_missing_card | ok |
| test_v4_1_2_regressions | TestVerifyMissingCard | test_no_card_no_texts_nonzero | ok |
| test_v4_1_2_regressions | TestVerifyMissingCard | test_no_card_with_stray_text_nonzero | ok |
| test_v4_1_2_regressions | TestVerifyMissingCard | test_repair_without_card_no_targets_nonzero | ok |
| test_v4_1_2_regressions | TestVerifyMissingCard | test_repair_without_card_nonzero_and_no_changes | ok |
| test_v4_1_3_html_edge | TestHtmlNeverBecomesEdition | test_anomaly_never_duplicate_for_html | ok |
| test_v4_1_3_html_edge | TestHtmlNeverBecomesEdition | test_fetch_verified_text_rejects_html | ok |
| test_v4_1_3_html_edge | TestLooksLikeHtml | test_html_cases_detected | ok |
| test_v4_1_3_html_edge | TestLooksLikeHtml | test_plain_text_not_detected | ok |
| test_v4_1_3_html_edge | TestLooksLikeHtml | test_txt_response_problem_for_each_html_case | ok |
| test_v4_1_4_html_fragments | TestShortFragments | test_anomaly_never_duplicate_for_fragments | ok |
| test_v4_1_4_html_fragments | TestShortFragments | test_fetch_verified_text_rejects_fragments | ok |
| test_v4_1_4_html_fragments | TestShortFragments | test_fragments_detected | ok |
| test_v4_1_4_html_fragments | TestShortFragments | test_legal_texts_not_detected | ok |
| test_v4_1_6_unicode_e2e | TestUnicodeEndToEnd | test_anomaly_cyrillic_vs_html_still_inconclusive | ok |
| test_v4_1_6_unicode_e2e | TestUnicodeEndToEnd | test_anomaly_record_duplicate_for_identical_cyrillic_texts | ok |
| test_v4_1_6_unicode_e2e | TestUnicodeEndToEnd | test_fetch_verified_text_accepts | ok |
| test_v4_1_6_unicode_e2e | TestUnicodeEndToEnd | test_sync_writes_verified_and_verify_clean | ok |

## Перевірки на реальній копії архіву (51 акт, без мережі; виконано для v4.1)

* `verify` на хмарній копії архіву (стан до синхронізації v4): 3 302 файли legacy_unverified, 2 verified, 0 corrupt, 0 date_mismatch, 0 missing; дата в шапці кожного старого файла збігається з іменем. Файли не змінювалися (10 с).
* Патч `npa.py` на тій самій копії: вивід `stattia` для КАС 193, ЦПК 189, 5076-17 ст. 6, 2343-12 ст. 1, 2201-20 і `porivniaty КАС 193` — **без змін** (картки ще без api v4.1); 2755-17 (chynna) — додано одне попередження про режим; `redaktsii КАС` — 4 умовні редакції позначено «(умовна)» замість «(майбутня)».
* Оркестрація живих тестів (`tests/live/live_v41.py`) прогнана на мінікопії з 3 актів без мережі: усі 34 кроки виконані, коди виходу й журнали зібрані, zip сформовано. Це перевірка сценарію, не живий тест.
