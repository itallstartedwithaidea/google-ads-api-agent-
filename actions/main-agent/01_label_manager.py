import subprocess
subprocess.check_call(["pip", "install", "google-ads>=28.1.0"])

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
import json

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

def list_labels(client, customer_id, name_contains=None, color=None, limit=100):
    ga_service = client.get_service("GoogleAdsService")

    query = """
        SELECT
            label.id,
            label.name,
            label.status,
            label.text_label.background_color,
            label.text_label.description
        FROM label
        WHERE label.status = 'ENABLED'
    """

    response = ga_service.search(customer_id=customer_id, query=query)

    results = []
    for row in response:
        name = row.label.name
        label_color = row.label.text_label.background_color if row.label.text_label else ""

        if name_contains and name_contains.lower() not in name.lower():
            continue
        if color and color.lower() not in label_color.lower():
            continue

        results.append({
            "id": str(row.label.id),
            "name": name,
            "status": str(row.label.status).replace("LabelStatusEnum.LabelStatus.", ""),
            "color": label_color,
            "description": row.label.text_label.description if row.label.text_label else ""
        })

    return {"status": "success", "labels": results[:limit], "total_found": len(results)}

def create_label(client, customer_id, name, color="#000000", description=""):
    label_service = client.get_service("LabelService")

    operation = client.get_type("LabelOperation")
    label = operation.create
    label.name = name
    label.text_label.background_color = color
    label.text_label.description = description

    try:
        response = label_service.mutate_labels(
            customer_id=customer_id,
            operations=[operation]
        )
        return {
            "status": "success",
            "message": f"Label '{name}' created",
            "resource_name": response.results[0].resource_name
        }
    except GoogleAdsException as ex:
        return {"status": "error", "message": str(ex.failure.errors[0].message)}

def apply_label(client, customer_id, label_id, entity_type, entity_ids):
    """Apply label to entities. entity_type: CAMPAIGN, AD_GROUP, AD, KEYWORD"""

    service_map = {
        "CAMPAIGN": "CampaignLabelService",
        "AD_GROUP": "AdGroupLabelService",
        "AD": "AdGroupAdLabelService",
        "KEYWORD": "AdGroupCriterionLabelService"
    }

    if entity_type.upper() not in service_map:
        return {"status": "error", "message": f"Invalid entity_type. Use: CAMPAIGN, AD_GROUP, AD, KEYWORD"}

    service_name = service_map[entity_type.upper()]
    service = client.get_service(service_name)

    operations = []
    label_resource = f"customers/{customer_id}/labels/{label_id}"

    for entity_id in entity_ids:
        if entity_type.upper() == "CAMPAIGN":
            op = client.get_type("CampaignLabelOperation")
            op.create.campaign = f"customers/{customer_id}/campaigns/{entity_id}"
            op.create.label = label_resource
        elif entity_type.upper() == "AD_GROUP":
            op = client.get_type("AdGroupLabelOperation")
            op.create.ad_group = f"customers/{customer_id}/adGroups/{entity_id}"
            op.create.label = label_resource
        elif entity_type.upper() == "AD":
            op = client.get_type("AdGroupAdLabelOperation")
            parts = str(entity_id).split("~")
            if len(parts) != 2:
                return {"status": "error", "message": "For ADs, use format 'ad_group_id~ad_id'"}
            op.create.ad_group_ad = f"customers/{customer_id}/adGroupAds/{parts[0]}~{parts[1]}"
            op.create.label = label_resource
        elif entity_type.upper() == "KEYWORD":
            op = client.get_type("AdGroupCriterionLabelOperation")
            parts = str(entity_id).split("~")
            if len(parts) != 2:
                return {"status": "error", "message": "For KEYWORDs, use format 'ad_group_id~criterion_id'"}
            op.create.ad_group_criterion = f"customers/{customer_id}/adGroupCriteria/{parts[0]}~{parts[1]}"
            op.create.label = label_resource

        operations.append(op)

    try:
        if entity_type.upper() == "CAMPAIGN":
            response = service.mutate_campaign_labels(customer_id=customer_id, operations=operations)
        elif entity_type.upper() == "AD_GROUP":
            response = service.mutate_ad_group_labels(customer_id=customer_id, operations=operations)
        elif entity_type.upper() == "AD":
            response = service.mutate_ad_group_ad_labels(customer_id=customer_id, operations=operations)
        elif entity_type.upper() == "KEYWORD":
            response = service.mutate_ad_group_criterion_labels(customer_id=customer_id, operations=operations)

        return {
            "status": "success",
            "message": f"Label applied to {len(entity_ids)} {entity_type}(s)",
            "results": [r.resource_name for r in response.results]
        }
    except GoogleAdsException as ex:
        return {"status": "error", "message": str(ex.failure.errors[0].message)}

