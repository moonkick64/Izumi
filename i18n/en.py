"""English string table (default language)."""

STRINGS: dict[str, str] = {
    # ── App-wide ──────────────────────────────────────────────────────────
    "app_title":            "Izumi – OSS Detection & SBOM Support",
    "browse_btn":           "Browse…",
    "back_to_scan_btn":     "← Back to Scan Results",
    "sbom_export_btn":      "SBOM Export →",
    "language_label":       "Language:",
    "restart_required_title": "Restart Required",
    "restart_required_msg": "Language change will take effect after restarting the application.",

    # ── settings_view ─────────────────────────────────────────────────────
    "scan_target_group":    "Scan Target",
    "source_path_placeholder": "Path to source tree to scan",
    "local_llm_group":      "Local LLM (Ollama)",
    "endpoint_label":       "Endpoint:",
    "model_label":          "Model:",
    "external_llm_group":   "External LLM",
    "api_key_placeholder":  "API Key (optional – env var also accepted)",
    "api_key_label":        "API Key:",
    "scan_start_btn":       "Start Scan",
    "browse_source_dialog": "Select Source Directory",
    "invalid_path_title":   "Invalid Path",
    "invalid_path_msg":     "'{path}' is not a directory.",

    # ── scan_view ─────────────────────────────────────────────────────────
    "file_tree_label":      "File Tree",
    "source_placeholder":   "Select a file to view its source code.",
    "llm_analysis_btn":     "LLM Analysis →",
    "read_error":           "[Read error: {exc}]",

    # ── review_view ───────────────────────────────────────────────────────
    "filter_unknown_only":  "UNKNOWN only",
    "filter_all":           "All",
    "filter_inferred_only": "INFERRED only",
    "filter_confirmed_only":"CONFIRMED only",

    "review_title":         "LLM SCA Review (Function Level)",
    "llm_option_group":     "LLM Analysis Options",
    "option1_radio":        "Option 1: Send function source code directly to local LLM for identification",
    "option2_radio":        "Option 2: Summarize with local LLM \u2192 User review/edit \u2192 Send to external LLM (confidential info protection)",
    "option3_radio":        "Option 3: Send function source code directly to external LLM for identification",

    "display_label":        "Show:",
    "file_list_label":      "File List",
    "extract_btn":          "Extract Functions from Selected Files",
    "function_list_label":  "Function List",
    "analyse_btn":          "Analyse",
    "delete_results_btn":   "Delete Results",

    "function_body_group":       "Function Source Code",
    "function_body_placeholder": "Select a function to view its source code here.",

    "opt2_panel_title":      "Summary (editable – review before sending to external LLM)",
    "opt2_summary_placeholder":
        'Press "Analyse" to generate a summary with local LLM. '
        "Edit here to remove confidential information before sending.",
    "approve_checkbox":      "Approve for sending to external LLM",
    "save_btn":              "Save",
    "send_external_btn":     "Send approved summaries to external LLM",

    "hint_group_title":     "LLM Hints (for reference – not confirmed information)",
    "hint_placeholder":     "Run LLM analysis to see hints here.",

    "option1_label":        "Analyse directly with local LLM",
    "option2_label":        "Generate summary with local LLM",
    "option3_label":        "Analyse directly with external LLM",
    "analyse_btn_default":  "Analyse with LLM",

    "no_target_title":      "No Target",
    "no_target_msg":        "No files to analyse.",
    "no_selection_title":   "Not Selected",
    "no_selection_msg":     "Please select a function to summarize.",
    "ollama_not_connected_title": "Ollama Not Connected",
    "ollama_not_connected_msg":
        "Cannot connect to Ollama ({api_base}).\nPlease check that Ollama is running.",
    "ollama_not_connected_msg_short":
        "Cannot connect to Ollama ({api_base}).",
    "no_approved_title":    "No Approved Summaries",
    "no_approved_msg":
        "Select a summary, check 'Approve', and save before sending.",
    "no_hint":              "No hints",
    "external_llm_error_title": "External LLM Error",
    "opt2_batch_unsupported_title": "Not Supported",
    "opt2_batch_unsupported_msg":
        "Option 2 requires per-function summarization, review, and approval "
        "and does not support batch analysis.",
    "no_functions_title":   "No Functions",
    "no_functions_msg":     "Please run 'Extract Functions from Selected Files' first.",
    "confirm_send_external_title": "Confirm Send to External LLM",
    "confirm_send_external_msg":
        "Sending source code of {count} function(s) directly to external LLM.\n"
        "Please verify there is no confidential information.\n\nProceed?",
    "analysing_progress":   "Analysing {current}/{total}: {name}",
    "analysis_complete":    "Analysis complete – auto-saved ({count} result(s))",
    "loaded_results":       "Loaded existing analysis results ({count} item(s))",
    "no_results_title":     "No Results",
    "no_results_msg":       "No saved analysis results.",
    "delete_results_title": "Delete Results",
    "delete_results_confirm_msg":
        "Saved analysis results will be deleted. This action cannot be undone.\n\nDelete?",
    "results_deleted":      "Analysis results deleted",
    "llm_error_title":      "LLM Error",

    # ── sbom_view ─────────────────────────────────────────────────────────
    "sbom_title":           "SBOM Export",
    "col_component":        "Component",
    "col_classification":   "Classification",
    "col_license":          "License",
    "col_file_count":       "File Count",
    "output_settings_group":"Output Settings",
    "format_label":         "Format:",
    "output_path_label":    "Output:",
    "output_path_placeholder": "Output file path",
    "export_sbom_btn":      "Export SBOM",
    "unknown_license":      "Unknown",
    "sbom_output_dialog":   "Save SBOM",
    "no_output_path_title": "Output Path Not Set",
    "no_output_path_msg":   "Please specify the output file path.",
    "export_complete_title":"Export Complete",
    "export_complete_msg":  "SBOM exported to:\n{out_path}",
    "export_error_title":   "Export Error",

    # ── main_window ───────────────────────────────────────────────────────
    "window_title":         "Izumi \u2013 OSS Detection & SBOM",
    "file_menu":            "File(&F)",
    "new_scan_action":      "New Scan(&N)",
    "quit_action":          "Quit(&Q)",
    "view_menu":            "View(&V)",
    "menu_settings":        "Settings",
    "menu_scan":            "Scan Results",
    "menu_review":          "LLM SCA Review",
    "menu_sbom":            "SBOM Export",
    "scanning_status":      "Scanning: {source_dir}",
    "scan_progress_status": "Scanning {current}/{total}: {path}",
    "scan_complete_status": "Done: CONFIRMED={confirmed}  INFERRED={inferred}  UNKNOWN={unknown}",
    "scan_error_title":     "Scan Error",
    "scan_error_status":    "Scan error",
}
