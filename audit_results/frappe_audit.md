# Drift Precision Audit: frappe

- **Score:** 0.544 (medium)
- **Files:** 1179 | Functions: 6232
- **Findings:** 913 total, 353 reviewable (MEDIUM+)
- **Duration:** 21.53s
- **Analyzed:** 2026-03-23T14:32:13.064820+00:00

## Review Instructions

For each finding, mark the **Verdict** column:
- **TP** — Real problem. You'd want this flagged in a code review.
- **FP** — Not a real problem. This would erode trust if shown to a dev.
- **?** — Unsure / context-dependent.

## Findings

| # | Signal | Sev | Score | File | Title | Verdict |
|---|--------|-----|-------|------|-------|---------|
| 1 | pattern_fragmentation | high | 0.989 | frappe\utils | error_handling: 92 variants in frappe/utils/ | |
| 2 | pattern_fragmentation | high | 0.978 | frappe | error_handling: 46 variants in frappe/ | |
| 3 | pattern_fragmentation | high | 0.969 | frappe\model | error_handling: 32 variants in frappe/model/ | |
| 4 | pattern_fragmentation | high | 0.952 | frappe\commands | error_handling: 21 variants in frappe/commands/ | |
| 5 | pattern_fragmentation | high | 0.947 | frappe\desk | error_handling: 19 variants in frappe/desk/ | |
| 6 | pattern_fragmentation | high | 0.944 | frappe\email | error_handling: 18 variants in frappe/email/ | |
| 7 | architecture_violation | medium | 0.6 | frappe\auth.py | Circular dependency (168 modules) | |
| 8 | pattern_fragmentation | high | 0.941 | frappe\database | error_handling: 17 variants in frappe/database/ | |
| 9 | pattern_fragmentation | high | 0.929 | frappe\core\doctype\file | error_handling: 14 variants in frappe/core/doctype/file/ | |
| 10 | pattern_fragmentation | high | 0.917 | frappe\search | error_handling: 12 variants in frappe/search/ | |
| 11 | pattern_fragmentation | high | 0.889 | frappe\website | error_handling: 9 variants in frappe/website/ | |
| 12 | pattern_fragmentation | high | 0.875 | frappe\core\doctype\doctype | error_handling: 8 variants in frappe/core/doctype/doctype/ | |
| 13 | pattern_fragmentation | high | 0.857 | frappe\utils\pdf_generator | error_handling: 7 variants in frappe/utils/pdf_generator/ | |
| 14 | pattern_fragmentation | high | 0.857 | frappe\email\doctype\email_account | error_handling: 7 variants in frappe/email/doctype/email_acc | |
| 15 | pattern_fragmentation | high | 0.857 | frappe\modules | error_handling: 7 variants in frappe/modules/ | |
| 16 | pattern_fragmentation | high | 0.857 | frappe\www | error_handling: 7 variants in frappe/www/ | |
| 17 | pattern_fragmentation | high | 0.833 | frappe\core\doctype\user | error_handling: 6 variants in frappe/core/doctype/user/ | |
| 18 | pattern_fragmentation | high | 0.8 | frappe\core\doctype\data_import | error_handling: 5 variants in frappe/core/doctype/data_impor | |
| 19 | pattern_fragmentation | high | 0.8 | frappe\core\doctype\scheduled_job_type | error_handling: 5 variants in frappe/core/doctype/scheduled_ | |
| 20 | pattern_fragmentation | high | 0.8 | frappe\desk\form | error_handling: 5 variants in frappe/desk/form/ | |
| 21 | pattern_fragmentation | high | 0.8 | frappe\integrations | error_handling: 5 variants in frappe/integrations/ | |
| 22 | pattern_fragmentation | high | 0.75 | frappe\api | error_handling: 4 variants in frappe/api/ | |
| 23 | pattern_fragmentation | high | 0.75 | frappe\email\doctype\notification | error_handling: 4 variants in frappe/email/doctype/notificat | |
| 24 | pattern_fragmentation | high | 0.75 | frappe\integrations\doctype\webhook | error_handling: 4 variants in frappe/integrations/doctype/we | |
| 25 | pattern_fragmentation | high | 0.75 | frappe\core\doctype\communication | error_handling: 4 variants in frappe/core/doctype/communicat | |
| 26 | pattern_fragmentation | high | 0.75 | …core\doctype\document_naming_settings | error_handling: 4 variants in frappe/core/doctype/document_n | |
| 27 | pattern_fragmentation | high | 0.75 | frappe\database\mariadb | error_handling: 4 variants in frappe/database/mariadb/ | |
| 28 | pattern_fragmentation | high | 0.75 | frappe\desk\doctype\workspace_sidebar | error_handling: 4 variants in frappe/desk/doctype/workspace_ | |
| 29 | pattern_fragmentation | high | 0.75 | …\integrations\doctype\google_calendar | error_handling: 4 variants in frappe/integrations/doctype/go | |
| 30 | pattern_fragmentation | medium | 0.667 | frappe\core\doctype\comment | error_handling: 3 variants in frappe/core/doctype/comment/ | |
| 31 | pattern_fragmentation | medium | 0.667 | frappe\core\page\permission_manager | error_handling: 3 variants in frappe/core/page/permission_ma | |
| 32 | pattern_fragmentation | medium | 0.667 | frappe\database\postgres | error_handling: 3 variants in frappe/database/postgres/ | |
| 33 | pattern_fragmentation | medium | 0.667 | frappe\desk\doctype\system_health_report | error_handling: 3 variants in frappe/desk/doctype/system_hea | |
| 34 | pattern_fragmentation | medium | 0.667 | …pe\integrations\doctype\ldap_settings | error_handling: 3 variants in frappe/integrations/doctype/ld | |
| 35 | pattern_fragmentation | medium | 0.667 | frappe\patches\v11_0 | error_handling: 3 variants in frappe/patches/v11_0/ | |
| 36 | pattern_fragmentation | medium | 0.667 | frappe\patches\v12_0 | error_handling: 3 variants in frappe/patches/v12_0/ | |
| 37 | pattern_fragmentation | medium | 0.667 | frappe\patches\v13_0 | error_handling: 3 variants in frappe/patches/v13_0/ | |
| 38 | pattern_fragmentation | medium | 0.667 | frappe\patches\v15_0 | error_handling: 3 variants in frappe/patches/v15_0/ | |
| 39 | pattern_fragmentation | medium | 0.667 | frappe\testing | error_handling: 3 variants in frappe/testing/ | |
| 40 | pattern_fragmentation | medium | 0.667 | frappe\utils\telemetry\pulse | error_handling: 3 variants in frappe/utils/telemetry/pulse/ | |
| 41 | pattern_fragmentation | medium | 0.667 | frappe\website\page_renderers | error_handling: 3 variants in frappe/website/page_renderers/ | |
| 42 | mutant_duplicate | high | 0.9 | frappe\database\mariadb\database.py | Exact duplicates (2×): MariaDBDatabase.create_global_search_ | |
| 43 | mutant_duplicate | high | 0.9 | frappe\database\mariadb\database.py | Exact duplicates (2×): MariaDBDatabase.get_column_index | |
| 44 | mutant_duplicate | high | 0.9 | frappe\database\mariadb\database.py | Exact duplicates (2×): MariaDBDatabase.add_index | |
| 45 | mutant_duplicate | high | 0.9 | frappe\database\mariadb\database.py | Exact duplicates (2×): MariaDBDatabase.add_unique | |
| 46 | mutant_duplicate | high | 0.9 | frappe\database\mariadb\database.py | Exact duplicates (2×): MariaDBDatabase.updatedb | |
| 47 | mutant_duplicate | high | 0.9 | frappe\database\mariadb\database.py | Exact duplicates (2×): MariaDBDatabase.get_tables | |
| 48 | mutant_duplicate | high | 0.9 | frappe\database\mariadb\database.py | Exact duplicates (2×): MariaDBDatabase.get_row_size | |
| 49 | mutant_duplicate | high | 0.9 | frappe\desk\desktop.py | Exact duplicates (2×): Workspace.get_cached, WorkspaceSideba | |
| 50 | mutant_duplicate | high | 0.9 | frappe\desk\desktop.py | Exact duplicates (2×): Workspace.get_allowed_modules, Worksp | |
| 51 | mutant_duplicate | high | 0.9 | …14_0\clear_long_pending_stale_logs.py | Exact duplicates (2×): get_current_setting | |
| 52 | pattern_fragmentation | medium | 0.5 | frappe\automation\doctype\auto_repeat | error_handling: 2 variants in frappe/automation/doctype/auto | |
| 53 | pattern_fragmentation | medium | 0.5 | frappe\core\doctype\deleted_document | error_handling: 2 variants in frappe/core/doctype/deleted_do | |
| 54 | pattern_fragmentation | medium | 0.5 | frappe\core\doctype\log_settings | error_handling: 2 variants in frappe/core/doctype/log_settin | |
| 55 | pattern_fragmentation | medium | 0.5 | frappe\core\doctype\page | error_handling: 2 variants in frappe/core/doctype/page/ | |
| 56 | pattern_fragmentation | medium | 0.5 | frappe\core\doctype\prepared_report | error_handling: 2 variants in frappe/core/doctype/prepared_r | |
| 57 | pattern_fragmentation | medium | 0.5 | frappe\core\doctype\rq_job | error_handling: 2 variants in frappe/core/doctype/rq_job/ | |
| 58 | pattern_fragmentation | medium | 0.5 | frappe\custom\doctype\custom_field | error_handling: 2 variants in frappe/custom/doctype/custom_f | |
| 59 | pattern_fragmentation | medium | 0.5 | frappe\database\sqlite | error_handling: 2 variants in frappe/database/sqlite/ | |
| 60 | pattern_fragmentation | medium | 0.5 | frappe\desk\doctype\changelog_feed | error_handling: 2 variants in frappe/desk/doctype/changelog_ | |
| 61 | pattern_fragmentation | medium | 0.5 | frappe\desk\doctype\desktop_icon | error_handling: 2 variants in frappe/desk/doctype/desktop_ic | |
| 62 | pattern_fragmentation | medium | 0.5 | frappe\desk\doctype\desktop_layout | error_handling: 2 variants in frappe/desk/doctype/desktop_la | |
| 63 | pattern_fragmentation | medium | 0.5 | frappe\desk\doctype\notification_log | error_handling: 2 variants in frappe/desk/doctype/notificati | |
| 64 | pattern_fragmentation | medium | 0.5 | …pe\desk\doctype\notification_settings | error_handling: 2 variants in frappe/desk/doctype/notificati | |
| 65 | pattern_fragmentation | medium | 0.5 | frappe\desk\doctype\workspace | error_handling: 2 variants in frappe/desk/doctype/workspace/ | |
| 66 | pattern_fragmentation | medium | 0.5 | frappe\desk\page\setup_wizard | error_handling: 2 variants in frappe/desk/page/setup_wizard/ | |
| 67 | pattern_fragmentation | medium | 0.5 | frappe\email\doctype\email_queue | error_handling: 2 variants in frappe/email/doctype/email_que | |
| 68 | pattern_fragmentation | medium | 0.5 | …\integrations\doctype\google_contacts | error_handling: 2 variants in frappe/integrations/doctype/go | |
| 69 | pattern_fragmentation | medium | 0.5 | frappe\patches\v14_0 | error_handling: 2 variants in frappe/patches/v14_0/ | |
| 70 | pattern_fragmentation | medium | 0.5 | …ting\doctype\network_printer_settings | error_handling: 2 variants in frappe/printing/doctype/networ | |
| 71 | pattern_fragmentation | medium | 0.5 | frappe\website\doctype\website_settings | error_handling: 2 variants in frappe/website/doctype/website | |
| 72 | explainability_deficit | high | 1.0 | …pe\assignment_rule\assignment_rule.py | Unexplained complexity: apply | |
| 73 | explainability_deficit | high | 1.0 | frappe\commands\execute.py | Unexplained complexity: _execute | |
| 74 | explainability_deficit | high | 1.0 | …\core\doctype\data_export\exporter.py | Unexplained complexity: DataExporter.build_field_columns | |
| 75 | explainability_deficit | high | 1.0 | …\core\doctype\data_export\exporter.py | Unexplained complexity: DataExporter.add_data | |
| 76 | explainability_deficit | high | 1.0 | …\core\doctype\data_import\importer.py | Unexplained complexity: Importer.import_data | |
| 77 | explainability_deficit | high | 1.0 | frappe\core\doctype\doctype\doctype.py | Unexplained complexity: validate_permissions | |
| 78 | explainability_deficit | high | 1.0 | …type\customize_form\customize_form.py | Unexplained complexity: CustomizeForm.allow_property_change | |
| 79 | explainability_deficit | high | 1.0 | frappe\database\mariadb\schema.py | Unexplained complexity: MariaDBTable.alter | |
| 80 | explainability_deficit | high | 1.0 | frappe\database\postgres\schema.py | Unexplained complexity: PostgresTable.alter | |
| 81 | explainability_deficit | high | 1.0 | frappe\database\schema.py | Unexplained complexity: DbColumn.build_for_alter_table | |
| 82 | explainability_deficit | high | 1.0 | frappe\database\sqlite\schema.py | Unexplained complexity: SQLiteTable.alter | |
| 83 | explainability_deficit | high | 1.0 | …sk\doctype\bulk_update\bulk_update.py | Unexplained complexity: _bulk_action | |
| 84 | explainability_deficit | high | 1.0 | frappe\desk\reportview.py | Unexplained complexity: _export_query | |
| 85 | explainability_deficit | high | 1.0 | frappe\installer.py | Unexplained complexity: install_app | |
| 86 | explainability_deficit | high | 1.0 | frappe\model\mapper.py | Unexplained complexity: get_mapped_doc | |
| 87 | explainability_deficit | high | 1.0 | frappe\model\mapper.py | Unexplained complexity: map_fields | |
| 88 | explainability_deficit | high | 1.0 | frappe\model\utils\rename_field.py | Unexplained complexity: update_reports | |
| 89 | explainability_deficit | high | 1.0 | frappe\utils\backups.py | Unexplained complexity: BackupGenerator.take_dump | |
| 90 | explainability_deficit | high | 1.0 | frappe\utils\pdf_generator\pdf_merge.py | Unexplained complexity: PDFTransformer.transform_pdf | |
| 91 | explainability_deficit | high | 1.0 | …\website_settings\website_settings.py | Unexplained complexity: get_website_settings | |
| 92 | explainability_deficit | high | 0.95 | frappe\core\doctype\doctype\doctype.py | Unexplained complexity: DocType.before_export | |
| 93 | explainability_deficit | high | 0.95 | frappe\database\__init__.py | Unexplained complexity: get_command | |
| 94 | explainability_deficit | high | 0.95 | frappe\desk\query_report.py | Unexplained complexity: _export_query | |
| 95 | explainability_deficit | high | 0.95 | frappe\model\db_query.py | Unexplained complexity: DatabaseQuery.set_order_by | |
| 96 | explainability_deficit | high | 0.95 | frappe\utils\pdf_generator\browser.py | Unexplained complexity: Browser.prepare_options_for_pdf | |
| 97 | explainability_deficit | high | 0.9 | frappe\auth.py | Unexplained complexity: LoginManager.authenticate | |
| 98 | explainability_deficit | high | 0.9 | frappe\boot.py | Unexplained complexity: load_desktop_data | |
| 99 | explainability_deficit | high | 0.9 | frappe\database\schema.py | Unexplained complexity: DbColumn.get_definition | |
| 100 | explainability_deficit | high | 0.9 | frappe\database\schema.py | Unexplained complexity: get_definition | |
| 101 | explainability_deficit | high | 0.9 | …e\desk\doctype\workspace\workspace.py | Unexplained complexity: Workspace.validate | |
| 102 | explainability_deficit | high | 0.9 | …octype\ldap_settings\ldap_settings.py | Unexplained complexity: LDAPSettings.validate | |
| 103 | explainability_deficit | high | 0.9 | frappe\model\db_query.py | Unexplained complexity: DatabaseQuery.prepare_args | |
| 104 | explainability_deficit | high | 0.9 | frappe\model\sync.py | Unexplained complexity: sync_for | |
| 105 | explainability_deficit | high | 0.9 | …s\v10_0\refactor_social_login_keys.py | Unexplained complexity: execute | |
| 106 | explainability_deficit | high | 0.9 | …pe\patches\v14_0\update_workspace2.py | Unexplained complexity: create_content | |
| 107 | explainability_deficit | high | 0.875 | frappe\app.py | Unexplained complexity: handle_exception | |
| 108 | explainability_deficit | high | 0.875 | frappe\desk\query_report.py | Unexplained complexity: generate_report_result | |
| 109 | explainability_deficit | high | 0.875 | frappe\desk\search.py | Unexplained complexity: search_widget | |
| 110 | explainability_deficit | high | 0.875 | frappe\handler.py | Unexplained complexity: upload_file | |
| 111 | explainability_deficit | high | 0.85 | frappe\boot.py | Unexplained complexity: get_user_pages_or_reports | |
| 112 | explainability_deficit | high | 0.85 | …\core\doctype\data_import\importer.py | Unexplained complexity: Column.validate_values | |
| 113 | explainability_deficit | high | 0.85 | frappe\model\meta.py | Unexplained complexity: Meta.apply_property_setters | |
| 114 | explainability_deficit | high | 0.85 | …\doctype\print_format\print_format.py | Unexplained complexity: PrintFormat.validate | |
| 115 | explainability_deficit | high | 0.85 | frappe\utils\data.py | Unexplained complexity: map_trackers | |
| 116 | explainability_deficit | high | 0.85 | …utils\pdf_generator\cdp_connection.py | Unexplained complexity: CDPSocketClient._handle_message | |
| 117 | explainability_deficit | high | 0.85 | frappe\www\list.py | Unexplained complexity: get_list_context | |
| 118 | explainability_deficit | high | 0.8 | frappe\core\doctype\file\file.py | Unexplained complexity: File.save_file | |
| 119 | explainability_deficit | high | 0.8 | …pe\system_settings\system_settings.py | Unexplained complexity: SystemSettings.validate | |
| 120 | explainability_deficit | high | 0.8 | frappe\core\doctype\user\user.py | Unexplained complexity: create_contact | |
| 121 | explainability_deficit | high | 0.8 | …\doctype\custom_field\custom_field.py | Unexplained complexity: CustomField.validate | |
| 122 | explainability_deficit | high | 0.8 | …\doctype\desktop_icon\desktop_icon.py | Unexplained complexity: DesktopIcon.is_permitted | |
| 123 | explainability_deficit | high | 0.8 | …\doctype\notification\notification.py | Unexplained complexity: evaluate_alert | |
| 124 | explainability_deficit | high | 0.8 | frappe\model\base_document.py | Unexplained complexity: BaseDocument.get_formatted | |
| 125 | explainability_deficit | high | 0.8 | frappe\translate.py | Unexplained complexity: get_messages_from_custom_fields | |
| 126 | explainability_deficit | high | 0.8 | …\website\doctype\web_form\web_form.py | Unexplained complexity: WebForm.load_translations | |
| 127 | explainability_deficit | high | 0.75 | frappe\config.py | Unexplained complexity: _get_site_config | |
| 128 | explainability_deficit | high | 0.75 | …\core\doctype\data_import\importer.py | Unexplained complexity: build_fields_dict_for_column_matchin | |
| 129 | explainability_deficit | high | 0.75 | frappe\core\doctype\doctype\doctype.py | Unexplained complexity: validate_series | |
| 130 | explainability_deficit | high | 0.75 | frappe\core\doctype\doctype\doctype.py | Unexplained complexity: validate_fields | |
| 131 | explainability_deficit | high | 0.75 | frappe\core\doctype\file\file.py | Unexplained complexity: has_permission | |
| 132 | explainability_deficit | high | 0.75 | frappe\core\doctype\version\version.py | Unexplained complexity: get_diff | |
| 133 | explainability_deficit | high | 0.75 | frappe\database\database.py | Unexplained complexity: Database.sql | |
| 134 | explainability_deficit | high | 0.75 | frappe\database\database.py | Unexplained complexity: Database.get_values | |
| 135 | explainability_deficit | high | 0.75 | …orkspace_sidebar\workspace_sidebar.py | Unexplained complexity: create_sidebar_items | |
| 136 | explainability_deficit | high | 0.75 | frappe\desk\form\linked_with.py | Unexplained complexity: get_linked_docs | |
| 137 | explainability_deficit | high | 0.75 | frappe\desk\form\load.py | Unexplained complexity: update_user_info | |
| 138 | explainability_deficit | high | 0.75 | frappe\desk\query_report.py | Unexplained complexity: add_total_row | |
| 139 | explainability_deficit | high | 0.75 | frappe\desk\query_report.py | Unexplained complexity: has_match | |
| 140 | explainability_deficit | high | 0.75 | frappe\desk\query_report.py | Unexplained complexity: get_linked_doctypes | |
| 141 | explainability_deficit | high | 0.75 | …uto_email_report\auto_email_report.py | Unexplained complexity: make_links | |
| 142 | explainability_deficit | high | 0.75 | …octype\email_account\email_account.py | Unexplained complexity: EmailAccount.validate | |
| 143 | explainability_deficit | high | 0.75 | frappe\frappeclient.py | Unexplained complexity: FrappeClient.migrate_doctype | |
| 144 | explainability_deficit | high | 0.75 | frappe\gettext\extractors\javascript.py | Unexplained complexity: extract_javascript | |
| 145 | explainability_deficit | high | 0.75 | frappe\gettext\extractors\web_form.py | Unexplained complexity: extract | |
| 146 | explainability_deficit | high | 0.75 | frappe\installer.py | Unexplained complexity: remove_app | |
| 147 | explainability_deficit | high | 0.75 | frappe\model\base_document.py | Unexplained complexity: BaseDocument.get_valid_dict | |
| 148 | explainability_deficit | high | 0.75 | frappe\model\base_document.py | Unexplained complexity: BaseDocument.get_invalid_links | |
| 149 | explainability_deficit | high | 0.75 | frappe\model\db_query.py | Unexplained complexity: DatabaseQuery.execute | |
| 150 | explainability_deficit | high | 0.75 | frappe\model\db_query.py | Unexplained complexity: DatabaseQuery.sanitize_fields | |
| 151 | explainability_deficit | high | 0.75 | frappe\model\db_query.py | Unexplained complexity: DatabaseQuery.apply_fieldlevel_read_ | |
| 152 | explainability_deficit | high | 0.75 | frappe\model\db_query.py | Unexplained complexity: DatabaseQuery.add_user_permissions | |
| 153 | explainability_deficit | high | 0.75 | frappe\model\delete_doc.py | Unexplained complexity: check_if_doc_is_linked | |
| 154 | explainability_deficit | high | 0.75 | frappe\model\delete_doc.py | Unexplained complexity: check_if_doc_is_dynamically_linked | |
| 155 | explainability_deficit | high | 0.75 | frappe\model\meta.py | Unexplained complexity: Meta.sort_fields | |
| 156 | explainability_deficit | high | 0.75 | frappe\model\meta.py | Unexplained complexity: Meta.add_doctype_links | |
| 157 | explainability_deficit | high | 0.75 | frappe\model\rename_doc.py | Unexplained complexity: validate_rename | |
| 158 | explainability_deficit | high | 0.75 | frappe\permissions.py | Unexplained complexity: has_user_permission | |
| 159 | explainability_deficit | high | 0.75 | frappe\search\sqlite_search.py | Unexplained complexity: SQLiteSearch.build_index | |
| 160 | explainability_deficit | high | 0.75 | frappe\search\sqlite_search.py | Unexplained complexity: SQLiteSearch._execute_search_query | |
| 161 | explainability_deficit | high | 0.75 | frappe\search\sqlite_search.py | Unexplained complexity: SQLiteSearch.index_chunks | |
| 162 | explainability_deficit | high | 0.75 | frappe\utils\formatters.py | Unexplained complexity: format_value | |
| 163 | explainability_deficit | high | 0.75 | frappe\utils\global_search.py | Unexplained complexity: rebuild_for_doctype | |
| 164 | explainability_deficit | high | 0.75 | frappe\utils\print_utils.py | Unexplained complexity: calculate_platform | |
| 165 | explainability_deficit | high | 0.75 | frappe\utils\typing_validations.py | Unexplained complexity: transform_parameter_types | |
| 166 | explainability_deficit | high | 0.75 | frappe\utils\user.py | Unexplained complexity: UserPermissions.build_permissions | |
| 167 | explainability_deficit | high | 0.75 | …\website\doctype\web_form\web_form.py | Unexplained complexity: get_link_options | |
| 168 | explainability_deficit | high | 0.75 | frappe\website\utils.py | Unexplained complexity: get_home_page | |
| 169 | explainability_deficit | high | 0.75 | frappe\www\printview.py | Unexplained complexity: get_rendered_template | |
| 170 | explainability_deficit | high | 0.712 | frappe\database\schema.py | Unexplained complexity: DBTable.validate | |
| 171 | explainability_deficit | high | 0.712 | frappe\model\meta.py | Unexplained complexity: get_field_currency | |
| 172 | explainability_deficit | high | 0.712 | frappe\modules\utils.py | Unexplained complexity: sync_customizations_for_doctype | |
| 173 | explainability_deficit | high | 0.712 | frappe\permissions.py | Unexplained complexity: get_role_permissions | |
| 174 | explainability_deficit | high | 0.712 | frappe\realtime.py | Unexplained complexity: publish_realtime | |
| 175 | explainability_deficit | high | 0.7 | frappe\client.py | Unexplained complexity: validate_link_and_fetch | |
| 176 | explainability_deficit | high | 0.7 | …sk\doctype\number_card\number_card.py | Unexplained complexity: NumberCard.validate | |
| 177 | explainability_deficit | high | 0.7 | …orkspace_sidebar\workspace_sidebar.py | Unexplained complexity: WorkspaceSidebar.is_item_allowed | |
| 178 | explainability_deficit | high | 0.7 | frappe\desk\search.py | Unexplained complexity: validate_ignore_user_permissions | |
| 179 | explainability_deficit | high | 0.7 | …\social_login_key\social_login_key.py | Unexplained complexity: SocialLoginKey.validate | |
| 180 | explainability_deficit | high | 0.7 | frappe\migrate.py | Unexplained complexity: DBQueryProgressMonitor.run | |
| 181 | explainability_deficit | high | 0.7 | frappe\model\base_document.py | Unexplained complexity: BaseDocument._validate_data_fields | |
| 182 | explainability_deficit | high | 0.7 | frappe\model\base_document.py | Unexplained complexity: BaseDocument._validate_length | |
| 183 | explainability_deficit | high | 0.7 | frappe\model\meta.py | Unexplained complexity: _serialize | |
| 184 | explainability_deficit | high | 0.7 | frappe\translate.py | Unexplained complexity: get_messages_from_workflow | |
| 185 | explainability_deficit | high | 0.7 | frappe\utils\print_utils.py | Unexplained complexity: attach_print | |
| 186 | explainability_deficit | high | 0.7 | frappe\utils\safe_exec.py | Unexplained complexity: get_keys_for_autocomplete | |
| 187 | explainability_deficit | high | 0.7 | frappe\website\utils.py | Unexplained complexity: _build | |
| 188 | explainability_deficit | medium | 0.675 | …il\doctype\email_queue\email_queue.py | Unexplained complexity: EmailQueue.send | |
| 189 | explainability_deficit | medium | 0.675 | …pe\google_calendar\google_calendar.py | Unexplained complexity: sync_events_from_google_calendar | |
| 190 | explainability_deficit | medium | 0.675 | frappe\model\base_document.py | Unexplained complexity: BaseDocument.db_insert | |
| 191 | explainability_deficit | medium | 0.675 | frappe\model\base_document.py | Unexplained complexity: BaseDocument._sanitize_content | |
| 192 | explainability_deficit | medium | 0.675 | frappe\model\base_document.py | Unexplained complexity: BaseDocument.reset_values_if_no_perm | |
| 193 | explainability_deficit | medium | 0.675 | frappe\model\naming.py | Unexplained complexity: set_new_name | |
| 194 | explainability_deficit | medium | 0.675 | frappe\website\path_resolver.py | Unexplained complexity: resolve_redirect | |
| 195 | explainability_deficit | medium | 0.675 | frappe\website\router.py | Unexplained complexity: setup_source | |
| 196 | explainability_deficit | medium | 0.656 | frappe\desk\link_preview.py | Unexplained complexity: get_preview_data | |
| 197 | explainability_deficit | medium | 0.65 | frappe\boot.py | Unexplained complexity: get_sidebar_items | |
| 198 | explainability_deficit | medium | 0.65 | frappe\commands\site.py | Unexplained complexity: _restore | |
| 199 | explainability_deficit | medium | 0.65 | …e\contacts\doctype\contact\contact.py | Unexplained complexity: Contact.get_vcard | |
| 200 | explainability_deficit | medium | 0.65 | …octype\communication\communication.py | Unexplained complexity: Communication.set_sender_full_name | |
| 201 | explainability_deficit | medium | 0.65 | …\core\doctype\data_export\exporter.py | Unexplained complexity: DataExporter.append_field_column | |
| 202 | explainability_deficit | medium | 0.65 | …re\doctype\data_import\data_import.py | Unexplained complexity: export_json | |
| 203 | explainability_deficit | medium | 0.65 | …\core\doctype\data_import\importer.py | Unexplained complexity: Row.validate_value | |
| 204 | explainability_deficit | medium | 0.65 | …pplications\installed_applications.py | Unexplained complexity: InstalledApplications.update_version | |
| 205 | explainability_deficit | medium | 0.65 | frappe\core\doctype\user\user.py | Unexplained complexity: User.on_update | |
| 206 | explainability_deficit | medium | 0.65 | …\doctype\desktop_icon\desktop_icon.py | Unexplained complexity: create_desktop_icons_from_workspace | |
| 207 | explainability_deficit | medium | 0.65 | frappe\desk\query_report.py | Unexplained complexity: get_prepared_report_result | |
| 208 | explainability_deficit | medium | 0.65 | frappe\desk\reportview.py | Unexplained complexity: validate_fields | |
| 209 | explainability_deficit | medium | 0.65 | frappe\desk\reportview.py | Unexplained complexity: parse_json | |
| 210 | explainability_deficit | medium | 0.65 | frappe\frappeclient.py | Unexplained complexity: FrappeClient.post_process | |
| 211 | explainability_deficit | medium | 0.65 | frappe\model\workflow.py | Unexplained complexity: _bulk_workflow_action | |
| 212 | explainability_deficit | medium | 0.65 | frappe\rate_limiter.py | Unexplained complexity: ratelimit_decorator | |
| 213 | explainability_deficit | medium | 0.65 | frappe\utils\change_log.py | Unexplained complexity: check_for_update | |
| 214 | explainability_deficit | medium | 0.65 | …est\personal_data_deletion_request.py | Unexplained complexity: PersonalDataDeletionRequest._anonymi | |
| 215 | explainability_deficit | medium | 0.65 | frappe\www\list.py | Unexplained complexity: prepare_filters | |
| 216 | explainability_deficit | medium | 0.637 | …type\permission_log\permission_log.py | Unexplained complexity: insert_perm_log | |
| 217 | explainability_deficit | medium | 0.637 | …pe\google_contacts\google_contacts.py | Unexplained complexity: sync_contacts_from_google_contacts | |
| 218 | explainability_deficit | medium | 0.637 | frappe\search\sqlite_search.py | Unexplained complexity: SQLiteSearch._index_documents | |
| 219 | explainability_deficit | medium | 0.637 | frappe\utils\global_search.py | Unexplained complexity: update_global_search | |
| 220 | explainability_deficit | medium | 0.637 | …\website\doctype\web_form\web_form.py | Unexplained complexity: WebForm.load_form_data | |
| 221 | explainability_deficit | medium | 0.625 | frappe\commands\site.py | Unexplained complexity: trim_database | |
| 222 | explainability_deficit | medium | 0.625 | frappe\desk\desktop.py | Unexplained complexity: get_workspace_sidebar_items | |
| 223 | explainability_deficit | medium | 0.625 | frappe\model\workflow.py | Unexplained complexity: apply_workflow | |
| 224 | explainability_deficit | medium | 0.625 | …\website\doctype\web_form\web_form.py | Unexplained complexity: accept | |
| 225 | explainability_deficit | medium | 0.625 | frappe\www\login.py | Unexplained complexity: get_context | |
| 226 | explainability_deficit | medium | 0.612 | …pe\dashboard_chart\dashboard_chart.py | Unexplained complexity: get | |
| 227 | explainability_deficit | medium | 0.6 | …\core\doctype\data_import\importer.py | Unexplained complexity: Column.parse | |
| 228 | explainability_deficit | medium | 0.6 | frappe\core\doctype\doctype\doctype.py | Unexplained complexity: make_module_and_roles | |
| 229 | explainability_deficit | medium | 0.6 | frappe\database\database.py | Unexplained complexity: Database.get_values_from_single | |
| 230 | explainability_deficit | medium | 0.6 | frappe\deprecation_dumpster.py | Unexplained complexity: get_tests_CompatFrappeTestCase | |
| 231 | explainability_deficit | medium | 0.6 | frappe\desk\desktop.py | Unexplained complexity: Workspace.is_item_allowed | |
| 232 | explainability_deficit | medium | 0.6 | …ch_settings\global_search_settings.py | Unexplained complexity: update_global_search_doctypes | |
| 233 | explainability_deficit | medium | 0.6 | …\doctype\notification\notification.py | Unexplained complexity: Notification.validate | |
| 234 | explainability_deficit | medium | 0.6 | …\doctype\notification\notification.py | Unexplained complexity: Notification.get_list_of_recipients | |
| 235 | explainability_deficit | medium | 0.6 | frappe\integrations\utils.py | Unexplained complexity: create_new_oauth_client | |
| 236 | explainability_deficit | medium | 0.6 | frappe\model\base_document.py | Unexplained complexity: BaseDocument._get_missing_mandatory_ | |
| 237 | explainability_deficit | medium | 0.6 | frappe\model\base_document.py | Unexplained complexity: BaseDocument._validate_selects | |
| 238 | explainability_deficit | medium | 0.6 | frappe\model\create_new.py | Unexplained complexity: set_dynamic_default_values | |
| 239 | explainability_deficit | medium | 0.6 | frappe\modules\utils.py | Unexplained complexity: sync | |
| 240 | explainability_deficit | medium | 0.6 | frappe\utils\csvutils.py | Unexplained complexity: read_csv_content | |
| 241 | explainability_deficit | medium | 0.6 | frappe\utils\csvutils.py | Unexplained complexity: check_record | |
| 242 | explainability_deficit | medium | 0.6 | frappe\utils\data.py | Unexplained complexity: money_in_words | |
| 243 | explainability_deficit | medium | 0.6 | frappe\utils\print_format.py | Unexplained complexity: _download_multi_pdf | |
| 244 | explainability_deficit | medium | 0.6 | frappe\utils\print_utils.py | Unexplained complexity: download_chromium | |
| 245 | explainability_deficit | medium | 0.6 | frappe\website\utils.py | Unexplained complexity: _get_home_page | |
| 246 | explainability_deficit | medium | 0.6 | …workflow\doctype\workflow\workflow.py | Unexplained complexity: Workflow.validate_docstatus | |
| 247 | explainability_deficit | medium | 0.594 | frappe\email\inbox.py | Unexplained complexity: create_email_flag_queue | |
| 248 | explainability_deficit | medium | 0.569 | …e\desk\doctype\workspace\workspace.py | Unexplained complexity: update_page | |
| 249 | explainability_deficit | medium | 0.562 | frappe\core\doctype\doctype\doctype.py | Unexplained complexity: DocType.validate_field_name_conflict | |
| 250 | explainability_deficit | medium | 0.562 | frappe\desk\query_report.py | Unexplained complexity: format_fields | |
| 251 | explainability_deficit | medium | 0.562 | frappe\email\receive.py | Unexplained complexity: EmailServer.retrieve_message | |
| 252 | explainability_deficit | medium | 0.562 | …e\gettext\extractors\customization.py | Unexplained complexity: extract | |
| 253 | explainability_deficit | medium | 0.562 | frappe\handler.py | Unexplained complexity: run_doc_method | |
| 254 | explainability_deficit | medium | 0.562 | frappe\permissions.py | Unexplained complexity: has_child_permission | |
| 255 | explainability_deficit | medium | 0.562 | frappe\search\sqlite_search.py | Unexplained complexity: SQLiteSearch._build_vocabulary_incre | |
| 256 | explainability_deficit | medium | 0.562 | frappe\utils\background_jobs.py | Unexplained complexity: execute_job | |
| 257 | explainability_deficit | medium | 0.562 | frappe\website\utils.py | Unexplained complexity: get_full_index | |
| 258 | explainability_deficit | medium | 0.55 | frappe\app.py | Unexplained complexity: init_request | |
| 259 | explainability_deficit | medium | 0.55 | frappe\app.py | Unexplained complexity: process_response | |
| 260 | explainability_deficit | medium | 0.55 | frappe\app.py | Unexplained complexity: set_cors_headers | |
| 261 | explainability_deficit | medium | 0.55 | …on\doctype\auto_repeat\auto_repeat.py | Unexplained complexity: AutoRepeat.create_documents | |
| 262 | explainability_deficit | medium | 0.55 | …\core\doctype\data_export\exporter.py | Unexplained complexity: DataExporter.build_response | |
| 263 | explainability_deficit | medium | 0.55 | …\core\doctype\data_export\exporter.py | Unexplained complexity: DataExporter.add_data_row | |
| 264 | explainability_deficit | medium | 0.55 | …\core\doctype\data_import\importer.py | Unexplained complexity: Row._parse_doc | |
| 265 | explainability_deficit | medium | 0.55 | frappe\core\doctype\doctype\doctype.py | Unexplained complexity: check_unique_and_text | |
| 266 | explainability_deficit | medium | 0.55 | frappe\core\doctype\doctype\doctype.py | Unexplained complexity: check_level_zero_is_set | |
| 267 | explainability_deficit | medium | 0.55 | frappe\core\doctype\doctype\doctype.py | Unexplained complexity: check_permission_dependency | |
| 268 | explainability_deficit | medium | 0.55 | frappe\database\mariadb\schema.py | Unexplained complexity: MariaDBTable.create | |
| 269 | explainability_deficit | medium | 0.55 | frappe\desk\desktop.py | Unexplained complexity: clean_up | |
| 270 | explainability_deficit | medium | 0.55 | frappe\desk\notifications.py | Unexplained complexity: _get_linked_document_counts | |
| 271 | explainability_deficit | medium | 0.55 | frappe\desk\query_report.py | Unexplained complexity: validate_filters_permissions | |
| 272 | explainability_deficit | medium | 0.55 | frappe\desk\reportview.py | Unexplained complexity: validate_filters | |
| 273 | explainability_deficit | medium | 0.55 | frappe\desk\reportview.py | Unexplained complexity: get_filters_cond | |
| 274 | explainability_deficit | medium | 0.55 | frappe\integrations\utils.py | Unexplained complexity: make_request | |
| 275 | explainability_deficit | medium | 0.55 | frappe\integrations\utils.py | Unexplained complexity: validate_dynamic_client_metadata | |
| 276 | explainability_deficit | medium | 0.55 | frappe\model\base_document.py | Unexplained complexity: BaseDocument._validate_update_after_ | |
| 277 | explainability_deficit | medium | 0.55 | frappe\model\create_new.py | Unexplained complexity: get_static_default_value | |
| 278 | explainability_deficit | medium | 0.55 | frappe\model\sync.py | Unexplained complexity: remove_orphan_entities | |
| 279 | explainability_deficit | medium | 0.55 | …ove_email_and_phone_to_child_table.py | Unexplained complexity: execute | |
| 280 | explainability_deficit | medium | 0.55 | frappe\permissions.py | Unexplained complexity: check_user_permission_on_link_fields | |
| 281 | explainability_deficit | medium | 0.55 | frappe\query_builder\utils.py | Unexplained complexity: execute_child_queries | |
| 282 | explainability_deficit | medium | 0.55 | frappe\utils\pdf.py | Unexplained complexity: get_pdf | |
| 283 | explainability_deficit | medium | 0.55 | frappe\utils\response.py | Unexplained complexity: _make_logs_v1 | |
| 284 | explainability_deficit | medium | 0.55 | …\website\doctype\web_page\web_page.py | Unexplained complexity: check_publish_status | |
| 285 | explainability_deficit | medium | 0.531 | frappe\desk\query_report.py | Unexplained complexity: run | |
| 286 | explainability_deficit | medium | 0.525 | frappe\app.py | Unexplained complexity: application | |
| 287 | explainability_deficit | medium | 0.525 | …\doctype\custom_field\custom_field.py | Unexplained complexity: create_custom_fields | |
| 288 | explainability_deficit | medium | 0.525 | …uto_email_report\auto_email_report.py | Unexplained complexity: AutoEmailReport.get_report_content | |
| 289 | explainability_deficit | medium | 0.525 | …octype\email_account\email_account.py | Unexplained complexity: setup_user_email_inbox | |
| 290 | explainability_deficit | medium | 0.525 | frappe\gettext\extractors\javascript.py | Unexplained complexity: parse_template_string | |
| 291 | explainability_deficit | medium | 0.525 | …egrations\doctype\webhook\__init__.py | Unexplained complexity: run_webhooks | |
| 292 | explainability_deficit | medium | 0.525 | frappe\integrations\oauth2.py | Unexplained complexity: set_cors_for_privileged_requests | |
| 293 | explainability_deficit | medium | 0.525 | frappe\model\base_document.py | Unexplained complexity: _filter | |
| 294 | explainability_deficit | medium | 0.525 | frappe\model\db_query.py | Unexplained complexity: DatabaseQuery.extract_tables | |
| 295 | explainability_deficit | medium | 0.525 | frappe\permissions.py | Unexplained complexity: get_doc_permissions | |
| 296 | explainability_deficit | medium | 0.525 | frappe\translate.py | Unexplained complexity: get_messages_from_doctype | |
| 297 | explainability_deficit | medium | 0.525 | frappe\utils\data.py | Unexplained complexity: attach_expanded_links | |
| 298 | explainability_deficit | medium | 0.525 | frappe\website\path_resolver.py | Unexplained complexity: PathResolver.resolve | |
| 299 | explainability_deficit | medium | 0.5 | frappe\auth.py | Unexplained complexity: LoginManager.set_user_info | |
| 300 | explainability_deficit | medium | 0.5 | …\core\doctype\data_import\exporter.py | Unexplained complexity: Exporter.get_data_to_export | |
| 301 | explainability_deficit | medium | 0.5 | …\core\doctype\data_import\importer.py | Unexplained complexity: Row.parse_value | |
| 302 | explainability_deficit | medium | 0.5 | frappe\core\doctype\doctype\doctype.py | Unexplained complexity: check_link_table_options | |
| 303 | explainability_deficit | medium | 0.5 | frappe\core\doctype\doctype\doctype.py | Unexplained complexity: check_email_append_to | |
| 304 | explainability_deficit | medium | 0.5 | frappe\core\doctype\file\file.py | Unexplained complexity: File.handle_is_private_changed | |
| 305 | explainability_deficit | medium | 0.5 | frappe\core\doctype\page\page.py | Unexplained complexity: Page.load_assets | |
| 306 | explainability_deficit | medium | 0.5 | …type\customize_form\customize_form.py | Unexplained complexity: CustomizeForm.update_in_custom_field | |
| 307 | explainability_deficit | medium | 0.5 | …it_system_hooks\audit_system_hooks.py | Unexplained complexity: get_data | |
| 308 | explainability_deficit | medium | 0.5 | frappe\database\database.py | Unexplained complexity: Database._return_as_iterator | |
| 309 | explainability_deficit | medium | 0.5 | frappe\database\mariadb\setup_db.py | Unexplained complexity: get_root_connection | |
| 310 | explainability_deficit | medium | 0.5 | frappe\database\postgres\setup_db.py | Unexplained complexity: get_root_connection | |
| 311 | explainability_deficit | medium | 0.5 | frappe\database\schema.py | Unexplained complexity: DbColumn.default_changed | |
| 312 | explainability_deficit | medium | 0.5 | frappe\database\schema.py | Unexplained complexity: DbColumn.default_changed_for_decimal | |
| 313 | explainability_deficit | medium | 0.5 | frappe\defaults.py | Unexplained complexity: get_user_default | |
| 314 | explainability_deficit | medium | 0.5 | frappe\desk\desktop.py | Unexplained complexity: save_new_widget | |
| 315 | explainability_deficit | medium | 0.5 | …pe\dashboard_chart\dashboard_chart.py | Unexplained complexity: get_permission_query_conditions | |
| 316 | explainability_deficit | medium | 0.5 | …pe\dashboard_chart\dashboard_chart.py | Unexplained complexity: DashboardChart.check_required_field | |
| 317 | explainability_deficit | medium | 0.5 | …e\desk\doctype\workspace\workspace.py | Unexplained complexity: Workspace.on_update | |
| 318 | explainability_deficit | medium | 0.5 | …e\desk\doctype\workspace\workspace.py | Unexplained complexity: Workspace.build_links_table_from_car | |
| 319 | explainability_deficit | medium | 0.5 | …esk\page\setup_wizard\setup_wizard.py | Unexplained complexity: make_records | |
| 320 | explainability_deficit | medium | 0.5 | frappe\desk\query_report.py | Unexplained complexity: build_xlsx_data | |
| 321 | explainability_deficit | medium | 0.5 | frappe\desk\query_report.py | Unexplained complexity: get_filtered_data | |
| 322 | explainability_deficit | medium | 0.5 | frappe\installer.py | Unexplained complexity: make_site_config | |
| 323 | explainability_deficit | medium | 0.5 | frappe\model\base_document.py | Unexplained complexity: BaseDocument._validate_constants | |
| 324 | explainability_deficit | medium | 0.5 | frappe\model\db_query.py | Unexplained complexity: DatabaseQuery.prepare_filter_conditi | |
| 325 | explainability_deficit | medium | 0.5 | frappe\model\delete_doc.py | Unexplained complexity: delete_doc | |
| 326 | explainability_deficit | medium | 0.5 | frappe\model\naming.py | Unexplained complexity: parse_naming_series | |
| 327 | explainability_deficit | medium | 0.5 | frappe\model\naming.py | Unexplained complexity: validate_name | |
| 328 | explainability_deficit | medium | 0.5 | frappe\model\qb_query.py | Unexplained complexity: DatabaseQuery.execute | |
| 329 | explainability_deficit | medium | 0.5 | frappe\model\rename_doc.py | Unexplained complexity: rename_doc | |
| 330 | explainability_deficit | medium | 0.5 | frappe\model\utils\user_settings.py | Unexplained complexity: update_user_settings_data | |
| 331 | explainability_deficit | medium | 0.5 | …hes\v12_0\delete_duplicate_indexes.py | Unexplained complexity: execute | |
| 332 | explainability_deficit | medium | 0.5 | …ve_timeline_links_to_dynamic_links.py | Unexplained complexity: execute | |
| 333 | explainability_deficit | medium | 0.5 | …es\v16_0\switch_default_sort_order.py | Unexplained complexity: update_sort_order_in_user_settings | |
| 334 | explainability_deficit | medium | 0.5 | frappe\search\sqlite_search.py | Unexplained complexity: update_doc_index | |
| 335 | explainability_deficit | medium | 0.5 | frappe\search\sqlite_search.py | Unexplained complexity: process_queue | |
| 336 | explainability_deficit | medium | 0.5 | frappe\utils\__init__.py | Unexplained complexity: execute_in_shell | |
| 337 | explainability_deficit | medium | 0.5 | frappe\utils\background_jobs.py | Unexplained complexity: enqueue | |
| 338 | explainability_deficit | medium | 0.5 | frappe\utils\backups.py | Unexplained complexity: BackupGenerator.setup_backup_directo | |
| 339 | explainability_deficit | medium | 0.5 | frappe\utils\change_log.py | Unexplained complexity: get_change_log | |
| 340 | explainability_deficit | medium | 0.5 | frappe\utils\dashboard.py | Unexplained complexity: generate_and_cache_results | |
| 341 | explainability_deficit | medium | 0.5 | frappe\utils\data.py | Unexplained complexity: fmt_money | |
| 342 | explainability_deficit | medium | 0.5 | frappe\utils\data.py | Unexplained complexity: get_url | |
| 343 | explainability_deficit | medium | 0.5 | frappe\utils\global_search.py | Unexplained complexity: search | |
| 344 | explainability_deficit | medium | 0.5 | frappe\utils\jinja_globals.py | Unexplained complexity: web_blocks | |
| 345 | explainability_deficit | medium | 0.5 | frappe\utils\messages.py | Unexplained complexity: msgprint | |
| 346 | explainability_deficit | medium | 0.5 | frappe\utils\nestedset.py | Unexplained complexity: update_nsm | |
| 347 | explainability_deficit | medium | 0.5 | frappe\utils\pdf.py | Unexplained complexity: prepare_options | |
| 348 | explainability_deficit | medium | 0.5 | …\website\doctype\web_form\web_form.py | Unexplained complexity: WebForm.validate | |
| 349 | explainability_deficit | medium | 0.5 | …\website\doctype\web_form\web_form.py | Unexplained complexity: has_link_option | |
| 350 | explainability_deficit | medium | 0.5 | frappe\website\utils.py | Unexplained complexity: get_home_page_via_hooks | |
| 351 | explainability_deficit | medium | 0.5 | frappe\website\utils.py | Unexplained complexity: get_next_link | |
| 352 | explainability_deficit | medium | 0.5 | frappe\website\utils.py | Unexplained complexity: get_portal_sidebar_items | |
| 353 | explainability_deficit | medium | 0.5 | frappe\www\printview.py | Unexplained complexity: make_layout | |

