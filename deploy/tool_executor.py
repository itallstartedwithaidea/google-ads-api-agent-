"""
Google Ads API Agent — Tool Executor (Production-Ready)
Executes tool calls by loading and running the corresponding action Python files.

Handles three agent-platform → standalone Python adaptation issues:
1. secrets injection — Platform injects `secrets` as a global; we do the same pre-exec
2. pip install suppression — Actions run subprocess pip install at import time;
   we monkey-patch subprocess to skip these since requirements.txt handles deps
3. Parameter filtering — Actions have explicit run() params (no **kwargs in 26/28);
   we inspect the signature and only pass matching params to avoid TypeErrors
"""

import os
import sys
import json
import inspect
import subprocess
import importlib.util
import traceback
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from deploy.tool_schemas import TOOL_TO_ACTION_FILE

logger = logging.getLogger(__name__)

# =============================================================================
# PIP INSTALL SUPPRESSOR
# =============================================================================

_original_check_call = subprocess.check_call
_original_run = subprocess.run

def _suppressed_check_call(cmd, *args, **kwargs):
    if isinstance(cmd, (list, tuple)) and len(cmd) >= 2 and cmd[0] == "pip" and cmd[1] == "install":
        logger.debug(f"Suppressed pip install: {' '.join(cmd)}")
        return 0
    return _original_check_call(cmd, *args, **kwargs)

def _suppressed_run(cmd, *args, **kwargs):
    if isinstance(cmd, (list, tuple)) and len(cmd) >= 2 and cmd[0] == "pip" and cmd[1] == "install":
        logger.debug(f"Suppressed pip install: {' '.join(cmd)}")
        class FakeResult:
            returncode = 0
            stdout = ""
            stderr = ""
        return FakeResult()
    return _original_run(cmd, *args, **kwargs)


class ToolExecutor:
    """Executes tools by loading action Python files and calling their run() function."""

    def __init__(self, repo_root: str = None, credentials: Dict[str, str] = None):
        self.repo_root = Path(repo_root or os.path.dirname(os.path.dirname(__file__)))
        self.credentials = credentials or self._load_credentials_from_env()
        self._action_cache: Dict[str, Any] = {}
        self._signature_cache: Dict[str, inspect.Signature] = {}

    def _load_credentials_from_env(self) -> Dict[str, str]:
        keys = [
            "GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CLIENT_ID",
            "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN",
            "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
            "DEVELOPER_TOKEN", "CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN",
            "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET",
            "SEARCHAPI_API_KEY", "GOOGLE_AI_API_KEY",
        ]
        creds = {}
        for key in keys:
            val = os.environ.get(key)
            if val:
                creds[key] = val
        # Auto-map Pattern A -> Pattern B
        for short, long in [("DEVELOPER_TOKEN", "GOOGLE_ADS_DEVELOPER_TOKEN"),
                            ("CLIENT_ID", "GOOGLE_ADS_CLIENT_ID"),
                            ("CLIENT_SECRET", "GOOGLE_ADS_CLIENT_SECRET"),
                            ("REFRESH_TOKEN", "GOOGLE_ADS_REFRESH_TOKEN")]:
            if short not in creds and long in creds:
                creds[short] = creds[long]
        return creds

    def _get_secrets_for_tool(self, tool_name: str) -> Dict[str, str]:
        no_cred = {"package_installer", "session_state_manager"}
        if tool_name in no_cred:
            return {}
        if tool_name == "cloudinary_creative_tools":
            return {k: v for k, v in self.credentials.items() if k.startswith("CLOUDINARY_")}
        pattern_a = {
            "label_manager", "conversion_tracking_manager", "scripts_manager",
            "experiments_manager", "query_planner", "recommendations_manager",
            "device_performance_manager", "change_history_manager",
            "campaign_creator", "ad_schedule_manager", "bidding_strategy_manager",
            "pmax_asset_group_manager"
        }
        if tool_name in pattern_a:
            return {k: v for k, v in self.credentials.items() if k.startswith("GOOGLE_ADS_")}
        return {
            "DEVELOPER_TOKEN": self.credentials.get("DEVELOPER_TOKEN", ""),
            "CLIENT_ID": self.credentials.get("CLIENT_ID", ""),
            "CLIENT_SECRET": self.credentials.get("CLIENT_SECRET", ""),
            "REFRESH_TOKEN": self.credentials.get("REFRESH_TOKEN", ""),
        }

    def _load_action_module(self, tool_name: str):
        """
        Load action file as a Python module with:
        1. secrets dict injected into module namespace BEFORE execution
        2. subprocess monkey-patched to suppress pip installs
        3. Module cached after first load
        """
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

        # Inject secrets BEFORE exec so `secrets["KEY"]` resolves during module load
        secrets = self._get_secrets_for_tool(tool_name)
        module.__dict__["secrets"] = secrets

        # Suppress pip installs during module loading
        subprocess.check_call = _suppressed_check_call
        subprocess.run = _suppressed_run
        try:
            spec.loader.exec_module(module)
        finally:
            subprocess.check_call = _original_check_call
            subprocess.run = _original_run

        self._action_cache[tool_name] = module
        if hasattr(module, "run"):
            self._signature_cache[tool_name] = inspect.signature(module.run)

        return module

    def _filter_params(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter tool_input to only include parameters the run() function accepts.
        
        26 of 28 action files have explicit params (no **kwargs).
        Passing an unexpected kwarg would raise TypeError.
        This inspects the actual function signature and drops any extras.
        """
        sig = self._signature_cache.get(tool_name)
        if not sig:
            return tool_input

        # If function has **kwargs, pass everything
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            return tool_input

        accepted = set(sig.parameters.keys())
        filtered = {}
        dropped = []
        for key, value in tool_input.items():
            if key in accepted:
                filtered[key] = value
            else:
                dropped.append(key)

        if dropped:
            logger.warning(f"Tool '{tool_name}': dropped params not in run() signature: {dropped}")

        return filtered

    def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """
        Execute a tool call: load module → filter params → call run() → return result.
        """
        try:
            module = self._load_action_module(tool_name)

            if not hasattr(module, "run"):
                return json.dumps({"error": f"Action '{tool_name}' has no run() function"})

            filtered_input = self._filter_params(tool_name, tool_input)

            logger.info(f"Executing: {tool_name}({', '.join(f'{k}={repr(v)[:50]}' for k,v in filtered_input.items())})")

            result = module.run(**filtered_input)

            if isinstance(result, str):
                return result
            return json.dumps(result, indent=2, default=str)

        except Exception as e:
            error_detail = traceback.format_exc()
            logger.error(f"Tool execution failed: {tool_name}\n{error_detail}")
            return json.dumps({
                "error": str(e),
                "tool": tool_name,
                "traceback": error_detail
            })

    def list_available_tools(self) -> list:
        available = []
        for tool_name, action_file in TOOL_TO_ACTION_FILE.items():
            file_path = self.repo_root / action_file
            available.append({
                "tool": tool_name,
                "file": action_file,
                "exists": file_path.exists()
            })
        return available

    def get_run_signature(self, tool_name: str) -> Dict:
        """Debug helper: get the actual run() function signature for a tool."""
        try:
            module = self._load_action_module(tool_name)
            sig = inspect.signature(module.run)
            return {
                "tool": tool_name,
                "params": {
                    name: {
                        "default": repr(param.default) if param.default != inspect.Parameter.empty else "REQUIRED",
                    }
                    for name, param in sig.parameters.items()
                }
            }
        except Exception as e:
            return {"tool": tool_name, "error": str(e)}
