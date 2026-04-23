"""
Servidor FastAPI — Agente de Vendas
"""
from __future__ import annotations

import asyncio
import logging
import traceback
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import config
from config import IMAGES_DIR, STATIC_DIR
from database import (
    Product, get_db, get_featured_products,
    get_or_create_customer, identify_customer, init_db,
    get_history,
)
from agent import run_agent

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

# ── Bootstrap ─────────────────────────────────────────────────────────────────
init_db()
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title=f"{config.STORE_NAME} — Agente Virtual",
    version="2.1.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/products/images", StaticFiles(directory=str(IMAGES_DIR)), name="imgs")
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message:    str            = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    session_id:    str
    response:      str
    products:      List[Dict] = []
    customer_name: Optional[str] = None
    is_returning:  bool = False

class IdentifyRequest(BaseModel):
    session_id: str
    name:  Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _sid(session_id: Optional[str]) -> str:
    return (session_id or "").strip() or str(uuid.uuid4())


# ══════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", include_in_schema=False)
def root():
    idx = STATIC_DIR / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    return {"store": config.STORE_NAME, "docs": "/docs"}


@app.get("/health")
def health():
    return {
        "status":   "ok",
        "store":    config.STORE_NAME,
        "provider": config.LLM_PROVIDER,
        "model":    config.LLM_MODEL,
    }


# ── CHAT (async para ser seguro com event loop do uvicorn) ────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    """
    Envia uma mensagem ao agente e recebe resposta com produtos estruturados.
    """
    session_id = _sid(req.session_id)
    log.info("POST /chat  session=%s  msg=%r", session_id, req.message[:80])

    try:
        # Executa o agente em thread pool para não bloquear o event loop do uvicorn.
        # Isso também evita o conflito de event loop que o agno.run() pode causar.
        loop = asyncio.get_event_loop()
        text, products = await loop.run_in_executor(
            None, run_agent, db, session_id, req.message
        )
    except Exception as exc:
        log.error("Erro no agente: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar mensagem: {exc}",
        )

    customer = get_or_create_customer(db, session_id)
    return ChatResponse(
        session_id=session_id,
        response=text,
        products=products,
        customer_name=customer.name,
        is_returning=customer.is_returning,
    )


# ── DEBUG endpoint — mostra o erro completo (desabilite em produção) ──────────

@app.post("/debug/chat")
async def debug_chat(req: ChatRequest, db: Session = Depends(get_db)):
    """
    Igual ao /chat mas retorna traceback completo em caso de erro.
    Use para diagnosticar problemas. Remova ou proteja em produção.
    """
    session_id = _sid(req.session_id)
    try:
        loop = asyncio.get_event_loop()
        text, products = await loop.run_in_executor(
            None, run_agent, db, session_id, req.message
        )
        return {
            "ok": True,
            "session_id": session_id,
            "response": text,
            "products_count": len(products),
            "provider": config.LLM_PROVIDER,
            "model": config.LLM_MODEL,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "type": type(exc).__name__,
            "traceback": traceback.format_exc(),
            "provider": config.LLM_PROVIDER,
            "model": config.LLM_MODEL,
        }


# ── CUSTOMER ──────────────────────────────────────────────────────────────────

@app.post("/identify")
def identify(req: IdentifyRequest, db: Session = Depends(get_db)):
    session_id = _sid(req.session_id)
    c = identify_customer(db, session_id, req.name, req.email, req.phone)
    return {
        "session_id":    session_id,
        "name":          c.name,
        "email":         c.email,
        "is_returning":  c.is_returning,
        "message_count": len(c.messages),
    }


@app.get("/history/{session_id}")
def history(session_id: str, limit: int = 50, db: Session = Depends(get_db)):
    msgs     = get_history(db, session_id, limit=limit)
    customer = db.query(__import__("database", fromlist=["Customer"]).Customer)\
                 .filter_by(session_id=session_id).first()
    return {
        "session_id": session_id,
        "customer":   {"name": customer.name, "email": customer.email} if customer else None,
        "messages":   [{"role": m.role, "content": m.content,
                        "at": m.created_at.isoformat()} for m in msgs],
        "total":      len(msgs),
    }


# ── PRODUCTS ──────────────────────────────────────────────────────────────────

@app.get("/products")
def list_products(
    categoria: Optional[str] = None,
    disponivel: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Product)
    if categoria:
        q = q.filter(Product.categoria.ilike(f"%{categoria}%"))
    if disponivel is not None:
        q = q.filter_by(disponibilidade=disponivel)
    prods = q.order_by(Product.categoria, Product.nome).all()
    return {"products": [p.to_dict() for p in prods], "total": len(prods)}


@app.get("/products/featured")
def featured(db: Session = Depends(get_db)):
    prods = get_featured_products(db, limit=8)
    return {"products": [p.to_dict() for p in prods]}


@app.get("/products/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db)):
    p = db.query(Product).filter_by(id=product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return p.to_dict()


# ── ERROR HANDLER ─────────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_error(request: Request, exc: Exception):
    log.error("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    print(f"\n{'═'*55}")
    print(f"  {config.STORE_NAME} — Agente Virtual")
    print(f"{'═'*55}")
    print(f"  Provider : {config.LLM_PROVIDER.upper()}  ({config.LLM_MODEL})")
    print(f"  DB       : {config.DATABASE_URL}")
    print(f"  UI       : http://localhost:{config.PORT}/")
    print(f"  Docs     : http://localhost:{config.PORT}/docs")
    print(f"  Debug    : http://localhost:{config.PORT}/debug/chat")
    print(f"{'═'*55}\n")

    uvicorn.run(
        "app:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,          # NÃO use True — causa loop ao salvar no DB
        log_level="info",
    )
