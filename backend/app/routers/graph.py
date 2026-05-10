from fastapi import APIRouter
from app.services.pdf_parser import get_parsed_textbook, list_parsed_textbooks
from app.services.knowledge_extractor import extract_textbook_knowledge, get_textbook_graph

router = APIRouter()

@router.post("/build/{textbook_id}")
async def build_graph(textbook_id: str, max_chapters: int = 50):
    textbook = get_parsed_textbook(textbook_id)
    if not textbook:
        return {"error": "未找到教材，请先上传"}

    graph = await extract_textbook_knowledge(textbook, max_chapters)
    return {
        "textbook_id": textbook_id,
        "textbook_name": textbook["title"],
        "stats": graph["stats"],
        "nodes_count": len(graph["nodes"]),
        "relations_count": len(graph["relations"])
    }

@router.get("/data/{textbook_id}")
async def get_graph_data(textbook_id: str):
    graph = get_textbook_graph(textbook_id)
    if graph:
        return graph
    return {"error": "未找到知识图谱，请先构建"}

@router.get("/list")
async def list_graphs():
    textbooks = list_parsed_textbooks()
    result = []
    for tb in textbooks:
        graph = get_textbook_graph(tb["textbook_id"])
        result.append({
            "textbook_id": tb["textbook_id"],
            "title": tb["title"],
            "has_graph": graph is not None,
            "nodes_count": len(graph["nodes"]) if graph else 0,
            "relations_count": len(graph["relations"]) if graph else 0
        })
    return result