## Detailed Findings

### #1: error_handling: 92 variants in frappe/utils/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.989 | **Impact:** 1.188
**File:** frappe\utils

> 92 error_handling variants in frappe/utils/ (10/158 use canonical pattern).
  - __init__.py:117 (validate_phone_number_with_country_code)
  - __init__.py:284 (is_valid_iban)
  - data.py:179 (get_datetime)

**Fix:** Konsolidiere auf das dominante Pattern (10×). 148 Abweichung(en) in: __init__.py, background_jobs.py, backups.py, bench_helper.py, boilerplate.py und 143 weitere.

**Related:** frappe\utils\__init__.py, frappe\utils\__init__.py, frappe\utils\data.py, frappe\utils\data.py, frappe\utils\__init__.py

**Verdict:** TP / FP / ?
**Note:**

---

### #2: error_handling: 46 variants in frappe/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.978 | **Impact:** 1.027
**File:** frappe

> 46 error_handling variants in frappe/ (9/78 use canonical pattern).
  - _optimizations.py:181 (parse_thread_siblings)
  - app.py:101 (application)
  - app.py:151 (application)

**Fix:** Konsolidiere auf das dominante Pattern (9×). 69 Abweichung(en) in: _optimizations.py, app.py, apps.py, auth.py, boot.py und 64 weitere.