def list_labeled_entities(client, customer_id, label_id, entity_type="CAMPAIGN", campaign_ids=None, limit=100):
    ga_service = client.get_service("GoogleAdsService")

    if entity_type.upper() == "CAMPAIGN":
        query = f"""
            SELECT
                campaign.id,
                campaign.name,
                campaign.status,
                label.id,
                label.name
            FROM campaign_label
            WHERE label.id = {label_id}
        """
    elif entity_type.upper() == "AD_GROUP":
        query = f"""
            SELECT
                ad_group.id,
                ad_group.name,
                ad_group.status,
                campaign.id,
                campaign.name,
                label.id,
                label.name
            FROM ad_group_label
            WHERE label.id = {label_id}
        """
    else:
        return {"status": "error", "message": "entity_type must be CAMPAIGN or AD_GROUP"}

    response = ga_service.search(customer_id=customer_id, query=query)

    results = []
    for row in response:
        if entity_type.upper() == "CAMPAIGN":
            if campaign_ids and str(row.campaign.id) not in [str(c) for c in campaign_ids]:
                continue
            results.append({
                "entity_id": str(row.campaign.id),
                "entity_name": row.campaign.name,
                "entity_type": "CAMPAIGN",
                "status": str(row.campaign.status).replace("CampaignStatusEnum.CampaignStatus.", ""),
                "label_name": row.label.name
            })
        elif entity_type.upper() == "AD_GROUP":
            if campaign_ids and str(row.campaign.id) not in [str(c) for c in campaign_ids]:
                continue
            results.append({
                "entity_id": str(row.ad_group.id),
                "entity_name": row.ad_group.name,
                "entity_type": "AD_GROUP",
                "status": str(row.ad_group.status).replace("AdGroupStatusEnum.AdGroupStatus.", ""),
                "campaign_id": str(row.campaign.id),
                "campaign_name": row.campaign.name,
                "label_name": row.label.name
            })

    return {"status": "success", "labeled_entities": results[:limit], "total_found": len(results)}

def run(action, search=None, customer_id=None, label_id=None, name=None, color=None,
        description=None, entity_type=None, entity_ids=None, name_contains=None,
        campaign_ids=None, limit=100):

    client = get_client()
    cid = resolve_customer_id(client, search, customer_id)

    if action == "list_labels":
        return list_labels(client, cid, name_contains, color, limit)

    elif action == "create_label":
        if not name:
            return {"status": "error", "message": "name required"}
        return create_label(client, cid, name, color or "#000000", description or "")

    elif action == "apply_label":
        if not label_id or not entity_type or not entity_ids:
            return {"status": "error", "message": "label_id, entity_type, and entity_ids required"}
        return apply_label(client, cid, label_id, entity_type, entity_ids)

    elif action == "remove_label":
        return {"status": "error", "message": "remove_label not yet implemented - use Google Ads UI"}

    elif action == "list_labeled_entities":
        if not label_id:
            return {"status": "error", "message": "label_id required"}
        return list_labeled_entities(client, cid, label_id, entity_type or "CAMPAIGN", campaign_ids, limit)

    else:
        return {"status": "error", "message": f"Unknown action: {action}. Use: list_labels, create_label, apply_label, remove_label, list_labeled_entities"}
