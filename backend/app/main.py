from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import administracao, base, configuracao, contratos, financeiro, importacao, operacao, pessoas
from app.config import settings

app = FastAPI(
    title="Field Agency API",
    version="0.1.0",
    description="Gestão operacional de agências de field marketing: contratos, planeamento, execução e apuramentos.",
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

for r in (base.router, pessoas.router, contratos.router, operacao.router, financeiro.router, importacao.router, configuracao.router, administracao.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health", tags=["sistema"])
def health():
    return {"ok": True}