**Related:** frappe\_optimizations.py, frappe\app.py, frappe\app.py, frappe\deferred_insert.py, frappe\app.py

**Verdict:** TP / FP / ?
**Note:**

---

### #3: error_handling: 32 variants in frappe/model/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.969 | **Impact:** 0.888
**File:** frappe\model

> 32 error_handling variants in frappe/model/ (3/38 use canonical pattern).
  - base_document.py:78 (_fetch_link_values)
  - meta.py:158 (Meta.load_from_db)
  - base_document.py:231 (_get_extended_class)

**Fix:** Konsolidiere auf das dominante Pattern (3×). 35 Abweichung(en) in: base_document.py, db_query.py, delete_doc.py, dynamic_links.py, mapper.py und 30 weitere.

**Related:** frappe\model\base_document.py, frappe\model\meta.py, frappe\model\base_document.py, frappe\model\base_document.py, frappe\model\base_document.py

**Verdict:** TP / FP / ?
**Note:**

---

### #4: error_handling: 21 variants in frappe/commands/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.952 | **Impact:** 0.788
**File:** frappe\commands

> 21 error_handling variants in frappe/commands/ (38/60 use canonical pattern).
  - __init__.py:27 (_func)
  - __init__.py:54 (get_site)
  - execute.py:68 (_execute)

**Fix:** Konsolidiere auf das dominante Pattern (38×). 22 Abweichung(en) in: __init__.py, execute.py, scheduler.py, site.py, testing.py und 17 weitere.

**Related:** frappe\commands\__init__.py, frappe\commands\__init__.py, frappe\commands\execute.py, frappe\commands\site.py, frappe\commands\execute.py

**Verdict:** TP / FP / ?
**Note:**

---

### #5: error_handling: 19 variants in frappe/desk/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.947 | **Impact:** 0.775
**File:** frappe\desk

> 19 error_handling variants in frappe/desk/ (3/24 use canonical pattern).
  - desktop.py:22 (wrapper)
  - desktop.py:363 (get_desktop_page)
  - desktop.py:430 (get_workspace_sidebar_items)

**Fix:** Konsolidiere auf das dominante Pattern (3×). 21 Abweichung(en) in: desktop.py, like.py, listview.py, notifications.py, query_report.py und 16 weitere.

**Related:** frappe\desk\desktop.py, frappe\desk\desktop.py, frappe\desk\desktop.py, frappe\desk\desktop.py, frappe\desk\like.py

**Verdict:** TP / FP / ?
**Note:**

---

### #6: error_handling: 18 variants in frappe/email/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.944 | **Impact:** 0.755
**File:** frappe\email

> 18 error_handling variants in frappe/email/ (4/23 use canonical pattern).
  - __init__.py:92 (get_communication_doctype)
  - oauth.py:38 (Oauth.connect)
  - queue.py:102 (unsubscribe)

**Fix:** Konsolidiere auf das dominante Pattern (4×). 19 Abweichung(en) in: __init__.py, oauth.py, queue.py, receive.py, smtp.py und 14 weitere.

**Related:** frappe\email\__init__.py, frappe\email\oauth.py, frappe\email\queue.py, frappe\email\queue.py, frappe\email\receive.py

**Verdict:** TP / FP / ?
**Note:**

---

### #7: Circular dependency (168 modules)
**Signal:** architecture_violation | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.735
**File:** frappe\auth.py

> Cycle: auth.py → assignment_rule.py → boot.py → cache_manager.py → client.py → testing.py → config.py → address_and_contact.py → address.py → contact.py → file.py → access_log.py → activity_log.py → feed.py → comment.py → communication.py → email.py → mixins.py → exporter.py → data_import.py → exporter.py → importer.py → doctype.py → file.py → utils.py → permission_type.py → prepared_report.py → role.py → scheduled_job_type.py → submission_queue.py → user.py → user_permission.py → user_type.py → custom_field.py → customize_form.py → property_setter.py → database.py → database.py → database.py → utils.py → defaults.py → deprecation_dumpster.py → desktop.py → changelog_feed.py → desktop_icon.py → note.py → notification_log.py → notification_settings.py → route_history.py → todo.py → workspace_sidebar.py → linked_with.py → load.py → meta.py → notifications.py → query_report.py → reportview.py → search.py → utils.py → email_account.py → email_queue.py → email_template.py → notification.py → email_body.py → frappemail.py → inbox.py → queue.py → receive.py → frappeclient.py → country_info.py → handler.py → installer.py → connected_app.py → ldap_settings.py → oauth_client.py → social_login_key.py → oauth2.py → utils.py → base_document.py → db_query.py → delete_doc.py → meta.py → naming.py → qb_query.py → rename_doc.py → sync.py → virtual_doctype.py → workflow.py → import_file.py → utils.py → monitor.py → oauth.py → parallel_test_runner.py → permissions.py → print_format.py → builder.py → functions.py → terms.py → utils.py → website_search.py → sessions.py → share.py → environment.py → loader.py → result.py → translate.py → twofactor.py → exporter.py → background_jobs.py → backups.py → csvutils.py → dashboard.py → data.py → dateutils.py → deprecations.py → error.py → file_manager.py → fixtures.py → formatters.py → global_search.py → html_utils.py → jinja.py → jinja_globals.py → nestedset.py → oauth.py → password.py → pdf.py → browser.py → chrome_pdf_generator.py → page.py → print_utils.py → redis_queue.py → redis_wrapper.py → response.py → safe_exec.py → scheduler.py → sentry.py → translations.py → user.py → verified_command.py → xlsxutils.py → web_form.py → web_page.py → web_page_view.py → website_settings.py → website_slideshow.py → base_renderer.py → base_template_page.py → document_page.py → error_page.py → list_renderer.py → not_found_page.py → not_permitted_page.py → print_page.py → redirect_page.py → static_page.py → template_page.py → web_form.py → path_resolver.py → router.py → serve.py → utils.py → website_generator.py → workflow.py → list.py → login.py → printview.py → sitemap.py

**Fix:** Zirkuläre Abhängigkeit (168 Module): auth.py → assignment_rule.py → boot.py → cache_manager.py → client.py → testing.py → config.py → address_and_contact.py → address.py → contact.py → file.py → access_log.py → activity_log.py → feed.py → comment.py → communication.py → email.py → mixins.py → exporter.py → data_import.py → exporter.py → importer.py → doctype.py → file.py → utils.py → permission_type.py → prepared_report.py → role.py → scheduled_job_type.py → submission_queue.py → user.py → user_permission.py → user_type.py → custom_field.py → customize_form.py → property_setter.py → database.py → database.py → database.py → utils.py → defaults.py → deprecation_dumpster.py → desktop.py → changelog_feed.py → desktop_icon.py → note.py → notification_log.py → notification_settings.py → route_history.py → todo.py → workspace_sidebar.py → linked_with.py → load.py → meta.py → notifications.py → query_report.py → reportview.py → search.py → utils.py → email_account.py → email_queue.py → email_template.py → notification.py → email_body.py → frappemail.py → inbox.py → queue.py → receive.py → frappeclient.py → country_info.py → handler.py → installer.py → connected_app.py → ldap_settings.py → oauth_client.py → social_login_key.py → oauth2.py → utils.py → base_document.py → db_query.py → delete_doc.py → meta.py → naming.py → qb_query.py → rename_doc.py → sync.py → virtual_doctype.py → workflow.py → import_file.py → utils.py → monitor.py → oauth.py → parallel_test_runner.py → permissions.py → print_format.py → builder.py → functions.py → terms.py → utils.py → website_search.py → sessions.py → share.py → environment.py → loader.py → result.py → translate.py → twofactor.py → exporter.py → background_jobs.py → backups.py → csvutils.py → dashboard.py → data.py → dateutils.py → deprecations.py → error.py → file_manager.py → fixtures.py → formatters.py → global_search.py → html_utils.py → jinja.py → jinja_globals.py → nestedset.py → oauth.py → password.py → pdf.py → browser.py → chrome_pdf_generator.py → page.py → print_utils.py → redis_queue.py → redis_wrapper.py → response.py → safe_exec.py → scheduler.py → sentry.py → translations.py → user.py → verified_command.py → xlsxutils.py → web_form.py → web_page.py → web_page_view.py → website_settings.py → website_slideshow.py → base_renderer.py → base_template_page.py → document_page.py → error_page.py → list_renderer.py → not_found_page.py → not_permitted_page.py → print_page.py → redirect_page.py → static_page.py → template_page.py → web_form.py → path_resolver.py → router.py → serve.py → utils.py → website_generator.py → workflow.py → list.py → login.py → printview.py → sitemap.py. Breche Zyklus durch Interface-Extraktion oder Dependency Inversion.

**Related:** frappe\automation\doctype\assignment_rule\assignment_rule.py, frappe\boot.py, frappe\cache_manager.py, frappe\client.py, frappe\commands\testing.py

**Verdict:** TP / FP / ?
**Note:**

---

### #8: error_handling: 17 variants in frappe/database/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.941 | **Impact:** 0.722
**File:** frappe\database

> 17 error_handling variants in frappe/database/ (1/17 use canonical pattern).
  - database.py:271 (Database.sql)
  - database.py:417 (Database.mogrify)
  - database.py:435 (Database.explain_query)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 16 Abweichung(en) in: database.py, schema.py, sequence.py, utils.py und 11 weitere.

**Related:** frappe\database\database.py, frappe\database\database.py, frappe\database\database.py, frappe\database\database.py, frappe\database\database.py

**Verdict:** TP / FP / ?
**Note:**

---

### #9: error_handling: 14 variants in frappe/core/doctype/file/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.929 | **Impact:** 0.689
**File:** frappe\core\doctype\file

> 14 error_handling variants in frappe/core/doctype/file/ (2/16 use canonical pattern).
  - file.py:165 (File.enforce_public_file_restrictions)
  - file.py:491 (File.make_thumbnail)
  - file.py:474 (File.make_thumbnail)

**Fix:** Konsolidiere auf das dominante Pattern (2×). 14 Abweichung(en) in: file.py, utils.py und 9 weitere.

