try:
    from google.api_core import protobuf_helpers
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
except ImportError:
    import subprocess
    subprocess.check_call(["pip", "install", "google-ads"])
    from google.api_core import protobuf_helpers
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException

API_VERSION = "v22"

def get_client(login_customer_id=None):
    config = {
        "developer_token": secrets["DEVELOPER_TOKEN"],
        "client_id": secrets["CLIENT_ID"],
        "client_secret": secrets["CLIENT_SECRET"],
        "refresh_token": secrets["REFRESH_TOKEN"],
        "use_proto_plus": True
    }
    if login_customer_id:
        config["login_customer_id"] = str(login_customer_id).replace("-", "")
    return GoogleAdsClient.load_from_dict(config, version=API_VERSION)

def run(customer_id, action, login_customer_id=None, asset_data=None, campaign_id=None, 
        ad_group_id=None, asset_id=None, asset_resource_name=None, field_type=None, asset_type=None, limit=500):
    try:
        customer_id = str(customer_id).replace("-", "")
        if login_customer_id:
            login_customer_id = str(login_customer_id).replace("-", "")
        client = get_client(login_customer_id)
        ga_service = client.get_service("GoogleAdsService")

        if action == "list":
            where = "asset.type != 'UNSPECIFIED'"
            if asset_type:
                where = f"asset.type = '{asset_type}'"
            query = f"SELECT asset.id, asset.name, asset.type, asset.sitelink_asset.link_text, asset.sitelink_asset.description1, asset.sitelink_asset.description2, asset.callout_asset.callout_text, asset.structured_snippet_asset.header, asset.structured_snippet_asset.values, asset.call_asset.phone_number, asset.final_urls FROM asset WHERE {where} LIMIT {limit}"
            results = []
            for row in ga_service.search(customer_id=customer_id, query=query):
                asset = row.asset
                asset_type_name = str(asset.type_.name) if asset.type_ else "UNKNOWN"
                details = {}
                if asset_type_name == "SITELINK" and asset.sitelink_asset:
                    details = {"link_text": asset.sitelink_asset.link_text, "description1": asset.sitelink_asset.description1, "description2": asset.sitelink_asset.description2, "final_urls": list(asset.final_urls) if asset.final_urls else []}
                elif asset_type_name == "CALLOUT" and asset.callout_asset:
                    details = {"callout_text": asset.callout_asset.callout_text}
                elif asset_type_name == "STRUCTURED_SNIPPET" and asset.structured_snippet_asset:
                    details = {"header": asset.structured_snippet_asset.header, "values": list(asset.structured_snippet_asset.values) if asset.structured_snippet_asset.values else []}
                elif asset_type_name == "CALL" and asset.call_asset:
                    details = {"phone_number": asset.call_asset.phone_number}
                results.append({"asset_id": asset.id, "name": asset.name, "type": asset_type_name, "details": details})
            return {"status": "success", "count": len(results), "assets": results, "api_version": API_VERSION}

        elif action == "create_sitelink":
            if not asset_data:
                return {"status": "error", "message": "asset_data required"}
            if not asset_data.get("final_urls"):
                return {"status": "error", "message": "final_urls required for sitelinks"}
            asset_service = client.get_service("AssetService")
            operation = client.get_type("AssetOperation")
            asset = operation.create
            asset.sitelink_asset.link_text = asset_data.get("link_text", asset_data.get("text", ""))
            asset.sitelink_asset.description1 = asset_data.get("description1", "")
            asset.sitelink_asset.description2 = asset_data.get("description2", "")
            asset.final_urls.extend(asset_data.get("final_urls", []))
            response = asset_service.mutate_assets(customer_id=customer_id, operations=[operation])
            return {"status": "success", "resource_name": response.results[0].resource_name, "type": "sitelink", "api_version": API_VERSION}

        elif action == "create_callout":
            if not asset_data or not asset_data.get("text"):
                return {"status": "error", "message": "asset_data with text required"}
            asset_service = client.get_service("AssetService")
            operation = client.get_type("AssetOperation")
            asset = operation.create
            asset.callout_asset.callout_text = asset_data.get("text", asset_data.get("callout_text", ""))
            response = asset_service.mutate_assets(customer_id=customer_id, operations=[operation])
            return {"status": "success", "resource_name": response.results[0].resource_name, "type": "callout", "api_version": API_VERSION}

        elif action == "create_call":
            if not asset_data or not asset_data.get("phone_number"):
                return {"status": "error", "message": "asset_data with phone_number required"}
            asset_service = client.get_service("AssetService")
            operation = client.get_type("AssetOperation")
            asset = operation.create
            asset.call_asset.phone_number = asset_data.get("phone_number", "")
            asset.call_asset.country_code = asset_data.get("country_code", "US")
            response = asset_service.mutate_assets(customer_id=customer_id, operations=[operation])
            return {"status": "success", "resource_name": response.results[0].resource_name, "type": "call", "api_version": API_VERSION}

        elif action == "link_to_campaign":
            if not campaign_id or not asset_resource_name or not field_type:
                return {"status": "error", "message": "campaign_id, asset_resource_name, and field_type required"}
            campaign_asset_service = client.get_service("CampaignAssetService")
            operation = client.get_type("CampaignAssetOperation")
            campaign_asset = operation.create
            campaign_asset.campaign = f"customers/{customer_id}/campaigns/{campaign_id}"
            campaign_asset.asset = asset_resource_name
            campaign_asset.field_type = client.enums.AssetFieldTypeEnum[field_type]
            response = campaign_asset_service.mutate_campaign_assets(customer_id=customer_id, operations=[operation])
            return {"status": "success", "resource_name": response.results[0].resource_name, "api_version": API_VERSION}

        elif action == "link_to_ad_group":
            if not ad_group_id or not asset_resource_name or not field_type:
                return {"status": "error", "message": "ad_group_id, asset_resource_name, and field_type required"}
            ad_group_asset_service = client.get_service("AdGroupAssetService")
            operation = client.get_type("AdGroupAssetOperation")
            ad_group_asset = operation.create
            ad_group_asset.ad_group = f"customers/{customer_id}/adGroups/{ad_group_id}"
            ad_group_asset.asset = asset_resource_name
            ad_group_asset.field_type = client.enums.AssetFieldTypeEnum[field_type]
            response = ad_group_asset_service.mutate_ad_group_assets(customer_id=customer_id, operations=[operation])
            return {"status": "success", "resource_name": response.results[0].resource_name, "api_version": API_VERSION}

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except GoogleAdsException as ex:
        errors = [{"code": str(e.error_code), "message": e.message} for e in ex.failure.errors]
        return {"status": "error", "request_id": ex.request_id, "errors": errors}
    except Exception as e:
        return {"status": "error", "message": str(e)}
