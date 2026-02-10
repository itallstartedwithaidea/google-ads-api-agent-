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
    for row in ga_service.search(customer_id=login_id, query="SELECT customer_client.id, customer_client.descriptive_name FROM customer_client WHERE customer_client.manager = FALSE"):
        if search.lower() in row.customer_client.descriptive_name.lower(): return str(row.customer_client.id)
    raise ValueError(f"No account found matching '{search}'")

def list_recommendations(client, customer_id, rec_type=None, campaign_ids=None, impact_min=None, dismissed=False, limit=100):
    ga_service = client.get_service("GoogleAdsService")
    query = "SELECT recommendation.resource_name, recommendation.type, recommendation.campaign, recommendation.dismissed, recommendation.impact.base_metrics.impressions, recommendation.impact.base_metrics.clicks, recommendation.impact.base_metrics.cost_micros, recommendation.impact.base_metrics.conversions, recommendation.impact.potential_metrics.impressions, recommendation.impact.potential_metrics.clicks, recommendation.impact.potential_metrics.cost_micros, recommendation.impact.potential_metrics.conversions, campaign.id, campaign.name FROM recommendation"
    conditions = []
    if not dismissed: conditions.append("recommendation.dismissed = FALSE")
    if rec_type: conditions.append(f"recommendation.type = '{rec_type}'")
    if conditions: query += " WHERE " + " AND ".join(conditions)
    results = []
    for row in ga_service.search(customer_id=customer_id, query=query):
        if campaign_ids and str(row.campaign.id) not in [str(c) for c in campaign_ids]: continue
        base_cost = row.recommendation.impact.base_metrics.cost_micros / MICROS if row.recommendation.impact.base_metrics.cost_micros else 0
        pot_cost = row.recommendation.impact.potential_metrics.cost_micros / MICROS if row.recommendation.impact.potential_metrics.cost_micros else 0
        cost_impact = pot_cost - base_cost
        base_conv = row.recommendation.impact.base_metrics.conversions or 0
        pot_conv = row.recommendation.impact.potential_metrics.conversions or 0
        conv_impact = pot_conv - base_conv
        if impact_min is not None and abs(cost_impact) < impact_min and abs(conv_impact) < impact_min: continue
        results.append({"resource_name": row.recommendation.resource_name, "type": str(row.recommendation.type).replace("RecommendationTypeEnum.RecommendationType.", ""), "campaign_id": str(row.campaign.id), "campaign_name": row.campaign.name, "impact": {"base_cost": round(base_cost, 2), "potential_cost": round(pot_cost, 2), "cost_impact": round(cost_impact, 2), "base_conversions": round(base_conv, 2), "potential_conversions": round(pot_conv, 2), "conversion_impact": round(conv_impact, 2)}})
    return {"status": "success", "recommendations": results[:limit], "total_found": len(results)}

def apply_recommendation(client, customer_id, resource_name):
    rec_service = client.get_service("RecommendationService")
    operation = client.get_type("ApplyRecommendationOperation")
    operation.resource_name = resource_name
    try:
        response = rec_service.apply_recommendation(customer_id=customer_id, operations=[operation])
        return {"status": "success", "message": "Recommendation applied", "resource_name": response.results[0].resource_name}
    except GoogleAdsException as ex:
        return {"status": "error", "message": str(ex.failure.errors[0].message)}

def dismiss_recommendation(client, customer_id, resource_name):
    rec_service = client.get_service("RecommendationService")
    operation = client.get_type("DismissRecommendationRequest.DismissRecommendationOperation")
    operation.resource_name = resource_name
    try:
        rec_service.dismiss_recommendation(customer_id=customer_id, operations=[operation])
        return {"status": "success", "message": "Recommendation dismissed"}
    except GoogleAdsException as ex:
        return {"status": "error", "message": str(ex.failure.errors[0].message)}

def run(action, search=None, customer_id=None, rec_type=None, campaign_ids=None, impact_min=None, dismissed=False, resource_name=None, limit=100):
    client = get_client(); cid = resolve_customer_id(client, search, customer_id)
    if action == "list_recommendations": return list_recommendations(client, cid, rec_type, campaign_ids, impact_min, dismissed, limit)
    elif action == "apply_recommendation":
        if not resource_name: return {"status": "error", "message": "resource_name required"}
        return apply_recommendation(client, cid, resource_name)
    elif action == "dismiss_recommendation":
        if not resource_name: return {"status": "error", "message": "resource_name required"}
        return dismiss_recommendation(client, cid, resource_name)
    elif action == "get_recommendation_impact":
        recs = list_recommendations(client, cid, rec_type, campaign_ids, None, False, limit * 2)
        if recs["status"] != "success": return recs
        type_summary = {}; total_cost_impact = 0; total_conv_impact = 0
        for rec in recs["recommendations"]:
            t = rec["type"]; i = rec["impact"]
            if t not in type_summary: type_summary[t] = {"type": t, "count": 0, "total_cost_impact": 0, "total_conversion_impact": 0}
            type_summary[t]["count"] += 1; type_summary[t]["total_cost_impact"] += i["cost_impact"]; type_summary[t]["total_conversion_impact"] += i["conversion_impact"]
            total_cost_impact += i["cost_impact"]; total_conv_impact += i["conversion_impact"]
        for t in type_summary.values(): t["total_cost_impact"] = round(t["total_cost_impact"], 2); t["total_conversion_impact"] = round(t["total_conversion_impact"], 2)
        return {"status": "success", "summary": {"total_recommendations": len(recs["recommendations"]), "total_cost_impact_dollars": round(total_cost_impact, 2), "total_conversion_impact": round(total_conv_impact, 2)}, "by_type": list(type_summary.values())}
    else: return {"status": "error", "message": f"Unknown action: {action}"}