**Related:** frappe\core\doctype\file\file.py, frappe\core\doctype\file\file.py, frappe\core\doctype\file\file.py, frappe\core\doctype\file\file.py, frappe\core\doctype\file\file.py

**Verdict:** TP / FP / ?
**Note:**

---

### #10: error_handling: 12 variants in frappe/search/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.917 | **Impact:** 0.667
**File:** frappe\search

> 12 error_handling variants in frappe/search/ (5/18 use canonical pattern).
  - full_text_search.py:89 (FullTextSearch.get_index)
  - sqlite_search.py:268 (SQLiteSearch.search)
  - sqlite_search.py:336 (SQLiteSearch.build_index)

**Fix:** Konsolidiere auf das dominante Pattern (5×). 13 Abweichung(en) in: full_text_search.py, sqlite_search.py, website_search.py und 8 weitere.

**Related:** frappe\search\full_text_search.py, frappe\search\sqlite_search.py, frappe\search\sqlite_search.py, frappe\search\sqlite_search.py, frappe\search\sqlite_search.py

**Verdict:** TP / FP / ?
**Note:**

---

### #11: error_handling: 9 variants in frappe/website/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.889 | **Impact:** 0.568
**File:** frappe\website

> 9 error_handling variants in frappe/website/ (1/9 use canonical pattern).
  - path_resolver.py:41 (PathResolver.resolve)
  - path_resolver.py:82 (PathResolver.get_custom_page_renderers)
  - path_resolver.py:159 (resolve_redirect)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 8 Abweichung(en) in: path_resolver.py, router.py, serve.py, utils.py und 3 weitere.

**Related:** frappe\website\path_resolver.py, frappe\website\path_resolver.py, frappe\website\path_resolver.py, frappe\website\router.py, frappe\website\router.py

**Verdict:** TP / FP / ?
**Note:**

---

### #12: error_handling: 8 variants in frappe/core/doctype/doctype/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.875 | **Impact:** 0.539
**File:** frappe\core\doctype\doctype

> 8 error_handling variants in frappe/core/doctype/doctype/ (2/9 use canonical pattern).
  - doctype.py:346 (DocType.setup_fields_to_fetch)
  - doctype.py:536 (DocType.on_update)
  - doctype.py:819 (DocType.before_export)

**Fix:** Konsolidiere auf das dominante Pattern (2×). 7 Abweichung(en) in: doctype.py und 2 weitere.

**Related:** frappe\core\doctype\doctype\doctype.py, frappe\core\doctype\doctype\doctype.py, frappe\core\doctype\doctype\doctype.py, frappe\core\doctype\doctype\doctype.py, frappe\core\doctype\doctype\doctype.py

**Verdict:** TP / FP / ?
**Note:**

---

### #13: error_handling: 7 variants in frappe/utils/pdf_generator/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.857 | **Impact:** 0.528
**File:** frappe\utils\pdf_generator

> 7 error_handling variants in frappe/utils/pdf_generator/ (3/10 use canonical pattern).
  - cdp_connection.py:37 (CDPSocketClient._listen)
  - cdp_connection.py:95 (CDPSocketClient._disconnect)
  - cdp_connection.py:86 (CDPSocketClient.disconnect)

**Fix:** Konsolidiere auf das dominante Pattern (3×). 7 Abweichung(en) in: cdp_connection.py, chrome_pdf_generator.py, page.py und 2 weitere.

**Related:** frappe\utils\pdf_generator\cdp_connection.py, frappe\utils\pdf_generator\cdp_connection.py, frappe\utils\pdf_generator\cdp_connection.py, frappe\utils\pdf_generator\cdp_connection.py, frappe\utils\pdf_generator\chrome_pdf_generator.py

**Verdict:** TP / FP / ?
**Note:**

---

### #14: error_handling: 7 variants in frappe/email/doctype/email_account/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.857 | **Impact:** 0.505
**File:** frappe\email\doctype\email_account

> 7 error_handling variants in frappe/email/doctype/email_account/ (2/8 use canonical pattern).
  - email_account.py:197 (EmailAccount.validate)
  - email_account.py:407 (EmailAccount.check_email_server_connection)
  - email_account.py:689 (EmailAccount.receive)

**Fix:** Konsolidiere auf das dominante Pattern (2×). 6 Abweichung(en) in: email_account.py und 1 weitere.

**Related:** frappe\email\doctype\email_account\email_account.py, frappe\email\doctype\email_account\email_account.py, frappe\email\doctype\email_account\email_account.py, frappe\email\doctype\email_account\email_account.py, frappe\email\doctype\email_account\email_account.py

**Verdict:** TP / FP / ?
**Note:**

---

### #15: error_handling: 7 variants in frappe/modules/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.857 | **Impact:** 0.505
**File:** frappe\modules

> 7 error_handling variants in frappe/modules/ (1/7 use canonical pattern).
  - import_file.py:108 (import_file_by_path)
  - import_file.py:176 (read_doc_from_file)
  - patch_handler.py:61 (run_patch)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 6 Abweichung(en) in: import_file.py, patch_handler.py, utils.py und 1 weitere.

**Related:** frappe\modules\import_file.py, frappe\modules\import_file.py, frappe\modules\patch_handler.py, frappe\modules\patch_handler.py, frappe\modules\patch_handler.py

**Verdict:** TP / FP / ?
**Note:**

---

### #16: error_handling: 7 variants in frappe/www/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.857 | **Impact:** 0.505
**File:** frappe\www

> 7 error_handling variants in frappe/www/ (1/7 use canonical pattern).
  - desk.py:29 (get_context)
  - list.py:78 (prepare_filters)
  - list.py:226 (get_dynamic_filters)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 6 Abweichung(en) in: desk.py, list.py, printview.py, sitemap.py und 1 weitere.

**Related:** frappe\www\desk.py, frappe\www\list.py, frappe\www\list.py, frappe\www\printview.py, frappe\www\printview.py

**Verdict:** TP / FP / ?
**Note:**

---

### #17: error_handling: 6 variants in frappe/core/doctype/user/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.833 | **Impact:** 0.465
**File:** frappe\core\doctype\user

> 6 error_handling variants in frappe/core/doctype/user/ (1/6 use canonical pattern).
  - user.py:787 (User.get_social_login_userid)
  - user.py:831 (User.find_by_credentials)
  - user.py:1130 (reset_password)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 5 Abweichung(en) in: user.py.

**Related:** frappe\core\doctype\user\user.py, frappe\core\doctype\user\user.py, frappe\core\doctype\user\user.py, frappe\core\doctype\user\user.py, frappe\core\doctype\user\user.py

**Verdict:** TP / FP / ?
**Note:**

---

### #18: error_handling: 5 variants in frappe/core/doctype/data_import/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.8 | **Impact:** 0.417
**File:** frappe\core\doctype\data_import

> 5 error_handling variants in frappe/core/doctype/data_import/ (2/6 use canonical pattern).
  - data_import.py:180 (stop_data_import)
  - data_import.py:192 (start_import)
  - importer.py:155 (Importer.import_data)

**Fix:** Konsolidiere auf das dominante Pattern (2×). 4 Abweichung(en) in: data_import.py, importer.py.

**Related:** frappe\core\doctype\data_import\data_import.py, frappe\core\doctype\data_import\data_import.py, frappe\core\doctype\data_import\importer.py, frappe\core\doctype\data_import\importer.py

**Verdict:** TP / FP / ?
**Note:**

---

### #19: error_handling: 5 variants in frappe/core/doctype/scheduled_job_type/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.8 | **Impact:** 0.417
**File:** frappe\core\doctype\scheduled_job_type

> 5 error_handling variants in frappe/core/doctype/scheduled_job_type/ (1/5 use canonical pattern).
  - scheduled_job_type.py:149 (ScheduledJobType.execute)
  - scheduled_job_type.py:215 (run_scheduled_job)
  - scheduled_job_type.py:287 (insert_single_event)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 4 Abweichung(en) in: scheduled_job_type.py.

**Related:** frappe\core\doctype\scheduled_job_type\scheduled_job_type.py, frappe\core\doctype\scheduled_job_type\scheduled_job_type.py, frappe\core\doctype\scheduled_job_type\scheduled_job_type.py, frappe\core\doctype\scheduled_job_type\scheduled_job_type.py

**Verdict:** TP / FP / ?
**Note:**

---

### #20: error_handling: 5 variants in frappe/desk/form/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.8 | **Impact:** 0.417
**File:** frappe\desk\form

> 5 error_handling variants in frappe/desk/form/ (1/5 use canonical pattern).
  - linked_with.py:308 (get_references_across_doctypes_by_dynamic_link_field)
  - linked_with.py:593 (_get_linked_doctypes)
  - load.py:33 (getdoc)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 4 Abweichung(en) in: linked_with.py, load.py, meta.py.

**Related:** frappe\desk\form\linked_with.py, frappe\desk\form\linked_with.py, frappe\desk\form\load.py, frappe\desk\form\meta.py

**Verdict:** TP / FP / ?
**Note:**

---

### #21: error_handling: 5 variants in frappe/integrations/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.8 | **Impact:** 0.417
**File:** frappe\integrations

> 5 error_handling variants in frappe/integrations/ (4/8 use canonical pattern).
  - oauth2.py:166 (revoke_token)
  - oauth2.py:231 (introspect_token)
  - oauth2.py:360 (register_client)

**Fix:** Konsolidiere auf das dominante Pattern (4×). 4 Abweichung(en) in: oauth2.py, utils.py.

**Related:** frappe\integrations\oauth2.py, frappe\integrations\oauth2.py, frappe\integrations\oauth2.py, frappe\integrations\utils.py

**Verdict:** TP / FP / ?
**Note:**

---

### #22: error_handling: 4 variants in frappe/api/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.75 | **Impact:** 0.391
**File:** frappe\api

> 4 error_handling variants in frappe/api/ (4/8 use canonical pattern).
  - __init__.py:58 (handle)
  - v1.py:133 (get_request_form_data)
  - v2.py:58 (handle_rpc_call)

**Fix:** Konsolidiere auf das dominante Pattern (4×). 4 Abweichung(en) in: __init__.py, v1.py, v2.py.

**Related:** frappe\api\__init__.py, frappe\api\v1.py, frappe\api\v2.py, frappe\api\v2.py

**Verdict:** TP / FP / ?
**Note:**

---

### #23: error_handling: 4 variants in frappe/email/doctype/notification/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.75 | **Impact:** 0.391
**File:** frappe\email\doctype\notification

> 4 error_handling variants in frappe/email/doctype/notification/ (3/7 use canonical pattern).
  - notification.py:97 (Notification.preview_meets_condition)
  - notification.py:110 (Notification.preview_message)
  - notification.py:127 (Notification.preview_subject)

**Fix:** Konsolidiere auf das dominante Pattern (3×). 4 Abweichung(en) in: notification.py.

**Related:** frappe\email\doctype\notification\notification.py, frappe\email\doctype\notification\notification.py, frappe\email\doctype\notification\notification.py, frappe\email\doctype\notification\notification.py

**Verdict:** TP / FP / ?
**Note:**

---

### #24: error_handling: 4 variants in frappe/integrations/doctype/webhook/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.75 | **Impact:** 0.391
**File:** frappe\integrations\doctype\webhook

> 4 error_handling variants in frappe/integrations/doctype/webhook/ (3/7 use canonical pattern).
  - webhook.py:126 (Webhook.preview_meets_condition)
  - webhook.py:136 (Webhook.preview_request_body)
  - webhook.py:165 (enqueue_webhook)

**Fix:** Konsolidiere auf das dominante Pattern (3×). 4 Abweichung(en) in: webhook.py.

**Related:** frappe\integrations\doctype\webhook\webhook.py, frappe\integrations\doctype\webhook\webhook.py, frappe\integrations\doctype\webhook\webhook.py, frappe\integrations\doctype\webhook\webhook.py

**Verdict:** TP / FP / ?
**Note:**

---

### #25: error_handling: 4 variants in frappe/core/doctype/communication/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.75 | **Impact:** 0.358
**File:** frappe\core\doctype\communication

> 4 error_handling variants in frappe/core/doctype/communication/ (1/4 use canonical pattern).
  - communication.py:534 (get_contacts)
  - communication.py:622 (get_email_without_link)
  - email.py:314 (_mark_email_as_seen)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 3 Abweichung(en) in: communication.py, email.py.

**Related:** frappe\core\doctype\communication\communication.py, frappe\core\doctype\communication\communication.py, frappe\core\doctype\communication\email.py

**Verdict:** TP / FP / ?
**Note:**

---

### #26: error_handling: 4 variants in frappe/core/doctype/document_naming_settings/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.75 | **Impact:** 0.358
**File:** frappe\core\doctype\document_naming_settings

> 4 error_handling variants in frappe/core/doctype/document_naming_settings/ (1/4 use canonical pattern).
  - document_naming_settings.py:92 (DocumentNamingSettings._evaluate_and_clean_templates)
  - document_naming_settings.py:244 (DocumentNamingSettings.preview_series)
  - document_naming_settings.py:253 (DocumentNamingSettings._fetch_last_doc_if_available)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 3 Abweichung(en) in: document_naming_settings.py.

**Related:** frappe\core\doctype\document_naming_settings\document_naming_settings.py, frappe\core\doctype\document_naming_settings\document_naming_settings.py, frappe\core\doctype\document_naming_settings\document_naming_settings.py

**Verdict:** TP / FP / ?
**Note:**

---

### #27: error_handling: 4 variants in frappe/database/mariadb/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.75 | **Impact:** 0.358
**File:** frappe\database\mariadb

> 4 error_handling variants in frappe/database/mariadb/ (2/5 use canonical pattern).
  - schema.py:157 (MariaDBTable.alter)
  - schema.py:149 (MariaDBTable.alter)
  - setup_db.py:103 (check_compatible_versions)

**Fix:** Konsolidiere auf das dominante Pattern (2×). 3 Abweichung(en) in: schema.py, setup_db.py.

**Related:** frappe\database\mariadb\schema.py, frappe\database\mariadb\schema.py, frappe\database\mariadb\setup_db.py

**Verdict:** TP / FP / ?
**Note:**

---

### #28: error_handling: 4 variants in frappe/desk/doctype/workspace_sidebar/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.75 | **Impact:** 0.358
**File:** frappe\desk\doctype\workspace_sidebar

> 4 error_handling variants in frappe/desk/doctype/workspace_sidebar/ (2/5 use canonical pattern).
  - workspace_sidebar.py:126 (WorkspaceSidebar.get_module_from_items)
  - workspace_sidebar.py:204 (add_sidebar_items)
  - workspace_sidebar.py:331 (choose_top_doctypes)

**Fix:** Konsolidiere auf das dominante Pattern (2×). 3 Abweichung(en) in: workspace_sidebar.py.

**Related:** frappe\desk\doctype\workspace_sidebar\workspace_sidebar.py, frappe\desk\doctype\workspace_sidebar\workspace_sidebar.py, frappe\desk\doctype\workspace_sidebar\workspace_sidebar.py

**Verdict:** TP / FP / ?
**Note:**

---

### #29: error_handling: 4 variants in frappe/integrations/doctype/google_calendar/
**Signal:** pattern_fragmentation | **Severity:** high | **Score:** 0.75 | **Impact:** 0.358
**File:** frappe\integrations\doctype\google_calendar

> 4 error_handling variants in frappe/integrations/doctype/google_calendar/ (5/8 use canonical pattern).
  - google_calendar.py:129 (GoogleCalendar.get_access_token)
  - google_calendar.py:169 (authorize_access)
  - google_calendar.py:290 (sync_events_from_google_calendar)

**Fix:** Konsolidiere auf das dominante Pattern (5×). 3 Abweichung(en) in: google_calendar.py.

**Related:** frappe\integrations\doctype\google_calendar\google_calendar.py, frappe\integrations\doctype\google_calendar\google_calendar.py, frappe\integrations\doctype\google_calendar\google_calendar.py

**Verdict:** TP / FP / ?
**Note:**

---

### #30: error_handling: 3 variants in frappe/core/doctype/comment/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.667 | **Impact:** 0.28
**File:** frappe\core\doctype\comment

> 3 error_handling variants in frappe/core/doctype/comment/ (1/3 use canonical pattern).
  - comment.py:160 (get_comments_from_parent)
  - comment.py:191 (update_comments_in_parent)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 2 Abweichung(en) in: comment.py.

**Related:** frappe\core\doctype\comment\comment.py, frappe\core\doctype\comment\comment.py

**Verdict:** TP / FP / ?
**Note:**

---

### #31: error_handling: 3 variants in frappe/core/page/permission_manager/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.667 | **Impact:** 0.28
**File:** frappe\core\page\permission_manager

> 3 error_handling variants in frappe/core/page/permission_manager/ (1/3 use canonical pattern).
  - permission_manager.py:185 (reset)
  - permission_manager.py:255 (get_permission_logs)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 2 Abweichung(en) in: permission_manager.py.

**Related:** frappe\core\page\permission_manager\permission_manager.py, frappe\core\page\permission_manager\permission_manager.py

**Verdict:** TP / FP / ?
**Note:**

---

### #32: error_handling: 3 variants in frappe/database/postgres/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.667 | **Impact:** 0.28
**File:** frappe\database\postgres

> 3 error_handling variants in frappe/database/postgres/ (1/3 use canonical pattern).
  - schema.py:237 (PostgresTable.alter)
  - schema.py:229 (PostgresTable.alter)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 2 Abweichung(en) in: schema.py.

**Related:** frappe\database\postgres\schema.py, frappe\database\postgres\schema.py

**Verdict:** TP / FP / ?
**Note:**

---

### #33: error_handling: 3 variants in frappe/desk/doctype/system_health_report/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.667 | **Impact:** 0.28
**File:** frappe\desk\doctype\system_health_report

> 3 error_handling variants in frappe/desk/doctype/system_health_report/ (1/3 use canonical pattern).
  - system_health_report.py:57 (wrapper)
  - system_health_report.py:373 (get_job_status)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 2 Abweichung(en) in: system_health_report.py.

**Related:** frappe\desk\doctype\system_health_report\system_health_report.py, frappe\desk\doctype\system_health_report\system_health_report.py

**Verdict:** TP / FP / ?
**Note:**

---

### #34: error_handling: 3 variants in frappe/integrations/doctype/ldap_settings/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.667 | **Impact:** 0.28
**File:** frappe\integrations\doctype\ldap_settings

> 3 error_handling variants in frappe/integrations/doctype/ldap_settings/ (1/3 use canonical pattern).
  - ldap_settings.py:136 (LDAPSettings.connect_to_ldap)
  - ldap_settings.py:317 (LDAPSettings.authenticate)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 2 Abweichung(en) in: ldap_settings.py.

**Related:** frappe\integrations\doctype\ldap_settings\ldap_settings.py, frappe\integrations\doctype\ldap_settings\ldap_settings.py

**Verdict:** TP / FP / ?
**Note:**

---

### #35: error_handling: 3 variants in frappe/patches/v11_0/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.667 | **Impact:** 0.28
**File:** frappe\patches\v11_0

> 3 error_handling variants in frappe/patches/v11_0/ (2/4 use canonical pattern).
  - replicate_old_user_permissions.py:45 (get_doctypes_to_skip)
  - replicate_old_user_permissions.py:84 (get_user_permission_doctypes)

**Fix:** Konsolidiere auf das dominante Pattern (2×). 2 Abweichung(en) in: replicate_old_user_permissions.py.

**Related:** frappe\patches\v11_0\replicate_old_user_permissions.py, frappe\patches\v11_0\replicate_old_user_permissions.py

**Verdict:** TP / FP / ?
**Note:**

---

### #36: error_handling: 3 variants in frappe/patches/v12_0/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.667 | **Impact:** 0.28
**File:** frappe\patches\v12_0

> 3 error_handling variants in frappe/patches/v12_0/ (1/3 use canonical pattern).
  - fix_public_private_files.py:18 (generate_file)
  - rename_uploaded_files_with_proper_name.py:19 (execute)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 2 Abweichung(en) in: fix_public_private_files.py, rename_uploaded_files_with_proper_name.py.

**Related:** frappe\patches\v12_0\fix_public_private_files.py, frappe\patches\v12_0\rename_uploaded_files_with_proper_name.py

**Verdict:** TP / FP / ?
**Note:**

---

### #37: error_handling: 3 variants in frappe/patches/v13_0/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.667 | **Impact:** 0.28
**File:** frappe\patches\v13_0

