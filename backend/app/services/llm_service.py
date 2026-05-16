import httpx
import json
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

# LLM provider config
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mimo")  # "deepseek" or "mimo"

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"

MIMO_API_KEY = os.getenv("MIMO_API_KEY", "tp-cktplfs1v4rqypizh4jv0l2rs6h2svvfmobce9z54n4r2k5c")
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_MODEL = "mimo-v2.5-pro"

def _get_llm_config():
    if LLM_PROVIDER == "mimo":
        return MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL
    return DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

async def call_llm(prompt: str, system_prompt: str = "", max_tokens: int = 4096) -> str:
    api_key, base_url, model = _get_llm_config()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3
    }

    for attempt in range(5):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                if response.status_code == 429:
                    wait = min(30 * (attempt + 1), 120)
                    await asyncio.sleep(wait)
                    continue
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < 4:
                wait = min(30 * (attempt + 1), 120)
                await asyncio.sleep(wait)
                continue
            raise
        except Exception as e:
            if attempt < 4:
                await asyncio.sleep(2 ** attempt)
            else:
                raise

async def call_llm_messages(messages: list[dict], max_tokens: int = 4096) -> str:
    """Call LLM with a full message list (for multi-turn conversations)"""
    api_key, base_url, model = _get_llm_config()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3
    }

    for attempt in range(5):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                if response.status_code == 429:
                    wait = min(30 * (attempt + 1), 120)
                    await asyncio.sleep(wait)
                    continue
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < 4:
                wait = min(30 * (attempt + 1), 120)
                await asyncio.sleep(wait)
                continue
            raise
        except Exception as e:
            if attempt < 4:
                await asyncio.sleep(2 ** attempt)
            else:
                raise

async def extract_json_from_llm(prompt: str, system_prompt: str = "", retries: int = 2, max_tokens: int = 4096) -> dict | list:
    last_response = ""
    for attempt in range(retries + 1):
        response = await call_llm(prompt, system_prompt, max_tokens=max_tokens)
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()
        last_response = response[:200]
        if not response:
            if attempt < retries:
                await asyncio.sleep(2)
                continue
            raise ValueError(f"LLM returned empty response after {retries+1} attempts")
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            if attempt < retries:
                await asyncio.sleep(2)
                continue
            raise ValueError(f"JSON parse error: {e}. Response starts with: {last_response}")

# Backward compatibility
call_deepseek = call_llm
call_deepseek_messages = call_llm_messages
