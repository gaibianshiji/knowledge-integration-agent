import httpx
import os
import json
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

QIANWEN_API_KEY = os.getenv("QIANWEN_API_KEY", "")
QIANWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

async def get_embedding(text: str) -> list[float]:
    """Get embedding for a single text using Qianwen API"""
    headers = {
        "Authorization": f"Bearer {QIANWEN_API_KEY}",
        "Content-Type": "application/json"
    }

    # Truncate text if too long
    if len(text) > 2000:
        text = text[:2000]

    payload = {
        "model": "text-embedding-v4",
        "input": text
    }

    async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
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

    # Truncate texts if too long
    truncated_texts = [t[:2000] if len(t) > 2000 else t for t in texts]

    # Process one by one to avoid batch API issues
    results = []
    for text in truncated_texts:
        try:
            payload = {
                "model": "text-embedding-v4",
                "input": text
            }
            async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                response = await client.post(
                    f"{QIANWEN_BASE_URL}/embeddings",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                results.append(data["data"][0]["embedding"])
        except Exception as e:
            print(f"Failed to get embedding: {e}")
            # Return a zero vector as fallback
            results.append([0.0] * 1024)
    return results

def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