> 3 error_handling variants in frappe/patches/v13_0/ (1/3 use canonical pattern).
  - generate_theme_files_in_public_folder.py:12 (execute)
  - reset_corrupt_defaults.py:28 (execute)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 2 Abweichung(en) in: generate_theme_files_in_public_folder.py, reset_corrupt_defaults.py.

**Related:** frappe\patches\v13_0\generate_theme_files_in_public_folder.py, frappe\patches\v13_0\reset_corrupt_defaults.py

**Verdict:** TP / FP / ?
**Note:**

---

### #38: error_handling: 3 variants in frappe/patches/v15_0/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.667 | **Impact:** 0.28
**File:** frappe\patches\v15_0

> 3 error_handling variants in frappe/patches/v15_0/ (1/3 use canonical pattern).
  - sanitize_workspace_titles.py:20 (execute)
  - set_contact_full_name.py:19 (execute)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 2 Abweichung(en) in: sanitize_workspace_titles.py, set_contact_full_name.py.

**Related:** frappe\patches\v15_0\sanitize_workspace_titles.py, frappe\patches\v15_0\set_contact_full_name.py

**Verdict:** TP / FP / ?
**Note:**

---

### #39: error_handling: 3 variants in frappe/testing/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.667 | **Impact:** 0.28
**File:** frappe\testing

> 3 error_handling variants in frappe/testing/ (4/6 use canonical pattern).
  - environment.py:91 (_get_config_from_pyproject)
  - environment.py:201 (IntegrationTestPreparation._create_global_test_record_dependencies)

**Fix:** Konsolidiere auf das dominante Pattern (4×). 2 Abweichung(en) in: environment.py.

**Related:** frappe\testing\environment.py, frappe\testing\environment.py

**Verdict:** TP / FP / ?
**Note:**

---

### #40: error_handling: 3 variants in frappe/utils/telemetry/pulse/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.667 | **Impact:** 0.28
**File:** frappe\utils\telemetry\pulse

> 3 error_handling variants in frappe/utils/telemetry/pulse/ (1/3 use canonical pattern).
  - client.py:173 (EventQueue.batch_process)
  - utils.py:60 (parse_interval)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 2 Abweichung(en) in: client.py, utils.py.

**Related:** frappe\utils\telemetry\pulse\client.py, frappe\utils\telemetry\pulse\utils.py

**Verdict:** TP / FP / ?
**Note:**

---

### #41: error_handling: 3 variants in frappe/website/page_renderers/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.667 | **Impact:** 0.28
**File:** frappe\website\page_renderers

> 3 error_handling variants in frappe/website/page_renderers/ (1/3 use canonical pattern).
  - list_renderer.py:12 (ListPage.can_render)
  - template_page.py:269 (TemplatePage.extract_frontmatter)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 2 Abweichung(en) in: list_renderer.py, template_page.py.

**Related:** frappe\website\page_renderers\list_renderer.py, frappe\website\page_renderers\template_page.py

**Verdict:** TP / FP / ?
**Note:**

---

### #42: Exact duplicates (2×): MariaDBDatabase.create_global_search_table
**Signal:** mutant_duplicate | **Severity:** high | **Score:** 0.9 | **Impact:** 0.229
**File:** frappe\database\mariadb\database.py (line 306)

> 2 identical copies (16 lines each) at: frappe\database\mariadb\database.py:306, frappe\database\mariadb\mysqlclient.py:333. Consider consolidating.

**Fix:** Extrahiere MariaDBDatabase.create_global_search_table() in frappe/database/mariadb/shared.py. 2 identische Kopien (Similarity: 1.00). Aufwand: S.

**Related:** frappe\database\mariadb\mysqlclient.py

**Verdict:** TP / FP / ?
**Note:**

---

### #43: Exact duplicates (2×): MariaDBDatabase.get_column_index
**Signal:** mutant_duplicate | **Severity:** high | **Score:** 0.9 | **Impact:** 0.229
**File:** frappe\database\mariadb\database.py (line 383)

> 2 identical copies (29 lines each) at: frappe\database\mariadb\database.py:383, frappe\database\mariadb\mysqlclient.py:410. Consider consolidating.

**Fix:** Extrahiere MariaDBDatabase.get_column_index() in frappe/database/mariadb/shared.py. 2 identische Kopien (Similarity: 1.00). Aufwand: S.

**Related:** frappe\database\mariadb\mysqlclient.py

**Verdict:** TP / FP / ?
**Note:**

---

### #44: Exact duplicates (2×): MariaDBDatabase.add_index
**Signal:** mutant_duplicate | **Severity:** high | **Score:** 0.9 | **Impact:** 0.229
**File:** frappe\database\mariadb\database.py (line 413)

> 2 identical copies (24 lines each) at: frappe\database\mariadb\database.py:413, frappe\database\mariadb\mysqlclient.py:440. Consider consolidating.

**Fix:** Extrahiere MariaDBDatabase.add_index() in frappe/database/mariadb/shared.py. 2 identische Kopien (Similarity: 1.00). Aufwand: S.

**Related:** frappe\database\mariadb\mysqlclient.py

**Verdict:** TP / FP / ?
**Note:**

---

### #45: Exact duplicates (2×): MariaDBDatabase.add_unique
**Signal:** mutant_duplicate | **Severity:** high | **Score:** 0.9 | **Impact:** 0.229
**File:** frappe\database\mariadb\database.py (line 438)

> 2 identical copies (16 lines each) at: frappe\database\mariadb\database.py:438, frappe\database\mariadb\mysqlclient.py:465. Consider consolidating.

**Fix:** Extrahiere MariaDBDatabase.add_unique() in frappe/database/mariadb/shared.py. 2 identische Kopien (Similarity: 1.00). Aufwand: S.

**Related:** frappe\database\mariadb\mysqlclient.py

**Verdict:** TP / FP / ?
**Note:**

---

### #46: Exact duplicates (2×): MariaDBDatabase.updatedb
**Signal:** mutant_duplicate | **Severity:** high | **Score:** 0.9 | **Impact:** 0.229
**File:** frappe\database\mariadb\database.py (line 455)

> 2 identical copies (17 lines each) at: frappe\database\mariadb\database.py:455, frappe\database\mariadb\mysqlclient.py:482. Consider consolidating.

**Fix:** Extrahiere MariaDBDatabase.updatedb() in frappe/database/mariadb/shared.py. 2 identische Kopien (Similarity: 1.00). Aufwand: S.

**Related:** frappe\database\mariadb\mysqlclient.py

**Verdict:** TP / FP / ?
**Note:**

---

### #47: Exact duplicates (2×): MariaDBDatabase.get_tables
**Signal:** mutant_duplicate | **Severity:** high | **Score:** 0.9 | **Impact:** 0.229
**File:** frappe\database\mariadb\database.py (line 476)

> 2 identical copies (20 lines each) at: frappe\database\mariadb\database.py:476, frappe\database\mariadb\mysqlclient.py:503. Consider consolidating.

**Fix:** Extrahiere MariaDBDatabase.get_tables() in frappe/database/mariadb/shared.py. 2 identische Kopien (Similarity: 1.00). Aufwand: S.

**Related:** frappe\database\mariadb\mysqlclient.py

**Verdict:** TP / FP / ?
**Note:**

---

### #48: Exact duplicates (2×): MariaDBDatabase.get_row_size
**Signal:** mutant_duplicate | **Severity:** high | **Score:** 0.9 | **Impact:** 0.229
**File:** frappe\database\mariadb\database.py (line 497)

> 2 identical copies (52 lines each) at: frappe\database\mariadb\database.py:497, frappe\database\mariadb\mysqlclient.py:524. Consider consolidating.

**Fix:** Extrahiere MariaDBDatabase.get_row_size() in frappe/database/mariadb/shared.py. 2 identische Kopien (Similarity: 1.00). Aufwand: S.

**Related:** frappe\database\mariadb\mysqlclient.py

**Verdict:** TP / FP / ?
**Note:**

---

### #49: Exact duplicates (2×): Workspace.get_cached, WorkspaceSidebar.get_cached
**Signal:** mutant_duplicate | **Severity:** high | **Score:** 0.9 | **Impact:** 0.229
**File:** frappe\desk\desktop.py (line 86)

> 2 identical copies (10 lines each) at: frappe\desk\desktop.py:86, frappe\desk\doctype\workspace_sidebar\workspace_sidebar.py:106. Consider consolidating.

**Fix:** Extrahiere Workspace.get_cached() in frappe/desk/shared.py. 2 identische Kopien (Similarity: 1.00). Aufwand: S.

**Related:** frappe\desk\doctype\workspace_sidebar\workspace_sidebar.py

**Verdict:** TP / FP / ?
**Note:**

---

### #50: Exact duplicates (2×): Workspace.get_allowed_modules, WorkspaceSidebar.get_allowed_modules
**Signal:** mutant_duplicate | **Severity:** high | **Score:** 0.9 | **Impact:** 0.229
**File:** frappe\desk\desktop.py (line 103)

> 2 identical copies (5 lines each) at: frappe\desk\desktop.py:103, frappe\desk\doctype\workspace_sidebar\workspace_sidebar.py:136. Consider consolidating.

**Fix:** Extrahiere Workspace.get_allowed_modules() in frappe/desk/shared.py. 2 identische Kopien (Similarity: 1.00). Aufwand: S.

**Related:** frappe\desk\doctype\workspace_sidebar\workspace_sidebar.py

**Verdict:** TP / FP / ?
**Note:**

---

### #51: Exact duplicates (2×): get_current_setting
**Signal:** mutant_duplicate | **Severity:** high | **Score:** 0.9 | **Impact:** 0.229
**File:** frappe\patches\v14_0\clear_long_pending_stale_logs.py (line 35)

> 2 identical copies (6 lines each) at: frappe\patches\v14_0\clear_long_pending_stale_logs.py:35, frappe\patches\v14_0\log_settings_migration.py:24. Consider consolidating.

**Fix:** Extrahiere get_current_setting() in frappe/patches/v14_0/shared.py. 2 identische Kopien (Similarity: 1.00). Aufwand: S.

**Related:** frappe\patches\v14_0\log_settings_migration.py

**Verdict:** TP / FP / ?
**Note:**

---

### #52: error_handling: 2 variants in frappe/automation/doctype/auto_repeat/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\automation\doctype\auto_repeat

> 2 error_handling variants in frappe/automation/doctype/auto_repeat/ (1/2 use canonical pattern).
  - auto_repeat.py:423 (AutoRepeat.send_notification)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 1 Abweichung(en) in: auto_repeat.py.

**Related:** frappe\automation\doctype\auto_repeat\auto_repeat.py

**Verdict:** TP / FP / ?
**Note:**

---

### #53: error_handling: 2 variants in frappe/core/doctype/deleted_document/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\core\doctype\deleted_document

> 2 error_handling variants in frappe/core/doctype/deleted_document/ (1/2 use canonical pattern).
  - deleted_document.py:78 (bulk_restore)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 1 Abweichung(en) in: deleted_document.py.

**Related:** frappe\core\doctype\deleted_document\deleted_document.py

**Verdict:** TP / FP / ?
**Note:**

---

### #54: error_handling: 2 variants in frappe/core/doctype/log_settings/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\core\doctype\log_settings

> 2 error_handling variants in frappe/core/doctype/log_settings/ (1/2 use canonical pattern).
  - log_settings.py:166 (clear_log_table)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 1 Abweichung(en) in: log_settings.py.

**Related:** frappe\core\doctype\log_settings\log_settings.py

**Verdict:** TP / FP / ?
**Note:**

---

### #55: error_handling: 2 variants in frappe/core/doctype/page/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\core\doctype\page

> 2 error_handling variants in frappe/core/doctype/page/ (1/2 use canonical pattern).
  - page.py:173 (Page.load_assets)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 1 Abweichung(en) in: page.py.

**Related:** frappe\core\doctype\page\page.py

**Verdict:** TP / FP / ?
**Note:**

---

### #56: error_handling: 2 variants in frappe/core/doctype/prepared_report/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\core\doctype\prepared_report

> 2 error_handling variants in frappe/core/doctype/prepared_report/ (1/2 use canonical pattern).
  - prepared_report.py:204 (stop_prepared_report)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 1 Abweichung(en) in: prepared_report.py.

**Related:** frappe\core\doctype\prepared_report\prepared_report.py

**Verdict:** TP / FP / ?
**Note:**

---

### #57: error_handling: 2 variants in frappe/core/doctype/rq_job/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\core\doctype\rq_job

> 2 error_handling variants in frappe/core/doctype/rq_job/ (1/2 use canonical pattern).
  - rq_job.py:110 (RQJob.stop_job)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 1 Abweichung(en) in: rq_job.py.

**Related:** frappe\core\doctype\rq_job\rq_job.py

**Verdict:** TP / FP / ?
**Note:**

---

### #58: error_handling: 2 variants in frappe/custom/doctype/custom_field/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\custom\doctype\custom_field

> 2 error_handling variants in frappe/custom/doctype/custom_field/ (1/2 use canonical pattern).
  - custom_field.py:353 (create_custom_fields)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 1 Abweichung(en) in: custom_field.py.

**Related:** frappe\custom\doctype\custom_field\custom_field.py

**Verdict:** TP / FP / ?
**Note:**

---

### #59: error_handling: 2 variants in frappe/database/sqlite/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\database\sqlite

> 2 error_handling variants in frappe/database/sqlite/ (2/3 use canonical pattern).
  - database.py:432 (SQLiteDatabase.execute_query)

**Fix:** Konsolidiere auf das dominante Pattern (2×). 1 Abweichung(en) in: database.py.

**Related:** frappe\database\sqlite\database.py

**Verdict:** TP / FP / ?
**Note:**

---

### #60: error_handling: 2 variants in frappe/desk/doctype/changelog_feed/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\desk\doctype\changelog_feed

> 2 error_handling variants in frappe/desk/doctype/changelog_feed/ (1/2 use canonical pattern).
  - changelog_feed.py:83 (_app_title)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 1 Abweichung(en) in: changelog_feed.py.

**Related:** frappe\desk\doctype\changelog_feed\changelog_feed.py

**Verdict:** TP / FP / ?
**Note:**

---

### #61: error_handling: 2 variants in frappe/desk/doctype/desktop_icon/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\desk\doctype\desktop_icon

> 2 error_handling variants in frappe/desk/doctype/desktop_icon/ (2/3 use canonical pattern).
  - desktop_icon.py:105 (DesktopIcon.is_permitted)

**Fix:** Konsolidiere auf das dominante Pattern (2×). 1 Abweichung(en) in: desktop_icon.py.

**Related:** frappe\desk\doctype\desktop_icon\desktop_icon.py

**Verdict:** TP / FP / ?
**Note:**

---

### #62: error_handling: 2 variants in frappe/desk/doctype/desktop_layout/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\desk\doctype\desktop_layout

> 2 error_handling variants in frappe/desk/doctype/desktop_layout/ (1/2 use canonical pattern).
  - desktop_layout.py:64 (get_layout)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 1 Abweichung(en) in: desktop_layout.py.

**Related:** frappe\desk\doctype\desktop_layout\desktop_layout.py

**Verdict:** TP / FP / ?
**Note:**

---

### #63: error_handling: 2 variants in frappe/desk/doctype/notification_log/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\desk\doctype\notification_log

> 2 error_handling variants in frappe/desk/doctype/notification_log/ (1/2 use canonical pattern).
  - notification_log.py:211 (set_notifications_as_unseen)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 1 Abweichung(en) in: notification_log.py.

**Related:** frappe\desk\doctype\notification_log\notification_log.py

**Verdict:** TP / FP / ?
**Note:**

---

### #64: error_handling: 2 variants in frappe/desk/doctype/notification_settings/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\desk\doctype\notification_settings

> 2 error_handling variants in frappe/desk/doctype/notification_settings/ (1/2 use canonical pattern).
  - notification_settings.py:91 (get_subscribed_documents)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 1 Abweichung(en) in: notification_settings.py.

**Related:** frappe\desk\doctype\notification_settings\notification_settings.py

**Verdict:** TP / FP / ?
**Note:**

---

### #65: error_handling: 2 variants in frappe/desk/doctype/workspace/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\desk\doctype\workspace

> 2 error_handling variants in frappe/desk/doctype/workspace/ (1/2 use canonical pattern).
  - workspace.py:165 (Workspace.delete_from_my_workspaces)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 1 Abweichung(en) in: workspace.py.

**Related:** frappe\desk\doctype\workspace\workspace.py

**Verdict:** TP / FP / ?
**Note:**

---

### #66: error_handling: 2 variants in frappe/desk/page/setup_wizard/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\desk\page\setup_wizard

> 2 error_handling variants in frappe/desk/page/setup_wizard/ (1/2 use canonical pattern).
  - setup_wizard.py:535 (make_records)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 1 Abweichung(en) in: setup_wizard.py.

**Related:** frappe\desk\page\setup_wizard\setup_wizard.py

**Verdict:** TP / FP / ?
**Note:**

---

### #67: error_handling: 2 variants in frappe/email/doctype/email_queue/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\email\doctype\email_queue

> 2 error_handling variants in frappe/email/doctype/email_queue/ (1/2 use canonical pattern).
  - email_queue.py:893 (QueueBuilder.as_dict)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 1 Abweichung(en) in: email_queue.py.

**Related:** frappe\email\doctype\email_queue\email_queue.py

**Verdict:** TP / FP / ?
**Note:**

---

### #68: error_handling: 2 variants in frappe/integrations/doctype/google_contacts/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\integrations\doctype\google_contacts

> 2 error_handling variants in frappe/integrations/doctype/google_contacts/ (3/4 use canonical pattern).
  - google_contacts.py:304 (get_indexed_value)

**Fix:** Konsolidiere auf das dominante Pattern (3×). 1 Abweichung(en) in: google_contacts.py.

**Related:** frappe\integrations\doctype\google_contacts\google_contacts.py

**Verdict:** TP / FP / ?
**Note:**

---

### #69: error_handling: 2 variants in frappe/patches/v14_0/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\patches\v14_0

> 2 error_handling variants in frappe/patches/v14_0/ (2/3 use canonical pattern).
  - reset_creation_datetime.py:23 (execute)

**Fix:** Konsolidiere auf das dominante Pattern (2×). 1 Abweichung(en) in: reset_creation_datetime.py.

**Related:** frappe\patches\v14_0\reset_creation_datetime.py

**Verdict:** TP / FP / ?
**Note:**

---

### #70: error_handling: 2 variants in frappe/printing/doctype/network_printer_settings/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\printing\doctype\network_printer_settings

> 2 error_handling variants in frappe/printing/doctype/network_printer_settings/ (1/2 use canonical pattern).
  - network_printer_settings.py:26 (NetworkPrinterSettings.get_printers_list)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 1 Abweichung(en) in: network_printer_settings.py.

**Related:** frappe\printing\doctype\network_printer_settings\network_printer_settings.py

**Verdict:** TP / FP / ?
**Note:**

---

### #71: error_handling: 2 variants in frappe/website/doctype/website_settings/
**Signal:** pattern_fragmentation | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.169
**File:** frappe\website\doctype\website_settings

> 2 error_handling variants in frappe/website/doctype/website_settings/ (1/2 use canonical pattern).
  - website_settings.py:133 (WebsiteSettings.validate_redirects)

**Fix:** Konsolidiere auf das dominante Pattern (1×). 1 Abweichung(en) in: website_settings.py.

**Related:** frappe\website\doctype\website_settings\website_settings.py

**Verdict:** TP / FP / ?
**Note:**

---

### #72: Unexplained complexity: apply
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\automation\doctype\assignment_rule\assignment_rule.py (line 269)

> Complexity: 26, LOC: 95. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion apply (Complexity 26): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #73: Unexplained complexity: _execute
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\commands\execute.py (line 8)

> Complexity: 20, LOC: 96. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion _execute (Complexity 20): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #74: Unexplained complexity: DataExporter.build_field_columns
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\core\doctype\data_export\exporter.py (line 208)

> Complexity: 20, LOC: 81. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion DataExporter.build_field_columns (Complexity 20): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #75: Unexplained complexity: DataExporter.add_data
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\core\doctype\data_export\exporter.py (line 362)

> Complexity: 22, LOC: 63. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion DataExporter.add_data (Complexity 22): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #76: Unexplained complexity: Importer.import_data
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\core\doctype\data_import\importer.py (line 78)

