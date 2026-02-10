"""
Google Ads API Agent — Orchestrator
The core agentic loop that drives the main agent and sub-agent delegation.

Usage:
    from deploy.orchestrator import GoogleAdsAgent
    
    agent = GoogleAdsAgent()
    response = agent.chat("Show me an account summary for Acme Corp")
    print(response)
    
    # Multi-turn conversation
    response = agent.chat("Drill into the top campaign by spend")
    print(response)
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

import anthropic

from deploy.tool_schemas import MAIN_AGENT_TOOLS
from deploy.tool_executor import ToolExecutor

logger = logging.getLogger(__name__)


class GoogleAdsAgent:
    """
    Main orchestrator for the Google Ads Agent system.
    
    Handles:
    - Multi-turn conversations with Claude
    - Tool use loop (send → tool_use → execute → return → repeat)
    - Sub-agent delegation for large/complex tasks
    - Conversation history management
    """

    DEFAULT_MODEL = "claude-opus-4-5-20251101"
    MAX_TOKENS = 8192
    MAX_TOOL_ROUNDS = 25  # Safety limit on tool use loops

    def __init__(
        self,
        api_key: str = None,
        model: str = None,
        repo_root: str = None,
        credentials: Dict[str, str] = None,
        system_prompt_path: str = None,
    ):
        """
        Initialize the Google Ads Agent.
        
        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            model: Claude model to use (default: claude-opus-4-5)
            repo_root: Path to the repo root (for loading action files)
            credentials: Dict of Google Ads/Cloudinary/etc credentials
            system_prompt_path: Path to system prompt file
        """
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model or self.DEFAULT_MODEL
        self.repo_root = Path(repo_root or os.path.dirname(os.path.dirname(__file__)))
        self.executor = ToolExecutor(repo_root=str(self.repo_root), credentials=credentials)
        self.system_prompt = self._load_system_prompt(system_prompt_path)
        self.conversation_history: List[Dict[str, Any]] = []
        self.sub_agents: Dict[str, "SubAgent"] = {}

    def _load_system_prompt(self, path: str = None) -> str:
        """Load the system prompt from file."""
        if path:
            prompt_path = Path(path)
        else:
            prompt_path = self.repo_root / "prompts" / "main_agent_system_prompt.md"

        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")

        logger.warning(f"System prompt not found at {prompt_path}, using minimal prompt")
        return (
            "You are an expert Google Ads strategist with LIVE API access. "
            "Use the provided tools to manage Google Ads accounts. "
            "All costs are in DOLLARS, never micros. "
            "Always ask clarifying questions before making API calls."
        )

    def chat(self, user_message: str) -> str:
        """
        Send a message and get a response, handling all tool use automatically.
        
        Args:
            user_message: The user's message
            
        Returns:
            The agent's final text response
        """
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Run the agentic loop
        response_text = self._run_agent_loop()
        return response_text

    def _run_agent_loop(self) -> str:
        """
        Core agentic loop: send → check for tool_use → execute → return → repeat.
        Continues until Claude returns a text response (no more tool calls).
        """
        rounds = 0

        while rounds < self.MAX_TOOL_ROUNDS:
            rounds += 1
            logger.debug(f"Agent loop round {rounds}")

            # Call Claude
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.MAX_TOKENS,
                system=self.system_prompt,
                tools=MAIN_AGENT_TOOLS,
                messages=self.conversation_history,
            )

            # Process the response
            assistant_content = response.content
            stop_reason = response.stop_reason

            # Add assistant response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_content
            })

            # If no tool use, we're done — extract text
            if stop_reason != "tool_use":
                return self._extract_text(assistant_content)

            # Handle tool calls
            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    logger.info(f"Executing tool: {block.name} (id: {block.id})")
                    logger.debug(f"Tool input: {json.dumps(block.input, indent=2)}")

                    # Execute the tool
                    result = self.executor.execute(block.name, block.input)
                    logger.debug(f"Tool result (truncated): {result[:500]}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            # Add tool results to history
            self.conversation_history.append({
                "role": "user",
                "content": tool_results
            })

        # Safety: hit max rounds
        logger.warning(f"Hit max tool rounds ({self.MAX_TOOL_ROUNDS})")
        return "[Agent reached maximum tool execution rounds. Please try a more specific request.]"

    def _extract_text(self, content_blocks) -> str:
        """Extract text from Claude's response content blocks."""
        texts = []
        for block in content_blocks:
            if hasattr(block, "text"):
                texts.append(block.text)
        return "\n".join(texts) if texts else "[No text response]"

    def reset_conversation(self):
        """Clear conversation history to start fresh."""
        self.conversation_history = []

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Return the full conversation history."""
        return self.conversation_history


class SubAgent:
    """
    A sub-agent that can be invoked by the main agent for specialized tasks.
    Each sub-agent has its own system prompt, tools, and conversation context.
    """

    def __init__(
        self,
        name: str,
        agent_id: str,
        model: str = "claude-opus-4-5-20251101",
        system_prompt_path: str = None,
        tools: List[Dict] = None,
        api_key: str = None,
        repo_root: str = None,
        credentials: Dict[str, str] = None,
    ):
        self.name = name
        self.agent_id = agent_id
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model
        self.tools = tools or []
        self.repo_root = Path(repo_root or os.path.dirname(os.path.dirname(__file__)))
        self.executor = ToolExecutor(repo_root=str(self.repo_root), credentials=credentials)
        self.system_prompt = self._load_prompt(system_prompt_path)

    def _load_prompt(self, path: str = None) -> str:
        if path and Path(path).exists():
            return Path(path).read_text(encoding="utf-8")
        return f"You are the {self.name} sub-agent."

    def execute_task(self, task_description: str, context: Dict = None) -> str:
        """
        Execute a delegated task and return the result.
        Sub-agents run a fresh conversation per task (no persistent history).
        """
        messages = [{"role": "user", "content": task_description}]
        if context:
            messages[0]["content"] = (
                f"Context: {json.dumps(context)}\n\nTask: {task_description}"
            )

        rounds = 0
        max_rounds = 15

        while rounds < max_rounds:
            rounds += 1
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=self.system_prompt,
                tools=self.tools,
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                return self._extract_text(response.content)

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = self.executor.execute(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            messages.append({"role": "user", "content": tool_results})

        return "[Sub-agent reached maximum rounds]"

    def _extract_text(self, content_blocks) -> str:
        texts = []
        for block in content_blocks:
            if hasattr(block, "text"):
                texts.append(block.text)
        return "\n".join(texts) if texts else "[No text response]"


def create_agent_system(api_key: str = None, repo_root: str = None) -> GoogleAdsAgent:
    """
    Factory function: Creates the full agent system with all sub-agents registered.
    
    Usage:
        agent = create_agent_system()
        response = agent.chat("Show me account summary for Acme Corp")
    """
    agent = GoogleAdsAgent(api_key=api_key, repo_root=repo_root)

    # Register sub-agents (they're instantiated on-demand when delegated to)
    sub_agent_configs = [
        {
            "name": "Simba — Reporting & Analysis",
            "agent_id": "8b9991fd-7750-417e-a2c2-69527d64388b",
            "prompt_file": "prompts/sub-agents/01_reporting_analysis.md",
        },
        {
            "name": "Nemo — Research & Intelligence",
            "agent_id": "47885bdc-0390-44a4-ab58-9046c1182691",
            "prompt_file": "prompts/sub-agents/02_research_intelligence.md",
        },
        {
            "name": "Moana — Creative",
            "agent_id": "9aeb9afc-bd87-4df7-955a-1b928b23aa0e",
            "prompt_file": "prompts/sub-agents/05_creative.md",
        },
        {
            "name": "Baymax — Creative Innovate",
            "agent_id": "9b971c1c-0204-4496-869e-7a3620718242",
            "model": "claude-sonnet-4-5-20250929",
            "prompt_file": "prompts/sub-agents/06_creative_innovate.md",
        },
    ]

    root = Path(repo_root or os.path.dirname(os.path.dirname(__file__)))
    for config in sub_agent_configs:
        prompt_path = str(root / config["prompt_file"])
        sub = SubAgent(
            name=config["name"],
            agent_id=config["agent_id"],
            model=config.get("model", "claude-opus-4-5-20251101"),
            system_prompt_path=prompt_path,
            api_key=api_key,
            repo_root=str(root),
        )
        agent.sub_agents[config["name"]] = sub

    return agent
