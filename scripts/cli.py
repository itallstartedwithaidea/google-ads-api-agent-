#!/usr/bin/env python3
"""
Google Ads Agent — Interactive CLI
Run the agent in your terminal with full tool use support.

Usage:
    python scripts/cli.py
    python scripts/cli.py --model claude-sonnet-4-5-20250929
    python scripts/cli.py --single "Show me account summary for Acme Corp"
"""

import os
import sys
import argparse
import logging

# Add repo root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from deploy.orchestrator import create_agent_system


def main():
    parser = argparse.ArgumentParser(description="Google Ads Agent CLI")
    parser.add_argument("--model", default=None, help="Claude model to use")
    parser.add_argument("--single", default=None, help="Single message (non-interactive)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s | %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    # Validate API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set.")
        print("  → Get one at https://console.anthropic.com/settings/keys")
        print("  → Add it to your .env file or export it")
        sys.exit(1)

    print("┌─────────────────────────────────────────┐")
    print("│    Google Ads Agent — Interactive CLI    │")
    print("│    Type 'quit' to exit, 'reset' to      │")
    print("│    clear conversation history            │")
    print("└─────────────────────────────────────────┘")

    agent = create_agent_system()
    if args.model:
        agent.model = args.model
    print(f"  Model: {agent.model}")
    print(f"  Tools: {len(agent.executor.list_available_tools())} loaded")
    print()

    # Single message mode
    if args.single:
        response = agent.chat(args.single)
        print(response)
        return

    # Interactive loop
    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break
        if user_input.lower() == "reset":
            agent.reset_conversation()
            print("  [Conversation reset]\n")
            continue
        if user_input.lower() == "history":
            for msg in agent.get_conversation_history():
                role = msg["role"]
                content = msg["content"] if isinstance(msg["content"], str) else "[structured]"
                print(f"  {role}: {content[:100]}...")
            print()
            continue

        print("  [thinking...]")
        try:
            response = agent.chat(user_input)
            print(f"\nAgent: {response}\n")
        except Exception as e:
            print(f"\n  ERROR: {e}\n")


if __name__ == "__main__":
    main()
