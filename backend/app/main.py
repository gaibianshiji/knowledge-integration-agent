from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import upload, graph, rag, chat, integration
from app.services.pdf_parser import preload_textbooks
from app.services.graph_service import preload_graphs

app = FastAPI(title="学科知识整合智能体", version="1.0.0")

@app.on_event("startup")
async def startup():
    preload_textbooks()
    preload_graphs()

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
    return {"message": "学科知识整合智能体 API"}

@app.get("/api/health")
async def health():
    return {"status": "ok"}
