# ============================================
try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
except ImportError:
    import subprocess
    subprocess.check_call(["pip", "install", "google-ads"])
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException

API_VERSION = "v22"
SORT_FIELDS = {'cost': 'metrics.cost_micros DESC', 'conversions': 'metrics.conversions DESC', 'clicks': 'metrics.clicks DESC', 'impressions': 'metrics.impressions DESC'}

def get_client(login_customer_id=None):
    config = {"developer_token": secrets["DEVELOPER_TOKEN"], "client_id": secrets["CLIENT_ID"], "client_secret": secrets["CLIENT_SECRET"], "refresh_token": secrets["REFRESH_TOKEN"], "use_proto_plus": True}
    if login_customer_id: config["login_customer_id"] = str(login_customer_id).replace("-", "")
    return GoogleAdsClient.load_from_dict(config, version=API_VERSION)

def dollars_to_micros(dollars):
    if dollars is None: return None
    return int(float(dollars) * 1000000)

def run(customer_id, action, login_customer_id=None, campaign_id=None, ad_group_id=None, date_range='LAST_30_DAYS', term_contains=None, status_filter=None, cost_min=None, cost_max=None, conversions_min=None, conversions_max=None, clicks_min=None, impressions_min=None, sort_by='cost', limit=200, cost_min_micros=None, cost_max_micros=None):
    try:
        customer_id = str(customer_id).replace("-", "")
        if login_customer_id: login_customer_id = str(login_customer_id).replace("-", "")
        client = get_client(login_customer_id)
        ga_service = client.get_service("GoogleAdsService")
        if cost_min is not None: cost_min_micros = dollars_to_micros(cost_min)
        if cost_max is not None: cost_max_micros = dollars_to_micros(cost_max)
        limit = min(int(limit), 1000)
        where_parts = ["segments.date DURING " + date_range.upper()]
        if campaign_id: where_parts.append("campaign.id = " + str(campaign_id))
        if ad_group_id: where_parts.append("ad_group.id = " + str(ad_group_id))
        if term_contains: where_parts.append("search_term_view.search_term LIKE '%" + term_contains.replace("'", "''") + "%'")
        if status_filter and status_filter.upper() != 'ALL': where_parts.append("search_term_view.status = '" + status_filter.upper() + "'")
        if cost_min_micros is not None: where_parts.append("metrics.cost_micros >= " + str(int(cost_min_micros)))
        if cost_max_micros is not None: where_parts.append("metrics.cost_micros <= " + str(int(cost_max_micros)))
        if conversions_min is not None: where_parts.append("metrics.conversions >= " + str(float(conversions_min)))
        if conversions_max is not None: where_parts.append("metrics.conversions <= " + str(float(conversions_max)))
        if clicks_min is not None: where_parts.append("metrics.clicks >= " + str(int(clicks_min)))
        if impressions_min is not None: where_parts.append("metrics.impressions >= " + str(int(impressions_min)))
        if action == "get_converting_terms":
            if conversions_min is None: where_parts.append("metrics.conversions > 0")
            sort_by = sort_by if sort_by != 'cost' else 'conversions'
        elif action == "get_wasted_spend":
            if conversions_max is None: where_parts.append("metrics.conversions = 0")
            if cost_min_micros is None: where_parts.append("metrics.cost_micros > 0")
            sort_by = 'cost'
        where_clause = " AND ".join(where_parts)
        order_by = SORT_FIELDS.get(sort_by, SORT_FIELDS['cost'])
        query = f"SELECT search_term_view.search_term, search_term_view.status, campaign.id, campaign.name, ad_group.id, ad_group.name, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value, metrics.ctr, metrics.average_cpc, metrics.cost_per_conversion FROM search_term_view WHERE {where_clause} ORDER BY {order_by} LIMIT {limit}"
        response = ga_service.search(customer_id=customer_id, query=query)
        results = []; total_cost = 0; total_conversions = 0; total_clicks = 0
        for row in response:
            cost = row.metrics.cost_micros; conversions = row.metrics.conversions
            total_cost += cost; total_conversions += conversions; total_clicks += row.metrics.clicks
            recommendation = None
            if conversions > 0 and row.search_term_view.status.name == 'NONE': recommendation = 'ADD_AS_KEYWORD'
            elif conversions == 0 and cost > 5000000: recommendation = 'ADD_AS_NEGATIVE'
            elif conversions == 0 and cost > 0: recommendation = 'MONITOR'
            results.append({"search_term": row.search_term_view.search_term, "status": row.search_term_view.status.name, "campaign_id": str(row.campaign.id), "campaign_name": row.campaign.name, "ad_group_id": str(row.ad_group.id), "ad_group_name": row.ad_group.name, "impressions": row.metrics.impressions, "clicks": row.metrics.clicks, "cost": round(cost / 1000000, 2), "conversions": round(conversions, 2), "conversion_value": round(row.metrics.conversions_value, 2), "ctr": round(row.metrics.ctr * 100, 2) if row.metrics.ctr else 0, "avg_cpc": round(row.metrics.average_cpc / 1000000, 2) if row.metrics.average_cpc else 0, "cost_per_conversion": round(row.metrics.cost_per_conversion / 1000000, 2) if row.metrics.cost_per_conversion else None, "recommendation": recommendation})
        summary = {"total_terms": len(results), "total_cost": round(total_cost / 1000000, 2), "total_conversions": round(total_conversions, 2), "potential_negatives": sum(1 for r in results if r['recommendation'] == 'ADD_AS_NEGATIVE'), "potential_keywords": sum(1 for r in results if r['recommendation'] == 'ADD_AS_KEYWORD')}
        return {"status": "success", "action": action, "date_range": date_range, "summary": summary, "search_terms": results, "api_version": API_VERSION}
    except GoogleAdsException as ex:
        errors = [{"code": str(e.error_code), "message": e.message} for e in ex.failure.errors]
        return {"status": "error", "request_id": ex.request_id, "errors": errors}
    except Exception as e:
        return {"status": "error", "message": str(e)}
