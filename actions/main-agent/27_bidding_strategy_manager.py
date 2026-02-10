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

def switch_bidding_strategy(client, cid, campaign_id, new_strategy, target_cpa=None, target_roas=None, max_cpc_limit=None):
    svc = client.get_service("CampaignService")
    op = client.get_type("CampaignOperation"); c = op.update
    c.resource_name = f"customers/{cid}/campaigns/{campaign_id}"
    fm = []
    if new_strategy == "MAXIMIZE_CONVERSIONS": c.maximize_conversions.target_cpa_micros = int(target_cpa*MICROS) if target_cpa else 0; fm.append("maximize_conversions")
    elif new_strategy == "TARGET_CPA":
        if not target_cpa: return {"status": "error", "message": "target_cpa required"}
        c.target_cpa.target_cpa_micros = int(target_cpa*MICROS)
        if max_cpc_limit: c.target_cpa.cpc_bid_ceiling_micros = int(max_cpc_limit*MICROS)
        fm.append("target_cpa")
    elif new_strategy == "MAXIMIZE_CONVERSION_VALUE": c.maximize_conversion_value.target_roas = target_roas if target_roas else 0; fm.append("maximize_conversion_value")
    elif new_strategy == "TARGET_ROAS":
        if not target_roas: return {"status": "error", "message": "target_roas required"}
        c.target_roas.target_roas = target_roas
        if max_cpc_limit: c.target_roas.cpc_bid_ceiling_micros = int(max_cpc_limit*MICROS)
        fm.append("target_roas")
    elif new_strategy == "MAXIMIZE_CLICKS": c.maximize_clicks.cpc_bid_ceiling_micros = int(max_cpc_limit*MICROS) if max_cpc_limit else 0; fm.append("maximize_clicks")
    elif new_strategy == "MANUAL_CPC": c.manual_cpc.enhanced_cpc_enabled = True; fm.append("manual_cpc")
    else: return {"status": "error", "message": f"Unknown strategy: {new_strategy}"}
    op.update_mask.paths.extend(fm)
    try:
        r = svc.mutate_campaigns(customer_id=cid, operations=[op])
        return {"status": "success", "message": f"Strategy changed to {new_strategy}", "campaign_id": campaign_id, "target_cpa_dollars": target_cpa, "target_roas": target_roas, "resource_name": r.results[0].resource_name}
    except GoogleAdsException as ex: return {"status": "error", "message": str(ex.failure.errors[0].message)}

def create_portfolio_strategy(client, cid, name, strategy_type, target_cpa=None, target_roas=None, max_cpc_limit=None):
    op = client.get_type("BiddingStrategyOperation"); s = op.create; s.name = name
    if strategy_type == "TARGET_CPA":
        if not target_cpa: return {"status": "error", "message": "target_cpa required"}
        s.target_cpa.target_cpa_micros = int(target_cpa*MICROS)
        if max_cpc_limit: s.target_cpa.cpc_bid_ceiling_micros = int(max_cpc_limit*MICROS)
    elif strategy_type == "TARGET_ROAS":
        if not target_roas: return {"status": "error", "message": "target_roas required"}
        s.target_roas.target_roas = target_roas
    elif strategy_type == "MAXIMIZE_CONVERSIONS":
        if target_cpa: s.maximize_conversions.target_cpa_micros = int(target_cpa*MICROS)
    elif strategy_type == "MAXIMIZE_CONVERSION_VALUE":
        if target_roas: s.maximize_conversion_value.target_roas = target_roas
    else: return {"status": "error", "message": f"Invalid strategy_type"}
    try:
        r = client.get_service("BiddingStrategyService").mutate_bidding_strategies(customer_id=cid, operations=[op])
        return {"status": "success", "message": f"Portfolio '{name}' created", "strategy_id": r.results[0].resource_name.split("/")[-1], "resource_name": r.results[0].resource_name}
    except GoogleAdsException as ex: return {"status": "error", "message": str(ex.failure.errors[0].message)}

