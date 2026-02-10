# ============================================
import subprocess
subprocess.check_call(["pip", "install", "google-ads>=28.1.0"])
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

MICROS = 1_000_000

def get_client():
    return GoogleAdsClient.load_from_dict({"developer_token": secrets["GOOGLE_ADS_DEVELOPER_TOKEN"], "client_id": secrets["GOOGLE_ADS_CLIENT_ID"], "client_secret": secrets["GOOGLE_ADS_CLIENT_SECRET"], "refresh_token": secrets["GOOGLE_ADS_REFRESH_TOKEN"], "login_customer_id": secrets.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", ""), "use_proto_plus": True})

def resolve_customer_id(client, search=None, customer_id=None):
    if customer_id: return customer_id.replace("-", "")
    login_id = secrets.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")
    for row in client.get_service("GoogleAdsService").search(customer_id=login_id, query="SELECT customer_client.id, customer_client.descriptive_name FROM customer_client WHERE customer_client.manager = FALSE"):
        if search.lower() in row.customer_client.descriptive_name.lower(): return str(row.customer_client.id)
    raise ValueError(f"No account found matching '{search}'")

def create_budget(client, cid, name, daily_budget_dollars):
    op = client.get_type("CampaignBudgetOperation"); b = op.create
    b.name = f"{name} Budget"; b.amount_micros = int(daily_budget_dollars * MICROS); b.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
    return client.get_service("CampaignBudgetService").mutate_campaign_budgets(customer_id=cid, operations=[op]).results[0].resource_name

def add_geo_targets(client, cid, campaign_id, geo_targets):
    cc_svc = client.get_service("CampaignCriterionService"); gtc_svc = client.get_service("GeoTargetConstantService")
    ops = []; results = []
    for t in geo_targets:
        if str(t).isdigit(): geo_id = t
        else:
            req = client.get_type("SuggestGeoTargetConstantsRequest"); req.locale = "en"; req.location_names.names.append(t)
            try:
                resp = gtc_svc.suggest_geo_target_constants(request=req)
                if resp.geo_target_constant_suggestions: geo_id = resp.geo_target_constant_suggestions[0].geo_target_constant.id
                else: results.append({"target": t, "status": "not_found"}); continue
            except: results.append({"target": t, "status": "error"}); continue
        op = client.get_type("CampaignCriterionOperation"); c = op.create
        c.campaign = f"customers/{cid}/campaigns/{campaign_id}"; c.location.geo_target_constant = f"geoTargetConstants/{geo_id}"
        ops.append(op); results.append({"target": t, "geo_id": geo_id, "status": "added"})
    if ops:
        try: cc_svc.mutate_campaign_criteria(customer_id=cid, operations=ops)
        except GoogleAdsException as ex: return {"status": "error", "message": str(ex.failure.errors[0].message)}
    return {"status": "success", "locations": results}

def create_search_campaign(client, cid, name, daily_budget, bidding_strategy, target_cpa=None, target_roas=None, geo_targets=None, start_date=None, end_date=None, status="PAUSED"):
    budget_resource = create_budget(client, cid, name, daily_budget)
    op = client.get_type("CampaignOperation"); c = op.create
    c.name = name; c.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SEARCH; c.campaign_budget = budget_resource
    c.status = client.enums.CampaignStatusEnum.PAUSED if status == "PAUSED" else client.enums.CampaignStatusEnum.ENABLED
    if bidding_strategy == "MAXIMIZE_CONVERSIONS": c.maximize_conversions.target_cpa_micros = int(target_cpa * MICROS) if target_cpa else 0
    elif bidding_strategy == "TARGET_CPA":
        if not target_cpa: return {"status": "error", "message": "target_cpa required"}
        c.target_cpa.target_cpa_micros = int(target_cpa * MICROS)
    elif bidding_strategy == "TARGET_ROAS":
        if not target_roas: return {"status": "error", "message": "target_roas required"}
        c.target_roas.target_roas = target_roas
    elif bidding_strategy == "MAXIMIZE_CLICKS": c.maximize_clicks.cpc_bid_ceiling_micros = 0
    elif bidding_strategy == "MANUAL_CPC": c.manual_cpc.enhanced_cpc_enabled = True
    else: c.maximize_conversions.target_cpa_micros = 0
    if start_date: c.start_date = start_date.replace("-", "")
    if end_date: c.end_date = end_date.replace("-", "")
    c.network_settings.target_google_search = True; c.network_settings.target_search_network = True; c.network_settings.target_content_network = False
    try:
        resp = client.get_service("CampaignService").mutate_campaigns(customer_id=cid, operations=[op])
        cid_new = resp.results[0].resource_name.split("/")[-1]
        geo_result = add_geo_targets(client, cid, cid_new, geo_targets) if geo_targets else None
        return {"status": "success", "message": f"Search campaign '{name}' created ({status})", "campaign_id": cid_new, "resource_name": resp.results[0].resource_name, "daily_budget_dollars": daily_budget, "bidding_strategy": bidding_strategy, "target_cpa_dollars": target_cpa, "geo_targeting": geo_result, "next_steps": ["1. Create ad group", "2. Add keywords", "3. Create RSA ads", "4. Enable when ready"]}
    except GoogleAdsException as ex: return {"status": "error", "message": str(ex.failure.errors[0].message)}

def create_pmax_campaign(client, cid, name, daily_budget, target_cpa=None, target_roas=None, geo_targets=None, status="PAUSED"):
    budget_resource = create_budget(client, cid, name, daily_budget)
    op = client.get_type("CampaignOperation"); c = op.create
    c.name = name; c.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.PERFORMANCE_MAX; c.campaign_budget = budget_resource
    c.status = client.enums.CampaignStatusEnum.PAUSED if status == "PAUSED" else client.enums.CampaignStatusEnum.ENABLED
    if target_roas: c.maximize_conversion_value.target_roas = target_roas
    elif target_cpa: c.maximize_conversions.target_cpa_micros = int(target_cpa * MICROS)
    else: c.maximize_conversion_value.target_roas = 0
    c.url_expansion_opt_out = False
    try:
        resp = client.get_service("CampaignService").mutate_campaigns(customer_id=cid, operations=[op])
        cid_new = resp.results[0].resource_name.split("/")[-1]
        geo_result = add_geo_targets(client, cid, cid_new, geo_targets) if geo_targets else None
        return {"status": "success", "message": f"PMax campaign '{name}' created ({status})", "campaign_id": cid_new, "daily_budget_dollars": daily_budget, "geo_targeting": geo_result}
    except GoogleAdsException as ex: return {"status": "error", "message": str(ex.failure.errors[0].message)}

def run(action, search=None, customer_id=None, name=None, daily_budget=None, bidding_strategy="MAXIMIZE_CONVERSIONS", target_cpa=None, target_roas=None, geo_targets=None, start_date=None, end_date=None, status="PAUSED", final_url=None):
    client = get_client(); cid = resolve_customer_id(client, search, customer_id)
    if not name: return {"status": "error", "message": "name required"}
    if not daily_budget: return {"status": "error", "message": "daily_budget (in dollars) required"}
    if action == "create_search_campaign": return create_search_campaign(client, cid, name, daily_budget, bidding_strategy, target_cpa, target_roas, geo_targets, start_date, end_date, status)
    elif action == "create_pmax_campaign": return create_pmax_campaign(client, cid, name, daily_budget, target_cpa, target_roas, geo_targets, status)
    elif action == "create_display_campaign":
        budget_resource = create_budget(client, cid, name, daily_budget)
        op = client.get_type("CampaignOperation"); c = op.create
        c.name = name; c.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.DISPLAY; c.campaign_budget = budget_resource
        c.status = client.enums.CampaignStatusEnum.PAUSED if status == "PAUSED" else client.enums.CampaignStatusEnum.ENABLED
        if target_cpa: c.maximize_conversions.target_cpa_micros = int(target_cpa * MICROS)
        else: c.maximize_conversions.target_cpa_micros = 0
        c.network_settings.target_content_network = True
        try:
            resp = client.get_service("CampaignService").mutate_campaigns(customer_id=cid, operations=[op])
            return {"status": "success", "message": f"Display campaign '{name}' created", "campaign_id": resp.results[0].resource_name.split("/")[-1]}
        except GoogleAdsException as ex: return {"status": "error", "message": str(ex.failure.errors[0].message)}
    else: return {"status": "error", "message": f"Unknown action: {action}"}
python
