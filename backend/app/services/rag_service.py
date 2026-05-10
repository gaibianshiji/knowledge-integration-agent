import json
import numpy as np
from pathlib import Path
from rank_bm25 import BM25Okapi
from app.services.llm_service import call_deepseek
from app.services.embedding_service import get_embedding, get_embeddings_batch, cosine_similarity
from app.utils import get_data_dir

CHUNKS_DIR = get_data_dir("chunks")
INDEX_DIR = get_data_dir("index")

embeddings_matrix = None
chunks_data = []
bm25_index = None

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

    # Load existing index first for incremental build
    if embeddings_matrix is None:
        load_index()

    # Find which textbooks are already indexed
    existing_tb_ids = set(c["textbook_id"] for c in chunks_data)
    new_textbooks = [tb for tb in textbooks if tb["textbook_id"] not in existing_tb_ids]

    if not new_textbooks:
        return {"status": "already_indexed", "count": len(chunks_data), "new": 0}

    # Chunk only new textbooks
    new_chunks = []
    for tb in new_textbooks:
        new_chunks.extend(chunk_textbook(tb))

    # Limit per build to avoid timeout
    if len(new_chunks) > 500:
        new_chunks = new_chunks[:500]

    if not new_chunks:
        return {"status": "no_chunks", "count": len(chunks_data), "new": 0}

    # Get embeddings for new chunks
    texts = [c["content"] for c in new_chunks]
    new_embeddings = []

    for i, text in enumerate(texts):
        try:
            embedding = await get_embedding(text)
            new_embeddings.append(embedding)
            if (i + 1) % 50 == 0:
                print(f"Processed {i + 1}/{len(texts)} embeddings")
        except Exception as e:
            print(f"Failed to get embedding for chunk {i}: {e}")
            new_embeddings.append([0.0] * 1024)

    new_embeddings_arr = np.array(new_embeddings, dtype='float32')

    # Merge with existing
    if embeddings_matrix is not None and len(chunks_data) > 0:
        chunks_data = chunks_data + new_chunks
        embeddings_matrix = np.vstack([embeddings_matrix, new_embeddings_arr])
    else:
        chunks_data = new_chunks
        embeddings_matrix = new_embeddings_arr

    # Persist to disk
    np.save(str(INDEX_DIR / "embeddings.npy"), embeddings_matrix)
    with open(CHUNKS_DIR / "chunks.json", 'w', encoding='utf-8') as f:
        json.dump(chunks_data, f, ensure_ascii=False, indent=2)

    # Build BM25 index
    _build_bm25_index()

    return {"status": "ok", "count": len(chunks_data), "new": len(new_chunks)}

def load_index() -> bool:
    global embeddings_matrix, chunks_data, bm25_index

    embeddings_path = INDEX_DIR / "embeddings.npy"
    chunks_path = CHUNKS_DIR / "chunks.json"

    if embeddings_path.exists() and chunks_path.exists():
        embeddings_matrix = np.load(str(embeddings_path))
        with open(chunks_path, 'r', encoding='utf-8') as f:
            chunks_data = json.load(f)
        # Build BM25 index
        _build_bm25_index()
        return True
    return False

def _build_bm25_index():
    """Build BM25 index from chunks for hybrid retrieval"""
    global bm25_index
    if chunks_data:
        # Simple character-level tokenization for Chinese
        tokenized = [list(c["content"]) for c in chunks_data]
        bm25_index = BM25Okapi(tokenized)

async def search(query: str, top_k: int = 5) -> list[dict]:
    global embeddings_matrix, chunks_data, bm25_index

    if embeddings_matrix is None:
        load_index()

    if embeddings_matrix is None or not chunks_data:
        return []

    # Get query embedding for vector search
    query_embedding = await get_embedding(query)
    query_vec = np.array(query_embedding, dtype='float32')

    # Vector cosine similarities
    vector_scores = np.dot(embeddings_matrix, query_vec) / (
        np.linalg.norm(embeddings_matrix, axis=1) * np.linalg.norm(query_vec)
    )

    # BM25 scores (hybrid retrieval)
    if bm25_index is not None:
        query_tokens = list(query)
        bm25_scores = bm25_index.get_scores(query_tokens)
        # Normalize BM25 scores to [0, 1]
        bm25_max = np.max(bm25_scores) if np.max(bm25_scores) > 0 else 1
        bm25_scores = bm25_scores / bm25_max
        # Weighted fusion: 0.5 vector + 0.5 BM25
        combined_scores = 0.5 * vector_scores + 0.5 * bm25_scores
    else:
        combined_scores = vector_scores

    # Get top-k indices
    top_indices = np.argsort(combined_scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        if idx < len(chunks_data) and combined_scores[idx] > 0:
            chunk = chunks_data[idx].copy()
            chunk["relevance_score"] = float(combined_scores[idx])
            chunk["vector_score"] = float(vector_scores[idx])
            if bm25_index is not None:
                chunk["bm25_score"] = float(bm25_scores[idx])
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
