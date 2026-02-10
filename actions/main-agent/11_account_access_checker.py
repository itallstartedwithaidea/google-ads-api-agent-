try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
except ImportError:
    import subprocess
    subprocess.check_call(["pip", "install", "google-ads"])
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

def run(operation="list_accessible", customer_id=None, login_customer_id=None, search=None):
    try:
        client = get_client(login_customer_id)

        if operation == "list_accessible":
            customer_service = client.get_service("CustomerService")
            accessible = customer_service.list_accessible_customers()

            accounts = []
            for resource_name in accessible.resource_names:
                cid = resource_name.split("/")[-1]
                accounts.append({"customer_id": cid, "resource_name": resource_name})

            return {
                "status": "success",
                "total_accounts": len(accounts),
                "accounts": accounts,
                "api_version": API_VERSION
            }

        elif operation == "get_hierarchy":
            if not customer_id:
                return {"status": "error", "message": "customer_id required"}

            cid = str(customer_id).replace("-", "")
            login_id = login_customer_id or cid

            hierarchy_client = get_client(login_id)
            ga_service = hierarchy_client.get_service("GoogleAdsService")

            query = """
                SELECT
                    customer_client.id,
                    customer_client.descriptive_name,
                    customer_client.manager,
                    customer_client.level,
                    customer_client.currency_code,
                    customer_client.time_zone
                FROM customer_client
                WHERE customer_client.level <= 1
            """

            response = ga_service.search(customer_id=cid, query=query)

            hierarchy = []
            for row in response:
                cc = row.customer_client
                hierarchy.append({
                    "customer_id": str(cc.id),
                    "name": cc.descriptive_name,
                    "is_manager": cc.manager,
                    "level": cc.level,
                    "currency": cc.currency_code,
                    "timezone": cc.time_zone
                })

            return {
                "status": "success",
                "customer_id": cid,
                "hierarchy": hierarchy,
                "api_version": API_VERSION
            }

        elif operation == "search" or operation == "find":
            if not search:
                return {"status": "error", "message": "search parameter required"}

            customer_service = client.get_service("CustomerService")
            accessible = customer_service.list_accessible_customers()

            all_accounts = []
            search_lower = str(search).lower().replace("-", "")

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
                        account = {
                            "customer_id": str(cc.id),
                            "name": cc.descriptive_name or "",
                            "is_manager": cc.manager,
                            "level": cc.level,
                            "mcc_id": root_id if cc.level > 0 else None
                        }
                        exists = any(a["customer_id"] == account["customer_id"] for a in all_accounts)
                        if not exists:
                            all_accounts.append(account)
                except Exception as e:
                    all_accounts.append({
                        "customer_id": root_id,
                        "name": "[Root]",
                        "error": str(e)
                    })

            matches = []
            for acc in all_accounts:
                if str(acc["customer_id"]).replace("-", "") == search_lower:
                    matches.append(acc)
                elif search_lower in acc.get("name", "").lower():
                    matches.append(acc)

            if matches:
                best = matches[0]
                return {
                    "status": "success",
                    "found": True,
                    "match_count": len(matches),
                    "best_match": best,
                    "all_matches": matches,
                    "login_customer_id": best.get("mcc_id") or best["customer_id"],
                    "customer_id": best["customer_id"],
                    "api_version": API_VERSION
                }
            else:
                return {
                    "status": "success",
                    "found": False,
                    "message": "No account found matching: " + str(search),
                    "available_accounts": all_accounts,
                    "api_version": API_VERSION
                }

        else:
            return {
                "status": "error",
                "message": "Unknown operation: " + str(operation),
                "available": ["list_accessible", "get_hierarchy", "search", "find"]
            }

    except GoogleAdsException as ex:
        errors = []
        for e in ex.failure.errors:
            errors.append({"code": str(e.error_code), "message": e.message})
        return {"status": "error", "request_id": ex.request_id, "errors": errors}
    except Exception as e:
        return {"status": "error", "message": str(e), "type": type(e).__name__}
