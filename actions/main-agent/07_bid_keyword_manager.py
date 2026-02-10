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
DATE_RANGES = ['TODAY', 'YESTERDAY', 'LAST_7_DAYS', 'LAST_14_DAYS', 'LAST_30_DAYS', 'LAST_90_DAYS', 'THIS_MONTH', 'LAST_MONTH', 'THIS_QUARTER', 'THIS_YEAR']
SORT_FIELDS = {'cost': 'metrics.cost_micros DESC', 'conversions': 'metrics.conversions DESC', 'clicks': 'metrics.clicks DESC', 'impressions': 'metrics.impressions DESC', 'quality_score': 'ad_group_criterion.quality_info.quality_score DESC', 'cpc_bid': 'ad_group_criterion.cpc_bid_micros DESC', 'keyword': 'ad_group_criterion.keyword.text ASC'}

def get_client(login_customer_id=None):
    config = {"developer_token": secrets["DEVELOPER_TOKEN"], "client_id": secrets["CLIENT_ID"], "client_secret": secrets["CLIENT_SECRET"], "refresh_token": secrets["REFRESH_TOKEN"], "use_proto_plus": True}
    if login_customer_id:
        config["login_customer_id"] = str(login_customer_id).replace("-", "")
    return GoogleAdsClient.load_from_dict(config, version=API_VERSION)

def dollars_to_micros(dollars):
    if dollars is None:
        return None
    return int(float(dollars) * 1000000)

