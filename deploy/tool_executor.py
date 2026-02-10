"""
Google Ads Agent — Tool Executor
Executes tool calls by loading and running the corresponding action Python files.

The action files from Relevance AI / agent platforms each define a `run()` function.
This executor:
1. Loads the action file
2. Injects credentials as `secrets` dict
3. Calls `run(**tool_input)` 
4. Returns the result as a string for Claude
"""

import os
import sys
import json
import importlib.util
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

from deploy.tool_schemas import TOOL_TO_ACTION_FILE


class ToolExecutor:
    """Executes tools by loading action Python files and calling their run() function."""

    def __init__(self, repo_root: str = None, credentials: Dict[str, str] = None):
        self.repo_root = Path(repo_root or os.path.dirname(os.path.dirname(__file__)))
        self.credentials = credentials or self._load_credentials_from_env()
        self._action_cache: Dict[str, Any] = {}

    def _load_credentials_from_env(self) -> Dict[str, str]:
        """Load all credentials from environment variables."""
        keys = [
            # Google Ads (Pattern A names)
            "GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CLIENT_ID",
            "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN",
            "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
            # Google Ads (Pattern B names — same values, different keys)
            "DEVELOPER_TOKEN", "CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN",
            # Cloudinary
            "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET",
            # SearchAPI
            "SEARCHAPI_API_KEY",
            # Google AI / Gemini
            "GOOGLE_AI_API_KEY",
        ]
        creds = {}
        for key in keys:
            val = os.environ.get(key)
            if val:
                creds[key] = val

        # Auto-map Pattern A → Pattern B if Pattern B not set explicitly
        mapping = {
            "DEVELOPER_TOKEN": "GOOGLE_ADS_DEVELOPER_TOKEN",
            "CLIENT_ID": "GOOGLE_ADS_CLIENT_ID",
            "CLIENT_SECRET": "GOOGLE_ADS_CLIENT_SECRET",
            "REFRESH_TOKEN": "GOOGLE_ADS_REFRESH_TOKEN",
        }
        for short_key, long_key in mapping.items():
            if short_key not in creds and long_key in creds:
                creds[short_key] = creds[long_key]

        return creds

    def _get_secrets_for_tool(self, tool_name: str) -> Dict[str, str]:
        """Return the appropriate secrets dict for a given tool based on its credential pattern."""
        # Pattern D — no credentials
        no_cred_tools = {"package_installer", "session_state_manager"}
        if tool_name in no_cred_tools:
            return {}

        # Pattern C — Cloudinary
        if tool_name == "cloudinary_creative_tools":
            return {k: v for k, v in self.credentials.items() if k.startswith("CLOUDINARY_")}

        # Pattern A tools (5-key, GOOGLE_ADS_ prefix)
        pattern_a_tools = {
            "label_manager", "conversion_tracking_manager", "scripts_manager",
            "experiments_manager", "query_planner", "recommendations_manager",
            "device_performance_manager", "change_history_manager",
            "campaign_creator", "ad_schedule_manager", "bidding_strategy_manager",
            "pmax_asset_group_manager"
        }
        if tool_name in pattern_a_tools:
            return {k: v for k, v in self.credentials.items() if k.startswith("GOOGLE_ADS_")}

        # Pattern B tools (4-key, short names) — everything else with Google Ads
        return {
            "DEVELOPER_TOKEN": self.credentials.get("DEVELOPER_TOKEN", ""),
            "CLIENT_ID": self.credentials.get("CLIENT_ID", ""),
            "CLIENT_SECRET": self.credentials.get("CLIENT_SECRET", ""),
            "REFRESH_TOKEN": self.credentials.get("REFRESH_TOKEN", ""),
        }

    def _load_action_module(self, tool_name: str):
        """Dynamically load a Python action file as a module."""
        if tool_name in self._action_cache:
            return self._action_cache[tool_name]

        action_file = TOOL_TO_ACTION_FILE.get(tool_name)
        if not action_file:
            raise ValueError(f"No action file mapped for tool: {tool_name}")

        file_path = self.repo_root / action_file
        if not file_path.exists():
            raise FileNotFoundError(f"Action file not found: {file_path}")

        spec = importlib.util.spec_from_file_location(f"action_{tool_name}", str(file_path))
        module = importlib.util.module_from_spec(spec)

        # Inject `secrets` as a module-level global before execution
        module.secrets = self._get_secrets_for_tool(tool_name)

        spec.loader.exec_module(module)
        self._action_cache[tool_name] = module
        return module

    def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """
        Execute a tool call and return the result as a string.
        
        Args:
            tool_name: The tool name from Claude's tool_use block
            tool_input: The input dict from Claude's tool_use block
            
        Returns:
            JSON string of the result, or error message
        """
        try:
            module = self._load_action_module(tool_name)

            if not hasattr(module, "run"):
                return json.dumps({"error": f"Action file for '{tool_name}' has no run() function"})

            # Call the run function with the tool input
            result = module.run(**tool_input)

            # Serialize result
            if isinstance(result, str):
                return result
            return json.dumps(result, indent=2, default=str)

        except Exception as e:
            error_detail = traceback.format_exc()
            return json.dumps({
                "error": str(e),
                "tool": tool_name,
                "traceback": error_detail
            })

    def list_available_tools(self) -> list:
        """List all tools that have action files present on disk."""
        available = []
        for tool_name, action_file in TOOL_TO_ACTION_FILE.items():
            file_path = self.repo_root / action_file
            available.append({
                "tool": tool_name,
                "file": action_file,
                "exists": file_path.exists()
            })
        return available
