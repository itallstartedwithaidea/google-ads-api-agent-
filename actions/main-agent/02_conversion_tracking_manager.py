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

def list_conversion_actions(client, customer_id, category=None, status=None, name_contains=None,
                            conversions_min=None, conversion_value_min=None, conversion_value_max=None,
                            date_range="LAST_30_DAYS", limit=100):
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            conversion_action.id,
            conversion_action.name,
            conversion_action.category,
            conversion_action.type,
            conversion_action.status,
            conversion_action.primary_for_goal,
            conversion_action.counting_type,
            conversion_action.attribution_model_settings.attribution_model,
            conversion_action.value_settings.default_value,
            conversion_action.click_through_lookback_window_days,
            metrics.conversions,
            metrics.conversions_value,
            metrics.all_conversions,
            metrics.all_conversions_value
        FROM conversion_action
        WHERE conversion_action.status != 'REMOVED'
    """

    if status:
        query += f" AND conversion_action.status = '{status}'"

    if category:
        query += f" AND conversion_action.category = '{category}'"

    response = ga_service.search(customer_id=customer_id, query=query)

    results = []
    for row in response:
        conv_value = row.metrics.conversions_value
        conversions = row.metrics.conversions
        name = row.conversion_action.name

        if name_contains and name_contains.lower() not in name.lower():
            continue
        if conversions_min is not None and conversions < conversions_min:
            continue
        if conversion_value_min is not None and conv_value < conversion_value_min:
            continue
        if conversion_value_max is not None and conv_value > conversion_value_max:
            continue

        results.append({
            "id": str(row.conversion_action.id),
            "name": name,
            "category": str(row.conversion_action.category).replace("ConversionActionCategoryEnum.ConversionActionCategory.", ""),
            "type": str(row.conversion_action.type_).replace("ConversionActionTypeEnum.ConversionActionType.", ""),
            "status": str(row.conversion_action.status).replace("ConversionActionStatusEnum.ConversionActionStatus.", ""),
            "primary_for_goal": row.conversion_action.primary_for_goal,
            "counting_type": str(row.conversion_action.counting_type).replace("ConversionActionCountingTypeEnum.ConversionActionCountingType.", ""),
            "attribution_model": str(row.conversion_action.attribution_model_settings.attribution_model).replace("AttributionModelEnum.AttributionModel.", ""),
            "default_value": row.conversion_action.value_settings.default_value if row.conversion_action.value_settings else 0,
            "lookback_window_days": row.conversion_action.click_through_lookback_window_days,
            "conversions": round(conversions, 2),
            "conversions_value": round(conv_value, 2),
            "all_conversions": round(row.metrics.all_conversions, 2),
            "all_conversions_value": round(row.metrics.all_conversions_value, 2)
        })

    return {
        "status": "success", 
        "conversion_actions": results[:limit], 
        "total_found": len(results),
        "filters_applied": {
            "category": category, "status": status, "name_contains": name_contains,
            "conversions_min": conversions_min, "conversion_value_min": conversion_value_min
        }
    }

def create_conversion_action(client, customer_id, name, category, counting_type="ONE_PER_CLICK",
                             default_value=0, attribution_model="GOOGLE_SEARCH_ATTRIBUTION_DATA_DRIVEN",
                             lookback_window_days=30):
    """Create conversion action. default_value is in DOLLARS."""
    conv_service = client.get_service("ConversionActionService")

    operation = client.get_type("ConversionActionOperation")
    conv_action = operation.create
    conv_action.name = name
    conv_action.type_ = client.enums.ConversionActionTypeEnum.WEBPAGE

    category_enum = client.enums.ConversionActionCategoryEnum
    category_map = {
        "PURCHASE": category_enum.PURCHASE,
        "LEAD": category_enum.LEAD,
        "SIGNUP": category_enum.SIGNUP,
        "PAGE_VIEW": category_enum.PAGE_VIEW,
        "ADD_TO_CART": category_enum.ADD_TO_CART,
        "BEGIN_CHECKOUT": category_enum.BEGIN_CHECKOUT,
        "CONTACT": category_enum.CONTACT,
        "SUBMIT_LEAD_FORM": category_enum.SUBMIT_LEAD_FORM,
        "BOOK_APPOINTMENT": category_enum.BOOK_APPOINTMENT,
        "REQUEST_QUOTE": category_enum.REQUEST_QUOTE,
        "GET_DIRECTIONS": category_enum.GET_DIRECTIONS,
        "OUTBOUND_CLICK": category_enum.OUTBOUND_CLICK,
        "DEFAULT": category_enum.DEFAULT
    }
    conv_action.category = category_map.get(category.upper(), category_enum.DEFAULT)

    counting_enum = client.enums.ConversionActionCountingTypeEnum
    conv_action.counting_type = counting_enum.ONE_PER_CLICK if counting_type == "ONE_PER_CLICK" else counting_enum.MANY_PER_CLICK

    conv_action.value_settings.default_value = default_value
    conv_action.value_settings.always_use_default_value = default_value > 0

    conv_action.click_through_lookback_window_days = lookback_window_days

    attr_enum = client.enums.AttributionModelEnum
    attr_map = {
        "DATA_DRIVEN": attr_enum.GOOGLE_SEARCH_ATTRIBUTION_DATA_DRIVEN,
        "LAST_CLICK": attr_enum.GOOGLE_SEARCH_ATTRIBUTION_LAST_CLICK,
        "FIRST_CLICK": attr_enum.GOOGLE_SEARCH_ATTRIBUTION_FIRST_CLICK,
        "LINEAR": attr_enum.GOOGLE_SEARCH_ATTRIBUTION_LINEAR,
        "TIME_DECAY": attr_enum.GOOGLE_SEARCH_ATTRIBUTION_TIME_DECAY,
        "POSITION_BASED": attr_enum.GOOGLE_SEARCH_ATTRIBUTION_POSITION_BASED
    }
    conv_action.attribution_model_settings.attribution_model = attr_map.get(
        attribution_model.upper().replace("GOOGLE_SEARCH_ATTRIBUTION_", ""),
        attr_enum.GOOGLE_SEARCH_ATTRIBUTION_DATA_DRIVEN
    )

    try:
        response = conv_service.mutate_conversion_actions(
            customer_id=customer_id,
            operations=[operation]
        )
        return {
            "status": "success",
            "message": f"Conversion action '{name}' created",
            "resource_name": response.results[0].resource_name,
            "default_value_dollars": default_value
        }
    except GoogleAdsException as ex:
        return {"status": "error", "message": str(ex.failure.errors[0].message)}

def update_conversion_action(client, customer_id, conversion_action_id, name=None, status=None,
                             default_value=None, counting_type=None, lookback_window_days=None):
    """Update conversion action. default_value is in DOLLARS."""
    conv_service = client.get_service("ConversionActionService")

    operation = client.get_type("ConversionActionOperation")
    conv_action = operation.update
    conv_action.resource_name = f"customers/{customer_id}/conversionActions/{conversion_action_id}"

    field_mask = []

    if name:
        conv_action.name = name
        field_mask.append("name")

    if status:
        status_enum = client.enums.ConversionActionStatusEnum
        status_map = {"ENABLED": status_enum.ENABLED, "PAUSED": status_enum.PAUSED}
        conv_action.status = status_map.get(status.upper(), status_enum.ENABLED)
        field_mask.append("status")

    if default_value is not None:
        conv_action.value_settings.default_value = default_value
        conv_action.value_settings.always_use_default_value = default_value > 0
        field_mask.append("value_settings.default_value")
        field_mask.append("value_settings.always_use_default_value")

    if counting_type:
        counting_enum = client.enums.ConversionActionCountingTypeEnum
        conv_action.counting_type = counting_enum.ONE_PER_CLICK if counting_type == "ONE_PER_CLICK" else counting_enum.MANY_PER_CLICK
        field_mask.append("counting_type")

    if lookback_window_days:
        conv_action.click_through_lookback_window_days = lookback_window_days
        field_mask.append("click_through_lookback_window_days")

    operation.update_mask.paths.extend(field_mask)

    try:
        response = conv_service.mutate_conversion_actions(
            customer_id=customer_id,
            operations=[operation]
        )
        return {
            "status": "success",
            "message": "Conversion action updated",
            "resource_name": response.results[0].resource_name,
            "fields_updated": field_mask
        }
    except GoogleAdsException as ex:
        return {"status": "error", "message": str(ex.failure.errors[0].message)}

def run(action, search=None, customer_id=None, category=None, status=None, name_contains=None,
        conversions_min=None, conversion_value_min=None, conversion_value_max=None,
        name=None, counting_type=None, default_value=None, attribution_model=None,
        lookback_window_days=None, conversion_action_id=None, date_range="LAST_30_DAYS", limit=100):

    client = get_client()
    cid = resolve_customer_id(client, search, customer_id)

    if action == "list_conversion_actions":
        return list_conversion_actions(client, cid, category, status, name_contains,
                                       conversions_min, conversion_value_min, conversion_value_max,
                                       date_range, limit)

    elif action == "create_conversion_action":
        if not name or not category:
            return {"status": "error", "message": "name and category required"}
        return create_conversion_action(client, cid, name, category, counting_type or "ONE_PER_CLICK",
                                       default_value or 0, attribution_model or "DATA_DRIVEN",
                                       lookback_window_days or 30)

    elif action == "update_conversion_action":
        if not conversion_action_id:
            return {"status": "error", "message": "conversion_action_id required"}
        return update_conversion_action(client, cid, conversion_action_id, name, status,
                                       default_value, counting_type, lookback_window_days)

    elif action == "get_conversion_attribution":
        result = list_conversion_actions(client, cid, category, status, name_contains,
                                        conversions_min, conversion_value_min, conversion_value_max,
                                        date_range, limit)
        if result["status"] == "success":
            attribution_summary = [{
                "name": ca["name"],
                "attribution_model": ca["attribution_model"],
                "lookback_window_days": ca["lookback_window_days"],
                "counting_type": ca["counting_type"],
                "conversions": ca["conversions"]
            } for ca in result["conversion_actions"]]
            return {"status": "success", "attribution_settings": attribution_summary}
        return result

    else:
        return {"status": "error", "message": f"Unknown action: {action}. Use: list_conversion_actions, create_conversion_action, update_conversion_action, get_conversion_attribution"}
