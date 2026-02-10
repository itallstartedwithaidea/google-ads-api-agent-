Secret Key	Description	Credential ID
DEVELOPER_TOKEN	Google Ads API Developer Token	d367d130-bc68-4f9a-8057-b22d7bfcc1aa
CLIENT_ID	OAuth2 Client ID	4cf4e22e-f66d-4728-b7a7-3655c6c87799
CLIENT_SECRET	OAuth2 Client Secret	b4dcdc1b-e2fa-471d-b1b3-453148c5ae19
REFRESH_TOKEN	OAuth2 Refresh Token	13ebb617-1662-43d6-8d06-2af3cf09c1d9
Full Code
try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
except ImportError:
    import subprocess
    subprocess.check_call(['pip', 'install', 'google-ads'])
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException

def get_client(login_customer_id=None):
    credentials = {
        "developer_token": secrets["DEVELOPER_TOKEN"],
        "client_id": secrets["CLIENT_ID"],
        "client_secret": secrets["CLIENT_SECRET"],
        "refresh_token": secrets["REFRESH_TOKEN"],
        "use_proto_plus": True
    }
    if login_customer_id:
        credentials["login_customer_id"] = str(login_customer_id).replace("-", "")
    return GoogleAdsClient.load_from_dict(credentials, version="v18")

def generate_keyword_ideas(client, customer_id, keywords=None, url=None, language_id="1000", geo_target_ids=None, limit=100):
    keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")

    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = customer_id
    request.language = f"languageConstants/{language_id}"

    # Add geo targets
    if geo_target_ids:
        for geo_id in geo_target_ids:
            request.geo_target_constants.append(f"geoTargetConstants/{geo_id}")
    else:
        # Default to US
        request.geo_target_constants.append("geoTargetConstants/2840")

    # Set keyword seed or URL seed
    if keywords:
        request.keyword_seed.keywords.extend(keywords)
    elif url:
        request.url_seed.url = url
    else:
        return []

    request.include_adult_keywords = False
    request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH_AND_PARTNERS

    results = []
    response = keyword_plan_idea_service.generate_keyword_ideas(request=request)

    for idea in response:
        metrics = idea.keyword_idea_metrics
        results.append({
            "keyword": idea.text,
            "avg_monthly_searches": metrics.avg_monthly_searches if metrics else 0,
            "competition": str(metrics.competition.name) if metrics and metrics.competition else "UNKNOWN",
            "competition_index": metrics.competition_index if metrics else 0,
            "low_top_of_page_bid": round(metrics.low_top_of_page_bid_micros / 1000000, 2) if metrics and metrics.low_top_of_page_bid_micros else 0,
            "high_top_of_page_bid": round(metrics.high_top_of_page_bid_micros / 1000000, 2) if metrics and metrics.high_top_of_page_bid_micros else 0
        })

        if len(results) >= limit:
            break

    return results

def get_historical_metrics(client, customer_id, keywords, language_id="1000", geo_target_ids=None):
    keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")

    request = client.get_type("GenerateKeywordHistoricalMetricsRequest")
    request.customer_id = customer_id
    request.keywords.extend(keywords)
    request.language = f"languageConstants/{language_id}"

    if geo_target_ids:
        for geo_id in geo_target_ids:
            request.geo_target_constants.append(f"geoTargetConstants/{geo_id}")
    else:
        request.geo_target_constants.append("geoTargetConstants/2840")

    request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH_AND_PARTNERS

    results = []
    response = keyword_plan_idea_service.generate_keyword_historical_metrics(request=request)

    for result in response.results:
        metrics = result.keyword_metrics

        # Get monthly search volumes
        monthly_volumes = []
        if metrics and metrics.monthly_search_volumes:
            for vol in metrics.monthly_search_volumes:
                monthly_volumes.append({
                    "year": vol.year,
                    "month": str(vol.month.name) if vol.month else "UNKNOWN",
                    "searches": vol.monthly_searches
                })

        results.append({
            "keyword": result.text,
            "avg_monthly_searches": metrics.avg_monthly_searches if metrics else 0,
            "competition": str(metrics.competition.name) if metrics and metrics.competition else "UNKNOWN",
            "low_top_of_page_bid": round(metrics.low_top_of_page_bid_micros / 1000000, 2) if metrics and metrics.low_top_of_page_bid_micros else 0,
            "high_top_of_page_bid": round(metrics.high_top_of_page_bid_micros / 1000000, 2) if metrics and metrics.high_top_of_page_bid_micros else 0,
            "monthly_volumes": monthly_volumes[-12:]  # Last 12 months
        })

    return results

def run(customer_id, action, login_customer_id=None, keywords=None, url=None, 
        language_id="1000", geo_target_ids=None, include_adult=False, limit=100):
    try:
        customer_id = str(customer_id).replace("-", "")
        if login_customer_id:
            login_customer_id = str(login_customer_id).replace("-", "")

        client = get_client(login_customer_id)

        if action == "generate_ideas":
            if not keywords and not url:
                return {"status": "error", "message": "keywords or url required"}
            ideas = generate_keyword_ideas(client, customer_id, keywords, url, language_id, geo_target_ids, limit)

            # Sort by search volume
            ideas.sort(key=lambda x: x["avg_monthly_searches"], reverse=True)

            return {
                "status": "success",
                "count": len(ideas),
                "seed_keywords": keywords,
                "seed_url": url,
                "keyword_ideas": ideas
            }

        elif action == "get_historical_metrics":
            if not keywords:
                return {"status": "error", "message": "keywords list required"}
            metrics = get_historical_metrics(client, customer_id, keywords, language_id, geo_target_ids)
            return {
                "status": "success",
                "count": len(metrics),
                "historical_metrics": metrics
            }

        else:
            return {"status": "error", "message": f"Unknown action: {action}. Use 'generate_ideas' or 'get_historical_metrics'"}

    except GoogleAdsException as ex:
        errors = [{"code": str(e.error_code), "message": e.message} for e in ex.failure.errors]
        return {"status": "error", "request_id": ex.request_id, "errors": errors}
    except Exception as e:
        return {"status": "error", "message": str(e)}
