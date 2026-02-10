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
    config = {"developer_token": secrets["DEVELOPER_TOKEN"], "client_id": secrets["CLIENT_ID"], "client_secret": secrets["CLIENT_SECRET"], "refresh_token": secrets["REFRESH_TOKEN"], "use_proto_plus": True}
    if login_customer_id:
        config["login_customer_id"] = str(login_customer_id).replace("-", "")
    return GoogleAdsClient.load_from_dict(config, version=API_VERSION)

def run(customer_id, action, login_customer_id=None, campaign_id=None, keyword_text=None,
        match_type="BROAD", shared_set_id=None, resource_name=None, level="campaign"):
    try:
        customer_id = str(customer_id).replace("-", "")
        client = get_client(login_customer_id)
        ga_service = client.get_service("GoogleAdsService")

        if action == "list_campaign_negatives":
            where = "campaign_criterion.negative = TRUE AND campaign_criterion.type = 'KEYWORD'"
            if campaign_id:
                where += f" AND campaign.id = {campaign_id}"
            query = f"SELECT campaign_criterion.criterion_id, campaign_criterion.keyword.text, campaign_criterion.keyword.match_type, campaign_criterion.negative, campaign.id, campaign.name FROM campaign_criterion WHERE {where} ORDER BY campaign_criterion.keyword.text LIMIT 1000"
            response = ga_service.search(customer_id=customer_id, query=query)
            negatives = [{"criterion_id": str(row.campaign_criterion.criterion_id), "keyword": row.campaign_criterion.keyword.text, "match_type": row.campaign_criterion.keyword.match_type.name, "campaign_id": str(row.campaign.id), "campaign_name": row.campaign.name, "resource_name": f"customers/{customer_id}/campaignCriteria/{row.campaign.id}~{row.campaign_criterion.criterion_id}"} for row in response]
            return {"status": "success", "count": len(negatives), "negative_keywords": negatives, "api_version": API_VERSION}

        elif action == "list_shared_sets":
            query = "SELECT shared_set.id, shared_set.name, shared_set.type, shared_set.status, shared_set.member_count FROM shared_set WHERE shared_set.type = 'NEGATIVE_KEYWORDS' AND shared_set.status != 'REMOVED' ORDER BY shared_set.name"
            response = ga_service.search(customer_id=customer_id, query=query)
            shared_sets = [{"id": str(row.shared_set.id), "name": row.shared_set.name, "type": row.shared_set.type_.name, "status": row.shared_set.status.name, "member_count": row.shared_set.member_count} for row in response]
            return {"status": "success", "count": len(shared_sets), "shared_sets": shared_sets, "api_version": API_VERSION}

        elif action == "add_campaign_negative":
            if not campaign_id or not keyword_text:
                return {"status": "error", "message": "campaign_id and keyword_text required"}
            cc_service = client.get_service("CampaignCriterionService")
            campaign_service = client.get_service("CampaignService")
            operation = client.get_type("CampaignCriterionOperation")
            criterion = operation.create
            criterion.campaign = campaign_service.campaign_path(customer_id, campaign_id)
            criterion.negative = True
            criterion.keyword.text = keyword_text
            criterion.keyword.match_type = getattr(client.enums.KeywordMatchTypeEnum, match_type)
            response = cc_service.mutate_campaign_criteria(customer_id=customer_id, operations=[operation])
            return {"status": "success", "resource_name": response.results[0].resource_name, "keyword": keyword_text, "match_type": match_type, "campaign_id": campaign_id, "api_version": API_VERSION}

        elif action == "add_to_shared_set":
            if not shared_set_id or not keyword_text:
                return {"status": "error", "message": "shared_set_id and keyword_text required"}
            sc_service = client.get_service("SharedCriterionService")
            shared_set_service = client.get_service("SharedSetService")
            operation = client.get_type("SharedCriterionOperation")
            criterion = operation.create
            criterion.shared_set = shared_set_service.shared_set_path(customer_id, shared_set_id)
            criterion.keyword.text = keyword_text
            criterion.keyword.match_type = getattr(client.enums.KeywordMatchTypeEnum, match_type)
            response = sc_service.mutate_shared_criteria(customer_id=customer_id, operations=[operation])
            return {"status": "success", "resource_name": response.results[0].resource_name, "keyword": keyword_text, "match_type": match_type, "shared_set_id": shared_set_id, "api_version": API_VERSION}

        elif action == "remove_negative":
            if not resource_name:
                return {"status": "error", "message": "resource_name required"}
            if level == "campaign" or "campaignCriteria" in resource_name:
                service = client.get_service("CampaignCriterionService")
                operation = client.get_type("CampaignCriterionOperation")
                operation.remove = resource_name
                response = service.mutate_campaign_criteria(customer_id=customer_id, operations=[operation])
            else:
                service = client.get_service("SharedCriterionService")
                operation = client.get_type("SharedCriterionOperation")
                operation.remove = resource_name
                response = service.mutate_shared_criteria(customer_id=customer_id, operations=[operation])
            return {"status": "success", "resource_name": response.results[0].resource_name, "message": "Negative keyword removed", "api_version": API_VERSION}

        elif action == "create_shared_set":
            if not keyword_text:
                return {"status": "error", "message": "Provide name via keyword_text parameter"}
            ss_service = client.get_service("SharedSetService")
            operation = client.get_type("SharedSetOperation")
            shared_set = operation.create
            shared_set.name = keyword_text
            shared_set.type_ = client.enums.SharedSetTypeEnum.NEGATIVE_KEYWORDS
            response = ss_service.mutate_shared_sets(customer_id=customer_id, operations=[operation])
            return {"status": "success", "resource_name": response.results[0].resource_name, "name": keyword_text, "api_version": API_VERSION}

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except GoogleAdsException as ex:
        errors = [{"code": str(e.error_code), "message": e.message} for e in ex.failure.errors]
        return {"status": "error", "request_id": ex.request_id, "errors": errors}
    except Exception as e:
        return {"status": "error", "message": str(e)}
