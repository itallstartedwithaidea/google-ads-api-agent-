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

DATE_RANGES = [
    'TODAY', 'YESTERDAY', 'LAST_7_DAYS', 'LAST_14_DAYS', 'LAST_30_DAYS',
    'LAST_90_DAYS', 'THIS_MONTH', 'LAST_MONTH', 'THIS_QUARTER', 'THIS_YEAR'
]

SORT_FIELDS = {
    'cost': 'metrics.cost_micros DESC',
    'conversions': 'metrics.conversions DESC',
    'clicks': 'metrics.clicks DESC',
    'impressions': 'metrics.impressions DESC',
    'name': 'campaign.name ASC',
    'ctr': 'metrics.ctr DESC'
}

AD_GROUP_TYPES = [
    'SEARCH_STANDARD', 'DISPLAY_STANDARD', 'SHOPPING_PRODUCT_ADS',
    'HOTEL_ADS', 'SHOPPING_SMART_ADS', 'VIDEO_BUMPER', 'VIDEO_TRUE_VIEW_IN_STREAM',
    'VIDEO_TRUE_VIEW_IN_DISPLAY', 'VIDEO_NON_SKIPPABLE_IN_STREAM', 'VIDEO_RESPONSIVE'
]

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


def resolve_account(search_term):
    client = get_client()
    customer_service = client.get_service("CustomerService")
    accessible = customer_service.list_accessible_customers()

    search_lower = str(search_term).lower().replace("-", "")

    for resource_name in accessible.resource_names:
        root_id = resource_name.split("/")[-1]
        try:
            root_client = get_client(root_id)
            ga_service = root_client.get_service("GoogleAdsService")

            query = """
                SELECT
                    customer_client.id,
                    customer_client.descriptive_name,
                    customer_client.manager,
                    customer_client.level
                FROM customer_client
                WHERE customer_client.status = 'ENABLED'
            """

            response = ga_service.search(customer_id=root_id, query=query)

            for row in response:
                cc = row.customer_client
                cid = str(cc.id)
                name = cc.descriptive_name or ""

                if cid.replace("-", "") == search_lower or search_lower in name.lower():
                    mcc_id = root_id if cc.level > 0 else cid
                    return cid, mcc_id
        except Exception:
            continue

    return None, None


def dollars_to_micros(dollars):
    if dollars is None:
        return None
    return int(float(dollars) * 1000000)


