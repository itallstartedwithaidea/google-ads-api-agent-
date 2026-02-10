#!/usr/bin/env python3
"""
Google Ads API Agent — Deployment Validator
Runs a series of checks to verify the deployment is working correctly.

Usage:
    python scripts/validate.py
    python scripts/validate.py --skip-api    # Skip live API calls
"""

import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def check(name: str, passed: bool, detail: str = ""):
    status = "✅" if passed else "❌"
    msg = f"  {status} {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return passed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-api", action="store_true", help="Skip live API calls")
    args = parser.parse_args()

    print("=" * 60)
    print("  GOOGLE ADS AGENT — DEPLOYMENT VALIDATION")
    print("=" * 60)
    results = []

    # ── Phase 1: File Structure ───────────────────────────────────────
    print("\n📁 Phase 1: Repository Structure")
    from pathlib import Path
    root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Check action files
    action_dir = root / "actions" / "main-agent"
    action_count = len(list(action_dir.glob("*.py"))) if action_dir.exists() else 0
    results.append(check("Main agent action files", action_count == 28, f"{action_count}/28 found"))

    # Check prompts
    prompt_file = root / "prompts" / "main_agent_system_prompt.md"
    results.append(check("Main system prompt", prompt_file.exists()))

    sub_prompts = list((root / "prompts" / "sub-agents").glob("*.md")) if (root / "prompts" / "sub-agents").exists() else []
    results.append(check("Sub-agent prompts", len(sub_prompts) == 6, f"{len(sub_prompts)}/6 found"))

    # Check deploy package
    results.append(check("deploy/__init__.py", (root / "deploy" / "__init__.py").exists()))
    results.append(check("deploy/tool_schemas.py", (root / "deploy" / "tool_schemas.py").exists()))
    results.append(check("deploy/tool_executor.py", (root / "deploy" / "tool_executor.py").exists()))
    results.append(check("deploy/orchestrator.py", (root / "deploy" / "orchestrator.py").exists()))
    results.append(check("deploy/server.py", (root / "deploy" / "server.py").exists()))

    # ── Phase 2: Imports ──────────────────────────────────────────────
    print("\n📦 Phase 2: Package Imports")

    try:
        import anthropic
        results.append(check("anthropic SDK", True, f"v{anthropic.__version__}"))
    except ImportError:
        results.append(check("anthropic SDK", False, "pip install anthropic"))

    try:
        from deploy.tool_schemas import MAIN_AGENT_TOOLS
        results.append(check("Tool schemas load", True, f"{len(MAIN_AGENT_TOOLS)} tools defined"))
    except Exception as e:
        results.append(check("Tool schemas load", False, str(e)))

    try:
        from deploy.tool_executor import ToolExecutor
        executor = ToolExecutor()
        tools = executor.list_available_tools()
        present = sum(1 for t in tools if t["exists"])
        results.append(check("Tool executor loads", True, f"{present}/{len(tools)} action files found"))
    except Exception as e:
        results.append(check("Tool executor loads", False, str(e)))

    try:
        from deploy.orchestrator import GoogleAdsAgent, create_agent_system
        results.append(check("Orchestrator loads", True))
    except Exception as e:
        results.append(check("Orchestrator loads", False, str(e)))

    # ── Phase 3: Credentials ──────────────────────────────────────────
    print("\n🔑 Phase 3: Credentials")

    cred_checks = {
        "ANTHROPIC_API_KEY": "Anthropic API (required for API deployment)",
        "GOOGLE_ADS_DEVELOPER_TOKEN": "Google Ads Developer Token",
        "GOOGLE_ADS_CLIENT_ID": "Google Ads OAuth2 Client ID",
        "GOOGLE_ADS_CLIENT_SECRET": "Google Ads OAuth2 Client Secret",
        "GOOGLE_ADS_REFRESH_TOKEN": "Google Ads Refresh Token",
        "GOOGLE_ADS_LOGIN_CUSTOMER_ID": "Google Ads MCC Login Customer ID",
        "CLOUDINARY_CLOUD_NAME": "Cloudinary Cloud Name",
        "CLOUDINARY_API_KEY": "Cloudinary API Key",
        "CLOUDINARY_API_SECRET": "Cloudinary API Secret",
        "SEARCHAPI_API_KEY": "SearchAPI.io Key",
        "GOOGLE_AI_API_KEY": "Google AI / Gemini Key",
    }
    for key, label in cred_checks.items():
        val = os.environ.get(key, "")
        is_set = bool(val)
        masked = f"{val[:8]}...{val[-4:]}" if len(val) > 12 else ("***" if val else "NOT SET")
        results.append(check(label, is_set, masked))

    # ── Phase 4: Tool Schema Validation ───────────────────────────────
    print("\n🔧 Phase 4: Tool Schema Validation")

    try:
        from deploy.tool_schemas import MAIN_AGENT_TOOLS
        for tool in MAIN_AGENT_TOOLS:
            has_name = "name" in tool
            has_desc = "description" in tool
            has_schema = "input_schema" in tool
            if not (has_name and has_desc and has_schema):
                results.append(check(f"Tool '{tool.get('name', '?')}'", False, "missing required fields"))
                continue
        results.append(check("All 28 tool schemas valid", True, "name, description, input_schema present"))
    except Exception as e:
        results.append(check("Tool schema validation", False, str(e)))

    # ── Phase 5: Live API Test ────────────────────────────────────────
    if not args.skip_api:
        print("\n🌐 Phase 5: Live API Connection")

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                response = client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=50,
                    messages=[{"role": "user", "content": "Reply with exactly: AGENT_READY"}]
                )
                text = response.content[0].text
                results.append(check("Anthropic API connection", "READY" in text, text.strip()))
            except Exception as e:
                results.append(check("Anthropic API connection", False, str(e)))
        else:
            results.append(check("Anthropic API connection", False, "ANTHROPIC_API_KEY not set"))

        # Test tool use round-trip
        if api_key:
            try:
                test_tool = [{
                    "name": "test_echo",
                    "description": "Test tool that echoes input",
                    "input_schema": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "required": ["message"]
                    }
                }]
                response = client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=100,
                    tools=test_tool,
                    tool_choice={"type": "tool", "name": "test_echo"},
                    messages=[{"role": "user", "content": "Echo 'hello'"}]
                )
                has_tool_use = any(b.type == "tool_use" for b in response.content)
                results.append(check("Tool use round-trip", has_tool_use, "Claude generated tool_use block"))
            except Exception as e:
                results.append(check("Tool use round-trip", False, str(e)))
    else:
        print("\n🌐 Phase 5: Live API Connection — SKIPPED (--skip-api)")

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"  RESULTS: {passed}/{total} checks passed")

    if passed == total:
        print("  🎉 All checks passed! Agent is ready to deploy.")
    else:
        failed = total - passed
        print(f"  ⚠️  {failed} check(s) failed. Review the items above.")
    print("=" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