def run(action, search=None, customer_id=None, campaign_id=None, new_strategy=None, target_cpa=None, target_roas=None, max_cpc_limit=None, name=None, strategy_type=None, portfolio_strategy_id=None, portfolio_only=False, cost_min=None, conversions_min=None, date_range="LAST_30_DAYS", limit=100):
    client = get_client(); cid = resolve_customer_id(client, search, customer_id)
    if action == "list_bidding_strategies":
        ga = client.get_service("GoogleAdsService")
        results = []
        for row in ga.search(customer_id=cid, query="SELECT bidding_strategy.id, bidding_strategy.name, bidding_strategy.type, bidding_strategy.status, bidding_strategy.campaign_count, bidding_strategy.target_cpa.target_cpa_micros, bidding_strategy.target_roas.target_roas, metrics.cost_micros, metrics.conversions FROM bidding_strategy"):
            cd = row.metrics.cost_micros/MICROS if row.metrics.cost_micros else 0; conv = row.metrics.conversions or 0
            if cost_min and cd < cost_min: continue
            if conversions_min and conv < conversions_min: continue
            st = str(row.bidding_strategy.type_).replace("BiddingStrategyTypeEnum.BiddingStrategyType.", "")
            if strategy_type and strategy_type.upper() != st: continue
            tcpa = row.bidding_strategy.target_cpa.target_cpa_micros/MICROS if row.bidding_strategy.target_cpa.target_cpa_micros else None
            tr = row.bidding_strategy.target_roas.target_roas if row.bidding_strategy.target_roas.target_roas else None
            results.append({"id": str(row.bidding_strategy.id), "name": row.bidding_strategy.name, "type": st, "campaign_count": row.bidding_strategy.campaign_count, "target_cpa_dollars": round(tcpa, 2) if tcpa else None, "target_roas": round(tr, 2) if tr else None, "cost_dollars": round(cd, 2), "conversions": round(conv, 2), "is_portfolio": True})
        return {"status": "success", "bidding_strategies": results[:limit], "total_found": len(results)}
    elif action == "switch_bidding_strategy":
        if not campaign_id or not new_strategy: return {"status": "error", "message": "campaign_id and new_strategy required"}
        return switch_bidding_strategy(client, cid, campaign_id, new_strategy, target_cpa, target_roas, max_cpc_limit)
    elif action == "set_target_cpa":
        if not campaign_id or not target_cpa: return {"status": "error", "message": "campaign_id and target_cpa required"}
        return switch_bidding_strategy(client, cid, campaign_id, "TARGET_CPA", target_cpa=target_cpa, max_cpc_limit=max_cpc_limit)
    elif action == "set_target_roas":
        if not campaign_id or not target_roas: return {"status": "error", "message": "campaign_id and target_roas required"}
        return switch_bidding_strategy(client, cid, campaign_id, "TARGET_ROAS", target_roas=target_roas, max_cpc_limit=max_cpc_limit)
    elif action == "create_portfolio_strategy":
        if not name or not strategy_type: return {"status": "error", "message": "name and strategy_type required"}
        return create_portfolio_strategy(client, cid, name, strategy_type, target_cpa, target_roas, max_cpc_limit)
    elif action == "add_to_portfolio":
        if not campaign_id or not portfolio_strategy_id: return {"status": "error", "message": "campaign_id and portfolio_strategy_id required"}
        op = client.get_type("CampaignOperation"); c = op.update
        c.resource_name = f"customers/{cid}/campaigns/{campaign_id}"; c.bidding_strategy = f"customers/{cid}/biddingStrategies/{portfolio_strategy_id}"
        op.update_mask.paths.append("bidding_strategy")
        try:
            r = client.get_service("CampaignService").mutate_campaigns(customer_id=cid, operations=[op])
            return {"status": "success", "message": f"Campaign added to portfolio {portfolio_strategy_id}"}
        except GoogleAdsException as ex: return {"status": "error", "message": str(ex.failure.errors[0].message)}
    else: return {"status": "error", "message": f"Unknown action: {action}"}
python
