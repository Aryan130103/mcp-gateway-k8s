import asyncio
import os
import sys

import httpx


def settings():
    return (os.environ.get("LLM_BASE_URL", ""), os.environ.get("LLM_MODEL", ""),
            os.environ.get("LLM_API_KEY", ""))


def configured() -> bool:
    return all(settings())


async def chat_completion(messages: list, tools: list | None = None) -> dict:
    base, model, key = settings()
    payload: dict = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools
    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(2):
            r = await client.post(
                base.rstrip("/") + "/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {key}"},
            )
            if r.status_code in (429, 503) and attempt == 0:
                await asyncio.sleep(3)
                continue
            break
    if r.status_code != 200:
        print(f"LLM error {r.status_code}: {r.text[:300]}", file=sys.stderr, flush=True)
        raise RuntimeError(f"LLM provider returned {r.status_code}")
    return r.json()["choices"][0]["message"]
