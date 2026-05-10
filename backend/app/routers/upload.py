import uuid
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
from app.services.pdf_parser import parse_pdf, get_parsed_textbook, list_parsed_textbooks
from app.utils import get_data_dir, store_in_memory

router = APIRouter()

UPLOAD_DIR = get_data_dir("uploads")
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {'.pdf', '.md', '.txt', '.docx'}

@router.post("/textbook")
async def upload_textbook(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())[:8]
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {file_ext}，仅支持 PDF、MD、TXT、DOCX")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件超过 100MB 限制。")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="文件内容为空")

    # Try to save to disk, fall back to /tmp
    save_path = None
    try:
        save_path = UPLOAD_DIR / f"{file_id}{file_ext}"
        with open(save_path, 'wb') as f:
            f.write(content)
    except Exception:
        # Fall back to /tmp
        tmp_dir = Path(tempfile.gettempdir()) / "knowledge_agent" / "uploads"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        save_path = tmp_dir / f"{file_id}{file_ext}"
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
        store_in_memory("parsed_textbooks", textbook_id, textbook)
    elif file_ext == '.docx':
        from docx import Document
        doc = Document(str(save_path))
        full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        chapters = [{
            "chapter_id": "ch_00",
            "title": file.filename,
            "page_start": 1,
            "page_end": 1,
            "content": full_text,
            "char_count": len(full_text)
        }]
        textbook = {
            "textbook_id": textbook_id,
            "filename": file.filename,
            "title": Path(file.filename).stem,
            "total_pages": 1,
            "total_chars": len(full_text),
            "chapters": chapters
        }
        store_in_memory("parsed_textbooks", textbook_id, textbook)
    else:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {file_ext}")

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
    raise HTTPException(status_code=404, detail="未找到教材")
