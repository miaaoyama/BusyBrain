"""ASI:One helpers shared by the orchestrator and specialists."""

from __future__ import annotations

import asyncio

from openai import OpenAI

from agent_config import ASI1_API_KEY


def make_client() -> OpenAI:
    if not ASI1_API_KEY:
        raise RuntimeError("ASI1_API_KEY is missing. Add it to .env or export it.")
    return OpenAI(base_url="https://api.asi1.ai/v1", api_key=ASI1_API_KEY)


async def ask_asi(system_prompt: str, user_prompt: str, max_tokens: int = 900) -> str:
    """Call the synchronous OpenAI-compatible SDK without blocking the agent loop."""
    client = make_client()

    def complete():
        return client.chat.completions.create(
            model="asi1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
        )

    response = await asyncio.to_thread(complete)
    return str(response.choices[0].message.content)

