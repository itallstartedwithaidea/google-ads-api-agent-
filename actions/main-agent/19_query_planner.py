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
    ga_service = client.get_service("GoogleAdsService")
    response = ga_service.search(customer_id=login_id, query="SELECT customer_client.id, customer_client.descriptive_name FROM customer_client WHERE customer_client.manager = FALSE")
    for row in response:
        if search.lower() in row.customer_client.descriptive_name.lower(): return str(row.customer_client.id)
    raise ValueError(f"No account found matching '{search}'")

def get_account_summary(client, customer_id, date_range="LAST_30_DAYS"):
    ga_service = client.get_service("GoogleAdsService")
    try:
        response = ga_service.search(customer_id=customer_id, query=f"SELECT customer.id, customer.descriptive_name, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value, metrics.ctr, metrics.average_cpc FROM customer WHERE segments.date DURING {date_range}")
        account_data = None
        for row in response:
            account_data = {"customer_id": str(row.customer.id), "account_name": row.customer.descriptive_name, "total_impressions": row.metrics.impressions, "total_clicks": row.metrics.clicks, "total_cost": round(row.metrics.cost_micros / MICROS, 2), "total_conversions": round(row.metrics.conversions, 2), "avg_ctr": round(row.metrics.ctr * 100, 2), "avg_cpc": round(row.metrics.average_cpc / MICROS, 2)}; break
        # Campaign counts
        response = ga_service.search(customer_id=customer_id, query="SELECT campaign.id, campaign.advertising_channel_type, campaign.status FROM campaign")
        type_counts = {}; status_counts = {"ENABLED": 0, "PAUSED": 0, "REMOVED": 0}; total = 0
        for row in response:
            total += 1
            ct = str(row.campaign.advertising_channel_type).replace("AdvertisingChannelTypeEnum.AdvertisingChannelType.", "")
            type_counts[ct] = type_counts.get(ct, 0) + 1
            cs = str(row.campaign.status).replace("CampaignStatusEnum.CampaignStatus.", "")
            if cs in status_counts: status_counts[cs] += 1
        ag_count = sum(1 for _ in ga_service.search(customer_id=customer_id, query="SELECT ad_group.id FROM ad_group WHERE ad_group.status != 'REMOVED'"))
        kw_count = sum(1 for _ in ga_service.search(customer_id=customer_id, query="SELECT ad_group_criterion.criterion_id FROM ad_group_criterion WHERE ad_group_criterion.type = 'KEYWORD' AND ad_group_criterion.status != 'REMOVED'"))
        return {"status": "success", "account_summary": account_data, "entity_counts": {"campaigns": total, "ad_groups": ag_count, "keywords": kw_count}, "campaigns_by_type": type_counts, "campaigns_by_status": status_counts, "date_range": date_range}
    except GoogleAdsException as ex:
        return {"status": "error", "message": str(ex.failure.errors[0].message)}

def build_query_plan(client, customer_id, intent, entity_type="CAMPAIGN", cost_min=None, cost_max=None, conversions_min=None, campaign_type=None, status="ENABLED", date_range="LAST_30_DAYS"):
    summary = get_account_summary(client, customer_id, date_range)
    if summary["status"] != "success": return summary
    estimated_rows = {"ACCOUNT": 1, "CAMPAIGN": summary["entity_counts"]["campaigns"], "AD_GROUP": summary["entity_counts"]["ad_groups"], "KEYWORD": summary["entity_counts"]["keywords"]}.get(entity_type.upper(), 100)
    if status == "ENABLED":
        ratio = summary["campaigns_by_status"].get("ENABLED", 0) / max(summary["entity_counts"]["campaigns"], 1)
        estimated_rows = int(estimated_rows * ratio)
    if cost_min: estimated_rows = int(estimated_rows * 0.3)
    if conversions_min: estimated_rows = int(estimated_rows * 0.2)
    action_map = {"CAMPAIGN": "Campaign Manager > list_campaigns", "AD_GROUP": "Campaign Manager > list_ad_groups", "KEYWORD": "Bid & Keyword Manager > list_keywords", "AD": "RSA Ad Manager > list"}
    return {"status": "success", "query_plan": {"intent": intent, "entity_type": entity_type, "estimated_rows": estimated_rows, "will_fit_in_single_query": estimated_rows <= 500, "recommended_action": action_map.get(entity_type.upper(), "Campaign Manager"), "recommended_filters": {"status": status, "date_range": date_range, "cost_min_dollars": cost_min, "cost_max_dollars": cost_max, "conversions_min": conversions_min, "campaign_type": campaign_type}, "account_context": summary["account_summary"]}}

def validate_completeness(client, customer_id, detail_cost_total, detail_row_count, entity_type="CAMPAIGN", date_range="LAST_30_DAYS"):
    summary = get_account_summary(client, customer_id, date_range)
    if summary["status"] != "success": return summary
    act = summary["account_summary"]["total_cost"]
    ec = summary["entity_counts"].get(entity_type.lower() + "s", 0)
    cost_pct = (detail_cost_total / act * 100) if act > 0 else 100
    row_pct = (detail_row_count / ec * 100) if ec > 0 else 100
    return {"status": "success", "validation": {"detail_cost_dollars": round(detail_cost_total, 2), "account_total_cost_dollars": act, "cost_completeness_pct": round(cost_pct, 1), "detail_row_count": detail_row_count, "account_entity_count": ec, "row_completeness_pct": round(row_pct, 1), "data_is_complete": cost_pct >= 99 and row_pct >= 99}}

def run(action, search=None, customer_id=None, date_range="LAST_30_DAYS", intent=None, entity_type="CAMPAIGN", cost_min=None, cost_max=None, conversions_min=None, campaign_type=None, status="ENABLED", detail_cost_total=None, detail_row_count=None):
    client = get_client(); cid = resolve_customer_id(client, search, customer_id)
    if action == "get_account_summary": return get_account_summary(client, cid, date_range)
    elif action == "build_query_plan": return build_query_plan(client, cid, intent, entity_type, cost_min, cost_max, conversions_min, campaign_type, status, date_range)
    elif action == "validate_completeness": return validate_completeness(client, cid, detail_cost_total, detail_row_count, entity_type, date_range)
    elif action == "estimate_row_count":
        ga_service = client.get_service("GoogleAdsService")
        q = {"CAMPAIGN": "SELECT campaign.id FROM campaign WHERE campaign.status != 'REMOVED'", "AD_GROUP": "SELECT ad_group.id FROM ad_group WHERE ad_group.status != 'REMOVED'", "KEYWORD": "SELECT ad_group_criterion.criterion_id FROM ad_group_criterion WHERE ad_group_criterion.type = 'KEYWORD' AND ad_group_criterion.status != 'REMOVED'"}.get(entity_type.upper())
        if not q: return {"status": "error", "message": f"Unsupported entity_type: {entity_type}"}
        count = sum(1 for _ in ga_service.search(customer_id=cid, query=q))
        if cost_min: count = int(count * 0.3)
        return {"status": "success", "estimated_rows": count, "will_need_pagination": count > 500}
    else: return {"status": "error", "message": f"Unknown action: {action}"}
