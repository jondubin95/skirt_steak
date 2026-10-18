# Fanfic Story Doctor status

Keyed to spec v0.4.3. A row may say "Test passed" only when the named test exists and pytest runs it.

| Section | Status | Test |
|---|---|---|
| 12 normalize | Test passed | test_two_chapters_three_breaks_and_author_notes |
| 12 hashes | Test passed | test_hard_wrap_and_quotes_and_stable_hash |
| 12 html | Test passed | test_html_matches_markdown_ids |
| 5 ids | Test passed | test_id_order_scene_and_chapter_100 |
| 13 intake | Test passed | test_intake_seeds_and_rejects |
| 6 fact store | Test passed | test_supersede_conflict_claim_and_reanchor |
| 7 timeline | Test passed | test_e1_through_e8_and_same_class |
| 6.4 stale | Test passed | test_stale_blocks_lower_layer |
| 8.1 dead | Test passed | test_dead_reappears_rows |
| 17.5 matrix | Test passed | test_dead_reappears_table |
| 1 divergence | Test passed | test_canon_divergence_and_report |
| 1 divergence table | Test passed | test_canon_divergence_classification |
| 6 private canon in run | Test passed | test_doctor_home_canon_loads_in_run |
| 11 golden report | Test passed | test_render_golden_matches_run |
| 11 never-rewrite markers | Test passed | test_validator_rewrite_markers_with_space |
| 9 holdout gate | Test passed | test_holdout_gate_tracks_git_state |
| 11 output | Test passed | test_validator_rejects_unknown_quote_and_rewrite |
| 8.6 mentions | Test passed | test_mentions_are_alias_exact_and_markers_uncertain |
| 5 canon load | Test passed | test_canon_load_refuses_repo_and_missing_quote |
| 9 layer b helpers | Test passed | test_later_confirmation_proposer_vote_cache_and_holdout |
| 7 layer b runner (mock) | Test passed | test_layer_b_runs_mock_and_contract_holds |
| 7 layer b skipped without flag | Test passed | test_without_flag_layer_b_is_skipped_layer_a_only |
| 7 closed labels | Test passed | test_labels_are_closed_and_match_rubric_files |
| 7 rails needs branch | Test passed | test_canon_rails_needs_a_declared_branch_and_later_passages |
| 7 exact quote | Test passed | test_invalid_responses_are_rejected_not_shown |
| 7 info only | Test passed | test_validator_blocks_layer_b_above_info |
| 7 mock deterministic | Test passed | test_mock_is_deterministic |
| 7 cache | Test passed | test_cache_skips_provider_on_second_run |
| 7 golden | Test passed | test_layer_b_golden |
| G9 gate | Test passed | test_non_mock_provider_refuses_without_g9_opt_in |
| 7 real provider | Not built | gated by G9 |
| 18 privacy | Test passed | test_gitignore_covers_private_drafts |
| 12 ao3 full work | Test passed | test_ao3_full_work_splits_chapters_and_strips_notes |
| 12 html in run | Test passed | test_html_chapter_files_and_full_work_run_through_doctor_run |
| 8.6 candidates | Test passed | test_candidates_never_cross_punctuation_and_are_substrings |
| 8.6 spelling noise | Test passed | test_possessives_stammers_and_plural_surnames_are_not_flagged |
| 8.6 spelling hits | Test passed | test_missing_apostrophe_and_real_typo_are_flagged |
| 8.6 common words | Test passed | test_common_words_are_not_flagged_against_short_names |
| 8.6 shared surname | Test passed | test_shared_surname_is_ambiguous_not_attributed |
| 11 drop invalid item | Test passed | test_invalid_item_is_dropped_not_fatal |
| 1 alternate setting | Test passed | test_alternate_setting_drops_canon_status_and_order_keeps_aliases |
| 1 divergence question | Test passed | test_branch_au_without_divergence_event_gets_question_without_disagreement |
| 6 conflicts single-valued | Test passed | test_multiple_aliases_and_order_edges_are_not_conflicts |