> Complexity: 32, LOC: 174. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Importer.import_data (Complexity 32): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #77: Unexplained complexity: validate_permissions
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\core\doctype\doctype\doctype.py (line 1822)

> Complexity: 53, LOC: 170. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion validate_permissions (Complexity 53): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #78: Unexplained complexity: CustomizeForm.allow_property_change
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\custom\doctype\customize_form\customize_form.py (line 327)

> Complexity: 28, LOC: 78. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion CustomizeForm.allow_property_change (Complexity 28): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #79: Unexplained complexity: MariaDBTable.alter
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\database\mariadb\schema.py (line 72)

> Complexity: 31, LOC: 106. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion MariaDBTable.alter (Complexity 31): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #80: Unexplained complexity: PostgresTable.alter
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\database\postgres\schema.py (line 73)

> Complexity: 40, LOC: 191. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion PostgresTable.alter (Complexity 40): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #81: Unexplained complexity: DbColumn.build_for_alter_table
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\database\schema.py (line 262)

> Complexity: 28, LOC: 54. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion DbColumn.build_for_alter_table (Complexity 28): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #82: Unexplained complexity: SQLiteTable.alter
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\database\sqlite\schema.py (line 60)

> Complexity: 22, LOC: 72. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion SQLiteTable.alter (Complexity 22): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #83: Unexplained complexity: _bulk_action
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\desk\doctype\bulk_update\bulk_update.py (line 82)

> Complexity: 21, LOC: 63. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion _bulk_action (Complexity 21): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #84: Unexplained complexity: _export_query
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\desk\reportview.py (line 416)

> Complexity: 22, LOC: 74. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion _export_query (Complexity 22): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #85: Unexplained complexity: install_app
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\installer.py (line 270)

> Complexity: 22, LOC: 79. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion install_app (Complexity 22): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #86: Unexplained complexity: get_mapped_doc
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\model\mapper.py (line 53)

> Complexity: 34, LOC: 118. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_mapped_doc (Complexity 34): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #87: Unexplained complexity: map_fields
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\model\mapper.py (line 187)

> Complexity: 21, LOC: 52. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion map_fields (Complexity 21): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #88: Unexplained complexity: update_reports
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\model\utils\rename_field.py (line 59)

> Complexity: 23, LOC: 66. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion update_reports (Complexity 23): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #89: Unexplained complexity: BackupGenerator.take_dump
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\utils\backups.py (line 378)

> Complexity: 22, LOC: 99. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion BackupGenerator.take_dump (Complexity 22): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #90: Unexplained complexity: PDFTransformer.transform_pdf
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\utils\pdf_generator\pdf_merge.py (line 26)

> Complexity: 24, LOC: 71. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion PDFTransformer.transform_pdf (Complexity 24): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #91: Unexplained complexity: get_website_settings
**Signal:** explainability_deficit | **Severity:** high | **Score:** 1.0 | **Impact:** 0.12
**File:** frappe\website\doctype\website_settings\website_settings.py (line 171)

> Complexity: 21, LOC: 95. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_website_settings (Complexity 21): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #92: Unexplained complexity: DocType.before_export
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.95 | **Impact:** 0.114
**File:** frappe\core\doctype\doctype\doctype.py (line 795)

> Complexity: 19, LOC: 47. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion DocType.before_export (Complexity 19): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #93: Unexplained complexity: get_command
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.95 | **Impact:** 0.114
**File:** frappe\database\__init__.py (line 92)

> Complexity: 19, LOC: 71. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_command (Complexity 19): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #94: Unexplained complexity: _export_query
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.95 | **Impact:** 0.114
**File:** frappe\desk\query_report.py (line 378)

> Complexity: 19, LOC: 81. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion _export_query (Complexity 19): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #95: Unexplained complexity: DatabaseQuery.set_order_by
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.95 | **Impact:** 0.114
**File:** frappe\model\db_query.py (line 1187)

> Complexity: 19, LOC: 39. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion DatabaseQuery.set_order_by (Complexity 19): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #96: Unexplained complexity: Browser.prepare_options_for_pdf
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.95 | **Impact:** 0.114
**File:** frappe\utils\pdf_generator\browser.py (line 218)

> Complexity: 19, LOC: 116. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Browser.prepare_options_for_pdf (Complexity 19): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #97: Unexplained complexity: LoginManager.authenticate
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.9 | **Impact:** 0.108
**File:** frappe\auth.py (line 262)

> Complexity: 18, LOC: 37. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion LoginManager.authenticate (Complexity 18): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #98: Unexplained complexity: load_desktop_data
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.9 | **Impact:** 0.108
**File:** frappe\boot.py (line 163)

> Complexity: 18, LOC: 61. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion load_desktop_data (Complexity 18): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #99: Unexplained complexity: DbColumn.get_definition
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.9 | **Impact:** 0.108
**File:** frappe\database\schema.py (line 211)

> Complexity: 18, LOC: 50. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion DbColumn.get_definition (Complexity 18): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #100: Unexplained complexity: get_definition
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.9 | **Impact:** 0.108
**File:** frappe\database\schema.py (line 411)

> Complexity: 18, LOC: 49. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_definition (Complexity 18): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #101: Unexplained complexity: Workspace.validate
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.9 | **Impact:** 0.108
**File:** frappe\desk\doctype\workspace\workspace.py (line 74)

> Complexity: 18, LOC: 40. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Workspace.validate (Complexity 18): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #102: Unexplained complexity: LDAPSettings.validate
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.9 | **Impact:** 0.108
**File:** frappe\integrations\doctype\ldap_settings\ldap_settings.py (line 68)

> Complexity: 18, LOC: 66. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion LDAPSettings.validate (Complexity 18): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #103: Unexplained complexity: DatabaseQuery.prepare_args
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.9 | **Impact:** 0.108
**File:** frappe\model\db_query.py (line 318)

> Complexity: 18, LOC: 72. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion DatabaseQuery.prepare_args (Complexity 18): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #104: Unexplained complexity: sync_for
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.9 | **Impact:** 0.108
**File:** frappe\model\sync.py (line 57)

> Complexity: 18, LOC: 86. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion sync_for (Complexity 18): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #105: Unexplained complexity: execute
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.9 | **Impact:** 0.108
**File:** frappe\patches\v10_0\refactor_social_login_keys.py (line 5)

> Complexity: 18, LOC: 53. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion execute (Complexity 18): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #106: Unexplained complexity: create_content
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.9 | **Impact:** 0.108
**File:** frappe\patches\v14_0\update_workspace2.py (line 14)

> Complexity: 18, LOC: 47. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion create_content (Complexity 18): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #107: Unexplained complexity: handle_exception
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.875 | **Impact:** 0.105
**File:** frappe\app.py (line 344)

> Complexity: 25, LOC: 70. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion handle_exception (Complexity 25): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #108: Unexplained complexity: generate_report_result
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.875 | **Impact:** 0.105
**File:** frappe\desk\query_report.py (line 77)

> Complexity: 23, LOC: 60. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion generate_report_result (Complexity 23): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #109: Unexplained complexity: search_widget
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.875 | **Impact:** 0.105
**File:** frappe\desk\search.py (line 67)

> Complexity: 47, LOC: 185. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion search_widget (Complexity 47): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #110: Unexplained complexity: upload_file
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.875 | **Impact:** 0.105
**File:** frappe\handler.py (line 126)

> Complexity: 22, LOC: 97. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion upload_file (Complexity 22): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #111: Unexplained complexity: get_user_pages_or_reports
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.85 | **Impact:** 0.102
**File:** frappe\boot.py (line 238)

> Complexity: 17, LOC: 104. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_user_pages_or_reports (Complexity 17): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #112: Unexplained complexity: Column.validate_values
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.85 | **Impact:** 0.102
**File:** frappe\core\doctype\data_import\importer.py (line 1029)

> Complexity: 17, LOC: 70. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Column.validate_values (Complexity 17): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #113: Unexplained complexity: Meta.apply_property_setters
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.85 | **Impact:** 0.102
**File:** frappe\model\meta.py (line 422)

> Complexity: 17, LOC: 41. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Meta.apply_property_setters (Complexity 17): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #114: Unexplained complexity: PrintFormat.validate
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.85 | **Impact:** 0.102
**File:** frappe\printing\doctype\print_format\print_format.py (line 74)

> Complexity: 17, LOC: 31. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion PrintFormat.validate (Complexity 17): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #115: Unexplained complexity: map_trackers
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.85 | **Impact:** 0.102
**File:** frappe\utils\data.py (line 2826)

> Complexity: 17, LOC: 34. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion map_trackers (Complexity 17): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #116: Unexplained complexity: CDPSocketClient._handle_message
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.85 | **Impact:** 0.102
**File:** frappe\utils\pdf_generator\cdp_connection.py (line 43)

> Complexity: 17, LOC: 33. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion CDPSocketClient._handle_message (Complexity 17): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #117: Unexplained complexity: get_list_context
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.85 | **Impact:** 0.102
**File:** frappe\www\list.py (line 108)

> Complexity: 17, LOC: 43. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_list_context (Complexity 17): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #118: Unexplained complexity: File.save_file
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.8 | **Impact:** 0.096
**File:** frappe\core\doctype\file\file.py (line 682)

> Complexity: 16, LOC: 70. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion File.save_file (Complexity 16): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #119: Unexplained complexity: SystemSettings.validate
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.8 | **Impact:** 0.096
**File:** frappe\core\doctype\system_settings\system_settings.py (line 112)

> Complexity: 16, LOC: 49. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion SystemSettings.validate (Complexity 16): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #120: Unexplained complexity: create_contact
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.8 | **Impact:** 0.096
**File:** frappe\core\doctype\user\user.py (line 1332)

> Complexity: 16, LOC: 65. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion create_contact (Complexity 16): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #121: Unexplained complexity: CustomField.validate
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.8 | **Impact:** 0.096
**File:** frappe\custom\doctype\custom_field\custom_field.py (line 164)

> Complexity: 16, LOC: 41. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion CustomField.validate (Complexity 16): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #122: Unexplained complexity: DesktopIcon.is_permitted
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.8 | **Impact:** 0.096
**File:** frappe\desk\doctype\desktop_icon\desktop_icon.py (line 87)

> Complexity: 16, LOC: 28. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion DesktopIcon.is_permitted (Complexity 16): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #123: Unexplained complexity: evaluate_alert
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.8 | **Impact:** 0.096
**File:** frappe\email\doctype\notification\notification.py (line 791)

> Complexity: 16, LOC: 46. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion evaluate_alert (Complexity 16): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #124: Unexplained complexity: BaseDocument.get_formatted
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.8 | **Impact:** 0.096
**File:** frappe\model\base_document.py (line 1460)

> Complexity: 16, LOC: 35. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion BaseDocument.get_formatted (Complexity 16): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #125: Unexplained complexity: get_messages_from_custom_fields
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.8 | **Impact:** 0.096
**File:** frappe\translate.py (line 430)

> Complexity: 16, LOC: 34. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_messages_from_custom_fields (Complexity 16): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #126: Unexplained complexity: WebForm.load_translations
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.8 | **Impact:** 0.096
**File:** frappe\website\doctype\web_form\web_form.py (line 278)

> Complexity: 16, LOC: 140. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion WebForm.load_translations (Complexity 16): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #127: Unexplained complexity: _get_site_config
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\config.py (line 33)

> Complexity: 32, LOC: 78. No docstring. No corresponding test found.

**Fix:** Funktion _get_site_config (Complexity 32): Füge Docstring, Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #128: Unexplained complexity: build_fields_dict_for_column_matching
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\core\doctype\data_import\importer.py (line 1117)

> Complexity: 20, LOC: 141. No corresponding test found. No return type annotation.

**Fix:** Funktion build_fields_dict_for_column_matching (Complexity 20): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #129: Unexplained complexity: validate_series
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\core\doctype\doctype\doctype.py (line 1115)

> Complexity: 23, LOC: 49. No corresponding test found. No return type annotation.

**Fix:** Funktion validate_series (Complexity 23): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #130: Unexplained complexity: validate_fields
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\core\doctype\doctype\doctype.py (line 1295)

> Complexity: 138, LOC: 495. No corresponding test found. No return type annotation.

**Fix:** Funktion validate_fields (Complexity 138): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #131: Unexplained complexity: has_permission
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\core\doctype\file\file.py (line 882)

> Complexity: 15, LOC: 38. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion has_permission (Complexity 15): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #132: Unexplained complexity: get_diff
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\core\doctype\version\version.py (line 102)

> Complexity: 40, LOC: 124. No corresponding test found. No return type annotation.

**Fix:** Funktion get_diff (Complexity 40): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #133: Unexplained complexity: Database.sql
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\database\database.py (line 183)

> Complexity: 40, LOC: 167. No corresponding test found. No return type annotation.

**Fix:** Funktion Database.sql (Complexity 40): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #134: Unexplained complexity: Database.get_values
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\database\database.py (line 594)

> Complexity: 24, LOC: 116. No corresponding test found. No return type annotation.

**Fix:** Funktion Database.get_values (Complexity 24): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #135: Unexplained complexity: create_sidebar_items
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\desk\doctype\workspace_sidebar\workspace_sidebar.py (line 348)

> Complexity: 15, LOC: 52. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion create_sidebar_items (Complexity 15): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #136: Unexplained complexity: get_linked_docs
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\desk\form\linked_with.py (line 427)

> Complexity: 28, LOC: 111. No docstring. No corresponding test found.

**Fix:** Funktion get_linked_docs (Complexity 28): Füge Docstring, Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #137: Unexplained complexity: update_user_info
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\desk\form\load.py (line 482)

> Complexity: 15, LOC: 21. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion update_user_info (Complexity 15): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #138: Unexplained complexity: add_total_row
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\desk\query_report.py (line 608)

> Complexity: 33, LOC: 95. No docstring. No corresponding test found.

**Fix:** Funktion add_total_row (Complexity 33): Füge Docstring, Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #139: Unexplained complexity: has_match
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\desk\query_report.py (line 832)

> Complexity: 23, LOC: 74. No corresponding test found. No return type annotation.

**Fix:** Funktion has_match (Complexity 23): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #140: Unexplained complexity: get_linked_doctypes
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\desk\query_report.py (line 934)

> Complexity: 15, LOC: 35. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_linked_doctypes (Complexity 15): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #141: Unexplained complexity: make_links
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\email\doctype\auto_email_report\auto_email_report.py (line 366)

> Complexity: 15, LOC: 22. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion make_links (Complexity 15): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #142: Unexplained complexity: EmailAccount.validate
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\email\doctype\email_account\email_account.py (line 143)

> Complexity: 41, LOC: 77. No corresponding test found. No return type annotation.

**Fix:** Funktion EmailAccount.validate (Complexity 41): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #143: Unexplained complexity: FrappeClient.migrate_doctype
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\frappeclient.py (line 260)

> Complexity: 22, LOC: 69. No corresponding test found. No return type annotation.

**Fix:** Funktion FrappeClient.migrate_doctype (Complexity 22): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #144: Unexplained complexity: extract_javascript
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\gettext\extractors\javascript.py (line 25)

> Complexity: 50, LOC: 145. No corresponding test found. No return type annotation.

**Fix:** Funktion extract_javascript (Complexity 50): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #145: Unexplained complexity: extract
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\gettext\extractors\web_form.py (line 4)

> Complexity: 24, LOC: 70. No corresponding test found. No return type annotation.

**Fix:** Funktion extract (Complexity 24): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #146: Unexplained complexity: remove_app
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\installer.py (line 379)

> Complexity: 21, LOC: 68. No corresponding test found. No return type annotation.

**Fix:** Funktion remove_app (Complexity 21): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #147: Unexplained complexity: BaseDocument.get_valid_dict
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\model\base_document.py (line 544)

> Complexity: 32, LOC: 66. No docstring. No corresponding test found.

**Fix:** Funktion BaseDocument.get_valid_dict (Complexity 32): Füge Docstring, Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #148: Unexplained complexity: BaseDocument.get_invalid_links
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\model\base_document.py (line 1008)

> Complexity: 38, LOC: 118. No corresponding test found. No return type annotation.

**Fix:** Funktion BaseDocument.get_invalid_links (Complexity 38): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #149: Unexplained complexity: DatabaseQuery.execute
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\model\db_query.py (line 106)

> Complexity: 38, LOC: 141. No docstring. No corresponding test found.

**Fix:** Funktion DatabaseQuery.execute (Complexity 38): Füge Docstring, Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #150: Unexplained complexity: DatabaseQuery.sanitize_fields
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\model\db_query.py (line 440)

> Complexity: 30, LOC: 109. No corresponding test found. No return type annotation.

**Fix:** Funktion DatabaseQuery.sanitize_fields (Complexity 30): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #151: Unexplained complexity: DatabaseQuery.apply_fieldlevel_read_permissions
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\model\db_query.py (line 693)

> Complexity: 23, LOC: 99. No corresponding test found. No return type annotation.

**Fix:** Funktion DatabaseQuery.apply_fieldlevel_read_permissions (Complexity 23): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #152: Unexplained complexity: DatabaseQuery.add_user_permissions
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\model\db_query.py (line 1103)

> Complexity: 15, LOC: 58. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion DatabaseQuery.add_user_permissions (Complexity 15): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #153: Unexplained complexity: check_if_doc_is_linked
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\model\delete_doc.py (line 300)

> Complexity: 21, LOC: 56. No corresponding test found. No return type annotation.

**Fix:** Funktion check_if_doc_is_linked (Complexity 21): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #154: Unexplained complexity: check_if_doc_is_dynamically_linked
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\model\delete_doc.py (line 358)

> Complexity: 21, LOC: 52. No corresponding test found. No return type annotation.

**Fix:** Funktion check_if_doc_is_dynamically_linked (Complexity 21): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #155: Unexplained complexity: Meta.sort_fields
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\model\meta.py (line 543)

> Complexity: 21, LOC: 73. No corresponding test found. No return type annotation.

**Fix:** Funktion Meta.sort_fields (Complexity 21): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #156: Unexplained complexity: Meta.add_doctype_links
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\model\meta.py (line 764)

> Complexity: 21, LOC: 56. No corresponding test found. No return type annotation.

**Fix:** Funktion Meta.add_doctype_links (Complexity 21): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #157: Unexplained complexity: validate_rename
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\model\rename_doc.py (line 345)

> Complexity: 21, LOC: 58. No docstring. No corresponding test found.

**Fix:** Funktion validate_rename (Complexity 21): Füge Docstring, Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #158: Unexplained complexity: has_user_permission
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\permissions.py (line 351)

> Complexity: 38, LOC: 128. No corresponding test found. No return type annotation.

**Fix:** Funktion has_user_permission (Complexity 38): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #159: Unexplained complexity: SQLiteSearch.build_index
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\search\sqlite_search.py (line 295)

> Complexity: 30, LOC: 164. No corresponding test found. No return type annotation.

**Fix:** Funktion SQLiteSearch.build_index (Complexity 30): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #160: Unexplained complexity: SQLiteSearch._execute_search_query
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\search\sqlite_search.py (line 793)

> Complexity: 23, LOC: 115. No corresponding test found. No return type annotation.

**Fix:** Funktion SQLiteSearch._execute_search_query (Complexity 23): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #161: Unexplained complexity: SQLiteSearch.index_chunks
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\search\sqlite_search.py (line 1326)

> Complexity: 15, LOC: 48. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion SQLiteSearch.index_chunks (Complexity 15): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #162: Unexplained complexity: format_value
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\utils\formatters.py (line 26)

> Complexity: 37, LOC: 119. No corresponding test found. No return type annotation.

**Fix:** Funktion format_value (Complexity 37): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #163: Unexplained complexity: rebuild_for_doctype
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\utils\global_search.py (line 66)

> Complexity: 22, LOC: 87. No corresponding test found. No return type annotation.

**Fix:** Funktion rebuild_for_doctype (Complexity 22): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #164: Unexplained complexity: calculate_platform
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\utils\print_utils.py (line 386)

> Complexity: 21, LOC: 52. No corresponding test found. No return type annotation.

**Fix:** Funktion calculate_platform (Complexity 21): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #165: Unexplained complexity: transform_parameter_types
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\utils\typing_validations.py (line 104)

> Complexity: 29, LOC: 94. No corresponding test found. No return type annotation.

**Fix:** Funktion transform_parameter_types (Complexity 29): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #166: Unexplained complexity: UserPermissions.build_permissions
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\utils\user.py (line 111)

