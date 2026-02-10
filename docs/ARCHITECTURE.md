# Google Ads Agent — Full Architecture & Reconstruction Kit

> **Enterprise-grade Google Ads management system** powered by Claude Opus 4.5, with 28 custom API actions, 6 specialized sub-agents, and live read/write access to Google Ads accounts.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Main Agent](#main-agent)
  - [Metadata](#agent-metadata)
  - [System Prompt](#system-prompt)
  - [Custom Actions Map (28)](#custom-actions-map)
  - [Action Schemas & Parameters](#action-schemas--parameters)
  - [Builtin Tools](#builtin-tools)
- [Sub-Agent Ecosystem](#sub-agent-ecosystem)
  - [Delegation Protocol](#delegation-protocol)
  - [1 — Reporting & Analysis](#1--reporting--analysis-sub-agent)
  - [2 — Research & Intelligence](#2--research--intelligence-sub-agent)
  - [3 — Optimization](#3--optimization-sub-agent)
  - [4 — Shopping & PMax](#4--shopping--pmax-sub-agent)
  - [5 — Creative](#5--creative-sub-agent)
  - [6 — Creative Innovate Tool](#6--creative-innovate-tool)
- [Credential Configuration](#credential-configuration)
- [Known Issues & Gaps](#known-issues--gaps)
- [Reconstruction Checklist](#reconstruction-checklist)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    GOOGLE ADS AGENT (Main)                          │
│                    claude-opus-4-5 · PRIVATE                        │
│                    28 Custom Actions · 10 Builtin Tools             │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Filter-First │  │    CEP       │  │  Session & State Manager │  │
│  │ Architecture │  │  Protocol    │  │  (Coordination Bus)      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                   API Gateway Layer                          │   │
│  │         Auto-offloads large responses to files              │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────────┐
          │                  │                       │
    ┌─────┴─────┐     ┌─────┴─────┐          ┌─────┴─────┐
    │ Sub-Agent │     │ Sub-Agent │          │ Sub-Agent │
    │  1 of 5   │     │  2 of 5   │   ...    │  5 of 5   │
    │ Reporting │     │ Research  │          │ Creative  │
    └───────────┘     └───────────┘          └───────────┘
                                                  │
                                          ┌───────┴────────┐
                                          │ Creative       │
                                          │ Innovate Tool  │
                                          │ (Cloudinary +  │
                                          │  Gemini)       │
                                          └────────────────┘
```

### System Design Principles

| Principle | Description |
|-----------|-------------|
| **Filter-First Architecture** | 6-tier filter priority system applied to every query |
| **Context Efficiency Protocol (CEP)** | Ask probing questions before any API call to minimize token usage |
| **Top-Down Reporting** | Always start at account level, then drill down on request |
| **Dollar-Based Inputs** | All costs in dollars — never micros. System converts internally |
| **Safety-First Writes** | Require explicit `CONFIRM` for any budget/bid/status changes |
| **Sub-Agent Delegation** | Offload large data pulls, bulk ops, and content generation to sub-agents |

---

## Main Agent

### Agent Metadata

| Property | Value |
|----------|-------|
| **Agent ID** | `dc78f37b-99ce-4c7a-b912-704b1aa78156` |
| **Name** | Google Ads Agent [beta/live-write/read] |
| **Model** | `claude-opus-4-5` (Anthropic) |
| **Access Level** | PRIVATE |
| **Organization** | org-10004586 |
| **Owner User ID** | 10481239 |
| **Custom Actions** | 28 |
| **Sub-Agents** | 6 |
| **Builtin Tools** | 10 |
| **Shared Users** | 5 (all CAN_EDIT) |

### System Prompt

<details>
<summary><strong>Click to expand full system prompt (Enterprise Edition v10.0)</strong></summary>

```markdown
# Google Ads Agent - Enterprise Edition v10.0
## Filter-First Architecture + Top-Down Reporting + Dollar-Based Inputs

## Identity
You are an expert Google Ads strategist with 15+ years experience. You have **LIVE API
access** to read, analyze, AND CREATE/MODIFY data in Google Ads accounts. You operate
with precision because your actions directly impact ad spend and business revenue.

---

## 🚨 CRITICAL: FIRST ACTION IN EVERY CONVERSATION

**Before doing ANYTHING else, run this command to ensure the correct Google Ads library
is installed:**

python
import subprocess
subprocess.check_call(["pip", "install", "google-ads>=28.1.0"])

Use the code_interpreter tool to run this at the START of every conversation, before
making any API calls. This ensures v22 API compatibility.

---

## 🎯 CONTEXT EFFICIENCY PROTOCOL (CEP) - MANDATORY

### ASK BEFORE YOU QUERY

**Before making ANY API calls, gather context through probing questions. Names work
just as well as IDs.**

#### Tier 1: Identity Questions (ALWAYS ASK)
- Which **account** (name or ID)?
- Which **campaign** (name or ID)?
- Which **ad group** (name or ID)?

#### Tier 2: Scope Questions (ASK FOR ANALYSIS TASKS)
- Focus on **ENABLED only** or include PAUSED?
- Date range: **last 7, 30, or 90 days**?
- Minimum spend threshold? (e.g., $50+)
- Include entities with **$0 spend**?

#### Tier 3: Existence Checks (ASK FOR CREATION TASKS)
- Do **RSAs/ads already exist** in this ad group?
- Are **customizers set up** already?
- Any **existing assets** to be aware of?
- Create as **PAUSED or ENABLED**?

#### Tier 4: Content Shortcuts (ASK FOR CONTENT TASKS)
- Do you have a **list of key points** already?
- Specific **keywords to align with**?
- Any **awards/promos** to mention?

### Decision Tree: When to Query vs. When to Ask

User Request
│
├─► Do I have Account name/ID? ──► NO ──► ASK (don't search)
│                              ──► YES ─┐
├─► Do I have Campaign name/ID? ─► NO ──► ASK (don't list all)
│                              ──► YES ─┐
├─► Do I have Ad Group name/ID? ─► NO ──► ASK (don't list all)
│                              ──► YES ─┐
└─► Do I have content/context? ──► NO ──► ASK (don't scrape yet)
                               ──► YES ──► PROCEED with targeted query

---

## 🤖 SUB-AGENT DELEGATION PROTOCOL

### When to Delegate vs. Handle Directly

**HANDLE IN MAIN AGENT (stay fast):**
- Single entity operations (pause 1 campaign, check 1 ad group)
- Simple status changes
- Quick lookups returning <50 rows
- User confirmation flows
- Clarifying questions

**DELEGATE TO SUB-AGENT when:**
- Large data pull (500+ rows)
- Multi-entity creation (5+ RSAs)
- Bulk operations (50+ negative keywords)
- Heavy analysis (all campaigns, 90 days)
- Content generation (ad copy for 10+ ad groups)
- Data exports (CSV generation)

---

## 🚨 CRITICAL: ALL COST VALUES USE DOLLARS - NEVER MICROS!

| Parameter      | What User Says         | What It Means                   |
|----------------|------------------------|---------------------------------|
| cost_min=50    | "$50 minimum spend"    | Filter to items with $50+ spend |
| cost_max=1000  | "$1,000 maximum spend" | Filter to items with <$1K spend |
| daily_budget=100 | "$100/day budget"    | Set daily budget to $100        |
| target_cpa=25  | "$25 target CPA"       | Target $25 cost per acquisition |
| target_roas=4.0 | "400% ROAS"           | Target 4x return on ad spend    |
| cpc_bid=2.50   | "$2.50 bid"            | Max CPC bid of $2.50            |

---

## 🚨 CRITICAL: TOP-DOWN REPORTING WORKFLOW

STEP 1: ACCOUNT SUMMARY FIRST → Query Planner > get_account_summary
STEP 2: ASK USER WHAT TO DRILL INTO
STEP 3: APPLY FILTERS BEFORE DRILLING DOWN
STEP 4: VALIDATE COMPLETENESS → Compare detail totals to account summary

---

## 📊 6-TIER FILTER PRIORITY SYSTEM

TIER 1: IDENTITY   → customer_id (via search='Client Name')
TIER 2: STATUS     → ENABLED, PAUSED (default: exclude REMOVED)
TIER 3: TYPE       → campaign_type, match_type, device_type
TIER 4: DATE       → date_range (default: LAST_30_DAYS for metrics)
TIER 5: METRICS    → cost_min, conversions_min (ALL IN DOLLARS!)
TIER 6: SHAPING    → limit, sort_by, detail_level

---

## ⛔ SAFETY RULES

**NEVER without explicit user approval:**
- Budget increase >20%
- Bid increase >30%
- Enable paused campaigns
- Remove entities
- Change conversion settings

**ALWAYS before writes:**
1. Show preview of changes
2. Display current vs. proposed values
3. Show dollar amounts clearly
4. Require user to type "CONFIRM"
5. Provide rollback instructions

---

## ⚠️ KEY REMINDERS (v10.0)

1. INSTALL FIRST — Run pip install google-ads>=28.1.0 at conversation start
2. CEP FIRST — Ask probing questions BEFORE any API calls
3. NAMES = IDs — Account/campaign/ad group names work just as well as IDs
4. ACCOUNT SUMMARY FIRST — Always run Query Planner > get_account_summary
5. ALL COSTS IN DOLLARS — cost_min=50 means $50, NEVER use micros
6. FILTER BEFORE QUERY — Apply filters to reduce result sets
7. VALIDATE COMPLETENESS — Compare detail sums to account totals
8. SHOW YOUR WORK — Tell users what filters you applied
9. SAFETY FIRST — Require CONFIRM for any budget/bid changes
10. TOP-DOWN ALWAYS — Start broad, drill down on request
```

</details>

### Custom Actions Map

All 28 custom actions organized by category:

#### Strategic Planning

| # | Action | ID | Key Operations |
|---|--------|----|----------------|
| 19 | **Query Planner & Budget Manager** | `c3f33a4e` | `get_account_summary`, `build_query_plan`, `validate_completeness` |

#### Campaign Lifecycle

| # | Action | ID | Key Operations |
|---|--------|----|----------------|
| 25 | **Campaign Creator** | `099db082` | `create_search`, `create_pmax`, `create_display`, `create_demand_gen`, `create_shopping` |
| 9 | **Campaign & Ad Group Manager** | `b818b493` | `list_campaigns`, `find_campaign`, `get_campaign`, `update_status`, `list_ad_groups`, `create_ad_group` |
| 5 | **Budget Manager** | `b191b54e` | `list_budgets`, `update_budget`, `create_budget`, `get_pacing` |
| 6 | **RSA Ad Manager** | `4c2ed646` | `list`, `create`, `pause`, `enable` |
| 7 | **Bid & Keyword Manager** | `facfd086` | `get_keyword_bids`, `update_bids`, `add_keywords`, `add_from_search_terms` |
| 10 | **Google Ads Mutate** | `205d3fbb` | Generic bulk `create`/`update`/`remove` operations |

#### Bidding & Optimization

| # | Action | ID | Key Operations |
|---|--------|----|----------------|
| 27 | **Bidding Strategy Manager** | `1b762c7d` | `list`, `switch`, `set_target_cpa`, `set_target_roas`, `create_portfolio`, `add_to_portfolio` |
| 26 | **Ad Schedule Manager** | `d9edcf51` | `get`/`set`/`remove` schedules, `hourly_performance` |
| 20 | **Recommendations Manager** | `b06c3b34` | `list`, `apply`, `dismiss`, `get_impact` |

#### Targeting

| # | Action | ID | Key Operations |
|---|--------|----|----------------|
| 22 | **Geo & Location Targeting Manager** | `56eecd1d` | `search_geo_targets`, `add`/`exclude`/`remove` locations, `geo_performance` |
| 23 | **Device Performance Manager** | `f92bb613` | `list_device_performance`, `update_bid_modifier`, `recommendations` |
| 3 | **Audience Manager** | `1ad57d33` | `list_audiences`, `get_performance`, `add_to_campaign`/`ad_group` |

#### Analysis

| # | Action | ID | Key Operations |
|---|--------|----|----------------|
| 21 | **Search Term Manager** | `da0ea470` | `list_search_terms`, `get_converting_terms`, `get_wasted_spend` |
| 24 | **Change History Manager** | `d56d5657` | `list_changes`, `budget_changes`, `bid_changes`, `status_changes` |
| 2 | **Conversion Tracking Manager** | `4e7dd1b7` | `list_conversion_actions`, `create`, `update`, `get_attribution` |

#### PMax & Experiments

| # | Action | ID | Key Operations |
|---|--------|----|----------------|
| 28 | **PMax Asset Group Manager** | `8218e0f3` | `list`/`create` asset groups, `add_assets`, `get_asset_performance` |
| 13 | **Experiments Manager** | `9b44f60e` | `list`, `create`, `get_results`, `end`, `promote` |

#### Organization

| # | Action | ID | Key Operations |
|---|--------|----|----------------|
| 1 | **Label Manager** | `99090289` | `list_labels`, `create_label`, `apply_label`, `list_labeled_entities` |
| 8 | **Negative Keywords Manager** | `fd7b1afc` | `list_campaign_negatives`, `list_shared_sets`, `add`, `remove` |
| 4 | **Asset Manager** | `b0d7f48c` | `list`, `create_sitelink`, `create_callout`, `create_call`, `link` |

#### Infrastructure

| # | Action | ID | Key Operations |
|---|--------|----|----------------|
| 11 | **Account Access Checker** | `cb0400cb` | `list_accessible`, `find`/`search`, `get_hierarchy` |
| 16 | **API Gateway - Context Manager** | `e4529640` | Route API calls, auto-offload large responses to files |
| 17 | **Session & State Manager** | `63993c88` | Sessions, query plan cache, sub-agent sync, file search |
| 14 | **Package Installer** | `9de09fd1` | Install optional Python packages by category |
| 15 | **Check User Access Levels** | `8f788bd9` | Check user roles (ADMIN/STANDARD/READ_ONLY) |
| 12 | **Scripts Manager** | `5b84fbfc` | Informational — Google Ads scripts guidance (UI only) |

#### Creative

| # | Action | ID | Key Operations |
|---|--------|----|----------------|
| 18 | **Cloudinary Creative Tools** | `413cabd5` | Upload, resize, platform presets, gen fill, batch resize |

### Action Schemas & Parameters

<details>
<summary><strong>Click to expand all 28 action schemas</strong></summary>

#### 1. Label Manager — `99090289-128a-4cf9-9a44-317bba38ce7e`

```python
run(action, search=None, customer_id=None, label_id=None, name=None, color=None,
    description=None, entity_type=None, entity_ids=None, name_contains=None,
    campaign_ids=None, limit=100)
```

| Parameter | Description |
|-----------|-------------|
| `action` | `list_labels`, `create_label`, `apply_label`, `remove_label`, `list_labeled_entities` |
| `entity_type` | `CAMPAIGN`, `AD_GROUP`, `AD`, `KEYWORD` |
| `name_contains` | Filter labels by name |

---

#### 2. Conversion Tracking Manager — `4e7dd1b7-36d1-40ce-855c-269c7e4877ae`

```python
run(action, search=None, customer_id=None, category=None, status=None, name_contains=None,
    conversions_min=None, conversion_value_min=None, conversion_value_max=None,
    name=None, counting_type=None, default_value=None, attribution_model=None,
    lookback_window_days=None, conversion_action_id=None, date_range="LAST_30_DAYS", limit=100)
```

| Parameter | Description |
|-----------|-------------|
| `action` | `list_conversion_actions`, `create_conversion_action`, `update_conversion_action`, `get_conversion_attribution` |
| `category` | `PURCHASE`, `LEAD`, `SIGNUP`, `PAGE_VIEW`, etc. |
| `conversion_value_min/max` | Filter by value (dollars) |

---

#### 3. Audience Manager — `1ad57d33-9849-44bc-b69e-c37f01c1b145`

```python
run(customer_id, action, login_customer_id=None, campaign_id=None, ad_group_id=None,
    audience_id=None, user_list_id=None, bid_modifier=None, date_range="LAST_30_DAYS",
    name_contains=None, type_filter=None, membership_status=None,
    size_min=None, size_max=None, eligible_for_search=None,
    eligible_for_display=None, sort_by='size', limit=200)
```

| Parameter | Description |
|-----------|-------------|
| `action` | `list_audiences`, `get_audience_performance`, `add_audience_to_campaign`, `add_audience_to_ad_group` |
| `type_filter` | `REMARKETING`, `CRM_BASED`, `RULE_BASED`, `SIMILAR`, `ALL` |

---

#### 4. Asset Manager — `b0d7f48c-18a4-4194-a251-29f3c0b3e222`

```python
run(customer_id, action, login_customer_id=None, asset_data=None, campaign_id=None,
    ad_group_id=None, asset_id=None, asset_resource_name=None, field_type=None,
    asset_type=None, limit=500)
```

| Parameter | Description |
|-----------|-------------|
| `action` | `list`, `create_sitelink`, `create_callout`, `create_call`, `link_to_campaign`, `link_to_ad_group` |
| `asset_data` | Dict: `{text, final_urls, description1, description2, phone_number, country_code}` |

---

#### 5. Budget Manager — `b191b54e-5d38-4da9-ac03-be0e1787a604`

```python
run(customer_id, action, login_customer_id=None, budget_id=None,
    name=None, delivery_method="STANDARD",
    amount=None, amount_min=None, amount_max=None,
    status_filter=None, name_contains=None, shared_filter=None,
    sort_by='amount', limit=100)
```

| Parameter | Description |
|-----------|-------------|
| `action` | `list_budgets`, `update_budget`, `create_budget`, `get_pacing` |
| `amount` | Budget in **dollars** (e.g., `100` = $100/day) |
| `shared_filter` | `SHARED`, `NOT_SHARED`, `ALL` |

---

#### 6. RSA Ad Manager — `4c2ed646-606d-450e-9f32-57d13f4342dd`

```python
run(customer_id, action, login_customer_id=None, ad_group_id=None, campaign_id=None,
    ad_data=None, ad_id=None, query_plan=None, status_filter=None, approval_filter=None,
    ad_strength_filter=None, date_range=None, limit=100, include_metrics=False, detail_level=None)
```

| Parameter | Description |
|-----------|-------------|
| `action` | `list`, `create`, `pause`, `enable` |
| `ad_data` | Dict: `{headlines: [], descriptions: [], final_urls: [], path1, path2}` |
| `ad_strength_filter` | `EXCELLENT`, `GOOD`, `AVERAGE`, `POOR`, `NEEDS_ATTENTION` |

---

#### 7. Bid & Keyword Manager — `facfd086-2437-4f6b-9625-3b68050d6437`

```python
run(customer_id, action, login_customer_id=None, ad_group_id=None, campaign_id=None,
    criterion_id=None, bid_modifier=None, cpc_bid=None, cost_min=None, cost_max=None,
    cpa_max=None, status_filter=None, match_type=None, keyword_contains=None,
    date_range=None, conversions_min=None, conversions_max=None, clicks_min=None,
    impressions_min=None, quality_score_min=None, quality_score_max=None,
    sort_by='cost', limit=200, keywords=None, min_conversions=1.0)
```

| Parameter | Description |
|-----------|-------------|
| `action` | `get_keyword_bids`, `update_keyword_bid`, `update_ad_group_bid`, `get_bid_modifiers`, `add_keywords`, `add_keywords_from_search_terms` |
| `cpc_bid` | Bid in **dollars** (e.g., `2.50` = $2.50) |
| `keywords` | List of `{keyword, match_type, cpc_bid}` dicts |
| `match_type` | `EXACT`, `PHRASE`, `BROAD` |
| `quality_score_min/max` | 1–10 |

---

#### 8. Negative Keywords Manager — `fd7b1afc-0766-4c7f-b7ab-e0ff2c97fe92`

```python
run(customer_id, action, login_customer_id=None, campaign_id=None, keyword_text=None,
    match_type="BROAD", shared_set_id=None, resource_name=None, level="campaign")
```

| Parameter | Description |
|-----------|-------------|
| `action` | `list_campaign_negatives`, `list_shared_sets`, `add_campaign_negative`, `add_to_shared_set`, `remove_negative`, `create_shared_set` |

---

#### 9. Campaign & Ad Group Manager — `b818b493-bf8c-469a-a123-e1c1cc509851`

```python
run(customer_id=None, action="list_campaigns", login_customer_id=None, campaign_id=None,
    ad_group_id=None, data=None, search=None, campaign_name=None,
    query_plan=None, status_filter=None, campaign_type_filter=None,
    date_range=None, fields=None, limit=100, include_metrics=False, detail_level=None,
    cost_min=None, cost_max=None, conversions_min=None, conversions_max=None,
    impressions_min=None, clicks_min=None, ctr_min=None, ctr_max=None,
    bidding_strategy_type=None, sort_by='name',
    ad_group_name=None, ad_group_type='SEARCH_STANDARD', default_cpc=None,
    target_cpa=None, target_roas=None)
```

| Parameter | Description |
|-----------|-------------|
| `action` | `list_campaigns`, `find_campaign`, `get_campaign`, `update_status`, `list_ad_groups`, `update_ad_group_status`, `create_ad_group`, `update_ad_group_bid` |
| `search` | Auto-resolves account by name (no `customer_id` needed) |
| `campaign_type_filter` | `SEARCH`, `DISPLAY`, `SHOPPING`, `VIDEO`, `PERFORMANCE_MAX` |

---

#### 10. Google Ads Mutate — `205d3fbb-9d0f-44c9-8137-70f687bfc072`

```python
run(customer_id, operations, login_customer_id=None)
```

Operations format:
```json
[{
  "type": "create|update|remove",
  "entity": "campaign|ad_group|ad_group_ad|ad_group_criterion|campaign_criterion|campaign_budget",
  "data": { }
}]
```

> ⚠️ Prefer specific managers over Mutate. Only use for bulk/atomic multi-entity operations.

---

#### 11. Account Access Checker — `cb0400cb-6be3-42d2-8ca5-b4c4a0ef6209`

```python
run(operation="list_accessible", customer_id=None, login_customer_id=None, search=None)
```

| Parameter | Description |
|-----------|-------------|
| `operation` | `list_accessible`, `discover`, `find`/`search`, `get_hierarchy`, `test_connection` |

---

#### 12. Scripts Manager — `5b84fbfc-021b-474b-a0de-e3521f3751e3`

```python
run(action, search=None, customer_id=None, name=None, name_contains=None,
    status=None, last_run_status=None, script_id=None, code=None, limit=100)
```

> ℹ️ Informational only — Google Ads Scripts are NOT accessible via the API.

---

#### 13. Experiments Manager — `9b44f60e-d0c1-4c42-bccd-7a81c3e34a22`

```python
run(action, search=None, customer_id=None, experiment_id=None, name=None,
    base_campaign_id=None, description=None, traffic_split=50,
    start_date=None, end_date=None, apply_changes=False,
    status=None, campaign_ids=None, name_contains=None,
    cost_min=None, cost_max=None, date_range="LAST_30_DAYS", limit=100)
```

| Parameter | Description |
|-----------|-------------|
| `action` | `list_experiments`, `create_experiment`, `get_experiment_results`, `end_experiment`, `promote_experiment` |

---

#### 14. Package Installer — `9de09fd1-92c3-4b72-bee3-b81b76431e80`

```python
run(install_category="all")
```

Categories: `math`, `testing`, `advertising`, `presentation`, `html_css`, `color_design`, `persistence`, `financial`, `all`

> No credentials required.

---

#### 15. Check User Access Levels — `8f788bd9-c295-4d8e-9227-4d9b52883c0e`

```python
run(customer_id, login_customer_id=None)
```

Returns: User list with access roles (`ADMIN`, `STANDARD`, `READ_ONLY`, `EMAIL_ONLY`)

---

#### 16. API Gateway - Context Manager — `e4529640-6761-4e95-a54b-84390b137515`

```python
run(action_type, action_params, session_id=None, max_preview_rows=5,
    force_file=False, ttl_hours=24)
```

| Parameter | Description |
|-----------|-------------|
| `max_preview_rows` | How many rows in preview (default 5) |
| `force_file` | Always write to file regardless of size |

> Threshold: >10KB → auto-offload to file.

---

#### 17. Session & State Manager — `63993c88-23e2-42d3-8f04-cb52758a736a`

```python
run(action, **kwargs)
```

| Action | Key kwargs |
|--------|-----------|
| `init_session` | `session_name`, `account_context`, `auto_detect` |
| `cache_query_plan` | `session_id`, `plan_name`, `query_plan`, `ttl_hours` |
| `prepare_handoff` | `session_id`, `target_agent`, `task_description`, `query_plan`, `file_ids`, `context_budget_tokens` |
| `sync_sub_agent_state` | `handoff_id`, `sub_agent_id`, `status`, `current_step`, `progress_percent` |
| `receive_sub_agent_result` | `handoff_id`, `result_summary`, `file_id`, `tokens_used`, `error` |
| `search_files` | `query`, `session_id` |
| `register_file` | `session_id`, `file_path`, `metadata`, `data_for_indexing`, `ttl_hours` |

> No credentials required.

---

#### 18. Cloudinary Creative Tools — `413cabd5-a8c8-4965-9c25-83e5d35e6aed`

```python
run(action, **kwargs)
```

| Key kwarg | Description |
|-----------|-------------|
| `file_url` | URL to upload |
| `public_id` | Cloudinary asset ID |
| `width`, `height` | Target dimensions |
| `crop` | `fill`, `fill_pad`, `crop`, `scale`, `fit`, `limit`, `pad`, `lpad` |
| `gravity` | `auto`, `auto:faces`, `auto:face`, `center`, `north`, `south`, etc. |
| `use_gen_fill` | AI generative fill for non-standard ratios |
| `platform_preset` | `instagram_story`, `tiktok`, `youtube_standard`, `leaderboard_728x90`, etc. |

Platform presets: `instagram_story`, `instagram_feed`, `instagram_reel`, `tiktok`, `youtube_shorts`, `youtube_standard`, `youtube_thumbnail`, `facebook_feed`, `facebook_story`, `linkedin`, `twitter`, `pinterest`, `leaderboard_728x90`, `skyscraper_160x600`, `wide_skyscraper_300x600`, `medium_rectangle_300x250`, `large_rectangle_336x280`, `half_page_300x600`, `billboard_970x250`

---

#### 19. Query Planner & Budget Manager — `c3f33a4e-138e-48a6-a5e2-9648450349b4`

```python
run(action, search=None, customer_id=None, date_range="LAST_30_DAYS",
    intent=None, entity_type="CAMPAIGN", cost_min=None, cost_max=None,
    conversions_min=None, campaign_type=None, status="ENABLED",
    detail_cost_total=None, detail_row_count=None)
```

| Parameter | Description |
|-----------|-------------|
| `action` | `get_account_summary`, `build_query_plan`, `validate_completeness`, `estimate_row_count`, `get_query_budget` |

> ⚡ **ALWAYS run `get_account_summary` FIRST before any detail queries.**

---

#### 20. Recommendations Manager — `b06c3b34-a3f1-43ec-b20d-33cadb4be6b7`

```python
run(action, search=None, customer_id=None, rec_type=None, campaign_ids=None,
    impact_min=None, dismissed=False, resource_name=None, limit=100)
```

---

#### 21. Search Term Manager — `da0ea470-868f-4ba8-9880-f7e34f705f9c`

```python
run(customer_id, action, login_customer_id=None, campaign_id=None, ad_group_id=None,
    date_range='LAST_30_DAYS', term_contains=None, status_filter=None,
    cost_min=None, cost_max=None, conversions_min=None, conversions_max=None,
    clicks_min=None, impressions_min=None, sort_by='cost', limit=200)
```

| Parameter | Description |
|-----------|-------------|
| `action` | `list_search_terms`, `get_converting_terms`, `get_wasted_spend` |
| `status_filter` | `ADDED`, `EXCLUDED`, `NONE`, `ALL` |

---

#### 22. Geo & Location Targeting Manager — `56eecd1d-fa61-4e1a-9df2-2381985db753`

```python
run(customer_id, action, login_customer_id=None, campaign_id=None,
    date_range='LAST_30_DAYS', location_type=None,
    cost_min=None, conversions_min=None, impressions_min=None,
    sort_by='cost', limit=200, criterion_id=None, bid_modifier=None,
    geo_target_ids=None, geo_query=None, country_code='US')
```

| Parameter | Description |
|-----------|-------------|
| `action` | `list_geo_performance`, `list_targeted_locations`, `list_excluded_locations`, `get_location_bid_modifiers`, `update_location_bid_modifier`, `add_location_targets`, `exclude_locations`, `remove_location_target`, `search_geo_targets` |
| `bid_modifier` | `1.0` = no change, `1.2` = +20%, `0.8` = -20% |

---

#### 23. Device Performance Manager — `f92bb613-63ed-4468-94de-4a061e18bc25`

```python
run(action, search=None, customer_id=None, date_range="LAST_30_DAYS",
    campaign_ids=None, campaign_id=None, device=None, bid_modifier=None,
    cost_min=None, cost_max=None, conversions_min=None,
    ctr_min=None, ctr_max=None, conversion_rate_min=None, limit=100)
```

Device values: `DESKTOP`, `MOBILE`, `TABLET`

---

#### 24. Change History Manager — `d56d5657-5e01-4b4a-bc7d-ae04de62e60d`

```python
run(action, search=None, customer_id=None, change_date_range="LAST_30_DAYS",
    resource_type=None, campaign_ids=None, user_email=None,
    amount_change_min=None, limit=100)
```

| Parameter | Description |
|-----------|-------------|
| `action` | `list_changes`, `list_budget_changes`, `list_bid_changes`, `list_status_changes` |
| `resource_type` | `CAMPAIGN`, `AD_GROUP`, `AD`, `KEYWORD`, etc. |

---

#### 25. Campaign Creator — `099db082-9e33-4b34-932f-2974d3209f65`

```python
run(action, search=None, customer_id=None, name=None, daily_budget=None,
    bidding_strategy="MAXIMIZE_CONVERSIONS", target_cpa=None, target_roas=None,
    geo_targets=None, language_codes=None, start_date=None, end_date=None,
    status="PAUSED", final_url=None)
```

| Parameter | Description |
|-----------|-------------|
| `action` | `create_search_campaign`, `create_pmax_campaign`, `create_display_campaign`, `create_demand_gen_campaign`, `create_shopping_campaign` |
| `daily_budget` | In **dollars** (e.g., `100` = $100/day) |
| `bidding_strategy` | `MAXIMIZE_CONVERSIONS`, `TARGET_CPA`, `TARGET_ROAS`, `MAXIMIZE_CLICKS`, `MANUAL_CPC` |

> Campaigns start **PAUSED** by default.

---

#### 26. Ad Schedule Manager — `d9edcf51-7016-47c0-bb59-ce6ba0c312c1`

```python
run(action, search=None, customer_id=None, campaign_id=None, campaign_ids=None,
    day_of_week=None, start_hour=None, end_hour=None,
    start_minute="ZERO", end_minute="ZERO", bid_modifier=1.0,
    criterion_resource_name=None, date_range="LAST_30_DAYS",
    cost_min=None, conversions_min=None, limit=100)
```

| Parameter | Description |
|-----------|-------------|
| `action` | `get_ad_schedule`, `set_ad_schedule`, `remove_ad_schedule`, `get_hourly_performance`, `get_schedule_recommendations` |
| `day_of_week` | `MONDAY` through `SUNDAY` |
| `start_hour`/`end_hour` | 0–24 |

---

#### 27. Bidding Strategy Manager — `1b762c7d-3968-4335-8e68-d4b7769894eb`

```python
run(action, search=None, customer_id=None, campaign_id=None,
    new_strategy=None, target_cpa=None, target_roas=None, max_cpc_limit=None,
    name=None, strategy_type=None, portfolio_strategy_id=None,
    portfolio_only=False, cost_min=None, conversions_min=None,
    date_range="LAST_30_DAYS", limit=100)
```

| Parameter | Description |
|-----------|-------------|
| `action` | `list_bidding_strategies`, `switch_bidding_strategy`, `set_target_cpa`, `set_target_roas`, `create_portfolio_strategy`, `add_to_portfolio` |
| `target_cpa` | In **dollars** (e.g., `25` = $25) |
| `target_roas` | Multiplier (e.g., `4.0` = 400%) |
| `new_strategy` | `MAXIMIZE_CONVERSIONS`, `TARGET_CPA`, `TARGET_ROAS`, `MAXIMIZE_CONVERSION_VALUE`, `MAXIMIZE_CLICKS`, `MANUAL_CPC` |

---

#### 28. PMax Asset Group Manager — `8218e0f3-f8b8-4484-9278-a8ed2e35d643`

```python
run(action, search=None, customer_id=None, campaign_id=None, asset_group_id=None,
    name=None, final_url=None, path1="", path2="", status="PAUSED",
    asset_type=None, texts=None, image_urls=None, performance_label=None,
    cost_min=None, cost_max=None, conversions_min=None,
    date_range="LAST_30_DAYS", limit=100)
```

| Parameter | Description |
|-----------|-------------|
| `action` | `list_asset_groups`, `create_asset_group`, `add_assets`, `remove_asset`, `set_audience_signal`, `get_asset_performance` |
| `asset_type` | `HEADLINE`, `DESCRIPTION`, `MARKETING_IMAGE`, `SQUARE_MARKETING_IMAGE`, `LOGO`, `LANDSCAPE_LOGO`, `BUSINESS_NAME` |
| `performance_label` | `BEST`, `GOOD`, `LOW`, `LEARNING` |

</details>

### Builtin Tools

| # | Tool | Type |
|---|------|------|
| 1 | `code_interpreter` | BUILTIN |
| 2 | `google_web_search` | BUILTIN |
| 3 | `researcher` | BUILTIN |
| 4 | `todo_write` | BUILTIN |
| 5 | `web_scraper` | BUILTIN |
| 6 | `query_executor` | BUILTIN |
| 7 | `csv_reader` | BUILTIN |
| 8 | `string_matcher` | BUILTIN |
| 9 | `display_file` | BUILTIN |
| 10 | `file_search` | BUILTIN |

---

## Sub-Agent Ecosystem

### Delegation Protocol

```
User Request
│
├─► Simple/Single entity? ──► YES ──► HANDLE DIRECTLY (main agent)
│                          ──► NO  ─┐
├─► Will response exceed 50 rows? ──► YES ──► DELEGATE
│                                  ──► NO  ─┐
├─► Multiple entities to create? ──► YES ──► DELEGATE
│                                ──► NO  ─┐
└─► Heavy processing/generation? ──► YES ──► DELEGATE
                                 ──► NO  ──► HANDLE DIRECTLY
```

#### Handoff Mechanism (via Session & State Manager)

```
┌─ MAIN AGENT ──────────────────────────────────────────────────┐
│  1. prepare_handoff(session_id, target_agent, task, plan)     │
│  2. Receives handoff_id → delegates to sub-agent              │
│  3. Later: get_sub_agent_result(handoff_id)                   │
├───────────────────────────────────────────────────────────────┤
│  SUB-AGENT                                                    │
│  1. receive_handoff(handoff_id) → gets task + context         │
│  2. sync_sub_agent_state(handoff_id, id, "started")           │
│  3. Executes task, writes large data to file                  │
│  4. receive_sub_agent_result(handoff_id, summary, file_id)    │
└───────────────────────────────────────────────────────────────┘
```

#### Context Budget Defaults

| Target Agent Type | Token Budget |
|-------------------|-------------|
| Standard Sub-Agent | 15,000 |
| Creative Innovate | 20,000 |
| Big Context Handler | 50,000–80,000 |

#### Task Routing

| Task Type | Best Sub-Agent | Why |
|-----------|----------------|-----|
| Performance reports, data analysis | Reporting & Analysis [1] | Summarize-don't-dump philosophy |
| Keyword research, competitive intel | Research & Intelligence [2] | External data + web tools |
| Bulk bid/budget changes, recommendations | Optimization [3] | Preview-before-execute safety |
| Shopping campaigns, PMax asset groups | Shopping & PMax [4] | ROAS-focused e-commerce specialist |
| Display ads, Demand Gen, visual formats | Creative [5] | Visual-first ad management |
| Image/video resizing, AI gen fill | Creative Innovate Tool [6] | Cloudinary + Gemini processing |

---

### 1 — Reporting & Analysis Sub-Agent

| Property | Value |
|----------|-------|
| **Agent ID** | `de724cf6-1bf3-4c88-8723-8f3583821824` |
| **Model** | `claude-opus-4-5` |
| **Access Level** | CHAT_ONLY |
| **Core Principle** | *Summarize, don't dump.* Return key findings and insights, not raw data. |

**Custom Actions (8):**

| # | Action | ID | API Version |
|---|--------|----|-------------|
| 1 | Performance Reporter | `fe13e086` | v19 |
| 2 | Search Terms Analyzer | (see source) | v19 |
| 3 | Interactive Keyword Viewer | (see source) | v18 |
| 4 | Interactive Ad Viewer | (see source) | v18 |
| 5 | Auction Insights Reporter | (see source) | v19 |
| 6 | Change History Auditor | (see source) | v19 |
| 7 | PMax Enhanced Reporting | (see source) | v19 |
| 8 | Package Installer | `9de09fd1` | N/A |

> ⚠️ Actions 3–4 use API v18 while others use v19 — verify version alignment during rebuild.

**Builtin Tools (9):** `code_interpreter`, `query_executor`, `csv_reader`, `string_matcher`, `display_file`, `file_search`, `browser_use`, `researcher`, `google_web_search`

<details>
<summary><strong>System Prompt</strong></summary>

```markdown
# Reporting & Analysis Sub-Agent

## Identity
You are a specialized Google Ads reporting and analysis expert. Your job is to pull
data, analyze performance, and return **concise, actionable summaries** to the main
Google Ads Agent. You have direct API access to Google Ads accounts.

## Core Principle
**SUMMARIZE, DON'T DUMP.** The main agent called you to avoid context bloat. Always:
- Return key findings and insights, not raw data dumps
- Highlight anomalies, opportunities, and risks
- Provide actionable recommendations
- Use tables for comparisons (limit to top 10-15 items)
- Offer to provide more detail only if specifically needed

## Reporting Rules
1. Never return more than 15 rows in any table unless explicitly asked
2. Always calculate derived metrics (CTR, CPA, ROAS)
3. Flag statistical significance when sample sizes are small (<100 clicks)
4. Include date ranges in every response
5. Compare to benchmarks when possible
6. Prioritize insights over data
7. Always mention what you're NOT showing
```

</details>

---

### 2 — Research & Intelligence Sub-Agent

| Property | Value |
|----------|-------|
| **Agent ID** | `77c5378f-e325-4de0-8504-29bbf44ffd0d` |
| **Model** | `claude-opus-4-5` |
| **Access Level** | CHAT_ONLY |
| **Core Principle** | *Insight over information.* Don't just report findings — explain what they mean for strategy. |

**Custom Actions (5):**

| # | Action | ID |
|---|--------|----|
| 1 | Keyword Planner | `0ffb2783` |
| 2 | Google Search API (SearchAPI.io) | (see source) |
| 3 | Google Ads Transparency Center | (see source) |
| 4 | Google Trends Analyzer | (see source) |
| 5 | Package Installer | `9de09fd1` |

**Builtin Tools (10):** `code_interpreter`, `query_executor`, `csv_reader`, `string_matcher`, `display_file`, `file_search`, `browser_use`, `researcher`, `google_web_search`, `web_scraper`

<details>
<summary><strong>System Prompt</strong></summary>

```markdown
# Research & Intelligence Sub-Agent

## Identity
You are a specialized market research and competitive intelligence expert for Google
Ads. Your job is to gather external intelligence and return **strategic insights** to
the main Google Ads Agent.

## Core Principle
**INSIGHT OVER INFORMATION.** Don't just report what you found - explain what it means
for the user's Google Ads strategy. Always:
- Connect findings to actionable Google Ads decisions
- Highlight competitive gaps and opportunities
- Identify trends that impact bidding, targeting, or creative
- Summarize large datasets into digestible intelligence

## Output Templates
- Keyword Research → Priority Keywords, Budget Consideration, Match Type Strategy
- Competitor Analysis → Messaging Themes, Platform Priority, Ad Longevity, Creative Approach
- Trend Analysis → Budget Timing, Targeting, Keyword Expansion, Competitive Timing

## Rules
1. Always provide strategic context — don't just show numbers
2. Limit tables to 15 rows max
3. Connect every insight to a Google Ads action
4. Flag data freshness
5. Compare to benchmarks when available
6. Identify quick wins
7. Note limitations (Trends data is indexed 0-100, not absolute volume)
```

</details>

---

### 3 — Optimization Sub-Agent

| Property | Value |
|----------|-------|
| **Agent ID** | `9f3a2bb4-67a5-4818-9e4c-d53dd694f3ae` |
| **Model** | `claude-opus-4-5` |
| **Access Level** | CHAT_ONLY |
| **Core Principle** | *Preview before execute.* Never make changes without showing exactly what will happen. |

**Custom Actions:** ⚠️ **NONE CREATED** — System prompt references two actions that need to be built:

| Referenced Action | Status | Description |
|-------------------|--------|-------------|
| Recommendations Manager - API | ❌ Not implemented | `list`, `apply`, `dismiss`, `get_score` |
| Bulk Operations Manager - API | ❌ Not implemented | `bulk_pause`, `bulk_enable`, `bulk_bid_change`, `bulk_budget_change`, `export` |

**Builtin Tools (10):** `code_interpreter`, `query_executor`, `csv_reader`, `string_matcher`, `display_file`, `file_search`, `browser_use`, `researcher`, `google_web_search`, `web_scraper`

<details>
<summary><strong>System Prompt</strong></summary>

```markdown
# Optimization Sub-Agent

## Identity
You are a specialized Google Ads optimization expert focused on bulk operations and
implementing Google's recommendations. Your job is to analyze optimization opportunities,
preview changes, and execute approved modifications efficiently.

## Core Principle
**PREVIEW BEFORE EXECUTE.** Never make changes without showing the user exactly what
will happen. Always:
- Show clear before/after comparisons
- Calculate estimated impact
- Get explicit confirmation before ANY write operation
- Summarize bulk operations concisely
- Provide rollback instructions after execution
```

</details>

---

### 4 — Shopping & PMax Sub-Agent

| Property | Value |
|----------|-------|
| **Agent ID** | `474e12e3-af1d-4b36-8851-6ee1bca996aa` |
| **Model** | `claude-opus-4-5` |
| **Access Level** | CHAT_ONLY |
| **Core Principle** | *E-commerce focused.* Everything connects to product sales and ROAS. |

**Custom Actions:** ⚠️ **NONE CREATED** — System prompt references one action that needs to be built:

| Referenced Action | Status | Operations |
|-------------------|--------|-----------|
| Shopping & PMax Manager - API | ❌ Not implemented | `list_shopping`, `list_pmax`, `list_asset_groups`, `get_product_performance`, `get_pmax_performance`, `get_pmax_insights`, `pause_asset_group`, `enable_asset_group` |

**Builtin Tools (10):** `code_interpreter`, `query_executor`, `csv_reader`, `string_matcher`, `display_file`, `file_search`, `browser_use`, `researcher`, `google_web_search`, `web_scraper`

<details>
<summary><strong>System Prompt</strong></summary>

```markdown
# Shopping & PMax Sub-Agent

## Identity
You are a specialized Google Ads expert focused exclusively on Shopping campaigns and
Performance Max. Your job is to analyze product performance, manage asset groups, and
provide PMax-specific insights.

## Core Principle
**E-COMMERCE FOCUSED.** Everything you report should connect to product sales and ROAS.
Always:
- Lead with revenue and ROAS metrics (not just clicks/impressions)
- Identify top and bottom performing products clearly
- Highlight asset group opportunities in PMax
- Connect insights to feed optimization and bidding decisions
- Remember: for Shopping/PMax, ROAS is king

## Rules
1. Always show ROAS prominently — #1 metric for e-commerce
2. Identify clear winners and losers — Top 10 / Bottom 10 format
3. Connect every insight to an action — don't just report, recommend
4. Flag ad strength issues immediately — POOR/AVERAGE = priority fix
5. Acknowledge PMax limitations — limited visibility into channels, be transparent
6. Use performance labels — BEST/GOOD/LOW are actionable signals
7. Compare to averages — show performance vs. campaign/account average
```

</details>

---

### 5 — Creative Sub-Agent

| Property | Value |
|----------|-------|
| **Agent ID** | `a1000ff9-63c7-4a99-a6fd-45c25cf361ef` |
| **Model** | `claude-opus-4-5` |
| **Access Level** | CHAT_ONLY |
| **Core Principle** | *Visual first.* Show how ads will look before anything else. |

**Custom Actions (2):**

| # | Action | ID |
|---|--------|----|
| 1 | Responsive Display Ads Manager | `0850dd7c` |
| 2 | Demand Gen Ads Manager | `0e42ea37` |

**Builtin Tools (10):** `code_interpreter`, `query_executor`, `csv_reader`, `string_matcher`, `display_file`, `file_search`, `browser_use`, `google_web_search`, `researcher`, `web_scraper`

<details>
<summary><strong>System Prompt (excerpt)</strong></summary>

```markdown
# Creative Sub-Agent

## Identity
You manage Responsive Display Ads and Demand Gen campaigns — creating, previewing, and
optimizing visual ad formats across Display, YouTube, Discover, and Gmail.

## Core Principle
**VISUAL FIRST.** Always show the user how their ad will look before anything else.

## Rules
1. Always mention preview availability
2. Limit to 3 ads per response — offer pagination
3. Include approval status (APPROVED/PENDING/DISAPPROVED)
4. Note placement differences across YouTube vs. Discover vs. Gmail
5. Suggest improvements — don't just report, recommend creative changes
6. Show asset counts — users need to know if they're missing required/recommended assets
```

</details>

---

### 6 — Creative Innovate Tool

| Property | Value |
|----------|-------|
| **Agent ID** | `08be59bb-819d-48fd-b2f7-851d002ae201` |
| **Model** | `claude-sonnet-4-5` *(lighter model for processing tasks)* |
| **Access Level** | CHAT_ONLY |
| **Version** | v5.11.0 (prompt) / v5.16.0 (Cloudinary) / v5.15.0 (Gemini) |
| **Core Capability** | Cloudinary + Gemini-powered creative asset processing |

**Custom Actions (3):**

| # | Action | Integration |
|---|--------|------------|
| 1 | Cloudinary Creative Tools | Cloudinary API |
| 2 | Gemini Vision / Gen Fill | Google AI |
| 3 | Package Installer | N/A |

**AI Routing:**

| Target | AI Service | Ratios |
|--------|------------|--------|
| Social Media | 🍌 Gemini | 1:1, 4:5, 3:4, 9:16, 16:9, 2:3 |
| Display Ads | ☁️ Cloudinary | 728×90, 300×250, 160×600, etc. |
| Video | 🎬 Veo 3.1 | 16:9, 9:16 |

**Platform Presets:** Instagram (feed, story, reel), TikTok, YouTube (shorts, standard, thumbnail), Facebook (feed, story), LinkedIn, Twitter, Pinterest, plus all IAB display sizes.

<details>
<summary><strong>System Prompt (excerpt)</strong></summary>

```markdown
# Creative Innovate Tool v5.11.0
## Cloudinary & Gemini-Powered Creative Asset Processing

## Identity
You are the Creative Innovate Tool, an AI assistant that helps paid media strategists
prepare creative assets for advertising campaigns. You work as a sub-agent of the
Google Ads Agent, handling all creative asset tasks.

Your job: Receive asset URLs or IDs → Process with appropriate AI → Return ready-to-use URLs.

## Quick Actions
- Upload: "Upload this image: [URL]"
- Resize Social: "Resize for Instagram" → Feed, Portrait, Tall, Story, Reel
- Resize Display: "Resize for leaderboard" → 728×90
- Batch: "Resize for all social platforms"
- Gen Fill: "Extend this image to 9:16 for Stories"
```

</details>

---

## Credential Configuration

### Pattern A: 5-Key Google Ads (12 actions)

```json
{
  "integration": "google_ads",
  "secrets": [
    {"key": "GOOGLE_ADS_DEVELOPER_TOKEN"},
    {"key": "GOOGLE_ADS_CLIENT_ID"},
    {"key": "GOOGLE_ADS_CLIENT_SECRET"},
    {"key": "GOOGLE_ADS_REFRESH_TOKEN"},
    {"key": "GOOGLE_ADS_LOGIN_CUSTOMER_ID"}
  ]
}
```

**Used by:** Label Manager, Conversion Tracking Manager, Scripts Manager, Experiments Manager, Query Planner, Recommendations Manager, Device Performance Manager, Change History Manager, Campaign Creator, Ad Schedule Manager, Bidding Strategy Manager, PMax Asset Group Manager

### Pattern B: 4-Key Google Ads (13 actions)

```json
{
  "integration": "google_ads",
  "secrets": [
    {"key": "DEVELOPER_TOKEN"},
    {"key": "CLIENT_ID"},
    {"key": "CLIENT_SECRET"},
    {"key": "REFRESH_TOKEN"}
  ]
}
```

**Used by:** Audience Manager, Asset Manager, Budget Manager, RSA Ad Manager, Bid & Keyword Manager, Negative Keywords Manager, Campaign & Ad Group Manager, Google Ads Mutate, Account Access Checker, Check User Access Levels, API Gateway, Search Term Manager, Geo & Location Manager

> Note: Pattern B actions accept `login_customer_id` as a function parameter rather than a stored secret.

### Pattern C: 3-Key Cloudinary (1 action)

```json
{
  "integration": "default",
  "secrets": [
    {"key": "CLOUDINARY_CLOUD_NAME"},
    {"key": "CLOUDINARY_API_KEY"},
    {"key": "CLOUDINARY_API_SECRET"}
  ]
}
```

**Used by:** Cloudinary Creative Tools

### Pattern D: No Credentials (3 actions)

**Used by:** Package Installer, Session & State Manager, Generate Reconstruction Doc

> ⚠️ Each action instance has unique `client_credential_id` values per secret key. When rebuilding, new IDs are auto-generated.

---

## Known Issues & Gaps

| Issue | Severity | Affected Agent | Details |
|-------|----------|----------------|---------|
| Shopping & PMax Manager action not built | 🔴 Critical | Shopping & PMax [4] | System prompt references full API but no custom action exists |
| Optimization actions not built | 🔴 Critical | Optimization [3] | Both Recommendations Manager and Bulk Operations Manager are spec-only |
| API version mismatch | 🟡 Medium | Reporting [1] | Interactive Keyword/Ad Viewers use v18, others use v19 |
| No datasets assigned | 🟡 Medium | Shopping & PMax [4] | If historical data exists in NinjaCat, should be attached |
| Sub-agent prompt references missing actions | 🟡 Medium | Optimization [3], Shopping [4] | Prompts describe capabilities that don't exist yet |

---

## Reconstruction Checklist

### Phase 1: Foundation

- [ ] Create agent: **Google Ads Agent [beta/live-write/read]**
- [ ] Set model to `claude-opus-4-5`
- [ ] Set access level to PRIVATE
- [ ] Paste full system prompt (Enterprise Edition v10.0)
- [ ] Set sub-agent description for delegation

### Phase 2: Builtin Tools

- [ ] Enable all 10 builtin tools

### Phase 3: Custom Actions (28 total)

**Pattern A — 5-Key Google Ads (12 actions):**

- [ ] Label Manager
- [ ] Conversion Tracking Manager
- [ ] Scripts Manager
- [ ] Experiments Manager
- [ ] Query Planner & Budget Manager
- [ ] Recommendations Manager
- [ ] Device Performance Manager
- [ ] Change History Manager
- [ ] Campaign Creator (v22)
- [ ] Ad Schedule Manager (v22)
- [ ] Bidding Strategy Manager (v22)
- [ ] PMax Asset Group Manager (v22)

**Pattern B — 4-Key Google Ads (13 actions):**

- [ ] Audience Manager
- [ ] Asset Manager
- [ ] Budget Manager
- [ ] RSA Ad Manager
- [ ] Bid & Keyword Manager
- [ ] Negative Keywords Manager
- [ ] Campaign & Ad Group Manager
- [ ] Google Ads Mutate
- [ ] Account Access Checker
- [ ] Check User Access Levels
- [ ] API Gateway - Context Manager
- [ ] Search Term Manager
- [ ] Geo & Location Targeting Manager

**Pattern C — 3-Key Cloudinary (1 action):**

- [ ] Cloudinary Creative Tools

**Pattern D — No Credentials (3 actions):**

- [ ] Package Installer
- [ ] Session & State Manager
- [ ] Generate Reconstruction Doc

### Phase 4: Sub-Agents (6 total)

- [ ] **[1 of 5]** Reporting & Analysis — 8 custom actions, 9 builtin tools
- [ ] **[2 of 5]** Research & Intelligence — 5 custom actions, 10 builtin tools
- [ ] **[3 of 5]** Optimization — ⚠️ 2 actions need to be built first
- [ ] **[4 of 5]** Shopping & PMax — ⚠️ 1 action needs to be built first
- [ ] **[5 of 5]** Creative — 2 custom actions, 10 builtin tools
- [ ] **[Tool]** Creative Innovate Tool — Cloudinary + Gemini, runs on Sonnet 4.5

### Phase 5: User Access

- [ ] Grant CAN_EDIT to 5 shared users

### Phase 6: Validation

- [ ] Test Account Access Checker → `test_connection`
- [ ] Test Query Planner → `get_account_summary`
- [ ] Test a read operation (Campaign Manager → `list_campaigns`)
- [ ] Test a write operation with PAUSED entity
- [ ] Test sub-agent delegation with a large data request
- [ ] Test Cloudinary integration with a test upload

---

## Source Code

All 28 main agent action source files plus sub-agent action source files are maintained in separate Python files. Each action follows this pattern:

```python
import subprocess
subprocess.check_call(["pip", "install", "google-ads>=28.1.0"])

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

def get_client():
    return GoogleAdsClient.load_from_dict({
        "developer_token": secrets["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "client_id": secrets["GOOGLE_ADS_CLIENT_ID"],
        "client_secret": secrets["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token": secrets["GOOGLE_ADS_REFRESH_TOKEN"],
        "login_customer_id": secrets.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", ""),
        "use_proto_plus": True
    })

def resolve_customer_id(client, search=None, customer_id=None):
    # Auto-resolves account name to customer_id via MCC
    ...

def run(**params):
    # Main entry point for each action
    ...
```

---

## User Access

| # | User ID | Access Level | Added |
|---|---------|-------------|-------|
| 1 | 10481230 | CAN_EDIT | 2026-02-06 |
| 2 | 10481240 | CAN_EDIT | 2026-02-06 |
| 3 | 10481271 | CAN_EDIT | 2026-02-06 |
| 4 | 10481257 | CAN_EDIT | 2026-02-06 |
| 5 | 10481275 | CAN_EDIT | 2026-02-06 |

**Owner:** User ID 10481239

---

## Category Index

| Category | Actions |
|----------|---------|
| **Strategic Planning** | Query Planner & Budget Manager |
| **Campaign Lifecycle** | Campaign Creator, Campaign & Ad Group Manager, Bid & Keyword Manager, RSA Ad Manager, Budget Manager, Google Ads Mutate |
| **Bidding & Optimization** | Bidding Strategy Manager, Ad Schedule Manager, Recommendations Manager |
| **Targeting** | Geo & Location Manager, Device Performance Manager, Audience Manager |
| **Analysis** | Search Term Manager, Change History Manager, Conversion Tracking Manager |
| **PMax & Experiments** | PMax Asset Group Manager, Experiments Manager |
| **Organization** | Label Manager, Negative Keywords Manager, Asset Manager |
| **Infrastructure** | Account Access Checker, API Gateway, Session & State Manager, Package Installer, Check User Access, Scripts Manager |
| **Creative** | Cloudinary Creative Tools |

---

> **Generated:** 2026-02-10  
> **Agent ID:** `dc78f37b-99ce-4c7a-b912-704b1aa78156`  
> **Version:** Enterprise Edition v10.0
