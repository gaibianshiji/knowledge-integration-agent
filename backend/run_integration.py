"""
整合 7 本教材的知识图谱。
先用名称匹配找跨教材候选，再用嵌入验证。

用法：cd backend && python run_integration.py
"""
import json
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from app.services.embedding_service import get_embeddings_batch
from app.services.llm_service import extract_json_from_llm
from app.utils import get_data_dir

GRAPH_DIR = get_data_dir("graphs")
INTEGRATION_DIR = get_data_dir("integration")
INTEGRATION_DIR.mkdir(parents=True, exist_ok=True)


async def main():
    print("=" * 60)
    print("开始跨教材知识整合")
    print("=" * 60)

    # 1. Load all graphs
    all_nodes = []
    for f in sorted(GRAPH_DIR.glob("*_graph.json")):
        with open(f, 'r', encoding='utf-8') as fh:
            graph = json.load(fh)
        tb_name = graph.get("textbook_name", f.stem)
        tb_id = graph.get("textbook_id", f.stem)
        for node in graph.get("nodes", []):
            node["textbook_name"] = tb_name
            node["textbook_id"] = tb_id
            all_nodes.append(node)
        print(f"  {tb_name}: {len(graph.get('nodes', []))} nodes")

    print(f"\n总计: {len(all_nodes)} 个知识点")

    # 2. Find cross-textbook candidates by name matching
    print("\n查找跨教材候选...")
    name_groups = {}
    for idx, node in enumerate(all_nodes):
        name = node.get("name", "").strip()
        if name:
            name_groups.setdefault(name, []).append(idx)

    # Candidates: same name in different textbooks
    candidate_pairs = []
    for name, indices in name_groups.items():
        if len(indices) < 2:
            continue
        # Group by textbook
        tb_groups = {}
        for idx in indices:
            tb = all_nodes[idx].get("textbook_id", "")
            tb_groups.setdefault(tb, []).append(idx)
        if len(tb_groups) < 2:
            continue
        # Create pairs across textbooks
        tb_keys = list(tb_groups.keys())
        for i in range(len(tb_keys)):
            for j in range(i+1, len(tb_keys)):
                for idx_a in tb_groups[tb_keys[i]]:
                    for idx_b in tb_groups[tb_keys[j]]:
                        candidate_pairs.append((idx_a, idx_b, 1.0))  # score=1.0 for exact name match

    print(f"  名称匹配候选: {len(candidate_pairs)} 对")

    # 3. Also find near-matches using embeddings (sample-based)
    # Only embed unique names to find fuzzy matches
    unique_names = list(set(n.get("name", "") for n in all_nodes if n.get("name")))
    print(f"  唯一名称: {len(unique_names)}")

    if len(unique_names) > 0:
        print("  计算名称嵌入（用于模糊匹配）...")
        name_embeddings = await get_embeddings_batch(unique_names[:3000], concurrency=20)
        name_emb_arr = np.array(name_embeddings, dtype='float32')
        name_norms = np.linalg.norm(name_emb_arr, axis=1, keepdims=True)
        name_normalized = name_emb_arr / name_norms

        # Find similar name pairs across textbooks
        print("  查找模糊匹配...")
        name_to_indices = {}
        for idx, node in enumerate(all_nodes):
            name = node.get("name", "").strip()
            if name:
                name_to_indices.setdefault(name, []).append(idx)

        unique_name_list = unique_names[:3000]
        chunk_size = 500
        fuzzy_pairs = set()
        for ci_start in range(0, len(unique_name_list), chunk_size):
            ci_end = min(ci_start + chunk_size, len(unique_name_list))
            chunk = name_normalized[ci_start:ci_end]
            sim = np.dot(chunk, name_normalized.T)
            for ci in range(sim.shape[0]):
                gi = ci_start + ci
                for gj in range(gi+1, len(unique_name_list)):
                    if sim[ci][gj] > 0.85 and unique_name_list[gi] != unique_name_list[gj]:
                        # Check if they come from different textbooks
                        for idx_a in name_to_indices.get(unique_name_list[gi], []):
                            for idx_b in name_to_indices.get(unique_name_list[gj], []):
                                if all_nodes[idx_a].get("textbook_id") != all_nodes[idx_b].get("textbook_id"):
                                    pair = (min(idx_a, idx_b), max(idx_a, idx_b))
                                    if pair not in fuzzy_pairs:
                                        fuzzy_pairs.add(pair)
                                        candidate_pairs.append((pair[0], pair[1], float(sim[ci][gj])))

        print(f"  模糊匹配新增: {len(fuzzy_pairs)} 对")

    # Deduplicate pairs
    seen = set()
    unique_pairs = []
    for i, j, s in candidate_pairs:
        key = (min(i, j), max(i, j))
        if key not in seen:
            seen.add(key)
            unique_pairs.append((i, j, s))
    candidate_pairs = unique_pairs
    candidate_pairs.sort(key=lambda x: x[2], reverse=True)
    print(f"  最终候选: {len(candidate_pairs)} 对")

    # 4. Detect conflicts
    conflicts = []
    for name, indices in name_groups.items():
        if len(indices) < 2:
            continue
        textbooks = set(all_nodes[idx].get("textbook_id", "") for idx in indices)
        if len(textbooks) < 2:
            continue
        defs = [all_nodes[idx].get("definition", "")[:100] for idx in indices]
        if len(set(defs)) > 1:
            conflicts.append({
                "concept": name,
                "sources": [{"textbook": all_nodes[idx].get("textbook_name", ""), "definition": all_nodes[idx].get("definition", "")[:150]} for idx in indices],
                "type": "definition_conflict"
            })

    print(f"  检测到 {len(conflicts)} 个跨教材冲突")

    # 5. Use LLM to decide merges
    print("\n使用 LLM 判断合并...")
    decisions = []
    merged_set = set()
    merge_batch_size = 5

    top_candidates = candidate_pairs[:1000]

    for batch_start in range(0, len(top_candidates), merge_batch_size):
        batch = top_candidates[batch_start:batch_start + merge_batch_size]

        pairs_text = ""
        for idx, (i, j, score) in enumerate(batch):
            pairs_text += f"\n对{idx+1}:\n"
            pairs_text += f"  A: {all_nodes[i]['name']} - {all_nodes[i].get('definition', '')[:80]} ({all_nodes[i].get('textbook_name', '')})\n"
            pairs_text += f"  B: {all_nodes[j]['name']} - {all_nodes[j].get('definition', '')[:80]} ({all_nodes[j].get('textbook_name', '')})\n"
            pairs_text += f"  相似度: {score:.3f}\n"

        prompt = f"""判断以下知识点对是否应合并（相同概念在不同教材中的表述）。
{pairs_text}
输出JSON: {{"decisions": [{{"pair_index": 1, "should_merge": true/false, "reason": "理由"}}]}}"""

        try:
            result = await extract_json_from_llm(prompt, "你是医学知识整合专家。判断知识点是否等价。只输出JSON。", max_tokens=2048)
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
            print(f"  [WARN] 整合判断失败: {e}")
            continue

        if (batch_start // merge_batch_size) % 20 == 0:
            print(f"  进度: {batch_start}/{len(top_candidates)}, 已合并 {len(decisions)} 对")

    # 6. Build final result
    final_nodes = [node for idx, node in enumerate(all_nodes) if idx not in merged_set]

    stats = {
        "original": len(all_nodes),
        "merged": len(final_nodes),
        "decisions_count": len(decisions),
        "conflicts_count": len(conflicts),
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

    print(f"\n{'='*60}")
    print(f"整合完成!")
    print(f"  原始知识点: {stats['original']}")
    print(f"  整合后: {stats['merged']}")
    print(f"  合并决策: {stats['decisions_count']}")
    print(f"  检测冲突: {stats['conflicts_count']}")
    print(f"  压缩比: {stats['compression_ratio']:.1%}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
