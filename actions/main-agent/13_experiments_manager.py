import subprocess
subprocess.check_call(["pip", "install", "google-ads>=28.1.0"])

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
import json

MICROS = 1_000_000

def get_client():
    return GoogleAdsClient.load_from_dict({
        "developer_token": secrets["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "client_id": secrets["GOOGLE_ADS_CLIENT_ID"],
        "client_secret": secrets["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token": secrets["GOOGLE_ADS_REFRESH_TOKEN"],
        "login_customer_id": secrets.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", ""),
        "use_proto_plus": True
    })

def resolve_customer_id(client, search=None, customer_id=None):
    if customer_id:
        return customer_id.replace("-", "")
    if not search:
        raise ValueError("Either customer_id or search parameter required")

    login_id = secrets.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")
    ga_service = client.get_service("GoogleAdsService")

    query = "SELECT customer_client.id, customer_client.descriptive_name FROM customer_client WHERE customer_client.manager = FALSE"
    response = ga_service.search(customer_id=login_id, query=query)

    search_lower = search.lower()
    for row in response:
        if search_lower in row.customer_client.descriptive_name.lower():
            return str(row.customer_client.id)

    raise ValueError(f"No account found matching '{search}'")

def list_experiments(client, customer_id, status=None, campaign_ids=None, name_contains=None,
                     cost_min=None, cost_max=None, date_range="LAST_30_DAYS", limit=100):
    ga_service = client.get_service("GoogleAdsService")

    query = """
        SELECT
            experiment.resource_name,
            experiment.experiment_id,
            experiment.name,
            experiment.description,
            experiment.status,
            experiment.start_date,
            experiment.end_date,
            experiment.goals,
            experiment.long_running_operation
        FROM experiment
    """

    conditions = []
    if status:
        conditions.append(f"experiment.status = '{status}'")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    try:
        response = ga_service.search(customer_id=customer_id, query=query)

        results = []
        for row in response:
            name = row.experiment.name

            if name_contains and name_contains.lower() not in name.lower():
                continue

            results.append({
                "experiment_id": str(row.experiment.experiment_id),
                "resource_name": row.experiment.resource_name,
                "name": name,
                "description": row.experiment.description,
                "status": str(row.experiment.status).replace("ExperimentStatusEnum.ExperimentStatus.", ""),
                "start_date": row.experiment.start_date,
                "end_date": row.experiment.end_date
            })

        return {
            "status": "success", 
            "experiments": results[:limit], 
            "total_found": len(results),
            "filters_applied": {
                "status": status, "name_contains": name_contains,
                "cost_min_dollars": cost_min, "cost_max_dollars": cost_max
            }
        }
    except GoogleAdsException as ex:
        return {"status": "error", "message": str(ex.failure.errors[0].message)}

def create_experiment(client, customer_id, name, base_campaign_id, description="",
                      traffic_split=50, start_date=None, end_date=None):
    """Create a campaign experiment. traffic_split is percentage to experiment (e.g., 50 = 50%)"""
    experiment_service = client.get_service("ExperimentService")

    operation = client.get_type("ExperimentOperation")
    experiment = operation.create
    experiment.name = name
    experiment.description = description
    experiment.type_ = client.enums.ExperimentTypeEnum.SEARCH_CUSTOM
    experiment.status = client.enums.ExperimentStatusEnum.SETUP

    if start_date:
        experiment.start_date = start_date
    if end_date:
        experiment.end_date = end_date

    base_arm = experiment.experiment_arms.add()
    base_arm.control = True
    base_arm.name = "Control"
    base_arm.campaigns.append(f"customers/{customer_id}/campaigns/{base_campaign_id}")
    base_arm.traffic_split = 100 - traffic_split

    treatment_arm = experiment.experiment_arms.add()
    treatment_arm.control = False
    treatment_arm.name = "Treatment"
    treatment_arm.traffic_split = traffic_split

    try:
        response = experiment_service.mutate_experiments(
            customer_id=customer_id,
            operations=[operation]
        )
        return {
            "status": "success",
            "message": f"Experiment '{name}' created in SETUP status",
            "resource_name": response.results[0].resource_name,
            "next_steps": [
                "1. Create a campaign draft with your changes",
                "2. Associate the draft with this experiment",
                "3. Schedule or start the experiment"
            ]
        }
    except GoogleAdsException as ex:
        return {"status": "error", "message": str(ex.failure.errors[0].message)}

def get_experiment_results(client, customer_id, experiment_id, date_range="LAST_30_DAYS"):
    """Get experiment performance comparison. All costs returned in dollars."""
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            experiment_arm.resource_name,
            experiment_arm.name,
            experiment_arm.control,
            experiment_arm.traffic_split,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            metrics.ctr,
            metrics.average_cpc
        FROM experiment_arm
        WHERE experiment_arm.experiment = 'customers/{customer_id}/experiments/{experiment_id}'
    """

    try:
        response = ga_service.search(customer_id=customer_id, query=query)

        arms = []
        for row in response:
            cost_dollars = row.metrics.cost_micros / MICROS if row.metrics.cost_micros else 0
            avg_cpc_dollars = row.metrics.average_cpc / MICROS if row.metrics.average_cpc else 0

            arms.append({
                "name": row.experiment_arm.name,
                "is_control": row.experiment_arm.control,
                "traffic_split": row.experiment_arm.traffic_split,
                "impressions": row.metrics.impressions or 0,
                "clicks": row.metrics.clicks or 0,
                "cost": round(cost_dollars, 2),
                "conversions": round(row.metrics.conversions or 0, 2),
                "conversions_value": round(row.metrics.conversions_value or 0, 2),
                "ctr": round((row.metrics.ctr or 0) * 100, 2),
                "avg_cpc": round(avg_cpc_dollars, 2)
            })

        control = next((a for a in arms if a["is_control"]), None)
        treatment = next((a for a in arms if not a["is_control"]), None)

        lift = None
        if control and treatment and control["conversions"] > 0:
            conv_lift = ((treatment["conversions"] - control["conversions"]) / control["conversions"]) * 100
            lift = {
                "conversion_lift_percent": round(conv_lift, 2),
                "control_conversions": control["conversions"],
                "treatment_conversions": treatment["conversions"]
            }

        return {
            "status": "success",
            "experiment_id": experiment_id,
            "arms": arms,
            "lift_analysis": lift,
            "note": "All cost values are in dollars"
        }
    except GoogleAdsException as ex:
        return {"status": "error", "message": str(ex.failure.errors[0].message)}

def end_experiment(client, customer_id, experiment_id, apply_changes=False):
    """End experiment. If apply_changes=True, promotes winning variant."""
    experiment_service = client.get_service("ExperimentService")

    operation = client.get_type("ExperimentOperation")
    experiment = operation.update
    experiment.resource_name = f"customers/{customer_id}/experiments/{experiment_id}"

    if apply_changes:
        experiment.status = client.enums.ExperimentStatusEnum.GRADUATED
    else:
        experiment.status = client.enums.ExperimentStatusEnum.REMOVED

    operation.update_mask.paths.append("status")

    try:
        response = experiment_service.mutate_experiments(
            customer_id=customer_id,
            operations=[operation]
        )
        action = "graduated (changes applied)" if apply_changes else "ended (changes discarded)"
        return {
            "status": "success",
            "message": f"Experiment {action}",
            "resource_name": response.results[0].resource_name
        }
    except GoogleAdsException as ex:
        return {"status": "error", "message": str(ex.failure.errors[0].message)}

def run(action, search=None, customer_id=None, experiment_id=None, name=None,
        base_campaign_id=None, description=None, traffic_split=50,
        start_date=None, end_date=None, apply_changes=False,
        status=None, campaign_ids=None, name_contains=None,
        cost_min=None, cost_max=None, date_range="LAST_30_DAYS", limit=100):

    client = get_client()
    cid = resolve_customer_id(client, search, customer_id)

    if action == "list_experiments":
        return list_experiments(client, cid, status, campaign_ids, name_contains,
                               cost_min, cost_max, date_range, limit)

    elif action == "create_experiment":
        if not name or not base_campaign_id:
            return {"status": "error", "message": "name and base_campaign_id required"}
        return create_experiment(client, cid, name, base_campaign_id, description or "",
                                traffic_split, start_date, end_date)

    elif action == "get_experiment_results":
        if not experiment_id:
            return {"status": "error", "message": "experiment_id required"}
        return get_experiment_results(client, cid, experiment_id, date_range)

    elif action == "end_experiment":
        if not experiment_id:
            return {"status": "error", "message": "experiment_id required"}
        return end_experiment(client, cid, experiment_id, apply_changes)

    elif action == "promote_experiment":
        if not experiment_id:
            return {"status": "error", "message": "experiment_id required"}
        return end_experiment(client, cid, experiment_id, apply_changes=True)

    else:
        return {"status": "error", "message": f"Unknown action: {action}. Use: list_experiments, create_experiment, get_experiment_results, end_experiment, promote_experiment"}
