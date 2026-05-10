import json
import numpy as np
from pathlib import Path
from app.services.llm_service import call_deepseek
from app.services.embedding_service import get_embedding, get_embeddings_batch, cosine_similarity

CHUNKS_DIR = Path(__file__).parent.parent.parent / "data" / "chunks"
INDEX_DIR = Path(__file__).parent.parent.parent / "data" / "index"
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)

embeddings_matrix = None
chunks_data = []

def chunk_textbook(textbook: dict, chunk_size: int = 600, overlap: int = 80) -> list[dict]:
    chunks = []
    chunk_id = 0

    for chapter in textbook["chapters"]:
        text = chapter["content"]
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end]

            if len(chunk_text.strip()) > 50:
                chunks.append({
                    "chunk_id": f"{textbook['textbook_id']}_chunk_{chunk_id:04d}",
                    "textbook_id": textbook["textbook_id"],
                    "textbook_name": textbook["title"],
                    "chapter_title": chapter["title"],
                    "page_start": chapter["page_start"],
                    "page_end": chapter["page_end"],
                    "content": chunk_text.strip(),
                    "char_count": len(chunk_text.strip())
                })
                chunk_id += 1

            start += chunk_size - overlap

    return chunks

async def build_index(textbooks: list[dict]) -> dict:
    global embeddings_matrix, chunks_data

    all_chunks = []
    for tb in textbooks:
        all_chunks.extend(chunk_textbook(tb))

    chunks_data = all_chunks

    if not chunks_data:
        return {"status": "no_chunks", "count": 0}

    # Get embeddings in batches
    texts = [c["content"] for c in chunks_data]
    batch_size = 20
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_embeddings = await get_embeddings_batch(batch)
        all_embeddings.extend(batch_embeddings)

    embeddings_matrix = np.array(all_embeddings, dtype='float32')

    # Save to disk
    np.save(str(INDEX_DIR / "embeddings.npy"), embeddings_matrix)
    with open(CHUNKS_DIR / "chunks.json", 'w', encoding='utf-8') as f:
        json.dump(chunks_data, f, ensure_ascii=False, indent=2)

    return {"status": "ok", "count": len(chunks_data)}

def load_index() -> bool:
    global embeddings_matrix, chunks_data

    embeddings_path = INDEX_DIR / "embeddings.npy"
    chunks_path = CHUNKS_DIR / "chunks.json"

    if embeddings_path.exists() and chunks_path.exists():
        embeddings_matrix = np.load(str(embeddings_path))
        with open(chunks_path, 'r', encoding='utf-8') as f:
            chunks_data = json.load(f)
        return True
    return False

async def search(query: str, top_k: int = 5) -> list[dict]:
    global embeddings_matrix, chunks_data

    if embeddings_matrix is None:
        load_index()

    if embeddings_matrix is None or not chunks_data:
        return []

    # Get query embedding
    query_embedding = await get_embedding(query)
    query_vec = np.array(query_embedding, dtype='float32')

    # Calculate cosine similarities
    similarities = np.dot(embeddings_matrix, query_vec) / (
        np.linalg.norm(embeddings_matrix, axis=1) * np.linalg.norm(query_vec)
    )

    # Get top-k indices
    top_indices = np.argsort(similarities)[::-1][:top_k]

    results = []
    for idx in top_indices:
        if idx < len(chunks_data) and similarities[idx] > 0:
            chunk = chunks_data[idx].copy()
            chunk["relevance_score"] = float(similarities[idx])
            results.append(chunk)

    return results

async def query_rag(question: str) -> dict:
    retrieved = await search(question, top_k=5)

    if not retrieved:
        return {
            "answer": "当前知识库中未找到相关信息，请先上传并索引教材。",
            "citations": [],
            "source_chunks": []
        }

    context_parts = []
    for i, chunk in enumerate(retrieved):
        context_parts.append(f"[来源{i+1}] {chunk['textbook_name']} - {chunk['chapter_title']}\n{chunk['content']}")

    context = "\n\n".join(context_parts)

    prompt = f"""基于以下参考资料回答用户问题。

要求：
1. 只基于提供的参考资料回答，不要使用自身知识
2. 每个关键论述后附带来源引用，格式为 [教材名称, 章节]
3. 如果参考资料中找不到答案，回复"当前知识库中未找到相关信息"
4. 回答要准确、简洁、有条理

参考资料：
{context}

用户问题：{question}"""

    system_prompt = "你是一个医学知识问答助手。严格基于提供的参考资料回答问题，每个论述都要注明来源。"

    answer = await call_deepseek(prompt, system_prompt)

    citations = []
    for chunk in retrieved:
        citations.append({
            "textbook": chunk["textbook_name"],
            "chapter": chunk["chapter_title"],
            "page": chunk["page_start"],
            "relevance_score": chunk["relevance_score"],
            "content_preview": chunk["content"][:200]
        })

    return {
        "answer": answer,
        "citations": citations,
        "source_chunks": [c["content"] for c in retrieved]
    }

def get_index_status() -> dict:
    return {
        "indexed_textbooks": len(set(c["textbook_id"] for c in chunks_data)),
        "total_chunks": len(chunks_data),
        "is_indexed": embeddings_matrix is not None
    }
