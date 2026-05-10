import httpx
import os
import json
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

QIANWEN_API_KEY = os.getenv("QIANWEN_API_KEY", "sk-87fd5a8557844463b46cf9cb518aff9f")
QIANWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

async def get_embedding(text: str) -> list[float]:
    """Get embedding for a single text using Qianwen API"""
    headers = {
        "Authorization": f"Bearer {QIANWEN_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "text-embedding-v4",
        "input": text
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{QIANWEN_BASE_URL}/embeddings",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]

async def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Get embeddings for multiple texts using Qianwen API"""
    headers = {
        "Authorization": f"Bearer {QIANWEN_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "text-embedding-v4",
        "input": texts
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{QIANWEN_BASE_URL}/embeddings",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]

def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
