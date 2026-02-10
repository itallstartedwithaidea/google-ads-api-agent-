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

DATE_RANGES = ['TODAY', 'YESTERDAY', 'LAST_7_DAYS', 'LAST_14_DAYS', 'LAST_30_DAYS', 'LAST_90_DAYS', 'THIS_MONTH', 'LAST_MONTH']
AUDIENCE_TYPES = ['REMARKETING', 'CRM_BASED', 'RULE_BASED', 'SIMILAR', 'BASIC_USER_LIST', 'LOGICAL_USER_LIST']
SORT_FIELDS = {'size': 'user_list.size_for_search DESC', 'name': 'user_list.name ASC', 'match_rate': 'user_list.match_rate_percentage DESC'}

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

def run(customer_id, action, login_customer_id=None, campaign_id=None, ad_group_id=None,
        audience_id=None, user_list_id=None, bid_modifier=None, date_range="LAST_30_DAYS",
        name_contains=None, type_filter=None, membership_status=None,
        size_min=None, size_max=None, eligible_for_search=None,
        eligible_for_display=None, sort_by='size', limit=200):
    try:
        customer_id = str(customer_id).replace("-", "")
        if login_customer_id:
            login_customer_id = str(login_customer_id).replace("-", "")
        list_id = user_list_id or audience_id
        limit = min(int(limit), 500)
        client = get_client(login_customer_id)
        ga_service = client.get_service("GoogleAdsService")

        if action == "list_audiences":
            where_parts = []
            if membership_status and membership_status.upper() != 'ALL':
                where_parts.append(f"user_list.membership_status = '{membership_status.upper()}'")
            else:
                where_parts.append("user_list.membership_status != 'CLOSED'")
            if name_contains:
                where_parts.append(f"user_list.name LIKE '%{name_contains}%'")
            if type_filter and type_filter.upper() != 'ALL':
                if type_filter.upper() in AUDIENCE_TYPES:
                    where_parts.append(f"user_list.type = '{type_filter.upper()}'")
            if size_min is not None:
                where_parts.append(f"user_list.size_for_search >= {int(size_min)}")
            if size_max is not None:
                where_parts.append(f"user_list.size_for_search <= {int(size_max)}")
            if eligible_for_search is True:
                where_parts.append("user_list.eligible_for_search = TRUE")
            if eligible_for_display is True:
                where_parts.append("user_list.eligible_for_display = TRUE")
            where_clause = " AND ".join(where_parts) if where_parts else "user_list.membership_status != 'CLOSED'"
            order_by = SORT_FIELDS.get(sort_by, SORT_FIELDS['size'])
            query = f"SELECT user_list.id, user_list.name, user_list.type, user_list.size_for_display, user_list.size_for_search, user_list.membership_status, user_list.match_rate_percentage, user_list.eligible_for_search, user_list.eligible_for_display FROM user_list WHERE {where_clause} ORDER BY {order_by} LIMIT {limit}"
            results = []
            total_size = 0
            type_counts = {}
            for row in ga_service.search(customer_id=customer_id, query=query):
                ul = row.user_list
                audience_type = str(ul.type_.name) if ul.type_ else "UNKNOWN"
                type_counts[audience_type] = type_counts.get(audience_type, 0) + 1
                total_size += ul.size_for_search or 0
                results.append({"user_list_id": ul.id, "name": ul.name, "type": audience_type, "size_for_display": ul.size_for_display, "size_for_search": ul.size_for_search, "membership_status": str(ul.membership_status.name) if ul.membership_status else "UNKNOWN", "match_rate": round(ul.match_rate_percentage, 2) if ul.match_rate_percentage else None, "eligible_for_search": ul.eligible_for_search if ul.eligible_for_search is not None else None, "eligible_for_display": ul.eligible_for_display if ul.eligible_for_display is not None else None})
            return {"status": "success", "count": len(results), "audiences": results, "summary": {"total_audience_size": total_size, "by_type": type_counts}, "api_version": API_VERSION}

        elif action == "get_audience_performance":
            where_parts = [f"segments.date DURING {date_range.upper()}"]
            if campaign_id:
                where_parts.append(f"campaign.id = {campaign_id}")
            where_clause = " AND ".join(where_parts)
            query = f"SELECT campaign.id, campaign.name, ad_group.id, ad_group.name, ad_group_criterion.criterion_id, ad_group_criterion.user_list.user_list, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions FROM ad_group_audience_view WHERE {where_clause} ORDER BY metrics.cost_micros DESC LIMIT 500"
            results = []
            total_cost = 0
            total_conversions = 0
            for row in ga_service.search(customer_id=customer_id, query=query):
                cost = row.metrics.cost_micros
                conversions = row.metrics.conversions
                total_cost += cost
                total_conversions += conversions
                results.append({"campaign_id": row.campaign.id, "campaign_name": row.campaign.name, "ad_group_id": row.ad_group.id, "ad_group_name": row.ad_group.name, "criterion_id": row.ad_group_criterion.criterion_id, "user_list": row.ad_group_criterion.user_list.user_list if row.ad_group_criterion.user_list else None, "impressions": row.metrics.impressions, "clicks": row.metrics.clicks, "cost": round(cost / 1000000, 2), "conversions": round(conversions, 2)})
            return {"status": "success", "count": len(results), "audience_performance": results, "summary": {"total_cost": round(total_cost / 1000000, 2), "total_conversions": round(total_conversions, 2), "avg_cpa": round((total_cost / total_conversions) / 1000000, 2) if total_conversions > 0 else None}, "date_range": date_range, "api_version": API_VERSION}

        elif action == "add_audience_to_campaign":
            if not campaign_id or not list_id:
                return {"status": "error", "message": "campaign_id and user_list_id required"}
            campaign_criterion_service = client.get_service("CampaignCriterionService")
            operation = client.get_type("CampaignCriterionOperation")
            criterion = operation.create
            criterion.campaign = f"customers/{customer_id}/campaigns/{campaign_id}"
            criterion.user_list.user_list = f"customers/{customer_id}/userLists/{list_id}"
            if bid_modifier is not None:
                criterion.bid_modifier = float(bid_modifier)
            response = campaign_criterion_service.mutate_campaign_criteria(customer_id=customer_id, operations=[operation])
            return {"status": "success", "resource_name": response.results[0].resource_name, "api_version": API_VERSION}

        elif action == "add_audience_to_ad_group":
            if not ad_group_id or not list_id:
                return {"status": "error", "message": "ad_group_id and user_list_id required"}
            ad_group_criterion_service = client.get_service("AdGroupCriterionService")
            operation = client.get_type("AdGroupCriterionOperation")
            criterion = operation.create
            criterion.ad_group = f"customers/{customer_id}/adGroups/{ad_group_id}"
            criterion.user_list.user_list = f"customers/{customer_id}/userLists/{list_id}"
            if bid_modifier is not None:
                criterion.bid_modifier = float(bid_modifier)
            response = ad_group_criterion_service.mutate_ad_group_criteria(customer_id=customer_id, operations=[operation])
            return {"status": "success", "resource_name": response.results[0].resource_name, "api_version": API_VERSION}

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except GoogleAdsException as ex:
        errors = [{"code": str(e.error_code), "message": e.message} for e in ex.failure.errors]
        return {"status": "error", "request_id": ex.request_id, "errors": errors}
    except Exception as e:
        return {"status": "error", "message": str(e)}
