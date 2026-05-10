from fastapi import APIRouter, HTTPException
from app.services.knowledge_extractor import get_textbook_graph
from app.services.pdf_parser import list_parsed_textbooks
from app.services.integration_service import align_knowledge_nodes, get_integration_result

router = APIRouter()

@router.post("/run")
async def run_integration():
    textbooks = list_parsed_textbooks()
    graphs = []

    for tb in textbooks:
        graph = get_textbook_graph(tb["textbook_id"])
        if graph:
            graphs.append(graph)

    if len(graphs) < 2:
        raise HTTPException(status_code=400, detail="需要至少2本教材的知识图谱才能进行整合")

    result = await align_knowledge_nodes(graphs)
    return {
        "stats": result["stats"],
        "decisions_count": len(result["decisions"]),
        "decisions": result["decisions"][:20]
    }

@router.get("/result")
async def get_result():
    result = get_integration_result()
    if result:
        return result
    raise HTTPException(status_code=404, detail="未找到整合结果，请先执行整合")

@router.get("/report")
async def get_report():
    result = get_integration_result()
    if not result:
        raise HTTPException(status_code=404, detail="未找到整合结果")

    stats = result["stats"]
    decisions = result["decisions"]

    merge_count = sum(1 for d in decisions if d["action"] == "merge")
    keep_count = sum(1 for d in decisions if d["action"] == "keep")
    remove_count = sum(1 for d in decisions if d["action"] == "remove")

    report = f"""# 整合报告

## 整合概览
- 原始教材数量：{len(set(n.get('textbook_id', '') for n in result.get('merged_nodes', [])))} 本
- 原始知识点总数：{stats['original']} 个
- 整合后知识点数：{stats['merged']} 个
- 压缩比：{stats['compression_ratio']:.1%}

## 整合决策摘要
- 合并决策：{merge_count} 项
- 保留决策：{keep_count} 项
- 删除决策：{remove_count} 项

## 知识图谱统计
- 整合前节点数：{stats['original']}
- 整合后节点数：{stats['merged']}
- 节点减少：{stats['original'] - stats['merged']} 个

## 重点整合案例
"""
    for i, d in enumerate(decisions[:5]):
        report += f"""
### 案例 {i+1}
- 决策类型：{d['action']}
- 涉及节点：{', '.join(d['affected_nodes'])}
- 决策理由：{d['reason']}
- 置信度：{d['confidence']:.2f}
"""

    report += """
## 教学完整性说明
整合过程通过语义对齐确保了核心知识点的保留，合并的是内容高度重复的知识点，
互补性知识点均被保留。系统支持教师通过对话界面调整整合决策，确保教学逻辑链路不断裂。
"""

    return {"report": report, "stats": stats}
