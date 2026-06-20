from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.knowledge_compilation import router as knowledge_compilation_router
from app.api.routes.security import router as security_router
from app.api.routes.wiki import router as wiki_router
from app.api.routes.wiki_index import router as wiki_index_router
from app.api.routes.wiki_qa import router as wiki_qa_router

app = FastAPI(title="OpsMind API")

app.include_router(auth_router)
app.include_router(security_router)
app.include_router(wiki_router)
app.include_router(wiki_index_router)
app.include_router(wiki_qa_router)
app.include_router(knowledge_compilation_router)


@app.get("/api/v1/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
