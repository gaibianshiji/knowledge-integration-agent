"""
重新提取 7 本教材的全部知识点，提高覆盖率。
合并小章节以减少 LLM 调用次数。

用法：cd backend && python re_extract.py
"""
import json
import asyncio
import sys
import os
import time
from pathlib import Path

# Fix Windows console encoding for Chinese characters
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.services.llm_service import extract_json_from_llm
from app.utils import get_data_dir

PARSED_DIR = get_data_dir("parsed")
GRAPH_DIR = get_data_dir("graphs")

# Concurrency limit for LLM calls
MAX_CONCURRENT = 6

EXTRACT_SYSTEM_PROMPT = """你是一个医学知识提取专家。你需要从教材章节中提取核心知识点和它们之间的关系。

要求：
1. 提取该章节中的核心知识点（概念、定理、方法、现象等）
2. 识别知识点之间的关系
3. 输出严格的JSON格式

知识点输出格式：
{
  "nodes": [
    {
      "id": "node_001",
      "name": "知识点名称",
      "definition": "简洁的定义或描述",
      "category": "核心概念|生理机制|病理变化|临床表现|治疗方法|解剖结构|微生物",
      "chapter": "章节标题",
      "confidence": 0.95
    }
  ],
  "relations": [
    {
      "source": "node_001",
      "target": "node_002",
      "relation_type": "prerequisite|parallel|contains|applies_to",
      "description": "关系描述"
    }
  ]
}

关系类型说明：
- prerequisite: 学习B之前必须先掌握A（前置依赖）
- parallel: 同一层级的平行概念（并列关系）
- contains: 上位概念与下位概念（包含关系）
- applies_to: 某知识点是另一个的应用场景（应用关系）

重要要求：
- 每个章节提取5-15个核心知识点（根据内容丰富程度）
- 必须提取至少5-10条关系
- 每种关系类型都要有
- 关系要有意义，不要随意连接
- 定义要简洁准确，不超过100字
- confidence字段表示提取置信度(0.0-1.0)
- 输出必须是合法的JSON"""


def merge_small_chapters(chapters: list[dict], min_size: int = 500) -> list[dict]:
    """合并小章节，使每个批次至少 min_size 字符"""
    merged = []
    buffer = None

    for ch in chapters:
        if buffer is None:
            buffer = ch.copy()
            continue

        if buffer["char_count"] < min_size:
            # Merge into buffer
            buffer["content"] += "\n\n" + ch["content"]
            buffer["char_count"] += ch["char_count"]
            buffer["page_end"] = ch["page_end"]
            buffer["title"] = buffer["title"] + "、" + ch["title"]
        else:
            merged.append(buffer)
            buffer = ch.copy()

    if buffer:
        if merged and buffer["char_count"] < min_size // 2:
            # Last buffer too small, merge with previous
            merged[-1]["content"] += "\n\n" + buffer["content"]
            merged[-1]["char_count"] += buffer["char_count"]
            merged[-1]["page_end"] = buffer["page_end"]
        else:
            merged.append(buffer)

    return merged


async def extract_one_chapter(chapter: dict, textbook_id: str, textbook_name: str, sem: asyncio.Semaphore) -> dict:
    """Extract knowledge from one chapter with concurrency control"""
    async with sem:
        content = chapter['content'][:8000]
        prompt = f"""请从以下教材章节中提取核心知识点和关系：

教材：{textbook_name}
章节：{chapter['title']}

章节内容：
{content}

请按照系统提示中的JSON格式输出知识点和关系。"""

        try:
            result = await extract_json_from_llm(prompt, EXTRACT_SYSTEM_PROMPT, max_tokens=8192)
            for node in result.get("nodes", []):
                node["textbook_id"] = textbook_id
                node["textbook_name"] = textbook_name
            return result
        except Exception as e:
            err_msg = str(e) if str(e) else type(e).__name__
            try:
                print(f"  [WARN] 提取失败 [{chapter['title'][:30]}]: {err_msg}")
            except Exception:
                print(f"  [WARN] 提取失败: {type(e).__name__}")
            return {"nodes": [], "relations": []}