def run(customer_id, action, login_customer_id=None, ad_group_id=None, campaign_id=None,
        criterion_id=None, bid_modifier=None, cpc_bid=None, cost_min=None, cost_max=None, cpa_max=None,
        status_filter=None, match_type=None, keyword_contains=None, date_range=None, 
        conversions_min=None, conversions_max=None, clicks_min=None, impressions_min=None,
        quality_score_min=None, quality_score_max=None, sort_by='cost', limit=200,
        keywords=None, min_conversions=1.0, cpc_bid_micros=None, cost_min_micros=None, cost_max_micros=None, cpa_max_micros=None):
    try:
        customer_id = str(customer_id).replace("-", "")
        client = get_client(login_customer_id)
        ga_service = client.get_service("GoogleAdsService")
        if cpc_bid is not None:
            cpc_bid_micros = dollars_to_micros(cpc_bid)
        if cost_min is not None:
            cost_min_micros = dollars_to_micros(cost_min)
        if cost_max is not None:
            cost_max_micros = dollars_to_micros(cost_max)
        if cpa_max is not None:
            cpa_max_micros = dollars_to_micros(cpa_max)
        limit = min(int(limit), 1000)
        has_metric_filters = any([cost_min_micros, cost_max_micros, conversions_min, conversions_max is not None, clicks_min, impressions_min, cpa_max_micros])
        if has_metric_filters and not date_range:
            date_range = 'LAST_30_DAYS'

        if action == "add_keywords":
            if not ad_group_id:
                return {"status": "error", "message": "ad_group_id required"}
            if not keywords or not isinstance(keywords, list):
                return {"status": "error", "message": "keywords list required"}
            agc_service = client.get_service("AdGroupCriterionService")
            ag_service = client.get_service("AdGroupService")
            operations = []
            for kw in keywords:
                if not kw.get("keyword"):
                    continue
                operation = client.get_type("AdGroupCriterionOperation")
                criterion = operation.create
                criterion.ad_group = ag_service.ad_group_path(customer_id, ad_group_id)
                criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
                criterion.keyword.text = kw["keyword"]
                kw_match = kw.get("match_type", "BROAD").upper()
                if kw_match not in ["EXACT", "PHRASE", "BROAD"]:
                    kw_match = "BROAD"
                criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[kw_match]
                if kw.get("cpc_bid"):
                    criterion.cpc_bid_micros = int(float(kw["cpc_bid"]) * 1000000)
                operations.append(operation)
            if not operations:
                return {"status": "error", "message": "No valid keywords to add"}
            response = agc_service.mutate_ad_group_criteria(customer_id=customer_id, operations=operations)
            added = [{"resource_name": result.resource_name, "keyword": keywords[i].get("keyword") if i < len(keywords) else None} for i, result in enumerate(response.results)]
            return {"status": "success", "message": f"Added {len(added)} keywords", "added_count": len(added), "keywords_added": added, "api_version": API_VERSION}

        elif action == "add_keywords_from_search_terms":
            if not campaign_id or not ad_group_id:
                return {"status": "error", "message": "campaign_id and ad_group_id required"}
            search_date_range = date_range or 'LAST_30_DAYS'
            query = f"SELECT search_term_view.search_term, metrics.conversions, metrics.cost_micros, metrics.clicks FROM search_term_view WHERE campaign.id = {campaign_id} AND segments.date DURING {search_date_range} AND metrics.conversions >= {min_conversions} AND search_term_view.status = 'NONE' ORDER BY metrics.conversions DESC LIMIT 50"
            response = ga_service.search(customer_id=customer_id, query=query)
            candidates = [{"keyword": row.search_term_view.search_term, "match_type": match_type or "EXACT", "conversions": round(row.metrics.conversions, 2), "cost": round(row.metrics.cost_micros / 1000000, 2), "clicks": row.metrics.clicks} for row in response]
            if not candidates:
                return {"status": "success", "message": f"No converting search terms found with >= {min_conversions} conversions", "candidates": []}
            agc_service = client.get_service("AdGroupCriterionService")
            ag_service = client.get_service("AdGroupService")
            operations = []
            for kw in candidates:
                operation = client.get_type("AdGroupCriterionOperation")
                criterion = operation.create
                criterion.ad_group = ag_service.ad_group_path(customer_id, ad_group_id)
                criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
                criterion.keyword.text = kw["keyword"]
                criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[kw["match_type"]]
                operations.append(operation)
            add_response = agc_service.mutate_ad_group_criteria(customer_id=customer_id, operations=operations)
            return {"status": "success", "message": f"Added {len(add_response.results)} converting search terms as keywords", "added_count": len(add_response.results), "keywords_added": candidates, "api_version": API_VERSION}

        elif action == "get_keyword_bids":
            where_parts = ["ad_group_criterion.type = 'KEYWORD'"]
            if status_filter and status_filter.upper() != 'ALL':
                where_parts.append(f"ad_group_criterion.status = '{status_filter.upper()}'")
            else:
                where_parts.append("ad_group_criterion.status != 'REMOVED'")
            if ad_group_id:
                where_parts.append(f"ad_group.id = {ad_group_id}")
            if campaign_id:
                where_parts.append(f"campaign.id = {campaign_id}")
            if match_type:
                where_parts.append(f"ad_group_criterion.keyword.match_type = '{match_type.upper()}'")
            if keyword_contains:
                where_parts.append(f"ad_group_criterion.keyword.text LIKE '%{keyword_contains}%'")
            if quality_score_min is not None:
                where_parts.append(f"ad_group_criterion.quality_info.quality_score >= {int(quality_score_min)}")
            if quality_score_max is not None:
                where_parts.append(f"ad_group_criterion.quality_info.quality_score <= {int(quality_score_max)}")
            if date_range:
                where_parts.append(f"segments.date DURING {date_range.upper()}")
            if cost_min_micros is not None:
                where_parts.append(f"metrics.cost_micros >= {int(cost_min_micros)}")
            if cost_max_micros is not None:
                where_parts.append(f"metrics.cost_micros <= {int(cost_max_micros)}")
            if conversions_min is not None:
                where_parts.append(f"metrics.conversions >= {float(conversions_min)}")
            if conversions_max is not None:
                where_parts.append(f"metrics.conversions <= {float(conversions_max)}")
            if clicks_min is not None:
                where_parts.append(f"metrics.clicks >= {int(clicks_min)}")
            if impressions_min is not None:
                where_parts.append(f"metrics.impressions >= {int(impressions_min)}")
            where_clause = " AND ".join(where_parts)
            order_by = SORT_FIELDS.get(sort_by, SORT_FIELDS['cost'])
            select_fields = ["ad_group_criterion.criterion_id", "ad_group_criterion.keyword.text", "ad_group_criterion.keyword.match_type", "ad_group_criterion.cpc_bid_micros", "ad_group_criterion.effective_cpc_bid_micros", "ad_group_criterion.status", "ad_group_criterion.quality_info.quality_score", "ad_group.id", "ad_group.name", "campaign.id", "campaign.name"]
            if date_range or has_metric_filters:
                select_fields.extend(["metrics.impressions", "metrics.clicks", "metrics.cost_micros", "metrics.conversions", "metrics.ctr", "metrics.average_cpc", "metrics.cost_per_conversion"])
            query = f"SELECT {', '.join(select_fields)} FROM keyword_view WHERE {where_clause} ORDER BY {order_by} LIMIT {limit}"
            response = ga_service.search(customer_id=customer_id, query=query)
            keywords_list = []
            total_cost = 0
            total_conversions = 0
            for row in response:
                kw = {"criterion_id": str(row.ad_group_criterion.criterion_id), "keyword": row.ad_group_criterion.keyword.text, "match_type": row.ad_group_criterion.keyword.match_type.name, "cpc_bid": round(row.ad_group_criterion.cpc_bid_micros / 1000000, 2) if row.ad_group_criterion.cpc_bid_micros else None, "effective_cpc_bid": round(row.ad_group_criterion.effective_cpc_bid_micros / 1000000, 2) if row.ad_group_criterion.effective_cpc_bid_micros else None, "status": row.ad_group_criterion.status.name, "quality_score": row.ad_group_criterion.quality_info.quality_score if row.ad_group_criterion.quality_info else None, "ad_group_id": str(row.ad_group.id), "ad_group_name": row.ad_group.name, "campaign_id": str(row.campaign.id), "campaign_name": row.campaign.name}
                if date_range or has_metric_filters:
                    cost = row.metrics.cost_micros
                    conversions = row.metrics.conversions
                    total_cost += cost
                    total_conversions += conversions
                    kw["impressions"] = row.metrics.impressions
                    kw["clicks"] = row.metrics.clicks
                    kw["cost"] = round(cost / 1000000, 2)
                    kw["conversions"] = round(conversions, 2)
                    kw["ctr"] = round(row.metrics.ctr * 100, 2) if row.metrics.ctr else 0
                    kw["avg_cpc"] = round(row.metrics.average_cpc / 1000000, 2) if row.metrics.average_cpc else 0
                    kw["cost_per_conversion"] = round(row.metrics.cost_per_conversion / 1000000, 2) if row.metrics.cost_per_conversion else None
                keywords_list.append(kw)
            result = {"status": "success", "count": len(keywords_list), "keywords": keywords_list, "api_version": API_VERSION}
            if date_range or has_metric_filters:
                result["summary"] = {"total_cost": round(total_cost / 1000000, 2), "total_conversions": round(total_conversions, 2), "avg_cpa": round((total_cost / total_conversions) / 1000000, 2) if total_conversions > 0 else None}
            return result

        elif action == "update_keyword_bid":
            if not all([ad_group_id, criterion_id, cpc_bid_micros]):
                return {"status": "error", "message": "ad_group_id, criterion_id, and cpc_bid required"}
            agc_service = client.get_service("AdGroupCriterionService")
            operation = client.get_type("AdGroupCriterionOperation")
            criterion = operation.update
            criterion.resource_name = agc_service.ad_group_criterion_path(customer_id, ad_group_id, criterion_id)
            criterion.cpc_bid_micros = int(cpc_bid_micros)
            client.copy_from(operation.update_mask, protobuf_helpers.field_mask(None, criterion._pb))
            response = agc_service.mutate_ad_group_criteria(customer_id=customer_id, operations=[operation])
            return {"status": "success", "resource_name": response.results[0].resource_name, "new_cpc_bid": round(cpc_bid_micros / 1000000, 2), "api_version": API_VERSION}

        elif action == "update_ad_group_bid":
            if not all([ad_group_id, cpc_bid_micros]):
                return {"status": "error", "message": "ad_group_id and cpc_bid required"}
            ag_service = client.get_service("AdGroupService")
            operation = client.get_type("AdGroupOperation")
            ad_group = operation.update
            ad_group.resource_name = ag_service.ad_group_path(customer_id, ad_group_id)
            ad_group.cpc_bid_micros = int(cpc_bid_micros)
            client.copy_from(operation.update_mask, protobuf_helpers.field_mask(None, ad_group._pb))
            response = ag_service.mutate_ad_groups(customer_id=customer_id, operations=[operation])
            return {"status": "success", "resource_name": response.results[0].resource_name, "new_cpc_bid": round(cpc_bid_micros / 1000000, 2), "api_version": API_VERSION}

        elif action == "get_bid_modifiers":
            if not campaign_id:
                return {"status": "error", "message": "campaign_id required"}
            query = f"SELECT campaign_criterion.criterion_id, campaign_criterion.bid_modifier, campaign_criterion.device.type, campaign_criterion.location.geo_target_constant, campaign.id, campaign.name FROM campaign_criterion WHERE campaign.id = {campaign_id} AND campaign_criterion.bid_modifier IS NOT NULL"
            response = ga_service.search(customer_id=customer_id, query=query)
            modifiers = []
            for row in response:
                modifier_type = "UNKNOWN"
                modifier_value = None
                if row.campaign_criterion.device.type:
                    modifier_type = "DEVICE"
                    modifier_value = row.campaign_criterion.device.type.name
                elif row.campaign_criterion.location.geo_target_constant:
                    modifier_type = "LOCATION"
                    modifier_value = row.campaign_criterion.location.geo_target_constant
                modifiers.append({"criterion_id": str(row.campaign_criterion.criterion_id), "bid_modifier": row.campaign_criterion.bid_modifier, "bid_adjustment_percent": round((row.campaign_criterion.bid_modifier - 1) * 100, 0), "type": modifier_type, "value": modifier_value, "campaign_id": str(row.campaign.id), "campaign_name": row.campaign.name})
            return {"status": "success", "count": len(modifiers), "modifiers": modifiers, "api_version": API_VERSION}

        else:
            return {"status": "error", "message": f"Unknown action: {action}", "available_actions": ["get_keyword_bids", "update_keyword_bid", "update_ad_group_bid", "get_bid_modifiers", "add_keywords", "add_keywords_from_search_terms"]}

    except GoogleAdsException as ex:
        errors = [{"code": str(e.error_code), "message": e.message} for e in ex.failure.errors]
        return {"status": "error", "request_id": ex.request_id, "errors": errors}
    except Exception as e:
        return {"status": "error", "message": str(e)}
