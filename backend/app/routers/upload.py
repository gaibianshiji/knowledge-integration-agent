import os
import uuid
from fastapi import APIRouter, UploadFile, File
from pathlib import Path
from app.services.pdf_parser import parse_pdf, get_parsed_textbook, list_parsed_textbooks
from app.utils import get_data_dir

router = APIRouter()

UPLOAD_DIR = get_data_dir("uploads")

@router.post("/textbook")
async def upload_textbook(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())[:8]
    file_ext = Path(file.filename).suffix.lower()

    save_path = UPLOAD_DIR / f"{file_id}{file_ext}"
    content = await file.read()
    with open(save_path, 'wb') as f:
        f.write(content)

    textbook_id = f"book_{file_id}"

    if file_ext == '.pdf':
        textbook = parse_pdf(str(save_path), textbook_id)
    elif file_ext in ['.md', '.txt']:
        text = content.decode('utf-8', errors='ignore')
        chapters = [{
            "chapter_id": "ch_00",
            "title": file.filename,
            "page_start": 1,
            "page_end": 1,
            "content": text,
            "char_count": len(text)
        }]
        textbook = {
            "textbook_id": textbook_id,
            "filename": file.filename,
            "title": Path(file.filename).stem,
            "total_pages": 1,
            "total_chars": len(text),
            "chapters": chapters
        }
    else:
        return {"error": f"不支持的文件格式: {file_ext}"}

    return {
        "textbook_id": textbook_id,
        "filename": file.filename,
        "title": textbook["title"],
        "total_pages": textbook["total_pages"],
        "total_chars": textbook["total_chars"],
        "chapter_count": len(textbook["chapters"]),
        "status": "parsed"
    }

@router.get("/textbooks")
async def get_textbooks():
    return list_parsed_textbooks()

@router.get("/textbook/{textbook_id}")
async def get_textbook(textbook_id: str):
    textbook = get_parsed_textbook(textbook_id)
    if textbook:
        return textbook
    return {"error": "未找到教材"}