async def extract_textbook_full(textbook: dict) -> dict:
    """Extract all chapters from a textbook with full coverage"""
    textbook_id = textbook["textbook_id"]
    textbook_name = textbook["title"]
    all_chapters = textbook["chapters"]

    print(f"\n{'='*60}")
    print(f"开始提取：{textbook_name}")
    print(f"原始章节数：{len(all_chapters)}")

    # Merge small chapters
    merged_chapters = merge_small_chapters(all_chapters, min_size=500)
    print(f"合并后章节数：{len(merged_chapters)}")

    # Extract with concurrency control
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [
        extract_one_chapter(ch, textbook_id, textbook_name, sem)
        for ch in merged_chapters
    ]

    start_time = time.time()
    results = []
    completed = 0

    for coro in asyncio.as_completed(tasks):
        try:
            result = await coro
        except Exception as e:
            try:
                print(f"  [WARN] 任务异常: {e}")
            except Exception:
                print(f"  [WARN] 任务异常: {type(e).__name__}")
            result = {"nodes": [], "relations": []}
        results.append(result)
        completed += 1
        nodes_count = len(result.get("nodes", []))
        elapsed = time.time() - start_time
        if completed % 5 == 0 or completed == len(tasks) or completed <= 3:
            print(f"  进度：{completed}/{len(tasks)} 已完成，本批 {nodes_count} 节点，耗时 {elapsed:.0f}s")

    # Build graph with unique node IDs
    all_nodes = []
    all_relations = []
    node_id_counter = 0
    node_id_mappings = []

    for result in results:
        chapter_mapping = {}
        for node in result.get("nodes", []):
            old_id = node.get("id", "")
            node_id_counter += 1
            new_id = f"{textbook_id}_node_{node_id_counter:03d}"
            node["id"] = new_id
            all_nodes.append(node)
            if old_id:
                chapter_mapping[old_id] = new_id
        node_id_mappings.append(chapter_mapping)

    node_ids = {n["id"] for n in all_nodes}
    for chapter_idx, result in enumerate(results):
        chapter_mapping = node_id_mappings[chapter_idx]
        for rel in result.get("relations", []):
            old_source = rel.get("source", "")
            old_target = rel.get("target", "")
            new_source = chapter_mapping.get(old_source, old_source)
            new_target = chapter_mapping.get(old_target, old_target)
            if new_source in node_ids and new_target in node_ids:
                all_relations.append({
                    "source": new_source,
                    "target": new_target,
                    "relation_type": rel.get("relation_type", ""),
                    "description": rel.get("description", "")
                })

    # Deduplicate nodes by name (keep first occurrence)
    seen_names = set()
    deduped_nodes = []
    for n in all_nodes:
        if n["name"] not in seen_names:
            seen_names.add(n["name"])
            deduped_nodes.append(n)

    # Rebuild relations after dedup
    deduped_ids = {n["id"] for n in deduped_nodes}
    deduped_relations = [
        r for r in all_relations
        if r["source"] in deduped_ids and r["target"] in deduped_ids
    ]

    elapsed = time.time() - start_time
    print(f"  完成！节点：{len(deduped_nodes)}，关系：{len(deduped_relations)}，耗时：{elapsed:.0f}s")

    graph_data = {
        "textbook_id": textbook_id,
        "textbook_name": textbook_name,
        "nodes": deduped_nodes,
        "relations": deduped_relations,
        "stats": {
            "total_nodes": len(deduped_nodes),
            "total_relations": len(deduped_relations),
            "chapters_processed": len(merged_chapters),
            "chapters_total": len(all_chapters)
        }
    }

    output_path = GRAPH_DIR / f"{textbook_id}_graph.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)

    return graph_data


async def main():
    # Load all parsed textbooks
    parsed_files = sorted(PARSED_DIR.glob("*.json"))
    print(f"找到 {len(parsed_files)} 本教材")

    textbooks = []
    for f in parsed_files:
        with open(f, 'r', encoding='utf-8') as fh:
            tb = json.load(fh)
            textbooks.append(tb)
            print(f"  - {tb['title']}: {len(tb['chapters'])} 章, {tb['total_chars']} 字")

    # Extract each textbook sequentially with delay between them
    total_start = time.time()
    all_graphs = []

    # Allow specifying which textbook to extract via command line
    target_id = sys.argv[1] if len(sys.argv) > 1 else None

    for idx, tb in enumerate(textbooks):
        tid = tb["textbook_id"]
        if target_id and tid != target_id:
            continue

        # Skip if recent good result exists (more than 50 nodes)
        graph_path = GRAPH_DIR / f"{tid}_graph.json"
        if graph_path.exists() and not target_id:
            with open(graph_path, 'r', encoding='utf-8') as gf:
                existing = json.load(gf)
                if len(existing.get("nodes", [])) > 200:
                    print(f"\n跳过 {tb['title']}（已有 {len(existing['nodes'])} 个节点）")
                    all_graphs.append(existing)
                    continue

        if idx > 0:
            print(f"\n等待 30 秒后开始下一本教材...")
            await asyncio.sleep(30)
        graph = await extract_textbook_full(tb)
        all_graphs.append(graph)

    total_elapsed = time.time() - total_start
    total_nodes = sum(len(g["nodes"]) for g in all_graphs)
    total_relations = sum(len(g["relations"]) for g in all_graphs)

    print(f"\n{'='*60}")
    print(f"全部完成！总耗时：{total_elapsed:.0f}s")
    print(f"总节点数：{total_nodes}，总关系数：{total_relations}")


if __name__ == "__main__":
    asyncio.run(main())
