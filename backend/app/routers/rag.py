from fastapi import APIRouter
from app.services.rag_service import build_index, query_rag, get_index_status
from app.services.pdf_parser import list_parsed_textbooks, get_parsed_textbook

router = APIRouter()

@router.post("/index")
async def index_textbooks():
    textbooks_data = list_parsed_textbooks()
    textbooks = []
    for tb_meta in textbooks_data:
        tb = get_parsed_textbook(tb_meta["textbook_id"])
        if tb:
            textbooks.append(tb)

    if not textbooks:
        return {"error": "未找到已解析的教材"}

    result = await build_index(textbooks)
    return result

@router.post("/query")
async def rag_query(question: str):
    result = await query_rag(question)
    return result

@router.get("/status")
async def rag_status():
    return get_index_status()
