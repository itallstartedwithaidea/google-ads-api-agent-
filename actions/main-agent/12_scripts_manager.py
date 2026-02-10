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

def run(action, search=None, customer_id=None, name=None, name_contains=None,
        status=None, last_run_status=None, script_id=None, code=None, limit=100):
    """
    Note: Google Ads API v22 does not expose Scripts directly.
    Scripts are managed through the Google Ads UI or Apps Script.

    This action provides guidance on using Scripts.
    """

    client = get_client()
    cid = resolve_customer_id(client, search, customer_id)

    if action == "list_scripts":
        return {
            "status": "info",
            "message": "Scripts are not directly accessible via the Google Ads API.",
            "guidance": {
                "access_via": "Google Ads UI > Tools & Settings > Bulk Actions > Scripts",
                "api_alternative": "Use Google Ads API directly for automation instead of Scripts",
                "documentation": "https://developers.google.com/google-ads/scripts/docs/overview"
            },
            "customer_id": cid
        }

    elif action == "create_script":
        return {
            "status": "info",
            "message": "Scripts must be created via Google Ads UI.",
            "steps": [
                "1. Go to Google Ads > Tools & Settings > Bulk Actions > Scripts",
                "2. Click the + button to create a new script",
                "3. Paste your JavaScript code",
                "4. Authorize the script to access your account",
                "5. Set a schedule if needed"
            ],
            "tip": "For complex automation, consider using the Google Ads API directly (which this agent uses)"
        }

    elif action == "run_script":
        return {
            "status": "info",
            "message": "Scripts cannot be run via API.",
            "alternative": "I can perform most script-like operations directly via the Google Ads API. What would you like to automate?"
        }

    elif action == "get_script_logs":
        return {
            "status": "info",
            "message": "Script logs are available in the Google Ads UI.",
            "access": "Google Ads > Tools & Settings > Bulk Actions > Scripts > [Script Name] > Logs"
        }

    else:
        return {
            "status": "error", 
            "message": f"Unknown action: {action}. Use: list_scripts, create_script, run_script, get_script_logs",
            "note": "Scripts have limited API support - most operations require the Google Ads UI"
        }
