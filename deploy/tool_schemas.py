"""
Google Ads Agent — Tool Schemas for Anthropic API
All 28 main agent tools defined in Claude tool_use JSON Schema format.

Usage:
    from deploy.tool_schemas import MAIN_AGENT_TOOLS, get_sub_agent_tools
    
    response = client.messages.create(
        model="claude-opus-4-5-20251101",
        tools=MAIN_AGENT_TOOLS,
        ...
    )
"""

# =============================================================================
# MAIN AGENT TOOLS (28 total)
# =============================================================================

MAIN_AGENT_TOOLS = [
    # ── 1. Label Manager ─────────────────────────────────────────────────
    {
        "name": "label_manager",
        "description": "Manage Google Ads labels — create, apply, remove, and list labeled entities across campaigns, ad groups, ads, and keywords.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list_labels", "create_label", "apply_label", "remove_label", "list_labeled_entities"]},
                "search": {"type": "string", "description": "Account name to auto-resolve customer_id"},
                "customer_id": {"type": "string", "description": "Google Ads customer ID (XXX-XXX-XXXX)"},
                "label_id": {"type": "string"},
                "name": {"type": "string", "description": "Label name"},
                "color": {"type": "string", "description": "Label color"},
                "description": {"type": "string"},
                "entity_type": {"type": "string", "enum": ["CAMPAIGN", "AD_GROUP", "AD", "KEYWORD"]},
                "entity_ids": {"type": "array", "items": {"type": "string"}},
                "name_contains": {"type": "string"},
                "campaign_ids": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "default": 100}
            },
            "required": ["action"]
        }
    },

    # ── 2. Conversion Tracking Manager ────────────────────────────────────
    {
        "name": "conversion_tracking_manager",
        "description": "Manage Google Ads conversion actions — list, create, update conversion tracking, and get attribution data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list_conversion_actions", "create_conversion_action", "update_conversion_action", "get_conversion_attribution"]},
                "search": {"type": "string"},
                "customer_id": {"type": "string"},
                "category": {"type": "string"},
                "status": {"type": "string"},
                "name_contains": {"type": "string"},
                "name": {"type": "string"},
                "counting_type": {"type": "string"},
                "default_value": {"type": "number"},
                "attribution_model": {"type": "string"},
                "lookback_window_days": {"type": "integer"},
                "conversion_action_id": {"type": "string"},
                "date_range": {"type": "string", "default": "LAST_30_DAYS"},
                "limit": {"type": "integer", "default": 100}
            },
            "required": ["action"]
        }
    },

    # ── 3. Audience Manager ───────────────────────────────────────────────
    {
        "name": "audience_manager",
        "description": "Manage Google Ads audiences — list, get performance, and add audiences to campaigns or ad groups.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "action": {"type": "string", "enum": ["list_audiences", "get_audience_performance", "add_audience_to_campaign", "add_audience_to_ad_group"]},
                "login_customer_id": {"type": "string"},
                "campaign_id": {"type": "string"},
                "ad_group_id": {"type": "string"},
                "audience_id": {"type": "string"},
                "user_list_id": {"type": "string"},
                "bid_modifier": {"type": "number"},
                "date_range": {"type": "string", "default": "LAST_30_DAYS"},
                "type_filter": {"type": "string", "enum": ["REMARKETING", "CRM_BASED", "RULE_BASED", "SIMILAR", "ALL"]},
                "sort_by": {"type": "string", "default": "size"},
                "limit": {"type": "integer", "default": 200}
            },
            "required": ["customer_id", "action"]
        }
    },

    # ── 4. Asset Manager ──────────────────────────────────────────────────
    {
        "name": "asset_manager",
        "description": "Manage Google Ads assets — list, create sitelinks/callouts/calls, and link assets to campaigns or ad groups.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "action": {"type": "string", "enum": ["list", "create_sitelink", "create_callout", "create_call", "link_to_campaign", "link_to_ad_group"]},
                "login_customer_id": {"type": "string"},
                "asset_data": {"type": "object"},
                "campaign_id": {"type": "string"},
                "ad_group_id": {"type": "string"},
                "asset_id": {"type": "string"},
                "asset_type": {"type": "string"},
                "limit": {"type": "integer", "default": 500}
            },
            "required": ["customer_id", "action"]
        }
    },

    # ── 5. Budget Manager ─────────────────────────────────────────────────
    {
        "name": "budget_manager",
        "description": "Manage Google Ads budgets — list, update, create budgets, and check pacing. All amounts in DOLLARS.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "action": {"type": "string", "enum": ["list_budgets", "update_budget", "create_budget", "get_pacing"]},
                "login_customer_id": {"type": "string"},
                "budget_id": {"type": "string"},
                "name": {"type": "string"},
                "delivery_method": {"type": "string", "default": "STANDARD"},
                "amount": {"type": "number", "description": "Budget in DOLLARS (100 = $100/day)"},
                "amount_min": {"type": "number"},
                "amount_max": {"type": "number"},
                "sort_by": {"type": "string", "default": "amount"},
                "limit": {"type": "integer", "default": 100}
            },
            "required": ["customer_id", "action"]
        }
    },

    # ── 6. RSA Ad Manager ─────────────────────────────────────────────────
    {
        "name": "rsa_ad_manager",
        "description": "Manage Responsive Search Ads — list, create, pause, enable RSAs with headlines and descriptions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "action": {"type": "string", "enum": ["list", "create", "pause", "enable"]},
                "login_customer_id": {"type": "string"},
                "ad_group_id": {"type": "string"},
                "campaign_id": {"type": "string"},
                "ad_data": {"type": "object", "description": "{headlines: [], descriptions: [], final_urls: [], path1, path2}"},
                "ad_id": {"type": "string"},
                "status_filter": {"type": "string"},
                "ad_strength_filter": {"type": "string", "enum": ["EXCELLENT", "GOOD", "AVERAGE", "POOR", "NEEDS_ATTENTION"]},
                "date_range": {"type": "string"},
                "limit": {"type": "integer", "default": 100},
                "include_metrics": {"type": "boolean", "default": False}
            },
            "required": ["customer_id", "action"]
        }
    },

    # ── 7. Bid & Keyword Manager ──────────────────────────────────────────
    {
        "name": "bid_keyword_manager",
        "description": "Manage keyword bids and keywords — get/update bids, add keywords, add from search terms. All bids in DOLLARS.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "action": {"type": "string", "enum": ["get_keyword_bids", "update_keyword_bid", "update_ad_group_bid", "get_bid_modifiers", "add_keywords", "add_keywords_from_search_terms"]},
                "login_customer_id": {"type": "string"},
                "ad_group_id": {"type": "string"},
                "campaign_id": {"type": "string"},
                "cpc_bid": {"type": "number", "description": "Bid in DOLLARS (2.50 = $2.50)"},
                "keywords": {"type": "array", "items": {"type": "object"}},
                "match_type": {"type": "string", "enum": ["EXACT", "PHRASE", "BROAD"]},
                "cost_min": {"type": "number"},
                "cost_max": {"type": "number"},
                "quality_score_min": {"type": "integer"},
                "quality_score_max": {"type": "integer"},
                "sort_by": {"type": "string", "default": "cost"},
                "limit": {"type": "integer", "default": 200},
                "date_range": {"type": "string"}
            },
            "required": ["customer_id", "action"]
        }
    },

    # ── 8. Negative Keywords Manager ──────────────────────────────────────
    {
        "name": "negative_keywords_manager",
        "description": "Manage negative keywords — list, add, remove campaign negatives and shared sets.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "action": {"type": "string", "enum": ["list_campaign_negatives", "list_shared_sets", "add_campaign_negative", "add_to_shared_set", "remove_negative", "create_shared_set"]},
                "login_customer_id": {"type": "string"},
                "campaign_id": {"type": "string"},
                "keyword_text": {"type": "string"},
                "match_type": {"type": "string", "default": "BROAD"},
                "shared_set_id": {"type": "string"},
                "resource_name": {"type": "string"},
                "level": {"type": "string", "default": "campaign"}
            },
            "required": ["customer_id", "action"]
        }
    },

    # ── 9. Campaign & Ad Group Manager ────────────────────────────────────
    {
        "name": "campaign_adgroup_manager",
        "description": "Manage campaigns and ad groups — list, find, get, update status, create ad groups. Supports name-based search.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "action": {"type": "string", "enum": ["list_campaigns", "find_campaign", "get_campaign", "update_status", "list_ad_groups", "update_ad_group_status", "create_ad_group", "update_ad_group_bid"], "default": "list_campaigns"},
                "login_customer_id": {"type": "string"},
                "campaign_id": {"type": "string"},
                "ad_group_id": {"type": "string"},
                "search": {"type": "string", "description": "Account name to auto-resolve"},
                "campaign_name": {"type": "string"},
                "status_filter": {"type": "string"},
                "campaign_type_filter": {"type": "string", "enum": ["SEARCH", "DISPLAY", "SHOPPING", "VIDEO", "PERFORMANCE_MAX"]},
                "date_range": {"type": "string"},
                "cost_min": {"type": "number"},
                "cost_max": {"type": "number"},
                "sort_by": {"type": "string", "default": "name"},
                "limit": {"type": "integer", "default": 100},
                "include_metrics": {"type": "boolean", "default": False}
            },
            "required": ["action"]
        }
    },

    # ── 10. Google Ads Mutate ─────────────────────────────────────────────
    {
        "name": "google_ads_mutate",
        "description": "Generic bulk create/update/remove operations. Use specific managers first; only use Mutate for bulk/atomic multi-entity ops.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "operations": {"type": "array", "items": {"type": "object"}, "description": "[{type, entity, data}]"},
                "login_customer_id": {"type": "string"}
            },
            "required": ["customer_id", "operations"]
        }
    },

    # ── 11. Account Access Checker ────────────────────────────────────────
    {
        "name": "account_access_checker",
        "description": "Check accessible Google Ads accounts, search by name, discover accounts, test connection, get MCC hierarchy.",
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["list_accessible", "discover", "find", "search", "get_hierarchy", "test_connection"], "default": "list_accessible"},
                "customer_id": {"type": "string"},
                "login_customer_id": {"type": "string"},
                "search": {"type": "string"}
            },
            "required": []
        }
    },

    # ── 12. Scripts Manager ───────────────────────────────────────────────
    {
        "name": "scripts_manager",
        "description": "Informational — Google Ads scripts guidance. Scripts are NOT accessible via API, only through the Google Ads UI.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "search": {"type": "string"},
                "customer_id": {"type": "string"},
                "name": {"type": "string"},
                "name_contains": {"type": "string"},
                "limit": {"type": "integer", "default": 100}
            },
            "required": ["action"]
        }
    },

    # ── 13. Experiments Manager ───────────────────────────────────────────
    {
        "name": "experiments_manager",
        "description": "Manage Google Ads experiments — list, create, get results, end, promote campaign experiments.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list_experiments", "create_experiment", "get_experiment_results", "end_experiment", "promote_experiment"]},
                "search": {"type": "string"},
                "customer_id": {"type": "string"},
                "experiment_id": {"type": "string"},
                "name": {"type": "string"},
                "base_campaign_id": {"type": "string"},
                "traffic_split": {"type": "integer", "default": 50},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "date_range": {"type": "string", "default": "LAST_30_DAYS"},
                "limit": {"type": "integer", "default": 100}
            },
            "required": ["action"]
        }
    },

    # ── 14. Package Installer ─────────────────────────────────────────────
    {
        "name": "package_installer",
        "description": "Install optional Python packages by category (math, testing, advertising, presentation, html_css, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "install_category": {"type": "string", "default": "all", "enum": ["math", "testing", "advertising", "presentation", "html_css", "color_design", "persistence", "financial", "all"]}
            },
            "required": []
        }
    },

    # ── 15. Check User Access ─────────────────────────────────────────────
    {
        "name": "check_user_access",
        "description": "Check user roles and access levels for a Google Ads account (ADMIN, STANDARD, READ_ONLY, EMAIL_ONLY).",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "login_customer_id": {"type": "string"}
            },
            "required": ["customer_id"]
        }
    },

    # ── 16. API Gateway ───────────────────────────────────────────────────
    {
        "name": "api_gateway",
        "description": "Route API calls with auto-offloading. Large responses (>10KB) are automatically saved to file with preview.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action_type": {"type": "string"},
                "action_params": {"type": "object"},
                "session_id": {"type": "string"},
                "max_preview_rows": {"type": "integer", "default": 5},
                "force_file": {"type": "boolean", "default": False},
                "ttl_hours": {"type": "integer", "default": 24}
            },
            "required": ["action_type", "action_params"]
        }
    },

    # ── 17. Session & State Manager ───────────────────────────────────────
    {
        "name": "session_state_manager",
        "description": "Manage sessions, query plan cache, sub-agent handoffs, and file search. Coordination bus for the agent system.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["init_session", "cache_query_plan", "prepare_handoff", "receive_handoff", "sync_sub_agent_state", "receive_sub_agent_result", "search_files", "register_file"]},
                "session_id": {"type": "string"},
                "session_name": {"type": "string"},
                "account_context": {"type": "object"},
                "target_agent": {"type": "string"},
                "task_description": {"type": "string"},
                "query_plan": {"type": "object"},
                "file_ids": {"type": "array", "items": {"type": "string"}},
                "context_budget_tokens": {"type": "integer"},
                "handoff_id": {"type": "string"},
                "sub_agent_id": {"type": "string"},
                "status": {"type": "string"},
                "result_summary": {"type": "string"},
                "file_id": {"type": "string"},
                "query": {"type": "string"}
            },
            "required": ["action"]
        }
    },

    # ── 18. Cloudinary Creative Tools ─────────────────────────────────────
    {
        "name": "cloudinary_creative_tools",
        "description": "Cloudinary image/video processing — upload, resize, platform presets, AI generative fill, batch operations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["upload", "resize", "platform_resize", "gen_fill", "batch_resize", "get_info", "list_assets"]},
                "file_url": {"type": "string"},
                "public_id": {"type": "string"},
                "width": {"type": "integer"},
                "height": {"type": "integer"},
                "crop": {"type": "string", "enum": ["fill", "fill_pad", "crop", "scale", "fit", "limit", "pad"]},
                "gravity": {"type": "string"},
                "use_gen_fill": {"type": "boolean"},
                "platform_preset": {"type": "string"}
            },
            "required": ["action"]
        }
    },

    # ── 19. Query Planner ─────────────────────────────────────────────────
    {
        "name": "query_planner",
        "description": "ALWAYS run get_account_summary FIRST. Plans efficient API queries, validates completeness, estimates row counts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["get_account_summary", "build_query_plan", "validate_completeness", "estimate_row_count", "get_query_budget"]},
                "search": {"type": "string"},
                "customer_id": {"type": "string"},
                "date_range": {"type": "string", "default": "LAST_30_DAYS"},
                "intent": {"type": "string"},
                "entity_type": {"type": "string", "default": "CAMPAIGN"},
                "cost_min": {"type": "number"},
                "cost_max": {"type": "number"},
                "conversions_min": {"type": "number"},
                "campaign_type": {"type": "string"},
                "status": {"type": "string", "default": "ENABLED"}
            },
            "required": ["action"]
        }
    },

    # ── 20. Recommendations Manager ───────────────────────────────────────
    {
        "name": "recommendations_manager",
        "description": "Get and manage Google Ads optimization recommendations — list, apply, dismiss, see impact estimates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "apply", "dismiss", "get_impact"]},
                "search": {"type": "string"},
                "customer_id": {"type": "string"},
                "rec_type": {"type": "string"},
                "campaign_ids": {"type": "array", "items": {"type": "string"}},
                "impact_min": {"type": "number"},
                "dismissed": {"type": "boolean", "default": False},
                "resource_name": {"type": "string"},
                "limit": {"type": "integer", "default": 100}
            },
            "required": ["action"]
        }
    },

    # ── 21. Search Term Manager ───────────────────────────────────────────
    {
        "name": "search_term_manager",
        "description": "Analyze search terms — list terms, find converting terms, identify wasted spend. All costs in DOLLARS.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "action": {"type": "string", "enum": ["list_search_terms", "get_converting_terms", "get_wasted_spend"]},
                "login_customer_id": {"type": "string"},
                "campaign_id": {"type": "string"},
                "ad_group_id": {"type": "string"},
                "date_range": {"type": "string", "default": "LAST_30_DAYS"},
                "term_contains": {"type": "string"},
                "cost_min": {"type": "number"},
                "cost_max": {"type": "number"},
                "sort_by": {"type": "string", "default": "cost"},
                "limit": {"type": "integer", "default": 200}
            },
            "required": ["customer_id", "action"]
        }
    },

    # ── 22. Geo & Location Manager ────────────────────────────────────────
    {
        "name": "geo_location_manager",
        "description": "Manage geographic targeting — performance by location, add/exclude locations, bid modifiers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "action": {"type": "string", "enum": ["list_geo_performance", "list_targeted_locations", "list_excluded_locations", "add_location_targets", "exclude_locations", "remove_location_target", "search_geo_targets", "update_location_bid_modifier"]},
                "login_customer_id": {"type": "string"},
                "campaign_id": {"type": "string"},
                "date_range": {"type": "string", "default": "LAST_30_DAYS"},
                "bid_modifier": {"type": "number"},
                "geo_target_ids": {"type": "array", "items": {"type": "string"}},
                "geo_query": {"type": "string"},
                "country_code": {"type": "string", "default": "US"},
                "cost_min": {"type": "number"},
                "sort_by": {"type": "string", "default": "cost"},
                "limit": {"type": "integer", "default": 200}
            },
            "required": ["customer_id", "action"]
        }
    },

    # ── 23. Device Performance Manager ────────────────────────────────────
    {
        "name": "device_performance_manager",
        "description": "Analyze device performance and manage device bid modifiers (DESKTOP, MOBILE, TABLET).",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list_device_performance", "update_bid_modifier", "get_recommendations"]},
                "search": {"type": "string"},
                "customer_id": {"type": "string"},
                "date_range": {"type": "string", "default": "LAST_30_DAYS"},
                "campaign_ids": {"type": "array", "items": {"type": "string"}},
                "device": {"type": "string", "enum": ["DESKTOP", "MOBILE", "TABLET"]},
                "bid_modifier": {"type": "number"},
                "cost_min": {"type": "number"},
                "limit": {"type": "integer", "default": 100}
            },
            "required": ["action"]
        }
    },

    # ── 24. Change History Manager ────────────────────────────────────────
    {
        "name": "change_history_manager",
        "description": "Audit account changes — list changes, budget changes, bid changes, status changes with date/user filters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list_changes", "list_budget_changes", "list_bid_changes", "list_status_changes"]},
                "search": {"type": "string"},
                "customer_id": {"type": "string"},
                "change_date_range": {"type": "string", "default": "LAST_30_DAYS"},
                "resource_type": {"type": "string"},
                "campaign_ids": {"type": "array", "items": {"type": "string"}},
                "user_email": {"type": "string"},
                "limit": {"type": "integer", "default": 100}
            },
            "required": ["action"]
        }
    },

    # ── 25. Campaign Creator ──────────────────────────────────────────────
    {
        "name": "campaign_creator",
        "description": "Create new campaigns — Search, PMax, Display, Demand Gen, Shopping. All budgets in DOLLARS. Default: PAUSED.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["create_search_campaign", "create_pmax_campaign", "create_display_campaign", "create_demand_gen_campaign", "create_shopping_campaign"]},
                "search": {"type": "string"},
                "customer_id": {"type": "string"},
                "name": {"type": "string"},
                "daily_budget": {"type": "number", "description": "Daily budget in DOLLARS (100 = $100/day)"},
                "bidding_strategy": {"type": "string", "default": "MAXIMIZE_CONVERSIONS"},
                "target_cpa": {"type": "number"},
                "target_roas": {"type": "number"},
                "geo_targets": {"type": "array", "items": {"type": "string"}},
                "language_codes": {"type": "array", "items": {"type": "string"}},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "status": {"type": "string", "default": "PAUSED"},
                "final_url": {"type": "string"}
            },
            "required": ["action"]
        }
    },

    # ── 26. Ad Schedule Manager ───────────────────────────────────────────
    {
        "name": "ad_schedule_manager",
        "description": "Manage ad schedules — get/set/remove schedules, analyze hourly performance, get scheduling recommendations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["get_ad_schedule", "set_ad_schedule", "remove_ad_schedule", "get_hourly_performance", "get_schedule_recommendations"]},
                "search": {"type": "string"},
                "customer_id": {"type": "string"},
                "campaign_id": {"type": "string"},
                "day_of_week": {"type": "string", "enum": ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]},
                "start_hour": {"type": "integer"},
                "end_hour": {"type": "integer"},
                "bid_modifier": {"type": "number", "default": 1.0},
                "date_range": {"type": "string", "default": "LAST_30_DAYS"},
                "limit": {"type": "integer", "default": 100}
            },
            "required": ["action"]
        }
    },

    # ── 27. Bidding Strategy Manager ──────────────────────────────────────
    {
        "name": "bidding_strategy_manager",
        "description": "Manage bidding strategies — list, switch, set CPA/ROAS targets, create/manage portfolio strategies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list_bidding_strategies", "switch_bidding_strategy", "set_target_cpa", "set_target_roas", "create_portfolio_strategy", "add_to_portfolio"]},
                "search": {"type": "string"},
                "customer_id": {"type": "string"},
                "campaign_id": {"type": "string"},
                "new_strategy": {"type": "string"},
                "target_cpa": {"type": "number", "description": "In DOLLARS (25 = $25)"},
                "target_roas": {"type": "number", "description": "Multiplier (4.0 = 400%)"},
                "max_cpc_limit": {"type": "number"},
                "name": {"type": "string"},
                "portfolio_strategy_id": {"type": "string"},
                "date_range": {"type": "string", "default": "LAST_30_DAYS"},
                "limit": {"type": "integer", "default": 100}
            },
            "required": ["action"]
        }
    },

    # ── 28. PMax Asset Group Manager ──────────────────────────────────────
    {
        "name": "pmax_asset_group_manager",
        "description": "Manage Performance Max asset groups — list, create, add/remove assets, set audience signals, get performance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list_asset_groups", "create_asset_group", "add_assets", "remove_asset", "set_audience_signal", "get_asset_performance"]},
                "search": {"type": "string"},
                "customer_id": {"type": "string"},
                "campaign_id": {"type": "string"},
                "asset_group_id": {"type": "string"},
                "name": {"type": "string"},
                "final_url": {"type": "string"},
                "status": {"type": "string", "default": "PAUSED"},
                "asset_type": {"type": "string", "enum": ["HEADLINE", "DESCRIPTION", "MARKETING_IMAGE", "SQUARE_MARKETING_IMAGE", "LOGO", "LANDSCAPE_LOGO", "BUSINESS_NAME"]},
                "texts": {"type": "array", "items": {"type": "string"}},
                "image_urls": {"type": "array", "items": {"type": "string"}},
                "performance_label": {"type": "string", "enum": ["BEST", "GOOD", "LOW", "LEARNING"]},
                "date_range": {"type": "string", "default": "LAST_30_DAYS"},
                "limit": {"type": "integer", "default": 100}
            },
            "required": ["action"]
        }
    },
]

