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

SERVICE_CONFIG = {
    "campaign": {
        "service": "CampaignService",
        "mutate_method": "mutate_campaigns",
        "operation_type": "CampaignOperation",
        "status_enum": "CampaignStatusEnum"
    },
    "ad_group": {
        "service": "AdGroupService",
        "mutate_method": "mutate_ad_groups",
        "operation_type": "AdGroupOperation",
        "status_enum": "AdGroupStatusEnum"
    },
    "ad_group_criterion": {
        "service": "AdGroupCriterionService",
        "mutate_method": "mutate_ad_group_criteria",
        "operation_type": "AdGroupCriterionOperation",
        "status_enum": "AdGroupCriterionStatusEnum"
    },
    "ad_group_ad": {
        "service": "AdGroupAdService",
        "mutate_method": "mutate_ad_group_ads",
        "operation_type": "AdGroupAdOperation",
        "status_enum": "AdGroupAdStatusEnum"
    },
    "campaign_budget": {
        "service": "CampaignBudgetService",
        "mutate_method": "mutate_campaign_budgets",
        "operation_type": "CampaignBudgetOperation",
        "status_enum": None
    },
    "campaign_criterion": {
        "service": "CampaignCriterionService",
        "mutate_method": "mutate_campaign_criteria",
        "operation_type": "CampaignCriterionOperation",
        "status_enum": None
    }
}

def build_operation(client, entity, op_type, data, customer_id):
    config = SERVICE_CONFIG.get(entity)
    if not config:
        raise ValueError("Unknown entity type: " + entity)

    operation = client.get_type(config["operation_type"])

    if op_type == "remove":
        operation.remove = data["resource_name"]
        return operation

    if op_type == "create":
        target = operation.create
    elif op_type == "update":
        target = operation.update
        if "resource_name" in data:
            target.resource_name = data["resource_name"]
    else:
        raise ValueError("Unknown operation type: " + op_type)

    if "status" in data and config["status_enum"]:
        status_enum = getattr(client.enums, config["status_enum"])
        target.status = getattr(status_enum, data["status"])

    if entity == "campaign":
        if "name" in data:
            target.name = data["name"]
        if "campaign_budget" in data:
            target.campaign_budget = data["campaign_budget"]

    elif entity == "ad_group":
        if "name" in data:
            target.name = data["name"]
        if "campaign" in data:
            target.campaign = data["campaign"]
        if "cpc_bid_micros" in data:
            target.cpc_bid_micros = int(data["cpc_bid_micros"])

    elif entity == "ad_group_criterion":
        if "ad_group" in data:
            target.ad_group = data["ad_group"]
        if "keyword" in data:
            target.keyword.text = data["keyword"]["text"]
            target.keyword.match_type = getattr(
                client.enums.KeywordMatchTypeEnum,
                data["keyword"].get("match_type", "BROAD")
            )
        if "cpc_bid_micros" in data:
            target.cpc_bid_micros = int(data["cpc_bid_micros"])
        if "negative" in data:
            target.negative = data["negative"]

    elif entity == "campaign_budget":
        if "name" in data:
            target.name = data["name"]
        if "amount_micros" in data:
            target.amount_micros = int(data["amount_micros"])
        if "delivery_method" in data:
            target.delivery_method = getattr(
                client.enums.BudgetDeliveryMethodEnum,
                data["delivery_method"]
            )

    if op_type == "update":
        client.copy_from(
            operation.update_mask,
            protobuf_helpers.field_mask(None, target._pb),
        )

    return operation

def run(customer_id, operations, login_customer_id=None):
    try:
        customer_id = str(customer_id).replace("-", "")
        client = get_client(login_customer_id)

        results = []

        entity_ops = {}
        for i, op in enumerate(operations):
            entity = op.get("entity")
            if entity not in entity_ops:
                entity_ops[entity] = []
            entity_ops[entity].append((i, op))

        for entity, ops in entity_ops.items():
            config = SERVICE_CONFIG.get(entity)
            if not config:
                for idx, _ in ops:
                    results.append({
                        "index": idx,
                        "status": "error",
                        "message": "Unknown entity: " + entity
                    })
                continue

            built_ops = []
            op_indices = []

            for idx, op in ops:
                try:
                    built_op = build_operation(
                        client, entity, op.get("type"), op.get("data", {}), customer_id
                    )
                    built_ops.append(built_op)
                    op_indices.append(idx)
                except Exception as e:
                    results.append({
                        "index": idx,
                        "status": "error",
                        "message": str(e)
                    })

            if built_ops:
                try:
                    service = client.get_service(config["service"])
                    mutate_method = getattr(service, config["mutate_method"])
                    response = mutate_method(
                        customer_id=customer_id,
                        operations=built_ops
                    )
                    for i, result in enumerate(response.results):
                        results.append({
                            "index": op_indices[i],
                            "status": "success",
                            "resource_name": result.resource_name
                        })
                except GoogleAdsException as ex:
                    for idx in op_indices:
                        errors = [{"code": str(e.error_code), "message": e.message} for e in ex.failure.errors]
                        results.append({
                            "index": idx,
                            "status": "error",
                            "errors": errors
                        })

        results.sort(key=lambda x: x.get("index", 0))
        success_count = sum(1 for r in results if r.get("status") == "success")

        return {
            "status": "success" if success_count == len(operations) else "partial" if success_count > 0 else "error",
            "total_operations": len(operations),
            "successful": success_count,
            "failed": len(operations) - success_count,
            "results": results,
            "api_version": API_VERSION
        }

    except GoogleAdsException as ex:
        errors = [{"code": str(e.error_code), "message": e.message} for e in ex.failure.errors]
        return {"status": "error", "request_id": ex.request_id, "errors": errors}
    except Exception as e:
        return {"status": "error", "message": str(e)}
