# ============================================
try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
except ImportError:
    import subprocess
    subprocess.check_call(["pip", "install", "google-ads"])
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException

def get_client(login_customer_id=None):
    config = {"developer_token": secrets["DEVELOPER_TOKEN"], "client_id": secrets["CLIENT_ID"], "client_secret": secrets["CLIENT_SECRET"], "refresh_token": secrets["REFRESH_TOKEN"], "use_proto_plus": True}
    if login_customer_id: config["login_customer_id"] = str(login_customer_id).replace("-", "")
    return GoogleAdsClient.load_from_dict(config, version="v19")

def run(customer_id, login_customer_id=None):
    try:
        customer_id = str(customer_id).replace("-", "")
        if login_customer_id: login_customer_id = str(login_customer_id).replace("-", "")
        client = get_client(login_customer_id)
        ga_service = client.get_service("GoogleAdsService")
        query = "SELECT customer_user_access.user_id, customer_user_access.email_address, customer_user_access.access_role, customer_user_access.access_creation_date_time, customer_user_access.inviter_user_email_address FROM customer_user_access"
        response = ga_service.search(customer_id=customer_id, query=query)
        users = []
        for row in response:
            access = row.customer_user_access
            users.append({"user_id": str(access.user_id), "email": access.email_address, "access_role": access.access_role.name if access.access_role else "UNKNOWN", "created": access.access_creation_date_time, "invited_by": access.inviter_user_email_address})
        return {"status": "success", "customer_id": customer_id, "user_count": len(users), "users": users, "access_levels_explained": {"ADMIN": "Full access", "STANDARD": "Can make changes", "READ_ONLY": "View only - CANNOT make changes", "EMAIL_ONLY": "Receives emails only"}}
    except GoogleAdsException as ex:
        errors = [{"code": str(e.error_code), "message": e.message} for e in ex.failure.errors]
        return {"status": "error", "request_id": ex.request_id, "errors": errors}
    except Exception as e:
        return {"status": "error", "message": str(e)}