# Map from tool name → action file path
TOOL_TO_ACTION_FILE = {
    "label_manager": "actions/main-agent/01_label_manager.py",
    "conversion_tracking_manager": "actions/main-agent/02_conversion_tracking_manager.py",
    "audience_manager": "actions/main-agent/03_audience_manager.py",
    "asset_manager": "actions/main-agent/04_asset_manager.py",
    "budget_manager": "actions/main-agent/05_budget_manager.py",
    "rsa_ad_manager": "actions/main-agent/06_rsa_ad_manager.py",
    "bid_keyword_manager": "actions/main-agent/07_bid_keyword_manager.py",
    "negative_keywords_manager": "actions/main-agent/08_negative_keywords_manager.py",
    "campaign_adgroup_manager": "actions/main-agent/09_campaign_adgroup_manager.py",
    "google_ads_mutate": "actions/main-agent/10_google_ads_mutate.py",
    "account_access_checker": "actions/main-agent/11_account_access_checker.py",
    "scripts_manager": "actions/main-agent/12_scripts_manager.py",
    "experiments_manager": "actions/main-agent/13_experiments_manager.py",
    "package_installer": "actions/main-agent/14_package_installer.py",
    "check_user_access": "actions/main-agent/15_check_user_access.py",
    "api_gateway": "actions/main-agent/16_api_gateway.py",
    "session_state_manager": "actions/main-agent/17_session_state_manager.py",
    "cloudinary_creative_tools": "actions/main-agent/18_cloudinary_creative_tools.py",
    "query_planner": "actions/main-agent/19_query_planner.py",
    "recommendations_manager": "actions/main-agent/20_recommendations_manager.py",
    "search_term_manager": "actions/main-agent/21_search_term_manager.py",
    "geo_location_manager": "actions/main-agent/22_geo_location_manager.py",
    "device_performance_manager": "actions/main-agent/23_device_performance_manager.py",
    "change_history_manager": "actions/main-agent/24_change_history_manager.py",
    "campaign_creator": "actions/main-agent/25_campaign_creator.py",
    "ad_schedule_manager": "actions/main-agent/26_ad_schedule_manager.py",
    "bidding_strategy_manager": "actions/main-agent/27_bidding_strategy_manager.py",
    "pmax_asset_group_manager": "actions/main-agent/28_pmax_asset_group_manager.py",
}
