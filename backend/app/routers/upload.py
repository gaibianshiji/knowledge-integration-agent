import os
import uuid
import tempfile
import httpx
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from pathlib import Path
from app.services.pdf_parser import parse_pdf, get_parsed_textbook, list_parsed_textbooks
from app.utils import get_data_dir, store_in_memory

router = APIRouter()

UPLOAD_DIR = get_data_dir("uploads")
MAX_FILE_SIZE = 4 * 1024 * 1024  # 4MB

class BlobUploadRequest(BaseModel):
    filename: str
    content_type: str = "application/pdf"

class TextbookUrlRequest(BaseModel):
    blob_url: str
    filename: str

@router.post("/presigned-url")
async def get_presigned_url(req: BlobUploadRequest):
    """Generate a presigned URL for direct Vercel Blob upload."""
    blob_token = os.getenv("BLOB_READ_WRITE_TOKEN", "")
    if not blob_token:
        raise HTTPException(status_code=500, detail="BLOB_READ_WRITE_TOKEN not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.vercel.com/v2/blob/client-upload",
            headers={
                "Authorization": f"Bearer {blob_token}",
                "Content-Type": "application/json",
            },
            json={
                "filename": req.filename,
                "contentType": req.content_type,
            },
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Failed to get presigned URL: {resp.text}")
        return resp.json()

@router.post("/textbook-url")
async def upload_textbook_from_url(req: TextbookUrlRequest):
    """Download file from Vercel Blob URL and parse it."""
    file_id = str(uuid.uuid4())[:8]
    original_filename = req.filename
    file_ext = Path(original_filename).suffix.lower()

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        resp = await client.get(req.blob_url)
        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to download file from blob")
        content = resp.content

    # Save to temp file for parsing
    tmp_dir = Path(tempfile.gettempdir()) / "knowledge_agent" / "uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    save_path = tmp_dir / f"{file_id}{file_ext}"
    with open(save_path, 'wb') as f:
        f.write(content)

    textbook_id = f"book_{file_id}"

    if file_ext == '.pdf':
        textbook = parse_pdf(str(save_path), textbook_id, original_filename)
    elif file_ext in ['.md', '.txt']:
        text = content.decode('utf-8', errors='ignore')
        chapters = [{
            "chapter_id": "ch_00",
            "title": original_filename,
            "page_start": 1,
            "page_end": 1,
            "content": text,
            "char_count": len(text)
        }]
        textbook = {
            "textbook_id": textbook_id,
            "filename": original_filename,
            "title": Path(original_filename).stem,
            "total_pages": 1,
            "total_chars": len(text),
            "chapters": chapters
        }
        store_in_memory("parsed_textbooks", textbook_id, textbook)
    else:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {file_ext}")

    return {
        "textbook_id": textbook_id,
        "filename": original_filename,
        "title": textbook["title"],
        "total_pages": textbook["total_pages"],
        "total_chars": textbook["total_chars"],
        "chapter_count": len(textbook["chapters"]),
        "status": "parsed"
    }

@router.post("/textbook")
async def upload_textbook(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())[:8]
    file_ext = Path(file.filename).suffix.lower()

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件超过 4MB 限制，请使用大文件上传（Vercel Blob）。")

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
        # Store in memory
        store_in_memory("parsed_textbooks", textbook_id, textbook)
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
