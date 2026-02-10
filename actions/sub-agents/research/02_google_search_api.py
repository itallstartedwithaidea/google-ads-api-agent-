Full Code
# Google Search API via SearchAPI.io
import requests

def run(query, location=None, gl="us", hl="en", num_results=10, time_period=None, device="desktop", safe="off", page=1):
    """
    Perform a Google search using SearchAPI.io

    Args:
        query: Search query string (required)
        location: Geographic location for results (e.g., 'New York, United States')
        gl: Country code (default: 'us')
        hl: Interface language (default: 'en')
        num_results: Number of results (default: 10)
        time_period: Time filter - 'last_hour', 'last_day', 'last_week', 'last_month', 'last_year'
        device: Device type - 'desktop', 'mobile', 'tablet' (default: 'desktop')
        safe: SafeSearch - 'active' or 'off' (default: 'off')
        page: Page number (default: 1)

    Returns:
        dict: Search results including organic results, knowledge graph, ads, etc.
    """

    # Get API key from secrets
    api_key = secrets.get("SEARCHAPI_API_KEY")

    if not api_key:
        return {
            "status": "error",
            "message": "SearchAPI.io API key not configured. Please add your API key in the Custom Action settings."
        }

    # Build request parameters
    params = {
        "engine": "google",
        "api_key": api_key,
        "q": query,
        "gl": gl,
        "hl": hl,
        "device": device,
        "safe": safe,
        "page": page
    }

    # Add optional parameters if provided
    if location:
        params["location"] = location

    if time_period and time_period in ["last_hour", "last_day", "last_week", "last_month", "last_year"]:
        params["time_period"] = time_period

    try:
        # Make the API request
        response = requests.get(
            "https://www.searchapi.io/api/v1/search",
            params=params,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()

            # Build a clean response summary
            result = {
                "status": "success",
                "query": query,
                "search_metadata": data.get("search_metadata", {}),
                "search_information": data.get("search_information", {})
            }

            # Include all available result types
            result_types = [
                "organic_results", "knowledge_graph", "answer_box", 
                "related_questions", "ads", "shopping_ads", "local_ads",
                "top_stories", "local_results", "local_map",
                "inline_images", "inline_videos", "inline_shopping",
                "related_searches", "discussions_and_forums",
                "ai_overview", "weather_result", "sports_results",
                "jobs", "events", "courses", "scholarly_articles",
                "inline_recipes", "perspectives", "inline_tweets"
            ]

            for result_type in result_types:
                if result_type in data and data[result_type]:
                    result[result_type] = data[result_type]

            # Add pagination info if available
            if "pagination" in data:
                result["pagination"] = data["pagination"]

            return result

        elif response.status_code == 401:
            return {
                "status": "error",
                "message": "Invalid API key. Please check your SearchAPI.io API key.",
                "status_code": 401
            }
        elif response.status_code == 429:
            return {
                "status": "error",
                "message": "Rate limit exceeded. Please wait before making more requests.",
                "status_code": 429
            }
        else:
            return {
                "status": "error",
                "message": f"API returned status code {response.status_code}",
                "status_code": response.status_code,
                "details": response.text[:500] if response.text else None
            }

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": "Request timed out. Please try again."
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"Request failed: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}"
        }
python
5.4 Google Ads Transparency Center - API
Field	Value
Action ID	458e1715-d525-4af3-8b4a-65fc19675708
Integration	google_ads
Created	2026-01-29T19:16:32.699Z
Updated	2026-01-29T19:16:33.184Z
Description
Retrieves competitor ad intelligence from Google Ads Transparency Center - see what ads competitors are running, their formats, and how long they've been active.

Use this for:
- Competitive intelligence on competitor ad campaigns
- See what ads a company is running (by domain or advertiser ID)
- Analyze ad formats (text, image, video) being used
- Track how long ads have been running
- Research ad strategies across platforms (YouTube, Search, Shopping, Maps)

Parameters:
- advertiser_id (optional): Advertiser's unique ID starting with 'AR'. Required if domain not provided.
- domain (optional): Advertiser's domain (e.g., 'tesla.com'). Required if advertiser_id not provided.
- region (optional): Region filter (default: 'anywhere')
- platform (optional): Filter by platform - 'google_play', 'google_maps', 'google_search', 'youtube', 'google_shopping'
- ad_format (optional): Filter by format - 'text', 'image', 'video'
- time_period (optional): 'today', 'yesterday', 'last_7_days', 'last_30_days' or custom 'YYYY-MM-DD..YYYY-MM-DD'
- num (optional): Number of results (default: 40, max: 100)
- next_page_token (optional): Token for pagination from previous response

Returns:
- ad_creatives: Array of ads with ID, format, dates shown, advertiser info, preview links
- format_summary: Count of ads by format type
- pagination: Token for fetching more results
- search_information: Total results count
pgsql
Function Signature
def run(advertiser_id=None, domain=None, region="anywhere", platform=None, ad_format=None, 
        time_period=None, num=40, next_page_token=None)