> Complexity: 33, LOC: 90. No corresponding test found. No return type annotation.

**Fix:** Funktion UserPermissions.build_permissions (Complexity 33): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #167: Unexplained complexity: get_link_options
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\website\doctype\web_form\web_form.py (line 857)

> Complexity: 15, LOC: 39. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_link_options (Complexity 15): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #168: Unexplained complexity: get_home_page
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\website\utils.py (line 97)

> Complexity: 15, LOC: 42. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_home_page (Complexity 15): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #169: Unexplained complexity: get_rendered_template
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.75 | **Impact:** 0.09
**File:** frappe\www\printview.py (line 140)

> Complexity: 31, LOC: 135. No docstring. No corresponding test found.

**Fix:** Funktion get_rendered_template (Complexity 31): Füge Docstring, Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #170: Unexplained complexity: DBTable.validate
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.712 | **Impact:** 0.085
**File:** frappe\database\schema.py (line 112)

> Complexity: 19, LOC: 57. No corresponding test found. No return type annotation.

**Fix:** Funktion DBTable.validate (Complexity 19): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #171: Unexplained complexity: get_field_currency
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.712 | **Impact:** 0.085
**File:** frappe\model\meta.py (line 863)

> Complexity: 19, LOC: 50. No corresponding test found. No return type annotation.

**Fix:** Funktion get_field_currency (Complexity 19): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #172: Unexplained complexity: sync_customizations_for_doctype
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.712 | **Impact:** 0.085
**File:** frappe\modules\utils.py (line 147)

> Complexity: 19, LOC: 93. No corresponding test found. No return type annotation.

**Fix:** Funktion sync_customizations_for_doctype (Complexity 19): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #173: Unexplained complexity: get_role_permissions
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.712 | **Impact:** 0.085
**File:** frappe\permissions.py (line 282)

> Complexity: 19, LOC: 61. No corresponding test found. No return type annotation.

**Fix:** Funktion get_role_permissions (Complexity 19): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #174: Unexplained complexity: publish_realtime
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.712 | **Impact:** 0.085
**File:** frappe\realtime.py (line 23)

> Complexity: 19, LOC: 61. No corresponding test found. No return type annotation.

**Fix:** Funktion publish_realtime (Complexity 19): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #175: Unexplained complexity: validate_link_and_fetch
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.7 | **Impact:** 0.084
**File:** frappe\client.py (line 427)

> Complexity: 16, LOC: 99. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion validate_link_and_fetch (Complexity 16): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #176: Unexplained complexity: NumberCard.validate
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.7 | **Impact:** 0.084
**File:** frappe\desk\doctype\number_card\number_card.py (line 60)

> Complexity: 14, LOC: 18. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion NumberCard.validate (Complexity 14): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #177: Unexplained complexity: WorkspaceSidebar.is_item_allowed
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.7 | **Impact:** 0.084
**File:** frappe\desk\doctype\workspace_sidebar\workspace_sidebar.py (line 81)

> Complexity: 14, LOC: 24. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion WorkspaceSidebar.is_item_allowed (Complexity 14): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #178: Unexplained complexity: validate_ignore_user_permissions
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.7 | **Impact:** 0.084
**File:** frappe\desk\search.py (line 254)

> Complexity: 14, LOC: 65. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion validate_ignore_user_permissions (Complexity 14): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #179: Unexplained complexity: SocialLoginKey.validate
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.7 | **Impact:** 0.084
**File:** frappe\integrations\doctype\social_login_key\social_login_key.py (line 76)

> Complexity: 14, LOC: 27. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion SocialLoginKey.validate (Complexity 14): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #180: Unexplained complexity: DBQueryProgressMonitor.run
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.7 | **Impact:** 0.084
**File:** frappe\migrate.py (line 292)

> Complexity: 14, LOC: 44. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion DBQueryProgressMonitor.run (Complexity 14): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #181: Unexplained complexity: BaseDocument._validate_data_fields
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.7 | **Impact:** 0.084
**File:** frappe\model\base_document.py (line 1180)

> Complexity: 14, LOC: 45. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion BaseDocument._validate_data_fields (Complexity 14): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #182: Unexplained complexity: BaseDocument._validate_length
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.7 | **Impact:** 0.084
**File:** frappe\model\base_document.py (line 1250)

> Complexity: 14, LOC: 34. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion BaseDocument._validate_length (Complexity 14): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #183: Unexplained complexity: _serialize
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.7 | **Impact:** 0.084
**File:** frappe\model\meta.py (line 1033)

> Complexity: 14, LOC: 23. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion _serialize (Complexity 14): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #184: Unexplained complexity: get_messages_from_workflow
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.7 | **Impact:** 0.084
**File:** frappe\translate.py (line 359)

> Complexity: 14, LOC: 69. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_messages_from_workflow (Complexity 14): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #185: Unexplained complexity: attach_print
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.7 | **Impact:** 0.084
**File:** frappe\utils\print_utils.py (line 106)

> Complexity: 14, LOC: 67. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion attach_print (Complexity 14): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #186: Unexplained complexity: get_keys_for_autocomplete
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.7 | **Impact:** 0.084
**File:** frappe\utils\safe_exec.py (line 325)

> Complexity: 14, LOC: 44. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_keys_for_autocomplete (Complexity 14): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #187: Unexplained complexity: _build
**Signal:** explainability_deficit | **Severity:** high | **Score:** 0.7 | **Impact:** 0.084
**File:** frappe\website\utils.py (line 274)

> Complexity: 14, LOC: 40. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion _build (Complexity 14): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #188: Unexplained complexity: EmailQueue.send
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.675 | **Impact:** 0.081
**File:** frappe\email\doctype\email_queue\email_queue.py (line 169)

> Complexity: 18, LOC: 88. No corresponding test found. No return type annotation.

**Fix:** Funktion EmailQueue.send (Complexity 18): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #189: Unexplained complexity: sync_events_from_google_calendar
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.675 | **Impact:** 0.081
**File:** frappe\integrations\doctype\google_calendar\google_calendar.py (line 274)

> Complexity: 18, LOC: 104. No corresponding test found. No return type annotation.

**Fix:** Funktion sync_events_from_google_calendar (Complexity 18): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #190: Unexplained complexity: BaseDocument.db_insert
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.675 | **Impact:** 0.081
**File:** frappe\model\base_document.py (line 751)

> Complexity: 18, LOC: 75. No corresponding test found. No return type annotation.

**Fix:** Funktion BaseDocument.db_insert (Complexity 18): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #191: Unexplained complexity: BaseDocument._sanitize_content
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.675 | **Impact:** 0.081
**File:** frappe\model\base_document.py (line 1356)

> Complexity: 18, LOC: 41. No corresponding test found. No return type annotation.

**Fix:** Funktion BaseDocument._sanitize_content (Complexity 18): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #192: Unexplained complexity: BaseDocument.reset_values_if_no_permlevel_access
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.675 | **Impact:** 0.081
**File:** frappe\model\base_document.py (line 1536)

> Complexity: 18, LOC: 45. No corresponding test found. No return type annotation.

**Fix:** Funktion BaseDocument.reset_values_if_no_permlevel_access (Complexity 18): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #193: Unexplained complexity: set_new_name
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.675 | **Impact:** 0.081
**File:** frappe\model\naming.py (line 141)

> Complexity: 18, LOC: 58. No corresponding test found. No return type annotation.

**Fix:** Funktion set_new_name (Complexity 18): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #194: Unexplained complexity: resolve_redirect
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.675 | **Impact:** 0.081
**File:** frappe\website\path_resolver.py (line 99)

> Complexity: 18, LOC: 82. No corresponding test found. No return type annotation.

**Fix:** Funktion resolve_redirect (Complexity 18): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #195: Unexplained complexity: setup_source
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.675 | **Impact:** 0.081
**File:** frappe\website\router.py (line 185)

> Complexity: 18, LOC: 61. No corresponding test found. No return type annotation.

**Fix:** Funktion setup_source (Complexity 18): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #196: Unexplained complexity: get_preview_data
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.656 | **Impact:** 0.079
**File:** frappe\desk\link_preview.py (line 9)

> Complexity: 15, LOC: 52. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_preview_data (Complexity 15): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #197: Unexplained complexity: get_sidebar_items
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\boot.py (line 544)

