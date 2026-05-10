import httpx
import json
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

async def call_deepseek(prompt: str, system_prompt: str = "", max_tokens: int = 4096) -> str:
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3
    }

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{DEEPSEEK_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
            else:
                raise

async def call_deepseek_messages(messages: list[dict], max_tokens: int = 4096) -> str:
    """Call DeepSeek with a full message list (for multi-turn conversations)"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3
    }

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{DEEPSEEK_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
            else:
                raise

async def extract_json_from_llm(prompt: str, system_prompt: str = "") -> dict | list:
    response = await call_deepseek(prompt, system_prompt)
    response = response.strip()
    if response.startswith("```json"):
        response = response[7:]
    if response.startswith("```"):
        response = response[3:]
    if response.endswith("```"):
        response = response[:-3]
    response = response.strip()
    return json.loads(response)
