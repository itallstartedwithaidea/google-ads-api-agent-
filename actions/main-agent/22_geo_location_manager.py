# ============================================
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
SORT_FIELDS = {'cost': 'metrics.cost_micros DESC', 'conversions': 'metrics.conversions DESC', 'clicks': 'metrics.clicks DESC', 'impressions': 'metrics.impressions DESC'}

def get_client(login_customer_id=None):
    config = {"developer_token": secrets["DEVELOPER_TOKEN"], "client_id": secrets["CLIENT_ID"], "client_secret": secrets["CLIENT_SECRET"], "refresh_token": secrets["REFRESH_TOKEN"], "use_proto_plus": True}
    if login_customer_id: config["login_customer_id"] = str(login_customer_id).replace("-", "")
    return GoogleAdsClient.load_from_dict(config, version=API_VERSION)

def dollars_to_micros(d):
    if d is None: return None
    return int(float(d) * 1000000)

def run(customer_id, action, login_customer_id=None, campaign_id=None, date_range='LAST_30_DAYS', location_type=None, cost_min=None, conversions_min=None, impressions_min=None, sort_by='cost', limit=200, criterion_id=None, bid_modifier=None, geo_target_ids=None, geo_query=None, country_code='US', cost_min_micros=None):
    try:
        customer_id = str(customer_id).replace("-", "")
        if login_customer_id: login_customer_id = str(login_customer_id).replace("-", "")
        client = get_client(login_customer_id)
        ga_service = client.get_service("GoogleAdsService")
        if cost_min is not None: cost_min_micros = dollars_to_micros(cost_min)
        limit = min(int(limit), 500)

        if action == "search_geo_targets":
            if not geo_query: return {"status": "error", "message": "geo_query required"}
            gtc_service = client.get_service("GeoTargetConstantService")
            request = client.get_type("SuggestGeoTargetConstantsRequest")
            request.locale = "en"; request.country_code = country_code.upper()
            location_names = client.get_type("SuggestGeoTargetConstantsRequest").LocationNames()
            location_names.names.append(geo_query); request.location_names = location_names
            response = gtc_service.suggest_geo_target_constants(request=request)
            results = []
            for s in response.geo_target_constant_suggestions:
                g = s.geo_target_constant
                results.append({"id": str(g.id), "resource_name": g.resource_name, "name": g.name, "canonical_name": g.canonical_name, "country_code": g.country_code, "target_type": g.target_type, "reach": s.reach if s.reach else None})
            return {"status": "success", "query": geo_query, "count": len(results), "geo_targets": results, "api_version": API_VERSION}

        elif action == "add_location_targets":
            if not campaign_id or not geo_target_ids: return {"status": "error", "message": "campaign_id and geo_target_ids required"}
            cc_service = client.get_service("CampaignCriterionService")
            cs = client.get_service("CampaignService")
            operations = []
            for geo_id in geo_target_ids:
                op = client.get_type("CampaignCriterionOperation"); c = op.create
                c.campaign = cs.campaign_path(customer_id, campaign_id)
                c.location.geo_target_constant = f"geoTargetConstants/{geo_id}"; c.negative = False
                if bid_modifier: c.bid_modifier = float(bid_modifier)
                operations.append(op)
            response = cc_service.mutate_campaign_criteria(customer_id=customer_id, operations=operations)
            return {"status": "success", "message": f"Added {len(response.results)} location targets", "api_version": API_VERSION}

        elif action == "exclude_locations":
            if not campaign_id or not geo_target_ids: return {"status": "error", "message": "campaign_id and geo_target_ids required"}
            cc_service = client.get_service("CampaignCriterionService")
            cs = client.get_service("CampaignService")
            operations = []
            for geo_id in geo_target_ids:
                op = client.get_type("CampaignCriterionOperation"); c = op.create
                c.campaign = cs.campaign_path(customer_id, campaign_id)
                c.location.geo_target_constant = f"geoTargetConstants/{geo_id}"; c.negative = True
                operations.append(op)
            response = cc_service.mutate_campaign_criteria(customer_id=customer_id, operations=operations)
            return {"status": "success", "message": f"Excluded {len(response.results)} locations", "api_version": API_VERSION}

        elif action == "remove_location_target":
            if not campaign_id or not criterion_id: return {"status": "error", "message": "campaign_id and criterion_id required"}
            cc_service = client.get_service("CampaignCriterionService")
            op = client.get_type("CampaignCriterionOperation")
            op.remove = f"customers/{customer_id}/campaignCriteria/{campaign_id}~{criterion_id}"
            response = cc_service.mutate_campaign_criteria(customer_id=customer_id, operations=[op])
            return {"status": "success", "message": "Location target removed", "api_version": API_VERSION}

        elif action == "list_geo_performance":
            where_parts = ["segments.date DURING " + date_range.upper()]
            if campaign_id: where_parts.append("campaign.id = " + str(campaign_id))
            if cost_min_micros: where_parts.append("metrics.cost_micros >= " + str(int(cost_min_micros)))
            if conversions_min: where_parts.append("metrics.conversions >= " + str(float(conversions_min)))
            query = f"SELECT geographic_view.country_criterion_id, geographic_view.location_type, campaign.id, campaign.name, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.ctr, metrics.average_cpc, metrics.cost_per_conversion FROM geographic_view WHERE {' AND '.join(where_parts)} ORDER BY {SORT_FIELDS.get(sort_by, SORT_FIELDS['cost'])} LIMIT {limit}"
            results = []; tc = 0; tv = 0
            for row in ga_service.search(customer_id=customer_id, query=query):
                cost = row.metrics.cost_micros; tc += cost; tv += row.metrics.conversions
                results.append({"country_criterion_id": str(row.geographic_view.country_criterion_id) if row.geographic_view.country_criterion_id else None, "location_type": row.geographic_view.location_type.name if row.geographic_view.location_type else "UNKNOWN", "campaign_id": str(row.campaign.id), "campaign_name": row.campaign.name, "impressions": row.metrics.impressions, "clicks": row.metrics.clicks, "cost": round(cost/1000000, 2), "conversions": round(row.metrics.conversions, 2), "ctr": round(row.metrics.ctr*100, 2) if row.metrics.ctr else 0, "avg_cpc": round(row.metrics.average_cpc/1000000, 2) if row.metrics.average_cpc else 0, "cost_per_conversion": round(row.metrics.cost_per_conversion/1000000, 2) if row.metrics.cost_per_conversion else None})
            return {"status": "success", "summary": {"total_locations": len(results), "total_cost": round(tc/1000000, 2), "total_conversions": round(tv, 2)}, "geo_performance": results, "api_version": API_VERSION}

        elif action == "list_targeted_locations":
            where = "campaign_criterion.negative = FALSE AND campaign_criterion.type = 'LOCATION'"
            if campaign_id: where += " AND campaign.id = " + str(campaign_id)
            results = []
            for row in ga_service.search(customer_id=customer_id, query=f"SELECT campaign_criterion.criterion_id, campaign_criterion.location.geo_target_constant, campaign_criterion.bid_modifier, campaign.id, campaign.name FROM campaign_criterion WHERE {where} LIMIT {limit}"):
                cc = row.campaign_criterion
                results.append({"criterion_id": str(cc.criterion_id), "geo_target_constant": cc.location.geo_target_constant, "bid_modifier": round(cc.bid_modifier, 2) if cc.bid_modifier else 1.0, "campaign_id": str(row.campaign.id), "campaign_name": row.campaign.name})
            return {"status": "success", "count": len(results), "targeted_locations": results, "api_version": API_VERSION}

        elif action == "list_excluded_locations":
            where = "campaign_criterion.negative = TRUE AND campaign_criterion.type = 'LOCATION'"
            if campaign_id: where += " AND campaign.id = " + str(campaign_id)
            results = []
            for row in ga_service.search(customer_id=customer_id, query=f"SELECT campaign_criterion.criterion_id, campaign_criterion.location.geo_target_constant, campaign.id, campaign.name FROM campaign_criterion WHERE {where} LIMIT {limit}"):
                results.append({"criterion_id": str(row.campaign_criterion.criterion_id), "geo_target_constant": row.campaign_criterion.location.geo_target_constant, "campaign_id": str(row.campaign.id), "campaign_name": row.campaign.name})
            return {"status": "success", "count": len(results), "excluded_locations": results, "api_version": API_VERSION}

        elif action == "update_location_bid_modifier":
            if not campaign_id or not criterion_id or bid_modifier is None: return {"status": "error", "message": "campaign_id, criterion_id, bid_modifier required"}
            cc_service = client.get_service("CampaignCriterionService")
            op = client.get_type("CampaignCriterionOperation"); c = op.update
            c.resource_name = f"customers/{customer_id}/campaignCriteria/{campaign_id}~{criterion_id}"
            c.bid_modifier = float(bid_modifier)
            client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, c._pb))
            response = cc_service.mutate_campaign_criteria(customer_id=customer_id, operations=[op])
            return {"status": "success", "new_bid_modifier": bid_modifier, "api_version": API_VERSION}

        else: return {"status": "error", "message": f"Unknown action: {action}"}
    except GoogleAdsException as ex:
        return {"status": "error", "errors": [{"code": str(e.error_code), "message": e.message} for e in ex.failure.errors]}
    except Exception as e: return {"status": "error", "message": str(e)}
