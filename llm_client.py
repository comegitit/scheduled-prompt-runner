 # Anthropic API wrapper
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


def get_claude_response(prompt_text: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set (check your .env file).")

    client = Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt_text}],
        )
    except APIConnectionError as exc:
        raise RuntimeError(f"Could not connect to the Anthropic API: {exc}") from exc
    except APIStatusError as exc:
        raise RuntimeError(f"Anthropic API returned an error status: {exc}") from exc
    except APIError as exc:
        raise RuntimeError(f"Anthropic API error: {exc}") from exc

    text_blocks = [block.text for block in message.content if block.type == "text"]
    if not text_blocks:
        raise RuntimeError("Claude's response contained no text content.")

    return "\n".join(text_blocks).strip()