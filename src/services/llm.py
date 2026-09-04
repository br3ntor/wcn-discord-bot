"""
LLM access through OpenRouter using the OpenAI SDK.

OpenRouter is OpenAI-API compatible, so the openai client is pointed at
https://openrouter.ai/api/v1 and the model is selected via OPENROUTER_MODEL.
"""

import logging

from openai import AsyncOpenAI

from src.config import Config

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

DIGEST_SYSTEM_PROMPT = (
    "You write short community digests for a Project Zomboid multiplayer server, "
    "posted in the community's Discord. You are given global in-game chat from one "
    "server covering a recent time window. Summarize what happened and what people "
    "were talking about: the main topics and discussions, notable happenings (events, "
    "milestones, arguments, drama, new or returning players), and the overall mood. "
    "Use short markdown sections or bullets. Keep the summary under 2000 characters. "
    "Refer to players by their in-game names and do not quote long messages. "
    "If the chat is quiet or mostly banter, say so briefly and keep it light."
)

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not Config.OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        _client = AsyncOpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=Config.OPENROUTER_API_KEY,
            timeout=120.0,
            max_retries=2,
        )
    return _client


async def summarize_chat(transcript: str, server_name: str, window_hours: int) -> str:
    """Summarize a chat transcript, returning markdown or an empty string."""
    client = get_client()
    response = await client.chat.completions.create(
        model=Config.OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": DIGEST_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Server: {server_name}\n"
                    f"Time window: the last {window_hours} hours of global chat.\n\n"
                    f"Chat log (oldest first):\n{transcript}"
                ),
            },
        ],
        max_tokens=4000,
        temperature=0.4,
        extra_body={"reasoning": {"effort": "none"}},
    )

    choice = response.choices[0] if response.choices else None
    finish_reason = choice.finish_reason if choice else None
    usage = response.usage

    if usage is not None:
        reasoning_tokens = (
            usage.completion_tokens_details.reasoning_tokens
            if usage.completion_tokens_details
            else None
        )
        logger.info(
            "LLM summary for %s finished (%s): %s prompt / %s completion " "tokens%s",
            server_name,
            finish_reason,
            usage.prompt_tokens,
            usage.completion_tokens,
            f", {reasoning_tokens} reasoning tokens" if reasoning_tokens else "",
        )

    content = choice.message.content if choice else None
    if not content:
        logger.warning("LLM returned an empty summary for %s", server_name)
        return ""
    if finish_reason == "length":
        logger.warning(
            "Summary for %s hit max_tokens and was truncated; consider "
            "raising max_tokens in src/services/llm.py",
            server_name,
        )
    return content.strip()
