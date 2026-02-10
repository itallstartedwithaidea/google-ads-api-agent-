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

def run(customer_id, action, login_customer_id=None, ad_group_id=None, campaign_id=None,
        ad_data=None, ad_id=None, query_plan=None, status_filter=None, approval_filter=None, 
        ad_strength_filter=None, date_range=None, limit=100, include_metrics=False, detail_level=None):
    try:
        customer_id = str(customer_id).replace("-", "")
        if login_customer_id:
            login_customer_id = str(login_customer_id).replace("-", "")
        client = get_client(login_customer_id)
        ga_service = client.get_service("GoogleAdsService")
        if query_plan:
            limit = query_plan.get("limit", limit)
            include_metrics = query_plan.get("include_metrics", include_metrics)
            detail_level = query_plan.get("detail_level", detail_level)
            if "filters" in query_plan:
                filters = query_plan["filters"]
                status_filter = status_filter or filters.get("status")
                approval_filter = approval_filter or filters.get("approval_status")
                ad_strength_filter = ad_strength_filter or filters.get("ad_strength")
                date_range = date_range or filters.get("date_range")
        limit = min(limit, 300)

        if action == "list":
            where_parts = ["ad_group_ad.ad.type = 'RESPONSIVE_SEARCH_AD'"]
            if status_filter and status_filter.upper() != "ALL":
                where_parts.append(f"ad_group_ad.status = '{status_filter.upper()}'")
            else:
                where_parts.append("ad_group_ad.status != 'REMOVED'")
            if approval_filter:
                af = approval_filter.upper()
                if af == "DISAPPROVED":
                    where_parts.append("ad_group_ad.policy_summary.approval_status = 'DISAPPROVED'")
                elif af == "APPROVED":
                    where_parts.append("ad_group_ad.policy_summary.approval_status = 'APPROVED'")
                elif af == "ANY_ISSUE":
                    where_parts.append("ad_group_ad.policy_summary.approval_status != 'APPROVED'")
            if ad_strength_filter:
                asf = ad_strength_filter.upper()
                if asf == "POOR":
                    where_parts.append("ad_group_ad.ad_strength = 'POOR'")
                elif asf == "NEEDS_ATTENTION":
                    where_parts.append("ad_group_ad.ad_strength IN ('POOR', 'AVERAGE')")
            if campaign_id:
                where_parts.append(f"campaign.id = {campaign_id}")
            if ad_group_id:
                where_parts.append(f"ad_group.id = {ad_group_id}")
            if date_range:
                where_parts.append(f"segments.date DURING {date_range.upper()}")
            where = " AND ".join(where_parts)
            select_fields = "ad_group_ad.ad.id, ad_group_ad.status, ad_group_ad.ad_strength, ad_group_ad.policy_summary.approval_status, ad_group_ad.ad.final_urls, ad_group.id, ad_group.name, campaign.id, campaign.name"
            if include_metrics:
                select_fields += ", metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions"
            query = f"SELECT {select_fields} FROM ad_group_ad WHERE {where} ORDER BY ad_group_ad.ad.id DESC LIMIT {limit}"
            response = ga_service.search(customer_id=customer_id, query=query)
            results = []
            for row in response:
                ad_row = {"ad_id": row.ad_group_ad.ad.id, "status": row.ad_group_ad.status.name, "ad_strength": row.ad_group_ad.ad_strength.name if row.ad_group_ad.ad_strength else "UNKNOWN", "approval_status": row.ad_group_ad.policy_summary.approval_status.name if row.ad_group_ad.policy_summary.approval_status else "UNKNOWN", "ad_group_id": row.ad_group.id, "ad_group_name": row.ad_group.name, "campaign_id": row.campaign.id, "campaign_name": row.campaign.name, "final_urls": list(row.ad_group_ad.ad.final_urls)}
                if include_metrics:
                    ad_row["impressions"] = row.metrics.impressions
                    ad_row["clicks"] = row.metrics.clicks
                    ad_row["cost"] = round(row.metrics.cost_micros / 1000000, 2)
                    ad_row["conversions"] = round(row.metrics.conversions, 2)
                results.append(ad_row)
            return {"status": "success", "count": len(results), "ads": results, "api_version": API_VERSION}

        elif action == "create":
            if not ad_group_id or not ad_data:
                return {"status": "error", "message": "ad_group_id and ad_data required"}
            if not ad_data.get("headlines") or len(ad_data["headlines"]) < 3:
                return {"status": "error", "message": "At least 3 headlines required"}
            if not ad_data.get("descriptions") or len(ad_data["descriptions"]) < 2:
                return {"status": "error", "message": "At least 2 descriptions required"}
            if not ad_data.get("final_urls"):
                return {"status": "error", "message": "At least 1 final URL required"}
            ad_group_ad_service = client.get_service("AdGroupAdService")
            operation = client.get_type("AdGroupAdOperation")
            ad_group_ad = operation.create
            ad_group_ad.ad_group = f"customers/{customer_id}/adGroups/{ad_group_id}"
            ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED
            ad = ad_group_ad.ad
            ad.final_urls.extend(ad_data.get("final_urls", []))
            for headline in ad_data.get("headlines", [])[:15]:
                headline_asset = client.get_type("AdTextAsset")
                headline_asset.text = headline
                ad.responsive_search_ad.headlines.append(headline_asset)
            for desc in ad_data.get("descriptions", [])[:4]:
                desc_asset = client.get_type("AdTextAsset")
                desc_asset.text = desc
                ad.responsive_search_ad.descriptions.append(desc_asset)
            if ad_data.get("path1"):
                ad.responsive_search_ad.path1 = ad_data["path1"]
            if ad_data.get("path2"):
                ad.responsive_search_ad.path2 = ad_data["path2"]
            response = ad_group_ad_service.mutate_ad_group_ads(customer_id=customer_id, operations=[operation])
            return {"status": "success", "resource_name": response.results[0].resource_name, "headlines_count": len(ad_data.get("headlines", [])), "descriptions_count": len(ad_data.get("descriptions", [])), "api_version": API_VERSION}

        elif action in ["pause", "enable"]:
            if not ad_group_id or not ad_id:
                return {"status": "error", "message": "ad_group_id and ad_id required"}
            new_status = "PAUSED" if action == "pause" else "ENABLED"
            ad_group_ad_service = client.get_service("AdGroupAdService")
            operation = client.get_type("AdGroupAdOperation")
            ad_group_ad = operation.update
            ad_group_ad.resource_name = f"customers/{customer_id}/adGroupAds/{ad_group_id}~{ad_id}"
            ad_group_ad.status = client.enums.AdGroupAdStatusEnum[new_status]
            client.copy_from(operation.update_mask, protobuf_helpers.field_mask(None, ad_group_ad._pb))
            response = ad_group_ad_service.mutate_ad_group_ads(customer_id=customer_id, operations=[operation])
            return {"status": "success", "resource_name": response.results[0].resource_name, "new_status": new_status, "api_version": API_VERSION}

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except GoogleAdsException as ex:
        errors = [{"code": str(e.error_code), "message": e.message} for e in ex.failure.errors]
        return {"status": "error", "request_id": ex.request_id, "errors": errors}
    except Exception as e:
        return {"status": "error", "message": str(e)}
