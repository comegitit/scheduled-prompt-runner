"""
llm_client.py - Thin wrapper around the Anthropic API.

Responsible for creating the client, sending the prompt, receiving the
response, and translating API errors into clear exceptions. No business
logic (prompt content, scheduling, output handling) lives here.
"""

import os
from anthropic import Anthropic, APIError, APIConnectionError, APIStatusError

MODEL = "claude-sonnet-5"
# Sonnet 5 has adaptive thinking on by default, and thinking tokens count
# against max_tokens along with the visible response. Kept generous here
# since this is a low-volume weekly job, not a cost-sensitive hot path.
MAX_TOKENS = 8192

# Basic web search tool. $10 per 1,000 searches plus standard token cost.
# max_uses caps searches per request - bounds cost, rarely truncates a
# simple lookup like a deprecation check or a two-topic news summary.
def _build_web_search_tool(allowed_domains=None) -> dict:
    tool = {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}
    if allowed_domains:
        tool["allowed_domains"] = allowed_domains
    return tool


def get_claude_response(
    prompt_text: str, enable_web_search: bool = False, allowed_domains=None
) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set (check your .env file).")

    client = Anthropic(api_key=api_key)

    create_kwargs = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt_text}],
    }
    if enable_web_search:
        create_kwargs["tools"] = [_build_web_search_tool(allowed_domains)]

    try:
        message = client.messages.create(**create_kwargs)
    except APIConnectionError as exc:
        raise RuntimeError(f"Could not connect to the Anthropic API: {exc}") from exc
    except APIStatusError as exc:
        raise RuntimeError(f"Anthropic API returned an error status: {exc}") from exc
    except APIError as exc:
        raise RuntimeError(f"Anthropic API error: {exc}") from exc

    if message.stop_reason == "pause_turn":
        raise RuntimeError(
            "Claude paused mid-search (stop_reason=pause_turn) instead of finishing. "
            "This app doesn't yet handle multi-turn search continuation."
        )

    text_blocks = [block.text for block in message.content if block.type == "text"]
    if not text_blocks:
        raise RuntimeError("Claude's response contained no text content.")

    return "\n".join(text_blocks).strip()