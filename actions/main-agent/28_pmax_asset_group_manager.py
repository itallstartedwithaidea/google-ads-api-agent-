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

def run(action, search=None, customer_id=None, campaign_id=None, asset_group_id=None, name=None, final_url=None, path1="", path2="", status="PAUSED", asset_type=None, texts=None, image_urls=None, performance_label=None, cost_min=None, cost_max=None, conversions_min=None, date_range="LAST_30_DAYS", limit=100):
    client = get_client(); cid = resolve_customer_id(client, search, customer_id)
    ga = client.get_service("GoogleAdsService")

    if action == "list_asset_groups":
        query = f"SELECT asset_group.id, asset_group.name, asset_group.campaign, asset_group.status, asset_group.final_urls, asset_group.path1, asset_group.path2, campaign.id, campaign.name, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value FROM asset_group WHERE segments.date DURING {date_range}"
        if campaign_id: query += f" AND campaign.id = {campaign_id}"
        results = []
        for row in ga.search(customer_id=cid, query=query):
            cd = row.metrics.cost_micros/MICROS if row.metrics.cost_micros else 0; conv = row.metrics.conversions or 0
            if cost_min and cd < cost_min: continue
            if cost_max and cd > cost_max: continue
            if conversions_min and conv < conversions_min: continue
            results.append({"asset_group_id": str(row.asset_group.id), "name": row.asset_group.name, "campaign_id": str(row.campaign.id), "campaign_name": row.campaign.name, "status": str(row.asset_group.status).replace("AssetGroupStatusEnum.AssetGroupStatus.", ""), "final_urls": list(row.asset_group.final_urls), "impressions": row.metrics.impressions or 0, "clicks": row.metrics.clicks or 0, "cost": round(cd, 2), "conversions": round(conv, 2), "conversions_value": round(row.metrics.conversions_value or 0, 2)})
        return {"status": "success", "asset_groups": results[:limit], "total_found": len(results)}

    elif action == "create_asset_group":
        if not campaign_id or not name or not final_url: return {"status": "error", "message": "campaign_id, name, final_url required"}
        op = client.get_type("AssetGroupOperation"); ag = op.create
        ag.name = name; ag.campaign = f"customers/{cid}/campaigns/{campaign_id}"; ag.final_urls.append(final_url)
        if path1: ag.path1 = path1
        if path2: ag.path2 = path2
        ag.status = client.enums.AssetGroupStatusEnum.PAUSED if status == "PAUSED" else client.enums.AssetGroupStatusEnum.ENABLED
        try:
            r = client.get_service("AssetGroupService").mutate_asset_groups(customer_id=cid, operations=[op])
            agid = r.results[0].resource_name.split("/")[-1]
            return {"status": "success", "message": f"Asset group '{name}' created", "asset_group_id": agid, "resource_name": r.results[0].resource_name, "next_steps": ["Add headlines", "Add descriptions", "Add images", "Add logos"]}
        except GoogleAdsException as ex: return {"status": "error", "message": str(ex.failure.errors[0].message)}

    elif action == "add_assets":
        if not asset_group_id or not asset_type: return {"status": "error", "message": "asset_group_id and asset_type required"}
        if asset_type in ["HEADLINE", "DESCRIPTION", "BUSINESS_NAME"]:
            if not texts: return {"status": "error", "message": "texts list required"}
            asset_svc = client.get_service("AssetService"); aga_svc = client.get_service("AssetGroupAssetService")
            ops = []
            for t in texts:
                op = client.get_type("AssetOperation"); op.create.text_asset.text = t
                tid = abs(hash(t)) % (10**10); op.create.resource_name = f"customers/{cid}/assets/-{tid}"
                ops.append(op)
            try:
                r = asset_svc.mutate_assets(customer_id=cid, operations=ops)
                created = [res.resource_name for res in r.results]
                ftm = {"HEADLINE": client.enums.AssetFieldTypeEnum.HEADLINE, "DESCRIPTION": client.enums.AssetFieldTypeEnum.DESCRIPTION, "BUSINESS_NAME": client.enums.AssetFieldTypeEnum.BUSINESS_NAME}
                link_ops = []
                for ar in created:
                    lop = client.get_type("AssetGroupAssetOperation"); lop.create.asset = ar
                    lop.create.asset_group = f"customers/{cid}/assetGroups/{asset_group_id}"
                    lop.create.field_type = ftm[asset_type]; link_ops.append(lop)
                lr = aga_svc.mutate_asset_group_assets(customer_id=cid, operations=link_ops)
                return {"status": "success", "message": f"{len(created)} {asset_type} assets added", "asset_resources": created}
            except GoogleAdsException as ex: return {"status": "error", "message": str(ex.failure.errors[0].message)}
        else:
            return {"status": "info", "message": "Image assets require uploading first. Use Cloudinary or Google Ads UI."}

    elif action == "get_asset_performance":
        query = "SELECT asset_group_asset.resource_name, asset_group_asset.field_type, asset_group_asset.performance_label, asset_group_asset.status, asset.id, asset.name, asset.type, asset.text_asset.text, asset_group.id, asset_group.name, campaign.id, campaign.name FROM asset_group_asset"
        conds = []
        if asset_group_id: conds.append(f"asset_group.id = {asset_group_id}")
        if campaign_id: conds.append(f"campaign.id = {campaign_id}")
        if performance_label: conds.append(f"asset_group_asset.performance_label = '{performance_label}'")
        if conds: query += " WHERE " + " AND ".join(conds)
        results = []; perf_summary = {}
        for row in ga.search(customer_id=cid, query=query):
            pl = str(row.asset_group_asset.performance_label).replace("AssetPerformanceLabelEnum.AssetPerformanceLabel.", "")
            perf_summary[pl] = perf_summary.get(pl, 0) + 1
            results.append({"asset_group_id": str(row.asset_group.id), "asset_group_name": row.asset_group.name, "asset_id": str(row.asset.id), "asset_type": str(row.asset.type_).replace("AssetTypeEnum.AssetType.", ""), "field_type": str(row.asset_group_asset.field_type).replace("AssetFieldTypeEnum.AssetFieldType.", ""), "text": row.asset.text_asset.text if row.asset.text_asset else None, "performance_label": pl, "status": str(row.asset_group_asset.status).replace("AssetLinkStatusEnum.AssetLinkStatus.", "")})
        return {"status": "success", "assets": results[:limit], "total_found": len(results), "performance_summary": perf_summary}

    else: return {"status": "error", "message": f"Unknown action: {action}"}
