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

def list_device_performance(client, customer_id, date_range="LAST_30_DAYS", campaign_ids=None, cost_min=None, cost_max=None, conversions_min=None, ctr_min=None, ctr_max=None, conversion_rate_min=None, limit=100):
    ga_service = client.get_service("GoogleAdsService")
    query = f"SELECT campaign.id, campaign.name, segments.device, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.ctr, metrics.average_cpc, metrics.conversions_from_interactions_rate FROM campaign WHERE segments.date DURING {date_range} AND campaign.status != 'REMOVED'"
    if campaign_ids: query += " AND campaign.id IN (" + ", ".join([f"'{c}'" for c in campaign_ids]) + ")"
    results = []
    for row in ga_service.search(customer_id=customer_id, query=query):
        cd = row.metrics.cost_micros / MICROS; conv = row.metrics.conversions; ctr = row.metrics.ctr * 100; cr = row.metrics.conversions_from_interactions_rate * 100
        if cost_min and cd < cost_min: continue
        if cost_max and cd > cost_max: continue
        if conversions_min and conv < conversions_min: continue
        if ctr_min and ctr < ctr_min: continue
        if ctr_max and ctr > ctr_max: continue
        if conversion_rate_min and cr < conversion_rate_min: continue
        results.append({"campaign_id": str(row.campaign.id), "campaign_name": row.campaign.name, "device": str(row.segments.device).replace("DeviceEnum.Device.", ""), "impressions": row.metrics.impressions, "clicks": row.metrics.clicks, "cost": round(cd, 2), "conversions": round(conv, 2), "ctr": round(ctr, 2), "avg_cpc": round(row.metrics.average_cpc/MICROS, 2), "conversion_rate": round(cr, 2)})
    # Aggregate by device
    agg = {}
    for r in results:
        d = r["device"]
        if d not in agg: agg[d] = {"device": d, "impressions": 0, "clicks": 0, "cost": 0, "conversions": 0, "campaigns": set()}
        agg[d]["impressions"] += r["impressions"]; agg[d]["clicks"] += r["clicks"]; agg[d]["cost"] += r["cost"]; agg[d]["conversions"] += r["conversions"]; agg[d]["campaigns"].add(r["campaign_name"])
    final = []
    for d in agg.values():
        d["cost"] = round(d["cost"], 2); d["conversions"] = round(d["conversions"], 2)
        d["ctr"] = round((d["clicks"]/d["impressions"]*100) if d["impressions"] > 0 else 0, 2)
        d["campaign_count"] = len(d["campaigns"]); del d["campaigns"]; final.append(d)
    return {"status": "success", "device_performance": final[:limit]}

def run(action, search=None, customer_id=None, date_range="LAST_30_DAYS", campaign_ids=None, campaign_id=None, device=None, bid_modifier=None, cost_min=None, cost_max=None, conversions_min=None, ctr_min=None, ctr_max=None, conversion_rate_min=None, limit=100):
    client = get_client(); cid = resolve_customer_id(client, search, customer_id)
    if action == "list_device_performance": return list_device_performance(client, cid, date_range, campaign_ids, cost_min, cost_max, conversions_min, ctr_min, ctr_max, conversion_rate_min, limit)
    elif action == "update_device_bid_modifier":
        if not campaign_id or not device or bid_modifier is None: return {"status": "error", "message": "campaign_id, device, bid_modifier required"}
        device_map = {"MOBILE": client.enums.DeviceEnum.MOBILE, "DESKTOP": client.enums.DeviceEnum.DESKTOP, "TABLET": client.enums.DeviceEnum.TABLET}
        if device.upper() not in device_map: return {"status": "error", "message": "Use MOBILE, DESKTOP, or TABLET"}
        op = client.get_type("CampaignCriterionOperation"); c = op.create
        c.campaign = f"customers/{cid}/campaigns/{campaign_id}"; c.device.type_ = device_map[device.upper()]; c.bid_modifier = bid_modifier
        try:
            r = client.get_service("CampaignCriterionService").mutate_campaign_criteria(customer_id=cid, operations=[op])
            return {"status": "success", "message": f"Device bid modifier for {device} set to {bid_modifier}x", "resource_name": r.results[0].resource_name}
        except GoogleAdsException as ex: return {"status": "error", "message": str(ex.failure.errors[0].message)}
    elif action == "get_device_recommendations":
        perf = list_device_performance(client, cid, date_range, campaign_ids, cost_min, cost_max, conversions_min, ctr_min, ctr_max, conversion_rate_min, limit)
        recs = []
        for d in perf.get("device_performance", []):
            cpa = d["cost"]/d["conversions"] if d["conversions"] > 0 else float('inf')
            if d["conversion_rate"] > 5 and cpa < 50: recs.append({"device": d["device"], "recommendation": "INCREASE_BID", "reason": f"High conv rate ({d['conversion_rate']}%) good CPA (${cpa:.2f})", "suggested_modifier": 1.2})
            elif d["conversion_rate"] < 1 and d["cost"] > 100: recs.append({"device": d["device"], "recommendation": "DECREASE_BID", "reason": f"Low conv rate ({d['conversion_rate']}%) high spend (${d['cost']})", "suggested_modifier": 0.7})
        return {"status": "success", "recommendations": recs, "device_data": perf.get("device_performance", [])}
    else: return {"status": "error", "message": f"Unknown action: {action}"}
