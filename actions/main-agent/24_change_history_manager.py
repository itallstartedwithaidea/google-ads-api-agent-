import subprocess
subprocess.check_call(["pip", "install", "google-ads>=28.1.0"])
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from datetime import datetime, timedelta

def get_client():
    return GoogleAdsClient.load_from_dict({"developer_token": secrets["GOOGLE_ADS_DEVELOPER_TOKEN"], "client_id": secrets["GOOGLE_ADS_CLIENT_ID"], "client_secret": secrets["GOOGLE_ADS_CLIENT_SECRET"], "refresh_token": secrets["GOOGLE_ADS_REFRESH_TOKEN"], "login_customer_id": secrets.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", ""), "use_proto_plus": True})

def resolve_customer_id(client, search=None, customer_id=None):
    if customer_id: return customer_id.replace("-", "")
    login_id = secrets.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")
    for row in client.get_service("GoogleAdsService").search(customer_id=login_id, query="SELECT customer_client.id, customer_client.descriptive_name FROM customer_client WHERE customer_client.manager = FALSE"):
        if search.lower() in row.customer_client.descriptive_name.lower(): return str(row.customer_client.id)
    raise ValueError(f"No account found matching '{search}'")

def get_dates(dr):
    today = datetime.now()
    days = {"LAST_7_DAYS": 7, "LAST_14_DAYS": 14, "LAST_30_DAYS": 30, "LAST_90_DAYS": 90}.get(dr, 30)
    return (today - timedelta(days=days)).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")

def list_changes(client, cid, dr="LAST_30_DAYS", resource_type=None, campaign_ids=None, user_email=None, limit=100):
    ga = client.get_service("GoogleAdsService"); sd, ed = get_dates(dr)
    q = f"SELECT change_event.change_date_time, change_event.change_resource_type, change_event.change_resource_name, change_event.user_email, change_event.resource_change_operation, change_event.changed_fields, campaign.id, campaign.name FROM change_event WHERE change_event.change_date_time >= '{sd}' AND change_event.change_date_time <= '{ed} 23:59:59'"
    if resource_type: q += f" AND change_event.change_resource_type = '{resource_type}'"
    q += f" ORDER BY change_event.change_date_time DESC LIMIT {limit}"
    results = []
    for row in ga.search(customer_id=cid, query=q):
        if campaign_ids and str(row.campaign.id) not in [str(c) for c in campaign_ids]: continue
        if user_email and user_email.lower() not in row.change_event.user_email.lower(): continue
        results.append({"change_date_time": row.change_event.change_date_time, "resource_type": str(row.change_event.change_resource_type).replace("ChangeEventResourceTypeEnum.ChangeEventResourceType.", ""), "operation": str(row.change_event.resource_change_operation).replace("ResourceChangeOperationEnum.ResourceChangeOperation.", ""), "user_email": row.change_event.user_email, "changed_fields": str(row.change_event.changed_fields), "campaign_id": str(row.campaign.id), "campaign_name": row.campaign.name})
    return {"status": "success", "changes": results[:limit], "total_found": len(results)}

def list_budget_changes(client, cid, dr="LAST_30_DAYS", campaign_ids=None, limit=100):
    ga = client.get_service("GoogleAdsService"); sd, ed = get_dates(dr)
    q = f"SELECT change_event.change_date_time, change_event.user_email, change_event.resource_change_operation, campaign.id, campaign.name, campaign_budget.amount_micros FROM change_event WHERE change_event.change_date_time >= '{sd}' AND change_event.change_date_time <= '{ed} 23:59:59' AND change_event.change_resource_type = 'CAMPAIGN_BUDGET' ORDER BY change_event.change_date_time DESC LIMIT {limit*2}"
    results = []
    for row in ga.search(customer_id=cid, query=q):
        if campaign_ids and str(row.campaign.id) not in [str(c) for c in campaign_ids]: continue
        results.append({"change_date_time": row.change_event.change_date_time, "operation": str(row.change_event.resource_change_operation).replace("ResourceChangeOperationEnum.ResourceChangeOperation.", ""), "user_email": row.change_event.user_email, "campaign_id": str(row.campaign.id), "campaign_name": row.campaign.name, "current_daily_budget": round(row.campaign_budget.amount_micros/1000000, 2)})
    return {"status": "success", "budget_changes": results[:limit]}

def run(action, search=None, customer_id=None, change_date_range="LAST_30_DAYS", resource_type=None, campaign_ids=None, user_email=None, limit=100):
    client = get_client(); cid = resolve_customer_id(client, search, customer_id)
    if action == "list_changes": return list_changes(client, cid, change_date_range, resource_type, campaign_ids, user_email, limit)
    elif action == "list_budget_changes": return list_budget_changes(client, cid, change_date_range, campaign_ids, limit)
    elif action == "list_bid_changes":
        ga = client.get_service("GoogleAdsService"); sd, ed = get_dates(change_date_range)
        q = f"SELECT change_event.change_date_time, change_event.user_email, change_event.change_resource_type, change_event.resource_change_operation, change_event.changed_fields, campaign.id, campaign.name FROM change_event WHERE change_event.change_date_time >= '{sd}' AND change_event.change_date_time <= '{ed} 23:59:59' AND change_event.change_resource_type IN ('AD_GROUP', 'AD_GROUP_CRITERION', 'CAMPAIGN') ORDER BY change_event.change_date_time DESC LIMIT {limit*2}"
        results = []
        for row in ga.search(customer_id=cid, query=q):
            if campaign_ids and str(row.campaign.id) not in [str(c) for c in campaign_ids]: continue
            cf = str(row.change_event.changed_fields).lower()
            if any(x in cf for x in ['bid', 'cpc', 'cpa', 'roas']):
                results.append({"change_date_time": row.change_event.change_date_time, "resource_type": str(row.change_event.change_resource_type).replace("ChangeEventResourceTypeEnum.ChangeEventResourceType.", ""), "user_email": row.change_event.user_email, "changed_fields": cf, "campaign_id": str(row.campaign.id), "campaign_name": row.campaign.name})
        return {"status": "success", "bid_changes": results[:limit]}
    elif action == "list_status_changes":
        ga = client.get_service("GoogleAdsService"); sd, ed = get_dates(change_date_range)
        q = f"SELECT change_event.change_date_time, change_event.user_email, change_event.change_resource_type, change_event.resource_change_operation, change_event.changed_fields, campaign.id, campaign.name FROM change_event WHERE change_event.change_date_time >= '{sd}' AND change_event.change_date_time <= '{ed} 23:59:59' ORDER BY change_event.change_date_time DESC LIMIT {limit*3}"
        results = []
        for row in ga.search(customer_id=cid, query=q):
            if campaign_ids and str(row.campaign.id) not in [str(c) for c in campaign_ids]: continue
            if 'status' in str(row.change_event.changed_fields).lower():
                results.append({"change_date_time": row.change_event.change_date_time, "resource_type": str(row.change_event.change_resource_type).replace("ChangeEventResourceTypeEnum.ChangeEventResourceType.", ""), "user_email": row.change_event.user_email, "campaign_id": str(row.campaign.id), "campaign_name": row.campaign.name})
        return {"status": "success", "status_changes": results[:limit]}
    else: return {"status": "error", "message": f"Unknown action: {action}"}
