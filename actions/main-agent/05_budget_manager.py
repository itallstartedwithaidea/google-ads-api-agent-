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
SORT_FIELDS = {'amount': 'campaign_budget.amount_micros DESC', 'name': 'campaign_budget.name ASC', 'campaigns_using': 'campaign_budget.reference_count DESC'}

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

def dollars_to_micros(dollars):
    if dollars is None:
        return None
    return int(float(dollars) * 1000000)

def run(customer_id, action, login_customer_id=None, budget_id=None,
        name=None, delivery_method="STANDARD",
        amount=None, amount_min=None, amount_max=None,
        status_filter=None, name_contains=None, shared_filter=None, 
        sort_by='amount', limit=100,
        amount_micros=None, amount_min_micros=None, amount_max_micros=None):
    try:
        customer_id = str(customer_id).replace("-", "")
        client = get_client(login_customer_id)
        ga_service = client.get_service("GoogleAdsService")
        if amount is not None:
            amount_micros = dollars_to_micros(amount)
        if amount_min is not None:
            amount_min_micros = dollars_to_micros(amount_min)
        if amount_max is not None:
            amount_max_micros = dollars_to_micros(amount_max)
        limit = min(int(limit), 500)

        if action == "list_budgets":
            where_parts = []
            if status_filter and status_filter.upper() != 'ALL':
                where_parts.append(f"campaign_budget.status = '{status_filter.upper()}'")
            else:
                where_parts.append("campaign_budget.status != 'REMOVED'")
            if name_contains:
                where_parts.append(f"campaign_budget.name LIKE '%{name_contains}%'")
            if amount_min_micros is not None:
                where_parts.append(f"campaign_budget.amount_micros >= {int(amount_min_micros)}")
            if amount_max_micros is not None:
                where_parts.append(f"campaign_budget.amount_micros <= {int(amount_max_micros)}")
            if shared_filter:
                sf = shared_filter.upper()
                if sf == 'SHARED':
                    where_parts.append("campaign_budget.explicitly_shared = TRUE")
                elif sf == 'NOT_SHARED':
                    where_parts.append("campaign_budget.explicitly_shared = FALSE")
            where_clause = " AND ".join(where_parts) if where_parts else "campaign_budget.status != 'REMOVED'"
            order_by = SORT_FIELDS.get(sort_by, SORT_FIELDS['amount'])
            query = f"SELECT campaign_budget.id, campaign_budget.name, campaign_budget.amount_micros, campaign_budget.status, campaign_budget.delivery_method, campaign_budget.total_amount_micros, campaign_budget.explicitly_shared, campaign_budget.reference_count FROM campaign_budget WHERE {where_clause} ORDER BY {order_by} LIMIT {limit}"
            response = ga_service.search(customer_id=customer_id, query=query)
            budgets = []
            total_budget_amount = 0
            shared_count = 0
            for row in response:
                budget_amount = row.campaign_budget.amount_micros
                total_budget_amount += budget_amount
                if row.campaign_budget.explicitly_shared:
                    shared_count += 1
                budgets.append({"id": str(row.campaign_budget.id), "name": row.campaign_budget.name, "amount": round(budget_amount / 1000000, 2), "status": row.campaign_budget.status.name, "delivery_method": row.campaign_budget.delivery_method.name, "explicitly_shared": row.campaign_budget.explicitly_shared, "campaigns_using": row.campaign_budget.reference_count})
            return {"status": "success", "count": len(budgets), "budgets": budgets, "summary": {"total_daily_budget": round(total_budget_amount / 1000000, 2), "shared_budgets": shared_count, "individual_budgets": len(budgets) - shared_count}, "api_version": API_VERSION}

        elif action == "update_budget":
            if not budget_id:
                return {"status": "error", "message": "budget_id required"}
            if not amount_micros:
                return {"status": "error", "message": "amount (in dollars) required"}
            budget_service = client.get_service("CampaignBudgetService")
            operation = client.get_type("CampaignBudgetOperation")
            budget = operation.update
            budget.resource_name = budget_service.campaign_budget_path(customer_id, budget_id)
            budget.amount_micros = int(amount_micros)
            client.copy_from(operation.update_mask, protobuf_helpers.field_mask(None, budget._pb))
            response = budget_service.mutate_campaign_budgets(customer_id=customer_id, operations=[operation])
            return {"status": "success", "resource_name": response.results[0].resource_name, "new_amount": round(amount_micros / 1000000, 2), "api_version": API_VERSION}

        elif action == "create_budget":
            if not name:
                return {"status": "error", "message": "name required"}
            if not amount_micros:
                return {"status": "error", "message": "amount (in dollars) required"}
            budget_service = client.get_service("CampaignBudgetService")
            operation = client.get_type("CampaignBudgetOperation")
            budget = operation.create
            budget.name = name
            budget.amount_micros = int(amount_micros)
            budget.delivery_method = client.enums.BudgetDeliveryMethodEnum[delivery_method]
            response = budget_service.mutate_campaign_budgets(customer_id=customer_id, operations=[operation])
            return {"status": "success", "resource_name": response.results[0].resource_name, "name": name, "amount": round(amount_micros / 1000000, 2), "api_version": API_VERSION}

        elif action == "get_pacing":
            query = "SELECT campaign.id, campaign.name, campaign.status, campaign_budget.id, campaign_budget.name, campaign_budget.amount_micros, metrics.cost_micros FROM campaign WHERE campaign.status = 'ENABLED' AND segments.date = TODAY"
            response = ga_service.search(customer_id=customer_id, query=query)
            pacing = []
            for row in response:
                budget_amount = row.campaign_budget.amount_micros
                spent = row.metrics.cost_micros
                pacing_pct = (spent / budget_amount * 100) if budget_amount > 0 else 0
                status = "ON_TRACK"
                if pacing_pct >= 100:
                    status = "OVER_BUDGET"
                elif pacing_pct >= 90:
                    status = "NEAR_LIMIT"
                elif pacing_pct < 50:
                    status = "UNDERPACING"
                pacing.append({"campaign_id": str(row.campaign.id), "campaign_name": row.campaign.name, "budget_id": str(row.campaign_budget.id), "budget_name": row.campaign_budget.name, "daily_budget": round(budget_amount / 1000000, 2), "spent_today": round(spent / 1000000, 2), "pacing_percent": round(pacing_pct, 1), "status": status})
            pacing.sort(key=lambda x: x["pacing_percent"], reverse=True)
            over_budget = sum(1 for p in pacing if p["status"] == "OVER_BUDGET")
            near_limit = sum(1 for p in pacing if p["status"] == "NEAR_LIMIT")
            underpacing = sum(1 for p in pacing if p["status"] == "UNDERPACING")
            return {"status": "success", "count": len(pacing), "pacing": pacing, "summary": {"over_budget": over_budget, "near_limit": near_limit, "on_track": len(pacing) - over_budget - near_limit - underpacing, "underpacing": underpacing}, "api_version": API_VERSION}

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except GoogleAdsException as ex:
        errors = [{"code": str(e.error_code), "message": e.message} for e in ex.failure.errors]
        return {"status": "error", "request_id": ex.request_id, "errors": errors}
    except Exception as e:
        return {"status": "error", "message": str(e)}
