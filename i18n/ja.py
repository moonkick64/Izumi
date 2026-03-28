"""Japanese string table."""

STRINGS: dict[str, str] = {
    # ── App-wide ──────────────────────────────────────────────────────────
    "app_title":            "Izumi \u2013 OSS \u691c\u51fa & SBOM \u652f\u63f4",
    "browse_btn":           "\u53c2\u7167\u2026",
    "back_to_scan_btn":     "\u2190 \u30b9\u30ad\u30e3\u30f3\u7d50\u679c\u306b\u623b\u308b",
    "sbom_export_btn":      "SBOM \u51fa\u529b \u2192",
    "language_label":       "\u8a00\u8a9e:",
    "restart_required_title": "\u518d\u8d77\u52d5\u304c\u5fc5\u8981",
    "restart_required_msg": "\u8a00\u8a9e\u306e\u5909\u66f4\u306f\u30a2\u30d7\u30ea\u30b1\u30fc\u30b7\u30e7\u30f3\u3092\u518d\u8d77\u52d5\u3059\u308b\u3068\u53cd\u6620\u3055\u308c\u307e\u3059\u3002",

    # ── settings_view ─────────────────────────────────────────────────────
    "scan_target_group":    "\u30b9\u30ad\u30e3\u30f3\u5bfe\u8c61",
    "source_path_placeholder": "\u30b9\u30ad\u30e3\u30f3\u3059\u308b\u30bd\u30fc\u30b9\u30c4\u30ea\u30fc\u306e\u30d1\u30b9",
    "local_llm_group":      "\u30ed\u30fc\u30ab\u30ebLLM (Ollama)",
    "endpoint_label":       "\u30a8\u30f3\u30c9\u30dd\u30a4\u30f3\u30c8:",
    "model_label":          "\u30e2\u30c7\u30eb:",
    "external_llm_group":   "\u5916\u90e8LLM",
    "api_key_placeholder":  "API\u30ad\u30fc\uff08\u30aa\u30d7\u30b7\u30e7\u30f3\u30fb\u74b0\u5883\u5909\u6570\u3067\u3082\u53ef\uff09",
    "api_key_label":        "API\u30ad\u30fc:",
    "scan_start_btn":       "\u30b9\u30ad\u30e3\u30f3\u958b\u59cb",
    "browse_source_dialog": "\u30b9\u30ad\u30e3\u30f3\u5bfe\u8c61\u30c7\u30a3\u30ec\u30af\u30c8\u30ea\u3092\u9078\u629e",
    "invalid_path_title":   "\u30d1\u30b9\u304c\u7121\u52b9",
    "invalid_path_msg":     "'{path}' \u306f\u30c7\u30a3\u30ec\u30af\u30c8\u30ea\u3067\u306f\u3042\u308a\u307e\u305b\u3093\u3002",

    # ── scan_view ─────────────────────────────────────────────────────────
    "file_tree_label":      "\u30d5\u30a1\u30a4\u30eb\u30c4\u30ea\u30fc",
    "source_placeholder":   "\u30d5\u30a1\u30a4\u30eb\u3092\u9078\u629e\u3059\u308b\u3068\u30bd\u30fc\u30b9\u30b3\u30fc\u30c9\u304c\u8868\u793a\u3055\u308c\u307e\u3059\u3002",
    "llm_analysis_btn":     "LLM \u89e3\u6790 \u2192",
    "read_error":           "[\u8aad\u307f\u8fbc\u307f\u30a8\u30e9\u30fc: {exc}]",

    # ── review_view ───────────────────────────────────────────────────────
    "filter_unknown_only":  "UNKNOWN \u306e\u307f",
    "filter_all":           "\u5168\u3066",
    "filter_inferred_only": "INFERRED \u306e\u307f",
    "filter_confirmed_only":"CONFIRMED \u306e\u307f",

    "review_title":         "LLM SCA \u30ec\u30d3\u30e5\u30fc\uff08\u95a2\u6570\u5358\u4f4d\uff09",
    "llm_option_group":     "LLM \u89e3\u6790\u30aa\u30d7\u30b7\u30e7\u30f3",
    "option1_radio":        "\u30aa\u30d7\u30b7\u30e7\u30f31: \u95a2\u6570\u306e\u30bd\u30fc\u30b9\u30b3\u30fc\u30c9\u3092\u30ed\u30fc\u30ab\u30ebLLM\u306b\u76f4\u63a5\u9001\u4fe1\u3057\u3066\u7279\u5b9a",
    "option2_radio":        "\u30aa\u30d7\u30b7\u30e7\u30f32: \u30ed\u30fc\u30ab\u30ebLLM\u3067\u8981\u7d04 \u2192 \u30e6\u30fc\u30b6\u30fc\u78ba\u8a8d\u30fb\u7de8\u96c6 \u2192 \u5916\u90e8LLM\u306b\u9001\u4fe1\uff08\u6a5f\u5bc6\u60c5\u5831\u4fdd\u8b77\uff09",
    "option3_radio":        "\u30aa\u30d7\u30b7\u30e7\u30f33: \u95a2\u6570\u306e\u30bd\u30fc\u30b9\u30b3\u30fc\u30c9\u3092\u5916\u90e8LLM\u306b\u76f4\u63a5\u9001\u4fe1\u3057\u3066\u7279\u5b9a",

    "display_label":        "\u8868\u793a:",
    "file_list_label":      "\u30d5\u30a1\u30a4\u30eb\u4e00\u89a7",
    "extract_btn":          "\u9078\u629e\u30d5\u30a1\u30a4\u30eb\u306e\u95a2\u6570\u3092\u629c\u51fa",
    "function_list_label":  "\u95a2\u6570\u4e00\u89a7",
    "analyse_btn":          "\u89e3\u6790",
    "delete_results_btn":   "\u7d50\u679c\u3092\u524a\u9664",

    "function_body_group":       "\u95a2\u6570\u30bd\u30fc\u30b9\u30b3\u30fc\u30c9",
    "function_body_placeholder": "\u95a2\u6570\u3092\u9078\u629e\u3059\u308b\u3068\u3053\u3053\u306b\u30bd\u30fc\u30b9\u30b3\u30fc\u30c9\u304c\u8868\u793a\u3055\u308c\u307e\u3059\u3002",

    "opt2_panel_title":      "\u8981\u7d04\uff08\u7de8\u96c6\u53ef\u80fd\u30fb\u5916\u90e8LLM\u3078\u306e\u9001\u4fe1\u524d\u306b\u78ba\u8a8d\u3057\u3066\u304f\u3060\u3055\u3044\uff09",
    "opt2_summary_placeholder":
        "\u300c\u89e3\u6790\u300d\u3092\u62bc\u3059\u3068\u30ed\u30fc\u30ab\u30ebLLM\u304c\u8981\u7d04\u3092\u751f\u6210\u3057\u307e\u3059\u3002"
        "\u6a5f\u5bc6\u60c5\u5831\u304c\u542b\u307e\u308c\u308b\u5834\u5408\u306f\u3053\u3053\u3067\u7de8\u96c6\u3057\u3066\u304b\u3089\u9001\u4fe1\u3057\u3066\u304f\u3060\u3055\u3044\u3002",
    "approve_checkbox":      "\u5916\u90e8LLM\u3078\u306e\u9001\u4fe1\u3092\u627f\u8a8d",
    "save_btn":              "\u4fdd\u5b58",
    "send_external_btn":     "\u627f\u8a8d\u6e08\u307f\u8981\u7d04\u3092\u5916\u90e8LLM\u306b\u9001\u4fe1",

    "hint_group_title":     "LLM\u304b\u3089\u306e\u30d2\u30f3\u30c8\uff08\u53c2\u8003\u60c5\u5831\u30fb\u78ba\u5b9a\u60c5\u5831\u3067\u306f\u3042\u308a\u307e\u305b\u3093\uff09",
    "hint_placeholder":     "LLM\u3067\u89e3\u6790\u3059\u308b\u3068\u3001\u3053\u3053\u306b\u30d2\u30f3\u30c8\u304c\u8868\u793a\u3055\u308c\u307e\u3059\u3002",
    "match_group_title":    "\u30de\u30c3\u30c1\u30f3\u30b0\u6c7a\u5b9a\uff08\u30e6\u30fc\u30b6\u30fc\u306e\u5224\u65ad\uff09",
    "component_label":      "\u30b3\u30f3\u30dd\u30fc\u30cd\u30f3\u30c8:",
    "component_placeholder":"\u4f8b: zlib 1.2.11",
    "license_label_match":  "\u30e9\u30a4\u30bb\u30f3\u30b9:",
    "license_placeholder":  "\u4f8b: MIT",
    "match_btn":            "\u30de\u30c3\u30c1\u30f3\u30b0",
    "summarise_progress":   "\u8981\u7d04\u4e2d {current}/{total}: {name}",
    "summarise_complete":   "\u8981\u7d04\u5b8c\u4e86\uff08{count} \u4ef6\uff09",

    "option1_label":        "\u30ed\u30fc\u30ab\u30ebLLM\u3067\u76f4\u63a5\u89e3\u6790",
    "option2_label":        "\u30ed\u30fc\u30ab\u30ebLLM\u3067\u8981\u7d04\u751f\u6210",
    "option3_label":        "\u5916\u90e8LLM\u3067\u76f4\u63a5\u89e3\u6790",
    "analyse_btn_default":  "LLM \u3067\u89e3\u6790",
    "option2_summarise_label":     "\u30ed\u30fc\u30ab\u30ebLLM\u3067\u4e00\u62ec\u8981\u7d04",
    "option2_send_external_btn":   "\u5916\u90e8LLM\u3067\u89e3\u6790\uff08\u6a5f\u5bc6\u60c5\u5831\u4fdd\u8b77\uff09",

    "no_target_title":      "\u5bfe\u8c61\u306a\u3057",
    "no_target_msg":        "\u89e3\u6790\u3059\u308b\u30d5\u30a1\u30a4\u30eb\u304c\u3042\u308a\u307e\u305b\u3093\u3002",
    "no_selection_title":   "\u672a\u9078\u629e",
    "no_selection_msg":     "\u8981\u7d04\u3059\u308b\u95a2\u6570\u3092\u9078\u629e\u3057\u3066\u304f\u3060\u3055\u3044\u3002",
    "ollama_not_connected_title": "Ollama \u672a\u63a5\u7d9a",
    "ollama_not_connected_msg":
        "Ollama \u306b\u63a5\u7d9a\u3067\u304d\u307e\u305b\u3093 ({api_base})\u3002\n"
        "Ollama \u304c\u8d77\u52d5\u3057\u3066\u3044\u308b\u304b\u78ba\u8a8d\u3057\u3066\u304f\u3060\u3055\u3044\u3002",
    "ollama_not_connected_msg_short":
        "Ollama \u306b\u63a5\u7d9a\u3067\u304d\u307e\u305b\u3093 ({api_base})\u3002",
    "no_approved_title":    "\u627f\u8a8d\u6e08\u307f\u8981\u7d04\u306a\u3057",
    "no_approved_msg":
        "\u9001\u4fe1\u3059\u308b\u8981\u7d04\u3092\u9078\u629e\u3057\u300c\u627f\u8a8d\u300d\u30c1\u30a7\u30c3\u30af\u3092\u30aa\u30f3\u306b\u3057\u3066\u4fdd\u5b58\u3057\u3066\u304f\u3060\u3055\u3044\u3002",
    "no_hint":              "\u30d2\u30f3\u30c8\u306a\u3057",
    "external_llm_error_title": "\u5916\u90e8LLM\u30a8\u30e9\u30fc",
    "opt2_batch_unsupported_title": "\u975e\u5bfe\u5fdc",
    "opt2_batch_unsupported_msg":
        "\u30aa\u30d7\u30b7\u30e7\u30f32\u306f\u95a2\u6570\u3054\u3068\u306b\u8981\u7d04\u30fb\u78ba\u8a8d\u30fb\u627f\u8a8d\u304c\u5fc5\u8981\u306a\u305f\u3081\u4e00\u62ec\u89e3\u6790\u306b\u5bfe\u5fdc\u3057\u3066\u3044\u307e\u305b\u3093\u3002",
    "no_functions_title":   "\u95a2\u6570\u306a\u3057",
    "no_functions_msg":     "\u5148\u306b\u300c\u9078\u629e\u30d5\u30a1\u30a4\u30eb\u306e\u95a2\u6570\u3092\u629c\u51fa\u300d\u3092\u5b9f\u884c\u3057\u3066\u304f\u3060\u3055\u3044\u3002",
    "no_summaries_title":   "\u8981\u7d04\u306a\u3057",
    "no_summaries_msg":     "\u5148\u306b\u300c\u30ed\u30fc\u30ab\u30ebLLM\u3067\u4e00\u62ec\u8981\u7d04\u300d\u3092\u5b9f\u884c\u3057\u3066\u304f\u3060\u3055\u3044\u3002",
    "confirm_send_external_title": "\u5916\u90e8LLM\u3078\u306e\u9001\u4fe1\u78ba\u8a8d",
    "confirm_send_external_msg":
        "{count} \u500b\u306e\u95a2\u6570\u306e\u30bd\u30fc\u30b9\u30b3\u30fc\u30c9\u3092\u305d\u306e\u307e\u307e\u5916\u90e8LLM\u306b\u9001\u4fe1\u3057\u307e\u3059\u3002\n"
        "\u6a5f\u5bc6\u60c5\u5831\u304c\u542b\u307e\u308c\u3066\u3044\u306a\u3044\u304b\u78ba\u8a8d\u3057\u3066\u304f\u3060\u3055\u3044\u3002\n\n\u9001\u4fe1\u3057\u307e\u3059\u304b\uff1f",
    "analysing_progress":   "\u89e3\u6790\u4e2d {current}/{total}: {name}",
    "analysis_complete":    "\u89e3\u6790\u5b8c\u4e86\u30fb\u81ea\u52d5\u4fdd\u5b58\u6e08\u307f\uff08{count} \u4ef6\uff09",
    "loaded_results":       "\u65e2\u5b58\u306e\u89e3\u6790\u7d50\u679c\u3092\u8aad\u307f\u8fbc\u307f\u307e\u3057\u305f\uff08{count} \u4ef6\uff09",
    "no_results_title":     "\u7d50\u679c\u306a\u3057",
    "no_results_msg":       "\u4fdd\u5b58\u6e08\u307f\u306e\u89e3\u6790\u7d50\u679c\u306f\u3042\u308a\u307e\u305b\u3093\u3002",
    "delete_results_title": "\u7d50\u679c\u3092\u524a\u9664",
    "delete_results_confirm_msg":
        "\u4fdd\u5b58\u6e08\u307f\u306e\u89e3\u6790\u7d50\u679c\u3092\u524a\u9664\u3057\u307e\u3059\u3002\u3053\u306e\u64cd\u4f5c\u306f\u5143\u306b\u623b\u305b\u307e\u305b\u3093\u3002\n\n\u524a\u9664\u3057\u307e\u3059\u304b\uff1f",
    "results_deleted":      "\u89e3\u6790\u7d50\u679c\u3092\u524a\u9664\u3057\u307e\u3057\u305f",
    "llm_error_title":      "LLM\u30a8\u30e9\u30fc",

    # ── sbom_view ─────────────────────────────────────────────────────────
    "sbom_title":           "SBOM \u51fa\u529b",
    "col_component":        "\u30b3\u30f3\u30dd\u30fc\u30cd\u30f3\u30c8",
    "col_classification":   "\u5206\u985e",
    "col_license":          "\u30e9\u30a4\u30bb\u30f3\u30b9",
    "col_file_count":       "\u30d5\u30a1\u30a4\u30eb\u6570",
    "output_settings_group":"\u51fa\u529b\u8a2d\u5b9a",
    "format_label":         "\u30d5\u30a9\u30fc\u30de\u30c3\u30c8:",
    "output_path_label":    "\u51fa\u529b\u5148:",
    "output_path_placeholder": "\u51fa\u529b\u30d5\u30a1\u30a4\u30eb\u306e\u30d1\u30b9",
    "export_sbom_btn":      "SBOM \u3092\u51fa\u529b",
    "unknown_license":      "\u4e0d\u660e",
    "sbom_output_dialog":   "SBOM \u51fa\u529b\u5148",
    "no_output_path_title": "\u51fa\u529b\u5148\u672a\u8a2d\u5b9a",
    "no_output_path_msg":   "\u51fa\u529b\u5148\u30d5\u30a1\u30a4\u30eb\u3092\u6307\u5b9a\u3057\u3066\u304f\u3060\u3055\u3044\u3002",
    "export_complete_title":"\u51fa\u529b\u5b8c\u4e86",
    "export_complete_msg":  "SBOM \u3092\u51fa\u529b\u3057\u307e\u3057\u305f:\n{out_path}",
    "export_error_title":   "\u51fa\u529b\u30a8\u30e9\u30fc",

    # ── main_window ───────────────────────────────────────────────────────
    "window_title":         "Izumi \u2013 OSS Detection & SBOM",
    "file_menu":            "\u30d5\u30a1\u30a4\u30eb(&F)",
    "new_scan_action":      "\u65b0\u898f\u30b9\u30ad\u30e3\u30f3(&N)",
    "quit_action":          "\u7d42\u4e86(&Q)",
    "view_menu":            "\u8868\u793a(&V)",
    "menu_settings":        "\u8a2d\u5b9a",
    "menu_scan":            "\u30b9\u30ad\u30e3\u30f3\u7d50\u679c",
    "menu_review":          "LLM SCA\u30ec\u30d3\u30e5\u30fc",
    "menu_sbom":            "SBOM\u51fa\u529b",
    "scanning_status":      "\u30b9\u30ad\u30e3\u30f3\u4e2d: {source_dir}",
    "scan_progress_status": "\u30b9\u30ad\u30e3\u30f3\u4e2d {current}/{total}: {path}",
    "scan_complete_status": "\u5b8c\u4e86: CONFIRMED={confirmed}  INFERRED={inferred}  UNKNOWN={unknown}",
    "scan_error_title":     "\u30b9\u30ad\u30e3\u30f3\u30a8\u30e9\u30fc",
    "scan_error_status":    "\u30b9\u30ad\u30e3\u30f3\u30a8\u30e9\u30fc",
}
