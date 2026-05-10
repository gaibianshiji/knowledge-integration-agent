import json
import asyncio
from pathlib import Path
import numpy as np
from app.services.llm_service import call_deepseek, extract_json_from_llm
from app.services.embedding_service import get_embeddings_batch, cosine_similarity
from app.utils import get_data_dir

INTEGRATION_DIR = get_data_dir("integration")

async def align_knowledge_nodes(graphs: list[dict]) -> dict:
    all_nodes = []
    for graph in graphs:
        for node in graph.get("nodes", []):
            all_nodes.append(node)

    if len(all_nodes) < 2:
        return {"merged_nodes": all_nodes, "decisions": [], "stats": {"original": len(all_nodes), "merged": len(all_nodes)}}

    # Get embeddings for all nodes
    node_texts = [f"{n['name']} {n['definition']}" for n in all_nodes]

    batch_size = 20
    all_embeddings = []
    for i in range(0, len(node_texts), batch_size):
        batch = node_texts[i:i + batch_size]
        batch_embeddings = await get_embeddings_batch(batch)
        all_embeddings.extend(batch_embeddings)

    embeddings_matrix = np.array(all_embeddings, dtype='float32')

    # Calculate similarity matrix
    norms = np.linalg.norm(embeddings_matrix, axis=1, keepdims=True)
    normalized = embeddings_matrix / norms
    sim_matrix = np.dot(normalized, normalized.T)

    # Find candidate pairs
    threshold = 0.75
    candidate_pairs = []
    for i in range(len(all_nodes)):
        for j in range(i + 1, len(all_nodes)):
            if all_nodes[i].get("textbook_id") != all_nodes[j].get("textbook_id"):
                if sim_matrix[i][j] > threshold:
                    candidate_pairs.append((i, j, float(sim_matrix[i][j])))

    candidate_pairs.sort(key=lambda x: x[2], reverse=True)

    decisions = []
    conflicts = []
    merged_nodes = list(all_nodes)
    merged_set = set()

    # Detect knowledge conflicts: same name, different definitions from different textbooks
    name_groups = {}
    for idx, node in enumerate(all_nodes):
        name = node.get("name", "")
        if name not in name_groups:
            name_groups[name] = []
        name_groups[name].append((idx, node))

    for name, group in name_groups.items():
        if len(group) < 2:
            continue
        textbooks = set(n.get("textbook_id", "") for _, n in group)
        if len(textbooks) < 2:
            continue
        # Same concept from different textbooks - check if definitions differ
        defs = [n.get("definition", "")[:100] for _, n in group]
        if len(set(defs)) > 1:  # Different definitions
            conflicts.append({
                "concept": name,
                "sources": [{"textbook": n.get("textbook_name", ""), "definition": n.get("definition", "")[:150], "node_id": n.get("id", "")} for _, n in group],
                "type": "definition_conflict"
            })

    # Process candidates in batches
    batch_size = 5
    for batch_start in range(0, min(len(candidate_pairs), 20), batch_size):
        batch = candidate_pairs[batch_start:batch_start + batch_size]

        pairs_text = ""
        for idx, (i, j, score) in enumerate(batch):
            pairs_text += f"\n对{idx+1}:\n"
            pairs_text += f"  知识点A: {all_nodes[i]['name']} - {all_nodes[i]['definition'][:80]} (来自{all_nodes[i].get('textbook_name', '')})\n"
            pairs_text += f"  知识点B: {all_nodes[j]['name']} - {all_nodes[j]['definition'][:80]} (来自{all_nodes[j].get('textbook_name', '')})\n"
            pairs_text += f"  语义相似度: {score:.3f}\n"

        prompt = f"""请判断以下知识点对是否应该合并。对于每一对，给出判断结果。

{pairs_text}

输出JSON格式：
{{
  "decisions": [
    {{
      "pair_index": 1,
      "should_merge": true/false,
      "reason": "判断理由",
      "merged_name": "如果合并，使用什么名称",
      "merged_definition": "如果合并，综合后的定义"
    }}
  ]
}}"""

        try:
            result = await extract_json_from_llm(prompt, "你是医学知识整合专家。判断知识点是否等价。输出JSON。")

            for d in result.get("decisions", []):
                pair_idx = d.get("pair_index", 1) - 1
                if 0 <= pair_idx < len(batch):
                    i, j, score = batch[pair_idx]
                    if d.get("should_merge", False):
                        merged_set.add(j)
                        decisions.append({
                            "decision_id": f"merge_{len(decisions):03d}",
                            "action": "merge",
                            "affected_nodes": [all_nodes[i]["id"], all_nodes[j]["id"]],
                            "result_node": all_nodes[i]["id"],
                            "reason": d.get("reason", ""),
                            "confidence": score
                        })
        except Exception as e:
            print(f"整合判断失败: {e}")
            continue

    final_nodes = [node for idx, node in enumerate(merged_nodes) if idx not in merged_set]

    stats = {
        "original": len(all_nodes),
        "merged": len(final_nodes),
        "decisions_count": len(decisions),
        "compression_ratio": len(final_nodes) / len(all_nodes) if all_nodes else 1.0
    }

    result = {
        "merged_nodes": final_nodes,
        "decisions": decisions,
        "conflicts": conflicts,
        "stats": stats
    }

    with open(INTEGRATION_DIR / "integration_result.json", 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result

async def adjust_decision(decision_id: str, action: str, reason: str) -> dict:
    path = INTEGRATION_DIR / "integration_result.json"
    if not path.exists():
        return {"error": "未找到整合结果，请先执行整合"}

    with open(path, 'r', encoding='utf-8') as f:
        result = json.load(f)

    for d in result["decisions"]:
        if d["decision_id"] == decision_id:
            d["action"] = action
            d["reason"] = reason
            break

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result

def get_integration_result() -> dict | None:
    path = INTEGRATION_DIR / "integration_result.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None