python
5.2 Package Installer [For EveryAgent]
Field	Value
Action ID	8845bc27-db18-47ac-8150-6ae02e36de80
Integration	_(none — no credentials)_
Created	2026-01-29T19:16:17.495Z
Updated	2026-01-29T19:16:17.501Z
Description
Installs optional Python packages by category to enhance agent capabilities.

Categories available:
- 'math': mpmath, gmpy2, uncertainties (high-precision calculations)
- 'testing': hypothesis, pytest (testing frameworks)
- 'advertising': facebook-business, bingads, msal, google-analytics-data (ad platform APIs)
- 'presentation': python-pptx (PowerPoint generation)
- 'html_css': jinja2, dominate, cssutils, css-inline, premailer, htmlmin (HTML/CSS tools)
- 'color_design': colour, colorthief, palettable (color manipulation)
- 'persistence': dill, cloudpickle, tinydb, diskcache (data persistence/caching)
- 'financial': pint, quantstats, lifetimes (financial analysis)
- 'all': Install all categories

Returns a detailed report of what installed successfully vs failed.

Usage: Run this action first to enable enhanced capabilities before using other actions that depend on these packages.
livecodeserver
Function Signature
def run(install_category="all")
python
Credential Configuration
None — this action requires no secrets.

Full Code
# ===========================================
# NINJACAT CUSTOM ACTION: FULL PACKAGE INSTALLER
# ===========================================
# WARNING: Some packages WILL fail due to system dependencies
# This gives you a complete inventory of what works
# ===========================================

import json
import time
from datetime import datetime

# ===========================================
# SAFE INSTALLATION HELPER
# ===========================================
def safe_install_and_import(package_spec, import_name=None, from_import=None):
    """
    Attempts to install and import a package safely.

    Args:
        package_spec: Full pip spec like 'mpmath>=1.3.0'
        import_name: Module name to import (if different from package)
        from_import: Specific item to import from module

    Returns:
        tuple: (success: bool, module_or_error: module|str)
    """
    if import_name is None:
        # Extract base name from spec like 'mpmath>=1.3.0' -> 'mpmath'
        import_name = package_spec.split('>=')[0].split('==')[0].split('[')[0].replace('-', '_')

    # First try: maybe it's already installed
    try:
        if from_import:
            mod = __import__(import_name, fromlist=[from_import])
            return (True, mod)
        else:
            return (True, __import__(import_name))
    except ImportError:
        pass

    # Second try: install then import
    try:
        import pip
        pip.main(['install', package_spec, '--quiet', '--disable-pip-version-check'])

        if from_import:
            mod = __import__(import_name, fromlist=[from_import])
            return (True, mod)
        else:
            return (True, __import__(import_name))
    except Exception as e:
        return (False, str(e))


# ===========================================
# MAIN RUN FUNCTION
# ===========================================
def run(install_category="all"):
    """
    Installs requested package categories and reports results.

    Args:
        install_category: "all", "math", "testing", "advertising", "presentation",
                         "html_css", "color_design", "persistence", or "financial"

    Returns:
        dict with installation results
    """

    start_time = time.time()
    results = {
        "status": "success",
        "requested_category": install_category,
        "timestamp": datetime.now().isoformat(),
        "packages": {},
        "summary": {
            "total": 0,
            "installed": 0,
            "failed": 0
        }
    }

    # ===========================================
    # PACKAGE DEFINITIONS BY CATEGORY
    # ===========================================

    packages = {
        "math": [
            {"spec": "mpmath>=1.3.0", "import": "mpmath", "name": "mpmath"},
            {"spec": "gmpy2>=2.1.5", "import": "gmpy2", "name": "gmpy2"},
            {"spec": "uncertainties>=3.1.7", "import": "uncertainties", "name": "uncertainties"},
        ],
        "testing": [
            {"spec": "hypothesis>=6.92.0", "import": "hypothesis", "name": "hypothesis"},
            {"spec": "pytest>=7.4.3", "import": "pytest", "name": "pytest"},
        ],
        "advertising": [
            {"spec": "facebook-business>=19.0.0", "import": "facebook_business", "name": "facebook-business"},
            {"spec": "bingads>=13.0.18", "import": "bingads", "name": "bingads"},
            {"spec": "msal>=1.26.0", "import": "msal", "name": "msal"},
            {"spec": "google-analytics-data>=0.18.4", "import": "google.analytics.data", "name": "google-analytics-data"},
        ],
        "presentation": [
            {"spec": "python-pptx>=0.6.23", "import": "pptx", "name": "python-pptx"},
        ],
        "html_css": [
            {"spec": "jinja2>=3.1.2", "import": "jinja2", "name": "jinja2"},
