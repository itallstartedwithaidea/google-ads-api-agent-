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

def run(action, search=None, customer_id=None, campaign_id=None, campaign_ids=None, day_of_week=None, start_hour=None, end_hour=None, start_minute="ZERO", end_minute="ZERO", bid_modifier=1.0, criterion_resource_name=None, date_range="LAST_30_DAYS", cost_min=None, conversions_min=None, limit=100):
    client = get_client(); cid = resolve_customer_id(client, search, customer_id)
    ga = client.get_service("GoogleAdsService")

    if action == "get_ad_schedule":
        if not campaign_id: return {"status": "error", "message": "campaign_id required"}
        schedules = []
        for row in ga.search(customer_id=cid, query=f"SELECT campaign_criterion.resource_name, campaign_criterion.criterion_id, campaign_criterion.ad_schedule.day_of_week, campaign_criterion.ad_schedule.start_hour, campaign_criterion.ad_schedule.start_minute, campaign_criterion.ad_schedule.end_hour, campaign_criterion.ad_schedule.end_minute, campaign_criterion.bid_modifier FROM campaign_criterion WHERE campaign.id = {campaign_id} AND campaign_criterion.type = 'AD_SCHEDULE'"):
            schedules.append({"resource_name": row.campaign_criterion.resource_name, "criterion_id": str(row.campaign_criterion.criterion_id), "day_of_week": str(row.campaign_criterion.ad_schedule.day_of_week).replace("DayOfWeekEnum.DayOfWeek.", ""), "start_hour": row.campaign_criterion.ad_schedule.start_hour, "end_hour": row.campaign_criterion.ad_schedule.end_hour, "bid_modifier": row.campaign_criterion.bid_modifier})
        return {"status": "success", "schedules": schedules}

    elif action == "set_ad_schedule":
        if not campaign_id or not day_of_week or start_hour is None or end_hour is None: return {"status": "error", "message": "campaign_id, day_of_week, start_hour, end_hour required"}
        day_map = {d: getattr(client.enums.DayOfWeekEnum, d) for d in ["MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY","SUNDAY"]}
        minute_map = {m: getattr(client.enums.MinuteOfHourEnum, m) for m in ["ZERO","FIFTEEN","THIRTY","FORTY_FIVE"]}
        if day_of_week.upper() not in day_map: return {"status": "error", "message": f"Invalid day"}
        op = client.get_type("CampaignCriterionOperation"); c = op.create
        c.campaign = f"customers/{cid}/campaigns/{campaign_id}"
        c.ad_schedule.day_of_week = day_map[day_of_week.upper()]; c.ad_schedule.start_hour = start_hour; c.ad_schedule.end_hour = end_hour
        c.ad_schedule.start_minute = minute_map.get(start_minute.upper(), client.enums.MinuteOfHourEnum.ZERO)
        c.ad_schedule.end_minute = minute_map.get(end_minute.upper(), client.enums.MinuteOfHourEnum.ZERO)
        c.bid_modifier = bid_modifier
        try:
            r = client.get_service("CampaignCriterionService").mutate_campaign_criteria(customer_id=cid, operations=[op])
            return {"status": "success", "message": f"Schedule set for {day_of_week} {start_hour}:00-{end_hour}:00 @ {bid_modifier}x", "resource_name": r.results[0].resource_name}
        except GoogleAdsException as ex: return {"status": "error", "message": str(ex.failure.errors[0].message)}

    elif action == "remove_ad_schedule":
        if not criterion_resource_name: return {"status": "error", "message": "criterion_resource_name required"}
        op = client.get_type("CampaignCriterionOperation"); op.remove = criterion_resource_name
        try:
            client.get_service("CampaignCriterionService").mutate_campaign_criteria(customer_id=cid, operations=[op])
            return {"status": "success", "message": "Schedule removed"}
        except GoogleAdsException as ex: return {"status": "error", "message": str(ex.failure.errors[0].message)}

    elif action == "get_hourly_performance":
        query = f"SELECT campaign.id, campaign.name, segments.hour, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions FROM campaign WHERE segments.date DURING {date_range} AND campaign.status != 'REMOVED'"
        if campaign_ids: query += " AND campaign.id IN (" + ",".join([f"'{c}'" for c in campaign_ids]) + ")"
        hourly = {}
        for row in ga.search(customer_id=cid, query=query):
            h = row.segments.hour; cd = row.metrics.cost_micros/MICROS
            if cost_min and cd < cost_min: continue
            if h not in hourly: hourly[h] = {"hour": h, "impressions": 0, "clicks": 0, "cost": 0, "conversions": 0}
            hourly[h]["impressions"] += row.metrics.impressions; hourly[h]["clicks"] += row.metrics.clicks; hourly[h]["cost"] += cd; hourly[h]["conversions"] += row.metrics.conversions
        results = []
        for h in sorted(hourly.keys()):
            d = hourly[h]; d["cost"] = round(d["cost"], 2); d["conversions"] = round(d["conversions"], 2)
            d["ctr"] = round((d["clicks"]/d["impressions"]*100) if d["impressions"] > 0 else 0, 2)
            d["cpa"] = round(d["cost"]/d["conversions"], 2) if d["conversions"] > 0 else None
            results.append(d)
        return {"status": "success", "hourly_performance": results[:limit]}

    else: return {"status": "error", "message": f"Unknown action: {action}"}
python
