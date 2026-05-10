import json
import asyncio
from pathlib import Path
from app.services.llm_service import extract_json_from_llm
from app.utils import get_data_dir, get_bundled_data_dir

GRAPH_DIR = get_data_dir("graphs")
BUNDLED_GRAPH_DIR = get_bundled_data_dir("graphs")

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
      "category": "核心概念|生理机制|病理变化|临床表现|治疗方法|解剖结构",
      "chapter": "章节标题",
      "page": 页码
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
- prerequisite: 学习B之前必须先掌握A
- parallel: 同一层级的平行概念
- contains: 上位概念与下位概念
- applies_to: 某知识点是另一个的应用场景

注意：
- 每个章节提取10-20个核心知识点
- 关系要有意义，不要随意连接
- 定义要简洁准确，不超过100字
- 输出必须是合法的JSON"""

async def extract_chapter_knowledge(chapter: dict, textbook_id: str, textbook_name: str) -> dict:
    prompt = f"""请从以下教材章节中提取核心知识点和关系：

教材：{textbook_name}
章节：{chapter['title']}
页码：{chapter['page_start']}-{chapter['page_end']}

章节内容：
{chapter['content'][:8000]}

请按照系统提示中的JSON格式输出知识点和关系。"""

    try:
        result = await extract_json_from_llm(prompt, EXTRACT_SYSTEM_PROMPT)

        for node in result.get("nodes", []):
            node["textbook_id"] = textbook_id
            node["textbook_name"] = textbook_name

        return result
    except Exception as e:
        print(f"提取章节 {chapter['title']} 知识点失败: {e}")
        return {"nodes": [], "relations": []}

async def extract_textbook_knowledge(textbook: dict, max_chapters: int = 5) -> dict:
    textbook_id = textbook["textbook_id"]
    textbook_name = textbook["title"]
    chapters = textbook["chapters"][:max_chapters]

    tasks = [
        extract_chapter_knowledge(ch, textbook_id, textbook_name)
        for ch in chapters
    ]

    results = await asyncio.gather(*tasks)

    all_nodes = []
    all_relations = []
    node_id_counter = 0

    for result in results:
        for node in result.get("nodes", []):
            node_id_counter += 1
            node["id"] = f"{textbook_id}_node_{node_id_counter:03d}"
            all_nodes.append(node)

        for rel in result.get("relations", []):
            all_relations.append(rel)

    graph_data = {
        "textbook_id": textbook_id,
        "textbook_name": textbook_name,
        "nodes": all_nodes,
        "relations": all_relations,
        "stats": {
            "total_nodes": len(all_nodes),
            "total_relations": len(all_relations),
            "chapters_processed": len(chapters)
        }
    }

    output_path = GRAPH_DIR / f"{textbook_id}_graph.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)

    return graph_data

def get_textbook_graph(textbook_id: str) -> dict | None:
    path = GRAPH_DIR / f"{textbook_id}_graph.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    # Fallback to bundled data (read-only on serverless)
    bundled_path = BUNDLED_GRAPH_DIR / f"{textbook_id}_graph.json"
    if bundled_path.exists():
        with open(bundled_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None
