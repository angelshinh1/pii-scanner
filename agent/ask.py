"""
Usage: uv run python agent/ask.py [--audit] "question"
--audit prints every tool result the model received.
"""

import asyncio
import json
import sys
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)
from dotenv import load_dotenv

load_dotenv()

SAMPLE_DIR = (Path(__file__).resolve().parent.parent / "sample_data").resolve()
DEFAULT_QUESTION = "Which files in sample_data hold SINs or credit card numbers?"

SYSTEM_PROMPT = f"""You audit files for sensitive data using the pii-scanner tools.

The scan root is {SAMPLE_DIR.as_posix()}. Pass absolute paths inside it to the tools.
"sample_data" means that folder.

The tools only return file paths, line numbers and masked values like XXX-XXX-544.
You never see file contents or full numbers. Never guess, complete or reconstruct
a masked number. If asked for a full number, explain that you don't have it.

Answer with a short per-file summary: path, what was found, how many, and on
which lines."""


def build_options() -> ClaudeAgentOptions:
    scanner = {
        "command": sys.executable,
        "args": ["-m", "pii_scanner.server"],
        "env": {"SCANNER_ALLOWED_ROOT": str(SAMPLE_DIR)},
    }
    return ClaudeAgentOptions(
        mcp_servers={"scanner": scanner},
        strict_mcp_config=True,  # ignore other MCP servers on this machine
        allowed_tools=["mcp__scanner__*"],
        tools=[],  # no built-in tools, so Claude can't read files directly
        system_prompt=SYSTEM_PROMPT,
        max_turns=5,
    )


def tool_result_text(block: ToolResultBlock) -> str:
    if isinstance(block.content, str):
        return block.content
    if isinstance(block.content, list):
        return "\n".join(part.get("text", json.dumps(part)) for part in block.content)
    return json.dumps(block.content)


async def main() -> None:
    args = sys.argv[1:]
    audit = "--audit" in args
    args = [a for a in args if a != "--audit"]
    question = " ".join(args) or DEFAULT_QUESTION

    print(f"> {question}\n")
    async for message in query(prompt=question, options=build_options()):
        if isinstance(message, SystemMessage) and message.subtype == "init":
            for server in message.data.get("mcp_servers", []):
                print(f"[mcp] {server['name']}: {server['status']}")

        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    print(f"[tool] {block.name}({json.dumps(block.input)})")

        elif isinstance(message, UserMessage) and audit and isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    print(f"[audit] result the model received:\n{tool_result_text(block)}\n")

        elif isinstance(message, ResultMessage):
            print(f"\n{message.result}")


if __name__ == "__main__":
    asyncio.run(main())