def run(customer_id=None, action="list_campaigns", login_customer_id=None, campaign_id=None,
        ad_group_id=None, data=None, search=None, campaign_name=None,
        query_plan=None, status_filter=None, campaign_type_filter=None,
        date_range=None, fields=None, limit=100, include_metrics=False,
        detail_level=None,
        cost_min=None, cost_max=None,
        conversions_min=None, conversions_max=None,
        impressions_min=None, clicks_min=None,
        ctr_min=None, ctr_max=None,
        bidding_strategy_type=None, sort_by='name',
        ad_group_name=None, ad_group_type='SEARCH_STANDARD', default_cpc=None,
        target_cpa=None, target_roas=None,
        cost_min_micros=None, cost_max_micros=None):
    try:
        if cost_min is not None:
            cost_min_micros = dollars_to_micros(cost_min)
        if cost_max is not None:
            cost_max_micros = dollars_to_micros(cost_max)

        if search and not customer_id:
            resolved_cid, resolved_mcc = resolve_account(search)
            if resolved_cid:
                customer_id = resolved_cid
                login_customer_id = resolved_mcc
            else:
                return {"status": "error", "message": "Could not find account matching: " + str(search)}

        if not customer_id:
            return {"status": "error", "message": "customer_id or search parameter required"}

        customer_id = str(customer_id).replace("-", "")
        if login_customer_id:
            login_customer_id = str(login_customer_id).replace("-", "")

        client = get_client(login_customer_id)
        ga_service = client.get_service("GoogleAdsService")

        if query_plan:
            limit = query_plan.get("limit", limit)
            include_metrics = query_plan.get("include_metrics", include_metrics)
            if "filters" in query_plan:
                filters = query_plan["filters"]
                status_filter = status_filter or filters.get("status")
                campaign_type_filter = campaign_type_filter or filters.get("campaign_type")
                date_range = date_range or filters.get("date_range")
                if filters.get("cost_min"):
                    cost_min_micros = dollars_to_micros(filters.get("cost_min"))
                if filters.get("conversions_min"):
                    conversions_min = filters.get("conversions_min")
                if filters.get("conversions_max") is not None:
                    conversions_max = filters.get("conversions_max")

        if limit > 500:
            limit = 500

        has_metric_filters = any([
            cost_min_micros, cost_max_micros, conversions_min,
            conversions_max is not None, impressions_min, clicks_min,
            ctr_min, ctr_max
        ])

        if has_metric_filters:
            include_metrics = True
            if not date_range:
                date_range = 'LAST_30_DAYS'

        if action == "create_ad_group":
            if not campaign_id:
                return {"status": "error", "message": "campaign_id required"}
            if not ad_group_name:
                return {"status": "error", "message": "ad_group_name required"}

            ag_service = client.get_service("AdGroupService")
            campaign_service = client.get_service("CampaignService")

            operation = client.get_type("AdGroupOperation")
            ad_group = operation.create

            ad_group.name = ad_group_name
            ad_group.campaign = campaign_service.campaign_path(customer_id, campaign_id)
            ad_group.status = client.enums.AdGroupStatusEnum.ENABLED

            ag_type = ad_group_type.upper() if ad_group_type else 'SEARCH_STANDARD'
            if ag_type not in AD_GROUP_TYPES:
                ag_type = 'SEARCH_STANDARD'
            ad_group.type_ = client.enums.AdGroupTypeEnum[ag_type]

            if default_cpc:
                ad_group.cpc_bid_micros = int(float(default_cpc) * 1000000)

            if target_cpa:
                ad_group.target_cpa_micros = int(float(target_cpa) * 1000000)
            if target_roas:
                ad_group.target_roas = float(target_roas)

            response = ag_service.mutate_ad_groups(
                customer_id=customer_id,
                operations=[operation]
            )

            ad_group_resource = response.results[0].resource_name
            new_ad_group_id = ad_group_resource.split("/")[-1]

            return {
                "status": "success",
                "message": f"Ad group '{ad_group_name}' created successfully",
                "ad_group_id": new_ad_group_id,
                "ad_group_resource": ad_group_resource,
                "campaign_id": campaign_id,
                "type": ag_type,
                "default_cpc": default_cpc,
                "api_version": API_VERSION,
                "next_steps": [
                    "Add keywords with Bid & Keyword Manager: action='add_keywords'",
                    "Create RSA ads with RSA Ad Manager: action='create'"
                ]
            }

        elif action == "update_ad_group_bid":
            if not ad_group_id:
                return {"status": "error", "message": "ad_group_id required"}
            if default_cpc is None:
                return {"status": "error", "message": "default_cpc (in dollars) required"}

            ag_service = client.get_service("AdGroupService")
            operation = client.get_type("AdGroupOperation")

            ad_group = operation.update
            ad_group.resource_name = ag_service.ad_group_path(customer_id, ad_group_id)
            ad_group.cpc_bid_micros = int(float(default_cpc) * 1000000)

            client.copy_from(
                operation.update_mask,
                protobuf_helpers.field_mask(None, ad_group._pb),
            )

            response = ag_service.mutate_ad_groups(
                customer_id=customer_id,
                operations=[operation]
            )

            return {
                "status": "success",
                "resource_name": response.results[0].resource_name,
                "new_default_cpc": default_cpc,
                "ad_group_id": ad_group_id,
                "api_version": API_VERSION
            }

        elif action == "list_campaigns":
            select_fields = [
                "campaign.id",
                "campaign.name",
                "campaign.status",
                "campaign.advertising_channel_type",
                "campaign.bidding_strategy_type",
                "campaign_budget.amount_micros"
            ]

            if include_metrics:
                select_fields.extend([
                    "metrics.cost_micros",
                    "metrics.clicks",
                    "metrics.impressions",
                    "metrics.conversions",
                    "metrics.ctr",
                    "metrics.average_cpc",
                    "metrics.cost_per_conversion"
                ])

            where_parts = []

            if status_filter:
                sf = status_filter.upper()
                if sf != "ALL":
                    where_parts.append("campaign.status = '" + sf + "'")
            else:
                where_parts.append("campaign.status != 'REMOVED'")

            if campaign_type_filter:
                where_parts.append("campaign.advertising_channel_type = '" + campaign_type_filter.upper() + "'")

            if campaign_name:
                where_parts.append("campaign.name LIKE '%" + campaign_name + "%'")

            if bidding_strategy_type:
                where_parts.append("campaign.bidding_strategy_type = '" + bidding_strategy_type.upper() + "'")

            if date_range:
                where_parts.append("segments.date DURING " + date_range.upper())

            if cost_min_micros is not None:
                where_parts.append("metrics.cost_micros >= " + str(int(cost_min_micros)))
            if cost_max_micros is not None:
                where_parts.append("metrics.cost_micros <= " + str(int(cost_max_micros)))
            if conversions_min is not None:
                where_parts.append("metrics.conversions >= " + str(float(conversions_min)))
            if conversions_max is not None:
                where_parts.append("metrics.conversions <= " + str(float(conversions_max)))
            if impressions_min is not None:
                where_parts.append("metrics.impressions >= " + str(int(impressions_min)))
            if clicks_min is not None:
                where_parts.append("metrics.clicks >= " + str(int(clicks_min)))
            if ctr_min is not None:
                where_parts.append("metrics.ctr >= " + str(float(ctr_min)))
            if ctr_max is not None:
                where_parts.append("metrics.ctr <= " + str(float(ctr_max)))

            where_clause = " AND ".join(where_parts) if where_parts else "campaign.status != 'REMOVED'"
            select_str = ", ".join(select_fields)

            order_by = SORT_FIELDS.get(sort_by, SORT_FIELDS['name'])

            query = "SELECT " + select_str + " FROM campaign WHERE " + where_clause + " ORDER BY " + order_by + " LIMIT " + str(limit)

            response = ga_service.search(customer_id=customer_id, query=query)

            campaigns = []
            for row in response:
                c = {
                    "id": str(row.campaign.id),
                    "name": row.campaign.name,
                    "status": row.campaign.status.name,
                    "channel_type": row.campaign.advertising_channel_type.name,
                    "bidding_strategy": row.campaign.bidding_strategy_type.name if row.campaign.bidding_strategy_type else None,
                    "budget": round(row.campaign_budget.amount_micros / 1000000, 2)
                }

                if include_metrics:
                    c["cost"] = round(row.metrics.cost_micros / 1000000, 2)
                    c["clicks"] = row.metrics.clicks
                    c["impressions"] = row.metrics.impressions
                    c["conversions"] = round(row.metrics.conversions, 2)
                    c["ctr"] = round(row.metrics.ctr * 100, 2) if row.metrics.ctr else 0
                    c["avg_cpc"] = round(row.metrics.average_cpc / 1000000, 2) if row.metrics.average_cpc else 0
                    c["cost_per_conversion"] = round(row.metrics.cost_per_conversion / 1000000, 2) if row.metrics.cost_per_conversion else None

                campaigns.append(c)

            return {
                "status": "success",
                "count": len(campaigns),
                "campaigns": campaigns,
                "api_version": API_VERSION,
                "account_used": {"customer_id": customer_id, "login_customer_id": login_customer_id}
            }

        elif action == "find_campaign":
            if not campaign_name and not campaign_id:
                return {"status": "error", "message": "campaign_name or campaign_id required"}

            if campaign_id:
                where = "campaign.id = " + str(campaign_id)
            else:
                where = "campaign.name LIKE '%" + campaign_name + "%' AND campaign.status != 'REMOVED'"

            query = "SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type, campaign_budget.amount_micros, campaign_budget.id FROM campaign WHERE " + where + " LIMIT " + str(limit)

            response = ga_service.search(customer_id=customer_id, query=query)

            matches = []
            for row in response:
                matches.append({
                    "id": str(row.campaign.id),
                    "name": row.campaign.name,
                    "status": row.campaign.status.name,
                    "channel_type": row.campaign.advertising_channel_type.name,
                    "budget": round(row.campaign_budget.amount_micros / 1000000, 2),
                    "budget_id": str(row.campaign_budget.id)
                })

            return {
                "status": "success",
                "found": len(matches) > 0,
                "count": len(matches),
                "campaigns": matches,
                "api_version": API_VERSION
            }

        elif action == "get_campaign":
            if not campaign_id and not campaign_name:
                return {"status": "error", "message": "campaign_id or campaign_name required"}

            if campaign_name and not campaign_id:
                if campaign_name.isdigit():
                    campaign_id = campaign_name
                else:
                    find_query = "SELECT campaign.id FROM campaign WHERE campaign.name LIKE '%" + campaign_name + "%' AND campaign.status != 'REMOVED' LIMIT 1"
                    find_response = ga_service.search(customer_id=customer_id, query=find_query)
                    for row in find_response:
                        campaign_id = row.campaign.id
                        break
                    if not campaign_id:
                        return {"status": "error", "message": "Campaign not found: " + campaign_name}

            query = "SELECT campaign.id, campaign.name, campaign.status, campaign.start_date, campaign.end_date, campaign.advertising_channel_type, campaign.bidding_strategy_type, campaign_budget.amount_micros, campaign_budget.id FROM campaign WHERE campaign.id = " + str(campaign_id)

            response = ga_service.search(customer_id=customer_id, query=query)

            for row in response:
                return {
                    "status": "success",
                    "campaign": {
                        "id": str(row.campaign.id),
                        "name": row.campaign.name,
                        "status": row.campaign.status.name,
                        "start_date": row.campaign.start_date,
                        "end_date": row.campaign.end_date,
                        "channel_type": row.campaign.advertising_channel_type.name,
                        "bidding_strategy": row.campaign.bidding_strategy_type.name,
                        "budget": round(row.campaign_budget.amount_micros / 1000000, 2),
                        "budget_id": str(row.campaign_budget.id)
                    },
                    "api_version": API_VERSION
                }

            return {"status": "error", "message": "Campaign not found"}

        elif action == "update_status":
            if not campaign_id and not campaign_name:
                return {"status": "error", "message": "campaign_id or campaign_name required"}
            if not data or "status" not in data:
                return {"status": "error", "message": "data.status required (ENABLED or PAUSED)"}

            if campaign_name and not campaign_id:
                find_query = "SELECT campaign.id FROM campaign WHERE campaign.name LIKE '%" + campaign_name + "%' LIMIT 1"
                find_response = ga_service.search(customer_id=customer_id, query=find_query)
                for row in find_response:
                    campaign_id = row.campaign.id
                    break
                if not campaign_id:
                    return {"status": "error", "message": "Campaign not found: " + campaign_name}

            campaign_service = client.get_service("CampaignService")
            operation = client.get_type("CampaignOperation")

            campaign = operation.update
            campaign.resource_name = campaign_service.campaign_path(customer_id, campaign_id)
            campaign.status = client.enums.CampaignStatusEnum[data["status"]]

            client.copy_from(
                operation.update_mask,
                protobuf_helpers.field_mask(None, campaign._pb),
            )

            response = campaign_service.mutate_campaigns(
                customer_id=customer_id,
                operations=[operation]
            )

            return {
                "status": "success",
                "resource_name": response.results[0].resource_name,
                "new_status": data["status"],
                "api_version": API_VERSION
            }

        elif action == "list_ad_groups":
            if not campaign_id and not campaign_name:
                return {"status": "error", "message": "campaign_id or campaign_name required"}

            if campaign_name and not campaign_id:
                find_query = "SELECT campaign.id FROM campaign WHERE campaign.name LIKE '%" + campaign_name + "%' LIMIT 1"
                find_response = ga_service.search(customer_id=customer_id, query=find_query)
                for row in find_response:
                    campaign_id = row.campaign.id
                    break
                if not campaign_id:
                    return {"status": "error", "message": "Campaign not found: " + campaign_name}

            where_parts = ["campaign.id = " + str(campaign_id)]

            if status_filter and status_filter.upper() != "ALL":
                where_parts.append("ad_group.status = '" + status_filter.upper() + "'")
            else:
                where_parts.append("ad_group.status != 'REMOVED'")

            where_clause = " AND ".join(where_parts)

            query = "SELECT ad_group.id, ad_group.name, ad_group.status, ad_group.type, ad_group.cpc_bid_micros, campaign.id, campaign.name FROM ad_group WHERE " + where_clause + " ORDER BY ad_group.name LIMIT " + str(limit)

            response = ga_service.search(customer_id=customer_id, query=query)

            ad_groups = []
            for row in response:
                ad_groups.append({
                    "id": str(row.ad_group.id),
                    "name": row.ad_group.name,
                    "status": row.ad_group.status.name,
                    "type": row.ad_group.type_.name,
                    "default_cpc": round(row.ad_group.cpc_bid_micros / 1000000, 2) if row.ad_group.cpc_bid_micros else None,
                    "campaign_id": str(row.campaign.id),
                    "campaign_name": row.campaign.name
                })

            return {
                "status": "success",
                "count": len(ad_groups),
                "ad_groups": ad_groups,
                "api_version": API_VERSION
            }

        elif action == "update_ad_group_status":
            if not ad_group_id:
                return {"status": "error", "message": "ad_group_id required"}
            if not data or "status" not in data:
                return {"status": "error", "message": "data.status required"}

            ad_group_service = client.get_service("AdGroupService")
            operation = client.get_type("AdGroupOperation")

            ad_group = operation.update
            ad_group.resource_name = ad_group_service.ad_group_path(customer_id, ad_group_id)
            ad_group.status = client.enums.AdGroupStatusEnum[data["status"]]

            client.copy_from(
                operation.update_mask,
                protobuf_helpers.field_mask(None, ad_group._pb),
            )

            response = ad_group_service.mutate_ad_groups(
                customer_id=customer_id,
                operations=[operation]
            )

            return {
                "status": "success",
                "resource_name": response.results[0].resource_name,
                "new_status": data["status"],
                "api_version": API_VERSION
            }

        else:
            return {
                "status": "error",
                "message": "Unknown action: " + str(action),
                "available_actions": ["list_campaigns", "find_campaign", "get_campaign", "update_status", "list_ad_groups", "update_ad_group_status", "create_ad_group", "update_ad_group_bid"]
            }

    except GoogleAdsException as ex:
        errors = []
        for e in ex.failure.errors:
            errors.append({"code": str(e.error_code), "message": e.message})
        return {"status": "error", "request_id": ex.request_id, "errors": errors}
    except Exception as e:
        return {"status": "error", "message": str(e)}
