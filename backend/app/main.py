from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from app.routers import upload, graph, rag, chat, integration
from app.services.pdf_parser import preload_textbooks
from app.services.graph_service import preload_graphs
from app.services.rag_service import load_index
from app.utils import clear_memory

app = FastAPI(title="学科知识整合智能体", version="1.0.0")

# Frontend static files
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend" / "dist"

@app.on_event("startup")
async def startup():
    clear_memory("parsed_textbooks")
    clear_memory("graphs")
    preload_textbooks()
    preload_graphs()
    # Load persisted RAG index
    loaded = load_index()
    if loaded:
        print("Loaded persisted RAG index")
    else:
        print("No persisted RAG index found")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api/upload", tags=["upload"])
app.include_router(graph.router, prefix="/api/graph", tags=["graph"])
app.include_router(rag.router, prefix="/api/rag", tags=["rag"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(integration.router, prefix="/api/integration", tags=["integration"])

@app.get("/")
async def root():
    if FRONTEND_DIR.exists() and (FRONTEND_DIR / "index.html").exists():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
    return {"message": "学科知识整合智能体 API"}

@app.get("/api/health")
async def health():
    return {"status": "ok"}

# Serve frontend static files (must be after API routes)
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_DIR / "index.html"))