> Complexity: 13, LOC: 66. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_sidebar_items (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #198: Unexplained complexity: _restore
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\commands\site.py (line 220)

> Complexity: 13, LOC: 105. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion _restore (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #199: Unexplained complexity: Contact.get_vcard
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\contacts\doctype\contact\contact.py (line 176)

> Complexity: 13, LOC: 48. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Contact.get_vcard (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #200: Unexplained complexity: Communication.set_sender_full_name
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\core\doctype\communication\communication.py (line 338)

> Complexity: 13, LOC: 29. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Communication.set_sender_full_name (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #201: Unexplained complexity: DataExporter.append_field_column
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\core\doctype\data_export\exporter.py (line 290)

> Complexity: 13, LOC: 25. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion DataExporter.append_field_column (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #202: Unexplained complexity: export_json
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\core\doctype\data_import\data_import.py (line 343)

> Complexity: 13, LOC: 51. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion export_json (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #203: Unexplained complexity: Row.validate_value
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\core\doctype\data_import\importer.py (line 711)

> Complexity: 13, LOC: 72. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Row.validate_value (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #204: Unexplained complexity: InstalledApplications.update_versions
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\core\doctype\installed_applications\installed_applications.py (line 29)

> Complexity: 13, LOC: 42. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion InstalledApplications.update_versions (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #205: Unexplained complexity: User.on_update
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\core\doctype\user\user.py (line 309)

> Complexity: 13, LOC: 44. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion User.on_update (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #206: Unexplained complexity: create_desktop_icons_from_workspace
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\desk\doctype\desktop_icon\desktop_icon.py (line 233)

> Complexity: 13, LOC: 44. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion create_desktop_icons_from_workspace (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #207: Unexplained complexity: get_prepared_report_result
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\desk\query_report.py (line 295)

> Complexity: 13, LOC: 35. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_prepared_report_result (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #208: Unexplained complexity: validate_fields
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\desk\reportview.py (line 124)

> Complexity: 13, LOC: 31. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion validate_fields (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #209: Unexplained complexity: parse_json
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\desk\reportview.py (line 255)

> Complexity: 13, LOC: 19. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion parse_json (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #210: Unexplained complexity: FrappeClient.post_process
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\frappeclient.py (line 376)

> Complexity: 13, LOC: 28. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion FrappeClient.post_process (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #211: Unexplained complexity: _bulk_workflow_action
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\model\workflow.py (line 334)

> Complexity: 13, LOC: 51. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion _bulk_workflow_action (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #212: Unexplained complexity: ratelimit_decorator
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\rate_limiter.py (line 129)

> Complexity: 13, LOC: 44. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion ratelimit_decorator (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #213: Unexplained complexity: check_for_update
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\utils\change_log.py (line 167)

> Complexity: 13, LOC: 48. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion check_for_update (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #214: Unexplained complexity: PersonalDataDeletionRequest._anonymize_data
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\website\doctype\personal_data_deletion_request\personal_data_deletion_request.py (line 260)

> Complexity: 13, LOC: 38. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion PersonalDataDeletionRequest._anonymize_data (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #215: Unexplained complexity: prepare_filters
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.65 | **Impact:** 0.078
**File:** frappe\www\list.py (line 76)

> Complexity: 13, LOC: 30. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion prepare_filters (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #216: Unexplained complexity: insert_perm_log
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.637 | **Impact:** 0.076
**File:** frappe\core\doctype\permission_log\permission_log.py (line 50)

> Complexity: 17, LOC: 48. No corresponding test found. No return type annotation.

**Fix:** Funktion insert_perm_log (Complexity 17): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #217: Unexplained complexity: sync_contacts_from_google_contacts
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.637 | **Impact:** 0.076
**File:** frappe\integrations\doctype\google_contacts\google_contacts.py (line 103)

> Complexity: 17, LOC: 94. No corresponding test found. No return type annotation.

**Fix:** Funktion sync_contacts_from_google_contacts (Complexity 17): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #218: Unexplained complexity: SQLiteSearch._index_documents
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.637 | **Impact:** 0.076
**File:** frappe\search\sqlite_search.py (line 1304)

> Complexity: 17, LOC: 72. No corresponding test found. No return type annotation.

**Fix:** Funktion SQLiteSearch._index_documents (Complexity 17): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #219: Unexplained complexity: update_global_search
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.637 | **Impact:** 0.076
**File:** frappe\utils\global_search.py (line 242)

> Complexity: 17, LOC: 45. No corresponding test found. No return type annotation.

**Fix:** Funktion update_global_search (Complexity 17): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #220: Unexplained complexity: WebForm.load_form_data
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.637 | **Impact:** 0.076
**File:** frappe\website\doctype\web_form\web_form.py (line 424)

> Complexity: 17, LOC: 65. No corresponding test found. No return type annotation.

**Fix:** Funktion WebForm.load_form_data (Complexity 17): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #221: Unexplained complexity: trim_database
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.625 | **Impact:** 0.075
**File:** frappe\commands\site.py (line 1389)

> Complexity: 20, LOC: 73. No corresponding test found. No return type annotation.

**Fix:** Funktion trim_database (Complexity 20): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #222: Unexplained complexity: get_workspace_sidebar_items
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.625 | **Impact:** 0.075
**File:** frappe\desk\desktop.py (line 381)

> Complexity: 21, LOC: 88. No corresponding test found. No return type annotation.

**Fix:** Funktion get_workspace_sidebar_items (Complexity 21): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #223: Unexplained complexity: apply_workflow
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.625 | **Impact:** 0.075
**File:** frappe\model\workflow.py (line 120)

> Complexity: 26, LOC: 108. No corresponding test found. No return type annotation.

**Fix:** Funktion apply_workflow (Complexity 26): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #224: Unexplained complexity: accept
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.625 | **Impact:** 0.075
**File:** frappe\website\doctype\web_form\web_form.py (line 625)

> Complexity: 30, LOC: 103. No corresponding test found. No return type annotation.

**Fix:** Funktion accept (Complexity 30): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #225: Unexplained complexity: get_context
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.625 | **Impact:** 0.075
**File:** frappe\www\login.py (line 25)

> Complexity: 24, LOC: 97. No docstring. No return type annotation.

**Fix:** Funktion get_context (Complexity 24): Füge Docstring, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #226: Unexplained complexity: get
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.612 | **Impact:** 0.073
**File:** frappe\desk\doctype\dashboard_chart\dashboard_chart.py (line 92)

> Complexity: 14, LOC: 48. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get (Complexity 14): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #227: Unexplained complexity: Column.parse
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\core\doctype\data_import\importer.py (line 917)

> Complexity: 12, LOC: 68. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Column.parse (Complexity 12): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #228: Unexplained complexity: make_module_and_roles
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\core\doctype\doctype\doctype.py (line 1994)

> Complexity: 16, LOC: 38. No corresponding test found. No return type annotation.

**Fix:** Funktion make_module_and_roles (Complexity 16): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #229: Unexplained complexity: Database.get_values_from_single
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\database\database.py (line 711)

> Complexity: 16, LOC: 69. No corresponding test found. No return type annotation.

**Fix:** Funktion Database.get_values_from_single (Complexity 16): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #230: Unexplained complexity: get_tests_CompatFrappeTestCase
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\deprecation_dumpster.py (line 558)

> Complexity: 16, LOC: 280. No corresponding test found. No return type annotation.

**Fix:** Funktion get_tests_CompatFrappeTestCase (Complexity 16): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #231: Unexplained complexity: Workspace.is_item_allowed
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\desk\desktop.py (line 134)

> Complexity: 12, LOC: 20. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Workspace.is_item_allowed (Complexity 12): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #232: Unexplained complexity: update_global_search_doctypes
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\desk\doctype\global_search_settings\global_search_settings.py (line 59)

> Complexity: 12, LOC: 37. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion update_global_search_doctypes (Complexity 12): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #233: Unexplained complexity: Notification.validate
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\email\doctype\notification\notification.py (line 148)

> Complexity: 12, LOC: 30. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Notification.validate (Complexity 12): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #234: Unexplained complexity: Notification.get_list_of_recipients
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\email\doctype\notification\notification.py (line 569)

> Complexity: 12, LOC: 38. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Notification.get_list_of_recipients (Complexity 12): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #235: Unexplained complexity: create_new_oauth_client
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\integrations\utils.py (line 225)

> Complexity: 12, LOC: 34. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion create_new_oauth_client (Complexity 12): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #236: Unexplained complexity: BaseDocument._get_missing_mandatory_fields
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\model\base_document.py (line 962)

> Complexity: 16, LOC: 45. No corresponding test found. No return type annotation.

**Fix:** Funktion BaseDocument._get_missing_mandatory_fields (Complexity 16): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #237: Unexplained complexity: BaseDocument._validate_selects
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\model\base_document.py (line 1150)

> Complexity: 12, LOC: 29. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion BaseDocument._validate_selects (Complexity 12): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #238: Unexplained complexity: set_dynamic_default_values
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\model\create_new.py (line 135)

> Complexity: 12, LOC: 23. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion set_dynamic_default_values (Complexity 12): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #239: Unexplained complexity: sync
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\modules\utils.py (line 154)

> Complexity: 12, LOC: 62. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion sync (Complexity 12): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #240: Unexplained complexity: read_csv_content
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\utils\csvutils.py (line 42)

> Complexity: 12, LOC: 63. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion read_csv_content (Complexity 12): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #241: Unexplained complexity: check_record
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\utils\csvutils.py (line 146)

> Complexity: 16, LOC: 27. No corresponding test found. No return type annotation.

**Fix:** Funktion check_record (Complexity 16): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #242: Unexplained complexity: money_in_words
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\utils\data.py (line 1504)

> Complexity: 16, LOC: 68. No corresponding test found. No return type annotation.

**Fix:** Funktion money_in_words (Complexity 16): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #243: Unexplained complexity: _download_multi_pdf
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\utils\print_format.py (line 82)

> Complexity: 16, LOC: 143. No corresponding test found. No return type annotation.

**Fix:** Funktion _download_multi_pdf (Complexity 16): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #244: Unexplained complexity: download_chromium
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\utils\print_utils.py (line 220)

> Complexity: 12, LOC: 79. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion download_chromium (Complexity 12): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #245: Unexplained complexity: _get_home_page
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\website\utils.py (line 101)

> Complexity: 12, LOC: 32. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion _get_home_page (Complexity 12): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #246: Unexplained complexity: Workflow.validate_docstatus
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.6 | **Impact:** 0.072
**File:** frappe\workflow\doctype\workflow\workflow.py (line 85)

> Complexity: 12, LOC: 41. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Workflow.validate_docstatus (Complexity 12): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #247: Unexplained complexity: create_email_flag_queue
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.594 | **Impact:** 0.071
**File:** frappe\email\inbox.py (line 41)

> Complexity: 19, LOC: 59. No corresponding test found. No return type annotation.

**Fix:** Funktion create_email_flag_queue (Complexity 19): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #248: Unexplained complexity: update_page
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.569 | **Impact:** 0.068
**File:** frappe\desk\doctype\workspace\workspace.py (line 366)

> Complexity: 13, LOC: 43. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion update_page (Complexity 13): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #249: Unexplained complexity: DocType.validate_field_name_conflicts
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.562 | **Impact:** 0.067
**File:** frappe\core\doctype\doctype\doctype.py (line 233)

> Complexity: 15, LOC: 44. No corresponding test found. No return type annotation.

**Fix:** Funktion DocType.validate_field_name_conflicts (Complexity 15): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #250: Unexplained complexity: format_fields
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.562 | **Impact:** 0.067
**File:** frappe\desk\query_report.py (line 467)

> Complexity: 15, LOC: 26. No docstring. No corresponding test found.

**Fix:** Funktion format_fields (Complexity 15): Füge Docstring, Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #251: Unexplained complexity: EmailServer.retrieve_message
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.562 | **Impact:** 0.067
**File:** frappe\email\receive.py (line 273)

> Complexity: 15, LOC: 42. No docstring. No corresponding test found.

**Fix:** Funktion EmailServer.retrieve_message (Complexity 15): Füge Docstring, Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #252: Unexplained complexity: extract
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.562 | **Impact:** 0.067
**File:** frappe\gettext\extractors\customization.py (line 6)

> Complexity: 15, LOC: 59. No corresponding test found. No return type annotation.

**Fix:** Funktion extract (Complexity 15): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #253: Unexplained complexity: run_doc_method
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.562 | **Impact:** 0.067
**File:** frappe\handler.py (line 277)

> Complexity: 15, LOC: 58. No corresponding test found. No return type annotation.

**Fix:** Funktion run_doc_method (Complexity 15): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #254: Unexplained complexity: has_child_permission
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.562 | **Impact:** 0.067
**File:** frappe\permissions.py (line 804)

> Complexity: 15, LOC: 89. No docstring. No corresponding test found.

**Fix:** Funktion has_child_permission (Complexity 15): Füge Docstring, Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #255: Unexplained complexity: SQLiteSearch._build_vocabulary_incremental
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.562 | **Impact:** 0.067
**File:** frappe\search\sqlite_search.py (line 487)

> Complexity: 15, LOC: 81. No corresponding test found. No return type annotation.

**Fix:** Funktion SQLiteSearch._build_vocabulary_incremental (Complexity 15): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #256: Unexplained complexity: execute_job
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.562 | **Impact:** 0.067
**File:** frappe\utils\background_jobs.py (line 239)

> Complexity: 15, LOC: 79. No corresponding test found. No return type annotation.

**Fix:** Funktion execute_job (Complexity 15): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #257: Unexplained complexity: get_full_index
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.562 | **Impact:** 0.067
**File:** frappe\website\utils.py (line 268)

> Complexity: 15, LOC: 52. No corresponding test found. No return type annotation.

**Fix:** Funktion get_full_index (Complexity 15): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #258: Unexplained complexity: init_request
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\app.py (line 171)

> Complexity: 11, LOC: 33. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion init_request (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #259: Unexplained complexity: process_response
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\app.py (line 244)

> Complexity: 11, LOC: 31. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion process_response (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #260: Unexplained complexity: set_cors_headers
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\app.py (line 277)

> Complexity: 11, LOC: 35. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion set_cors_headers (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #261: Unexplained complexity: AutoRepeat.create_documents
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\automation\doctype\auto_repeat\auto_repeat.py (line 228)

> Complexity: 11, LOC: 21. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion AutoRepeat.create_documents (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #262: Unexplained complexity: DataExporter.build_response
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\core\doctype\data_export\exporter.py (line 129)

> Complexity: 11, LOC: 44. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion DataExporter.build_response (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #263: Unexplained complexity: DataExporter.add_data_row
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\core\doctype\data_export\exporter.py (line 426)

> Complexity: 11, LOC: 27. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion DataExporter.add_data_row (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #264: Unexplained complexity: Row._parse_doc
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\core\doctype\data_import\importer.py (line 664)

> Complexity: 11, LOC: 46. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Row._parse_doc (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #265: Unexplained complexity: check_unique_and_text
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\core\doctype\doctype\doctype.py (line 1465)

> Complexity: 11, LOC: 35. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion check_unique_and_text (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #266: Unexplained complexity: check_level_zero_is_set
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\core\doctype\doctype\doctype.py (line 1857)

> Complexity: 11, LOC: 18. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion check_level_zero_is_set (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #267: Unexplained complexity: check_permission_dependency
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\core\doctype\doctype\doctype.py (line 1876)

> Complexity: 11, LOC: 26. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion check_permission_dependency (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #268: Unexplained complexity: MariaDBTable.create
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\database\mariadb\schema.py (line 10)

> Complexity: 11, LOC: 61. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion MariaDBTable.create (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #269: Unexplained complexity: clean_up
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\desk\desktop.py (line 572)

> Complexity: 11, LOC: 21. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion clean_up (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #270: Unexplained complexity: _get_linked_document_counts
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\desk\notifications.py (line 266)

> Complexity: 11, LOC: 47. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion _get_linked_document_counts (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #271: Unexplained complexity: validate_filters_permissions
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\desk\query_report.py (line 1023)

> Complexity: 11, LOC: 30. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion validate_filters_permissions (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #272: Unexplained complexity: validate_filters
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\desk\reportview.py (line 157)

> Complexity: 11, LOC: 28. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion validate_filters (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #273: Unexplained complexity: get_filters_cond
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\desk\reportview.py (line 826)

> Complexity: 11, LOC: 45. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_filters_cond (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #274: Unexplained complexity: make_request
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\integrations\utils.py (line 48)

> Complexity: 11, LOC: 27. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion make_request (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #275: Unexplained complexity: validate_dynamic_client_metadata
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\integrations\utils.py (line 205)

> Complexity: 11, LOC: 18. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion validate_dynamic_client_metadata (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #276: Unexplained complexity: BaseDocument._validate_update_after_submit
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\model\base_document.py (line 1319)

> Complexity: 11, LOC: 36. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion BaseDocument._validate_update_after_submit (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #277: Unexplained complexity: get_static_default_value
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\model\create_new.py (line 99)

> Complexity: 11, LOC: 20. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_static_default_value (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #278: Unexplained complexity: remove_orphan_entities
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\model\sync.py (line 202)

> Complexity: 11, LOC: 60. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion remove_orphan_entities (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #279: Unexplained complexity: execute
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\patches\v12_0\move_email_and_phone_to_child_table.py (line 4)

> Complexity: 11, LOC: 102. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion execute (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #280: Unexplained complexity: check_user_permission_on_link_fields
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\permissions.py (line 416)

> Complexity: 11, LOC: 54. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion check_user_permission_on_link_fields (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #281: Unexplained complexity: execute_child_queries
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\query_builder\utils.py (line 143)

> Complexity: 11, LOC: 15. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion execute_child_queries (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #282: Unexplained complexity: get_pdf
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\utils\pdf.py (line 87)

> Complexity: 11, LOC: 46. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_pdf (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #283: Unexplained complexity: _make_logs_v1
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\utils\response.py (line 189)

> Complexity: 11, LOC: 20. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion _make_logs_v1 (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #284: Unexplained complexity: check_publish_status
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.55 | **Impact:** 0.066
**File:** frappe\website\doctype\web_page\web_page.py (line 218)

> Complexity: 11, LOC: 18. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion check_publish_status (Complexity 11): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #285: Unexplained complexity: run
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.531 | **Impact:** 0.064
**File:** frappe\desk\query_report.py (line 201)

> Complexity: 17, LOC: 59. No docstring. No corresponding test found.

**Fix:** Funktion run (Complexity 17): Füge Docstring, Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #286: Unexplained complexity: application
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.525 | **Impact:** 0.063
**File:** frappe\app.py (line 98)

> Complexity: 12, LOC: 63. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion application (Complexity 12): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #287: Unexplained complexity: create_custom_fields
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.525 | **Impact:** 0.063
**File:** frappe\custom\doctype\custom_field\custom_field.py (line 316)

> Complexity: 14, LOC: 67. No corresponding test found. No return type annotation.

**Fix:** Funktion create_custom_fields (Complexity 14): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #288: Unexplained complexity: AutoEmailReport.get_report_content
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.525 | **Impact:** 0.063
**File:** frappe\email\doctype\auto_email_report\auto_email_report.py (line 140)

> Complexity: 14, LOC: 69. No corresponding test found. No return type annotation.

**Fix:** Funktion AutoEmailReport.get_report_content (Complexity 14): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #289: Unexplained complexity: setup_user_email_inbox
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.525 | **Impact:** 0.063
**File:** frappe\email\doctype\email_account\email_account.py (line 1062)

> Complexity: 14, LOC: 53. No corresponding test found. No return type annotation.

**Fix:** Funktion setup_user_email_inbox (Complexity 14): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #290: Unexplained complexity: parse_template_string
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.525 | **Impact:** 0.063
**File:** frappe\gettext\extractors\javascript.py (line 172)

> Complexity: 14, LOC: 53. No corresponding test found. No return type annotation.

**Fix:** Funktion parse_template_string (Complexity 14): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #291: Unexplained complexity: run_webhooks
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.525 | **Impact:** 0.063
**File:** frappe\integrations\doctype\webhook\__init__.py (line 33)

> Complexity: 14, LOC: 39. No corresponding test found. No return type annotation.

**Fix:** Funktion run_webhooks (Complexity 14): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #292: Unexplained complexity: set_cors_for_privileged_requests
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.525 | **Impact:** 0.063
**File:** frappe\integrations\oauth2.py (line 499)

> Complexity: 14, LOC: 42. No corresponding test found. No return type annotation.

**Fix:** Funktion set_cors_for_privileged_requests (Complexity 14): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #293: Unexplained complexity: _filter
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.525 | **Impact:** 0.063
**File:** frappe\model\base_document.py (line 1599)

> Complexity: 14, LOC: 38. No corresponding test found. No return type annotation.

**Fix:** Funktion _filter (Complexity 14): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #294: Unexplained complexity: DatabaseQuery.extract_tables
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.525 | **Impact:** 0.063
**File:** frappe\model\db_query.py (line 550)

> Complexity: 14, LOC: 37. No corresponding test found. No return type annotation.

**Fix:** Funktion DatabaseQuery.extract_tables (Complexity 14): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #295: Unexplained complexity: get_doc_permissions
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.525 | **Impact:** 0.063
**File:** frappe\permissions.py (line 227)

> Complexity: 14, LOC: 53. No corresponding test found. No return type annotation.

**Fix:** Funktion get_doc_permissions (Complexity 14): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #296: Unexplained complexity: get_messages_from_doctype
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.525 | **Impact:** 0.063
**File:** frappe\translate.py (line 313)

> Complexity: 14, LOC: 44. No corresponding test found. No return type annotation.

**Fix:** Funktion get_messages_from_doctype (Complexity 14): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #297: Unexplained complexity: attach_expanded_links
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.525 | **Impact:** 0.063
**File:** frappe\utils\data.py (line 2862)

> Complexity: 14, LOC: 73. No corresponding test found. No return type annotation.

**Fix:** Funktion attach_expanded_links (Complexity 14): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #298: Unexplained complexity: PathResolver.resolve
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.525 | **Impact:** 0.063
**File:** frappe\website\path_resolver.py (line 27)

> Complexity: 14, LOC: 46. No corresponding test found. No return type annotation.

**Fix:** Funktion PathResolver.resolve (Complexity 14): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #299: Unexplained complexity: LoginManager.set_user_info
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\auth.py (line 192)

> Complexity: 10, LOC: 29. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion LoginManager.set_user_info (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #300: Unexplained complexity: Exporter.get_data_to_export
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\core\doctype\data_import\exporter.py (line 112)

> Complexity: 10, LOC: 28. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Exporter.get_data_to_export (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #301: Unexplained complexity: Row.parse_value
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\core\doctype\data_import\importer.py (line 787)

> Complexity: 10, LOC: 25. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Row.parse_value (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #302: Unexplained complexity: check_link_table_options
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\core\doctype\doctype\doctype.py (line 1360)

> Complexity: 10, LOC: 33. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion check_link_table_options (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #303: Unexplained complexity: check_email_append_to
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\core\doctype\doctype\doctype.py (line 2050)

> Complexity: 10, LOC: 29. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion check_email_append_to (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #304: Unexplained complexity: File.handle_is_private_changed
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\core\doctype\file\file.py (line 246)

> Complexity: 10, LOC: 66. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion File.handle_is_private_changed (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #305: Unexplained complexity: Page.load_assets
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\core\doctype\page\page.py (line 142)

> Complexity: 10, LOC: 55. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Page.load_assets (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #306: Unexplained complexity: CustomizeForm.update_in_custom_field
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\custom\doctype\customize_form\customize_form.py (line 493)

> Complexity: 10, LOC: 30. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion CustomizeForm.update_in_custom_field (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #307: Unexplained complexity: get_data
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\custom\report\audit_system_hooks\audit_system_hooks.py (line 26)

> Complexity: 10, LOC: 37. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_data (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #308: Unexplained complexity: Database._return_as_iterator
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\database\database.py (line 351)

> Complexity: 10, LOC: 21. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Database._return_as_iterator (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #309: Unexplained complexity: get_root_connection
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\database\mariadb\setup_db.py (line 124)

> Complexity: 10, LOC: 29. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_root_connection (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #310: Unexplained complexity: get_root_connection
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\database\postgres\setup_db.py (line 61)

> Complexity: 10, LOC: 30. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_root_connection (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #311: Unexplained complexity: DbColumn.default_changed
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\database\schema.py (line 317)

> Complexity: 10, LOC: 28. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion DbColumn.default_changed (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #312: Unexplained complexity: DbColumn.default_changed_for_decimal
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\database\schema.py (line 346)

> Complexity: 10, LOC: 28. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion DbColumn.default_changed_for_decimal (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #313: Unexplained complexity: get_user_default
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\defaults.py (line 20)

> Complexity: 10, LOC: 20. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_user_default (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #314: Unexplained complexity: save_new_widget
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\desk\desktop.py (line 531)

> Complexity: 10, LOC: 39. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion save_new_widget (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #315: Unexplained complexity: get_permission_query_conditions
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\desk\doctype\dashboard_chart\dashboard_chart.py (line 26)

> Complexity: 10, LOC: 42. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_permission_query_conditions (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #316: Unexplained complexity: DashboardChart.check_required_field
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\desk\doctype\dashboard_chart\dashboard_chart.py (line 398)

> Complexity: 10, LOC: 19. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion DashboardChart.check_required_field (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #317: Unexplained complexity: Workspace.on_update
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\desk\doctype\workspace\workspace.py (line 130)

> Complexity: 10, LOC: 12. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Workspace.on_update (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #318: Unexplained complexity: Workspace.build_links_table_from_card
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\desk\doctype\workspace\workspace.py (line 233)

> Complexity: 10, LOC: 44. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion Workspace.build_links_table_from_card (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #319: Unexplained complexity: make_records
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\desk\page\setup_wizard\setup_wizard.py (line 511)

> Complexity: 10, LOC: 39. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion make_records (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #320: Unexplained complexity: build_xlsx_data
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\desk\query_report.py (line 495)

> Complexity: 24, LOC: 111. No corresponding test found.

**Fix:** Funktion build_xlsx_data (Complexity 24): Füge Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #321: Unexplained complexity: get_filtered_data
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\desk\query_report.py (line 785)

> Complexity: 10, LOC: 45. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_filtered_data (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #322: Unexplained complexity: make_site_config
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\installer.py (line 591)

> Complexity: 10, LOC: 37. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion make_site_config (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #323: Unexplained complexity: BaseDocument._validate_constants
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\model\base_document.py (line 1226)

> Complexity: 10, LOC: 23. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion BaseDocument._validate_constants (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #324: Unexplained complexity: DatabaseQuery.prepare_filter_condition
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\model\db_query.py (line 793)

> Complexity: 78, LOC: 236. No corresponding test found.

**Fix:** Funktion DatabaseQuery.prepare_filter_condition (Complexity 78): Füge Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #325: Unexplained complexity: delete_doc
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\model\delete_doc.py (line 23)

> Complexity: 38, LOC: 200. No corresponding test found.

**Fix:** Funktion delete_doc (Complexity 38): Füge Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #326: Unexplained complexity: parse_naming_series
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\model\naming.py (line 341)

> Complexity: 20, LOC: 62. No corresponding test found.

**Fix:** Funktion parse_naming_series (Complexity 20): Füge Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #327: Unexplained complexity: validate_name
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\model\naming.py (line 500)

> Complexity: 10, LOC: 28. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion validate_name (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #328: Unexplained complexity: DatabaseQuery.execute
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\model\qb_query.py (line 26)

> Complexity: 30, LOC: 202. No corresponding test found.

**Fix:** Funktion DatabaseQuery.execute (Complexity 30): Füge Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #329: Unexplained complexity: rename_doc
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\model\rename_doc.py (line 119)

> Complexity: 22, LOC: 125. No corresponding test found.

**Fix:** Funktion rename_doc (Complexity 22): Füge Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #330: Unexplained complexity: update_user_settings_data
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\model\utils\user_settings.py (line 77)

> Complexity: 10, LOC: 28. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion update_user_settings_data (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #331: Unexplained complexity: execute
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\patches\v12_0\delete_duplicate_indexes.py (line 7)

> Complexity: 10, LOC: 37. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion execute (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #332: Unexplained complexity: execute
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\patches\v12_0\move_timeline_links_to_dynamic_links.py (line 4)

> Complexity: 10, LOC: 61. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion execute (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #333: Unexplained complexity: update_sort_order_in_user_settings
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\patches\v16_0\switch_default_sort_order.py (line 36)

> Complexity: 10, LOC: 27. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion update_sort_order_in_user_settings (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #334: Unexplained complexity: update_doc_index
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\search\sqlite_search.py (line 1846)

> Complexity: 10, LOC: 24. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion update_doc_index (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #335: Unexplained complexity: process_queue
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\search\sqlite_search.py (line 1919)

> Complexity: 10, LOC: 33. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion process_queue (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #336: Unexplained complexity: execute_in_shell
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\utils\__init__.py (line 482)

> Complexity: 10, LOC: 44. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion execute_in_shell (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #337: Unexplained complexity: enqueue
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\utils\background_jobs.py (line 76)

> Complexity: 24, LOC: 134. No corresponding test found.

**Fix:** Funktion enqueue (Complexity 24): Füge Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #338: Unexplained complexity: BackupGenerator.setup_backup_directory
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\utils\backups.py (line 92)

> Complexity: 10, LOC: 26. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion BackupGenerator.setup_backup_directory (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #339: Unexplained complexity: get_change_log
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\utils\change_log.py (line 18)

> Complexity: 10, LOC: 40. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_change_log (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #340: Unexplained complexity: generate_and_cache_results
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\utils\dashboard.py (line 38)

> Complexity: 10, LOC: 34. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion generate_and_cache_results (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #341: Unexplained complexity: fmt_money
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\utils\data.py (line 1394)

> Complexity: 24, LOC: 85. No corresponding test found.

**Fix:** Funktion fmt_money (Complexity 24): Füge Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #342: Unexplained complexity: get_url
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\utils\data.py (line 1822)

> Complexity: 27, LOC: 61. No corresponding test found.

**Fix:** Funktion get_url (Complexity 27): Füge Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #343: Unexplained complexity: search
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\utils\global_search.py (line 480)

> Complexity: 16, LOC: 65. No corresponding test found. No return type annotation.

**Fix:** Funktion search (Complexity 16): Füge Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #344: Unexplained complexity: web_blocks
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\utils\jinja_globals.py (line 40)

> Complexity: 10, LOC: 50. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion web_blocks (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #345: Unexplained complexity: msgprint
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\utils\messages.py (line 11)

> Complexity: 34, LOC: 108. No corresponding test found.

**Fix:** Funktion msgprint (Complexity 34): Füge Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #346: Unexplained complexity: update_nsm
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\utils\nestedset.py (line 41)

> Complexity: 10, LOC: 24. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion update_nsm (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #347: Unexplained complexity: prepare_options
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\utils\pdf.py (line 178)

> Complexity: 10, LOC: 45. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion prepare_options (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #348: Unexplained complexity: WebForm.validate
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\website\doctype\web_form\web_form.py (line 78)

> Complexity: 10, LOC: 20. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion WebForm.validate (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #349: Unexplained complexity: has_link_option
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\website\doctype\web_form\web_form.py (line 839)

> Complexity: 10, LOC: 16. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion has_link_option (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #350: Unexplained complexity: get_home_page_via_hooks
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\website\utils.py (line 141)

> Complexity: 10, LOC: 26. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_home_page_via_hooks (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #351: Unexplained complexity: get_next_link
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\website\utils.py (line 244)

> Complexity: 10, LOC: 22. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_next_link (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #352: Unexplained complexity: get_portal_sidebar_items
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\website\utils.py (line 457)

> Complexity: 10, LOC: 27. No docstring. No corresponding test found. No return type annotation.

**Fix:** Funktion get_portal_sidebar_items (Complexity 10): Füge Docstring, Tests, Return-Type hinzu.

**Verdict:** TP / FP / ?
**Note:**

---

### #353: Unexplained complexity: make_layout
**Signal:** explainability_deficit | **Severity:** medium | **Score:** 0.5 | **Impact:** 0.06
**File:** frappe\www\printview.py (line 471)

> Complexity: 23, LOC: 90. No corresponding test found.

**Fix:** Funktion make_layout (Complexity 23): Füge Tests hinzu.

**Verdict:** TP / FP / ?
**Note:**

---
