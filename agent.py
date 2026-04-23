# """
# Agente de Vendas — Agno Framework
# Suporta: Anthropic Claude | OpenAI GPT-4o | Groq (Llama 3.3)

# Histórico: gerenciado pelo SqliteStorage nativo do Agno (NÃO via messages=)
# Memória de cliente: injetada no system prompt via SQLAlchemy
# """
# from __future__ import annotations

# import logging
# import threading
# import uuid
# from pathlib import Path
# from textwrap import dedent
# from typing import Optional

# from sqlalchemy.orm import Session

# from agno.agent import Agent
# from agno.tools import tool

# try:
#     from agno.storage.sqlite import SqliteStorage
#     _HAS_STORAGE = True
# except ImportError:
#     _HAS_STORAGE = False
#     logging.warning("agno.storage.sqlite não disponível — histórico desabilitado")

# import config
# from database import (
#     Customer, Product,
#     get_or_create_customer,
#     search_products, get_products_by_category,
#     get_products_by_price, update_preferences,
#     save_message,
# )

# log = logging.getLogger(__name__)
# BASE_DIR = Path(__file__).parent


# # ── Thread-local: compartilha DB e lista de produtos com as tools ─────────────
# _ctx = threading.local()

# def _db() -> Optional[Session]:
#     return getattr(_ctx, "db", None)

# def _capture(products: list[dict]):
#     if not hasattr(_ctx, "products"):
#         _ctx.products = []
#     _ctx.products.extend(products)

# def get_captured_products() -> list[dict]:
#     return list(getattr(_ctx, "products", []))


# # ══════════════════════════════════════════════════════════════════════════════
# #  LLM FACTORY
# # ══════════════════════════════════════════════════════════════════════════════

# def build_model():
#     provider = config.LLM_PROVIDER
#     model_id  = config.LLM_MODEL

#     log.info("Provider: %s | Modelo: %s", provider, model_id)

#     if provider == "anthropic":
#         from agno.models.anthropic import Claude
#         return Claude(id=model_id)
#     elif provider == "openai":
#         from agno.models.openai import OpenAIChat
#         return OpenAIChat(id=model_id)
#     elif provider == "groq":
#         from agno.models.groq import Groq
#         return Groq(id=model_id)
#     else:
#         raise ValueError(
#             f"LLM_PROVIDER inválido: '{provider}'. Use: anthropic | openai | groq"
#         )


# # ══════════════════════════════════════════════════════════════════════════════
# #  EXTRAÇÃO DE TEXTO ROBUSTA
# #  O Agno pode retornar string, RunResponse, gerador ou objetos variados.
# #  Esta função extrai o texto em qualquer cenário.
# # ══════════════════════════════════════════════════════════════════════════════

# def _extract_text(response) -> str:
#     if response is None:
#         return ""

#     # 1. String direta
#     if isinstance(response, str):
#         return response.strip()

#     # 2. Gerador (stream acidental com stream=False)
#     if hasattr(response, "__next__"):
#         parts = []
#         try:
#             for chunk in response:
#                 t = _extract_text(chunk)
#                 if t:
#                     parts.append(t)
#         except Exception:
#             pass
#         return "".join(parts).strip()

#     # 3. .content como string
#     if hasattr(response, "content"):
#         c = response.content
#         if isinstance(c, str) and c.strip():
#             return c.strip()
#         # 3a. .content como lista de blocos (Anthropic style)
#         if isinstance(c, list):
#             parts = []
#             for b in c:
#                 if isinstance(b, str):
#                     parts.append(b)
#                 elif isinstance(b, dict) and b.get("type") == "text":
#                     parts.append(b.get("text", ""))
#                 elif hasattr(b, "text"):
#                     parts.append(str(b.text))
#             text = "\n".join(p for p in parts if p).strip()
#             if text:
#                 return text

#     # 4. Busca no .messages (fallback pós-tool-use quando .content é None)
#     if hasattr(response, "messages") and response.messages:
#         for msg in reversed(response.messages):
#             role = getattr(msg, "role", None)
#             if role in ("assistant", "model"):
#                 content = getattr(msg, "content", None)
#                 if content:
#                     if isinstance(content, str) and content.strip():
#                         return content.strip()
#                     if isinstance(content, list):
#                         parts = []
#                         for b in content:
#                             if isinstance(b, dict) and b.get("type") == "text":
#                                 parts.append(b.get("text", ""))
#                             elif hasattr(b, "text"):
#                                 parts.append(str(b.text))
#                         text = "\n".join(p for p in parts if p).strip()
#                         if text:
#                             return text

#     # 5. Último recurso
#     fallback = str(response).strip()
#     if fallback.startswith("<") or "object at 0x" in fallback:
#         return ""
#     return fallback


# # ══════════════════════════════════════════════════════════════════════════════
# #  PRODUCT FORMATTER
# # ══════════════════════════════════════════════════════════════════════════════

# def _fmt(p: dict) -> str:
#     avail = "✅ Disponível" if p["disponibilidade"] else "❌ Fora de estoque"
#     return (
#         "[PRODUCT_START]\n"
#         f"ID:{p['id']}|NOME:{p['nome']}|PRECO:{p['preco']:.2f}"
#         f"|CATEGORIA:{p['categoria']}|DISPONIVEL:{p['disponibilidade']}"
#         f"|IMG:{p['image_url']}\n"
#         f"📦 **{p['nome']}**  |  💰 R$ {p['preco']:.2f}  |  {avail}\n"
#         f"📝 {p['descricao']}\n"
#         "[PRODUCT_END]"
#     )


# # ══════════════════════════════════════════════════════════════════════════════
# #  TOOLS
# # ══════════════════════════════════════════════════════════════════════════════

# @tool
# def buscar_produtos(consulta: str) -> str:
#     """
#     Busca produtos no catálogo por texto livre.
#     SEMPRE use quando o cliente mencionar qualquer produto.

#     Args:
#         consulta: Termos de busca (ex: 'tenis corrida', 'camiseta preta barata').
#     """
#     db = _db()
#     if not db:
#         return "Erro: banco de dados indisponível."
#     results: list[Product] = search_products(db, consulta, max_results=3)
#     if not results:
#         return f"Nenhum produto encontrado para '{consulta}'."
#     _capture([p.to_dict() for p in results])
#     lines = [f"Encontrei {len(results)} produto(s) para '{consulta}':\n"]
#     for p in results:
#         lines.append(_fmt(p.to_dict()))
#     return "\n\n".join(lines)


# @tool
# def listar_categorias() -> str:
#     """Lista todas as categorias de produtos disponíveis na loja."""
#     db = _db()
#     if not db:
#         return "Erro interno."
#     cats = sorted({p.categoria for p in db.query(Product).all()})
#     return "Categorias disponíveis: " + " | ".join(cats)


# @tool
# def listar_por_categoria(categoria: str) -> str:
#     """
#     Lista produtos de uma categoria específica.

#     Args:
#         categoria: Nome da categoria (ex: 'Calcados', 'Roupas', 'Acessorios').
#     """
#     db = _db()
#     if not db:
#         return "Erro interno."
#     results = get_products_by_category(db, categoria)
#     if not results:
#         return f"Nenhum produto na categoria '{categoria}'."
#     top = results[:4]
#     _capture([p.to_dict() for p in top])
#     lines = [f"Produtos em '{categoria}' ({len(results)} itens):\n"]
#     for p in top:
#         lines.append(_fmt(p.to_dict()))
#     if len(results) > 4:
#         lines.append(f"...e mais {len(results)-4} produto(s).")
#     return "\n\n".join(lines)


# @tool
# def buscar_por_preco(preco_min: float, preco_max: float) -> str:
#     """
#     Busca produtos dentro de uma faixa de preco.

#     Args:
#         preco_min: Preco minimo em reais (ex: 50.0).
#         preco_max: Preco maximo em reais (ex: 200.0).
#     """
#     db = _db()
#     if not db:
#         return "Erro interno."
#     results = get_products_by_price(db, preco_min, preco_max)
#     if not results:
#         return f"Nenhum produto entre R$ {preco_min:.2f} e R$ {preco_max:.2f}."
#     top = results[:4]
#     _capture([p.to_dict() for p in top])
#     lines = [f"Produtos entre R$ {preco_min:.2f} e R$ {preco_max:.2f}:\n"]
#     for p in top:
#         lines.append(_fmt(p.to_dict()))
#     return "\n\n".join(lines)


# @tool
# def verificar_estoque(nome_produto: str) -> str:
#     """
#     Verifica disponibilidade em estoque de um produto.

#     Args:
#         nome_produto: Nome ou parte do nome do produto.
#     """
#     db = _db()
#     if not db:
#         return "Erro interno."
#     results: list[Product] = search_products(db, nome_produto, max_results=3)
#     if not results:
#         return f"Produto '{nome_produto}' nao encontrado."
#     lines = []
#     for p in results:
#         s = "Disponivel" if p.disponibilidade else "Fora de estoque"
#         lines.append(f"{p.nome} — {s} | R$ {p.preco:.2f}")
#     return "\n".join(lines)


# @tool
# def detalhe_produto(produto_id: str) -> str:
#     """
#     Retorna detalhes completos de um produto pelo ID.

#     Args:
#         produto_id: ID do produto (ex: 'CAL001').
#     """
#     db = _db()
#     if not db:
#         return "Erro interno."
#     p: Optional[Product] = db.query(Product).filter_by(id=produto_id).first()
#     if not p:
#         return f"Produto '{produto_id}' nao encontrado."
#     _capture([p.to_dict()])
#     return _fmt(p.to_dict())


# @tool
# def registrar_preferencia(categoria_favorita: str = "", faixa_preco: str = "") -> str:
#     """
#     Salva preferencias do cliente para personalizar futuras visitas.

#     Args:
#         categoria_favorita: Categoria de maior interesse (ex: 'Calcados').
#         faixa_preco: Budget aproximado (ex: 'ate-100', '100-300', 'acima-300').
#     """
#     # As preferencias sao salvas via update_preferences apos a execucao
#     return "Preferencias registradas."


# # ══════════════════════════════════════════════════════════════════════════════
# #  SYSTEM PROMPT
# # ══════════════════════════════════════════════════════════════════════════════

# _SYSTEM = dedent("""\
#     Voce e o atendente virtual do {store}, uma loja online de moda.
#     Atenda em portugues do Brasil com simpatia e naturalidade.
#     Conduza sempre a conversa em direcao a uma venda.

#     FERRAMENTAS — USE SEMPRE para buscar produtos (nunca invente):
#     - buscar_produtos(consulta): busca geral por texto
#     - listar_categorias(): mostra categorias disponiveis
#     - listar_por_categoria(categoria): filtra por categoria
#     - buscar_por_preco(min, max): filtra por faixa de preco
#     - verificar_estoque(nome): checa disponibilidade
#     - detalhe_produto(id): detalhes por ID
#     - registrar_preferencia(cat, preco): salva preferencias

#     REGRAS:
#     - NUNCA invente produtos, precos ou informacoes
#     - Se nao encontrar, seja honesto
#     - Sempre apresente: nome + preco + descricao
#     - Sugira produtos relacionados
#     - Faca perguntas para entender o cliente
#     - Finalize com uma pergunta para manter a conversa
#     - Nao responda sobre temas fora da loja

#     {customer_context}
# """)


# # ══════════════════════════════════════════════════════════════════════════════
# #  AGENT FACTORY
# # ══════════════════════════════════════════════════════════════════════════════

# def _make_agent(session_id: str, customer: Optional[Customer], db: Session) -> Agent:
#     _ctx.db = db
#     _ctx.products = []

#     customer_ctx = ""
#     if customer:
#         customer_ctx = "CONTEXTO DO CLIENTE:\n" + customer.context_summary()

#     system = _SYSTEM.format(
#         store=config.STORE_NAME,
#         customer_context=customer_ctx,
#     )

#     import inspect as _inspect
#     _agent_params = set(_inspect.signature(Agent.__init__).parameters.keys())

#     def _has(k): return k in _agent_params or "kwargs" in _agent_params

#     kwargs: dict = dict(
#         name="Atendente",
#         model=build_model(),
#         tools=[
#             buscar_produtos,
#             listar_categorias,
#             listar_por_categoria,
#             buscar_por_preco,
#             verificar_estoque,
#             detalhe_produto,
#             registrar_preferencia,
#         ],
#         instructions=system,
#     )

#     if _has("markdown"):         kwargs["markdown"]         = True
#     if _has("show_tool_calls"):  kwargs["show_tool_calls"]  = False
#     if _has("debug_mode"):       kwargs["debug_mode"]       = False

#     if _HAS_STORAGE:
#         storage_extra = dict(
#             storage=SqliteStorage(
#                 table_name="agent_sessions",
#                 db_file=str(BASE_DIR / "agent_sessions.db"),
#             ),
#             session_id=session_id,
#             add_history_to_messages=True,
#             num_history_responses=config.MAX_HISTORY,
#         )
#         for k, v in storage_extra.items():
#             if _has(k):
#                 kwargs[k] = v

#     return Agent(**kwargs)


# # ══════════════════════════════════════════════════════════════════════════════
# #  PUBLIC API
# # ══════════════════════════════════════════════════════════════════════════════

# def run_agent(db: Session, session_id: str, user_message: str) -> tuple[str, list[dict]]:
#     """
#     Executa o agente e retorna (texto_resposta, produtos_encontrados).
#     Salva mensagens no DB de clientes para histórico e perfil.
#     """
#     customer = get_or_create_customer(db, session_id)
#     agent    = _make_agent(session_id, customer, db)

#     log.info("run_agent start: session=%s", session_id)

#     response = agent.run(user_message, stream=False)

#     text = _extract_text(response)
#     log.info("run_agent ok: text_len=%d", len(text))

#     if not text.strip():
#         text = "Desculpe, nao consegui processar sua mensagem. Pode repetir?"

#     # Salva no DB de clientes (perfil + histórico externo)
#     save_message(db, session_id, "user", user_message)
#     save_message(db, session_id, "assistant", text)

#     return text, get_captured_products()


# # ══════════════════════════════════════════════════════════════════════════════
# #  CLI
# # ══════════════════════════════════════════════════════════════════════════════

# if __name__ == "__main__":
#     from database import SessionLocal, init_db

#     logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
#     init_db()

#     print("\n" + "=" * 52)
#     print(f"   Loja: {config.STORE_NAME}")
#     print(f"   Provider: {config.LLM_PROVIDER.upper()} / {config.LLM_MODEL}")
#     print("=" * 52)
#     print("   'sair' para encerrar\n")

#     db_sess  = SessionLocal()
#     sess_id  = "cli_" + uuid.uuid4().hex[:8]

#     try:
#         while True:
#             try:
#                 msg = input("Voce: ").strip()
#                 if not msg:
#                     continue
#                 if msg.lower() in ("sair", "exit"):
#                     print("\nAte logo!\n")
#                     break
#                 resp, prods = run_agent(db_sess, sess_id, msg)
#                 print(f"\nAgente: {resp}")
#                 if prods:
#                     print(f"[{len(prods)} produto(s) encontrado(s)]\n")
#                 else:
#                     print()
#             except KeyboardInterrupt:
#                 print("\n\nAte logo!\n")
#                 break
#     finally:
#         db_sess.close()


#####################################################################################
           """
Agente de Vendas — Agno Framework
Suporta: Anthropic Claude | OpenAI GPT-4o | Groq (Llama 3.3)

Histórico: gerenciado pelo SqliteStorage nativo do Agno (NÃO via messages=)
Memória de cliente: injetada no system prompt via SQLAlchemy
"""
from __future__ import annotations

import logging
import threading
import uuid
from pathlib import Path
from textwrap import dedent
from typing import Optional

from sqlalchemy.orm import Session

from agno.agent import Agent
from agno.tools import tool

try:
    from agno.storage.sqlite import SqliteStorage
    _HAS_STORAGE = True
except ImportError:
    _HAS_STORAGE = False
    logging.warning("agno.storage.sqlite não disponível — histórico desabilitado")

import config
from database import (
    Customer, Product,
    get_or_create_customer,
    search_products, get_products_by_category,
    get_products_by_price, update_preferences,
    save_message,
    get_history,
)

log = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent


# ── Thread-local: compartilha DB e lista de produtos com as tools ─────────────
_ctx = threading.local()

def _db() -> Optional[Session]:
    return getattr(_ctx, "db", None)

def _capture(products: list[dict]):
    if not hasattr(_ctx, "products"):
        _ctx.products = []
    _ctx.products.extend(products)

def get_captured_products() -> list[dict]:
    return list(getattr(_ctx, "products", []))


# ══════════════════════════════════════════════════════════════════════════════
#  LLM FACTORY
# ══════════════════════════════════════════════════════════════════════════════

def build_model():
    provider = config.LLM_PROVIDER
    model_id  = config.LLM_MODEL

    log.info("Provider: %s | Modelo: %s", provider, model_id)

    if provider == "anthropic":
        from agno.models.anthropic import Claude
        return Claude(id=model_id)
    elif provider == "openai":
        from agno.models.openai import OpenAIChat
        return OpenAIChat(id=model_id)
    elif provider == "groq":
        from agno.models.groq import Groq
        return Groq(id=model_id)
    else:
        raise ValueError(
            f"LLM_PROVIDER inválido: '{provider}'. Use: anthropic | openai | groq"
        )


# ══════════════════════════════════════════════════════════════════════════════
#  EXTRAÇÃO DE TEXTO ROBUSTA
#  O Agno pode retornar string, RunResponse, gerador ou objetos variados.
#  Esta função extrai o texto em qualquer cenário.
# ══════════════════════════════════════════════════════════════════════════════

def _extract_text(response) -> str:
    if response is None:
        return ""

    # 1. String direta
    if isinstance(response, str):
        return response.strip()

    # 2. Gerador (stream acidental com stream=False)
    if hasattr(response, "__next__"):
        parts = []
        try:
            for chunk in response:
                t = _extract_text(chunk)
                if t:
                    parts.append(t)
        except Exception:
            pass
        return "".join(parts).strip()

    # 3. .content como string
    if hasattr(response, "content"):
        c = response.content
        if isinstance(c, str) and c.strip():
            return c.strip()
        # 3a. .content como lista de blocos (Anthropic style)
        if isinstance(c, list):
            parts = []
            for b in c:
                if isinstance(b, str):
                    parts.append(b)
                elif isinstance(b, dict) and b.get("type") == "text":
                    parts.append(b.get("text", ""))
                elif hasattr(b, "text"):
                    parts.append(str(b.text))
            text = "\n".join(p for p in parts if p).strip()
            if text:
                return text

    # 4. Busca no .messages (fallback pós-tool-use quando .content é None)
    if hasattr(response, "messages") and response.messages:
        for msg in reversed(response.messages):
            role = getattr(msg, "role", None)
            if role in ("assistant", "model"):
                content = getattr(msg, "content", None)
                if content:
                    if isinstance(content, str) and content.strip():
                        return content.strip()
                    if isinstance(content, list):
                        parts = []
                        for b in content:
                            if isinstance(b, dict) and b.get("type") == "text":
                                parts.append(b.get("text", ""))
                            elif hasattr(b, "text"):
                                parts.append(str(b.text))
                        text = "\n".join(p for p in parts if p).strip()
                        if text:
                            return text

    # 5. Último recurso
    fallback = str(response).strip()
    if fallback.startswith("<") or "object at 0x" in fallback:
        return ""
    return fallback


# ══════════════════════════════════════════════════════════════════════════════
#  PRODUCT FORMATTER
# ══════════════════════════════════════════════════════════════════════════════

def _fmt(p: dict) -> str:
    avail = "✅ Disponível" if p["disponibilidade"] else "❌ Fora de estoque"
    return (
        "[PRODUCT_START]\n"
        f"ID:{p['id']}|NOME:{p['nome']}|PRECO:{p['preco']:.2f}"
        f"|CATEGORIA:{p['categoria']}|DISPONIVEL:{p['disponibilidade']}"
        f"|IMG:{p['image_url']}\n"
        f"📦 **{p['nome']}**  |  💰 R$ {p['preco']:.2f}  |  {avail}\n"
        f"📝 {p['descricao']}\n"
        "[PRODUCT_END]"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  TOOLS
# ══════════════════════════════════════════════════════════════════════════════

@tool
def buscar_produtos(consulta: str) -> str:
    """
    Busca produtos no catálogo por texto livre.
    SEMPRE use quando o cliente mencionar qualquer produto.

    Args:
        consulta: Termos de busca (ex: 'tenis corrida', 'camiseta preta barata').
    """
    db = _db()
    if not db:
        return "Erro: banco de dados indisponível."
    results: list[Product] = search_products(db, consulta, max_results=3)
    if not results:
        return f"Nenhum produto encontrado para '{consulta}'."
    _capture([p.to_dict() for p in results])
    lines = [f"Encontrei {len(results)} produto(s) para '{consulta}':\n"]
    for p in results:
        lines.append(_fmt(p.to_dict()))
    return "\n\n".join(lines)


@tool
def listar_categorias() -> str:
    """Lista todas as categorias de produtos disponíveis na loja."""
    db = _db()
    if not db:
        return "Erro interno."
    cats = sorted({p.categoria for p in db.query(Product).all()})
    return "Categorias disponíveis: " + " | ".join(cats)


@tool
def listar_por_categoria(categoria: str) -> str:
    """
    Lista produtos de uma categoria específica.

    Args:
        categoria: Nome da categoria (ex: 'Calcados', 'Roupas', 'Acessorios').
    """
    db = _db()
    if not db:
        return "Erro interno."
    results = get_products_by_category(db, categoria)
    if not results:
        return f"Nenhum produto na categoria '{categoria}'."
    top = results[:4]
    _capture([p.to_dict() for p in top])
    lines = [f"Produtos em '{categoria}' ({len(results)} itens):\n"]
    for p in top:
        lines.append(_fmt(p.to_dict()))
    if len(results) > 4:
        lines.append(f"...e mais {len(results)-4} produto(s).")
    return "\n\n".join(lines)


@tool
def buscar_por_preco(preco_min: float, preco_max: float) -> str:
    """
    Busca produtos dentro de uma faixa de preco.

    Args:
        preco_min: Preco minimo em reais (ex: 50.0).
        preco_max: Preco maximo em reais (ex: 200.0).
    """
    db = _db()
    if not db:
        return "Erro interno."
    results = get_products_by_price(db, preco_min, preco_max)
    if not results:
        return f"Nenhum produto entre R$ {preco_min:.2f} e R$ {preco_max:.2f}."
    top = results[:4]
    _capture([p.to_dict() for p in top])
    lines = [f"Produtos entre R$ {preco_min:.2f} e R$ {preco_max:.2f}:\n"]
    for p in top:
        lines.append(_fmt(p.to_dict()))
    return "\n\n".join(lines)


@tool
def verificar_estoque(nome_produto: str) -> str:
    """
    Verifica disponibilidade em estoque de um produto.

    Args:
        nome_produto: Nome ou parte do nome do produto.
    """
    db = _db()
    if not db:
        return "Erro interno."
    results: list[Product] = search_products(db, nome_produto, max_results=3)
    if not results:
        return f"Produto '{nome_produto}' nao encontrado."
    lines = []
    for p in results:
        s = "Disponivel" if p.disponibilidade else "Fora de estoque"
        lines.append(f"{p.nome} — {s} | R$ {p.preco:.2f}")
    return "\n".join(lines)


@tool
def detalhe_produto(produto_id: str) -> str:
    """
    Retorna detalhes completos de um produto pelo ID.

    Args:
        produto_id: ID do produto (ex: 'CAL001').
    """
    db = _db()
    if not db:
        return "Erro interno."
    p: Optional[Product] = db.query(Product).filter_by(id=produto_id).first()
    if not p:
        return f"Produto '{produto_id}' nao encontrado."
    _capture([p.to_dict()])
    return _fmt(p.to_dict())


@tool
def registrar_preferencia(categoria_favorita: str = "", faixa_preco: str = "") -> str:
    """
    Salva preferencias do cliente para personalizar futuras visitas.

    Args:
        categoria_favorita: Categoria de maior interesse (ex: 'Calcados').
        faixa_preco: Budget aproximado (ex: 'ate-100', '100-300', 'acima-300').
    """
    # As preferencias sao salvas via update_preferences apos a execucao
    return "Preferencias registradas."


# ══════════════════════════════════════════════════════════════════════════════
#  SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════════════

_SYSTEM = dedent("""\
    Voce e o atendente virtual do {store}, uma loja de moda online.
    Atenda em portugues do Brasil com simpatia, calor humano e naturalidade.

    == PRIMEIRO CONTATO ==
    Se for a primeira mensagem do cliente (historico vazio):
    - Cumprimente com entusiasmo e se apresente brevemente
    - Pergunte o nome do cliente de forma gentil e natural
    - Exemplo: "Ola! Bem-vindo(a) ao {store}! Eu sou a assistente virtual daqui. Qual e o seu nome por favor?"

    == CLIENTE RECORRENTE ==
    Se o nome do cliente estiver no historico/contexto:
    - Cumprimente pelo nome com entusiasmo: "Que bom te ver de volta, [Nome]!"
    - Retome o contexto anterior se relevante

    == IDENTIFICACAO DE GENERO E PERFIL ==
    Apos saber o nome, pergunte de forma natural para quem e a compra:
    - "E para voce mesmo(a) ou vai de presente para alguem?"
    - Se for presente: pergunte o genero de quem vai receber para sugerir produtos certos
    - Use essa informacao para filtrar sugestoes adequadas
    - Armazene isso mentalmente durante toda a conversa

    == FERRAMENTAS - USE SEMPRE (nunca invente produtos) ==
    - buscar_produtos(consulta)
    - listar_categorias()
    - listar_por_categoria(categoria)
    - buscar_por_preco(min, max)
    - verificar_estoque(nome)
    - detalhe_produto(id)
    - registrar_preferencia(cat, preco)

    == FOTOS E PRODUTOS ==
    - SO mostre imagens/cards de produtos se o cliente PEDIR explicitamente
      (ex: "me mostra", "quero ver", "tem foto?", "mostra opcoes")
    - Quando apenas conversando ou respondendo duvidas, descreva o produto em texto
    - Quando mostrar produtos, use a ferramenta buscar_produtos ou listar_por_categoria

    == REGRAS CRITICAS ==
    1. NUNCA invente produtos ou precos - use SEMPRE as ferramentas
    2. NUNCA repita perguntas ja respondidas - leia o historico
    3. NUNCA use "seu nome" como placeholder - so use o nome se foi informado
    4. Faca no maximo UMA pergunta por resposta
    5. Seja direto e objetivo
    6. Nao saia do contexto da loja

    {customer_context}
""")

# ══════════════════════════════════════════════════════════════════════════════
#  AGENT FACTORY
# ══════════════════════════════════════════════════════════════════════════════

def _make_agent(session_id: str, customer: Optional[Customer], db: Session,
               history_msgs: list[dict] | None = None) -> Agent:
    _ctx.db = db
    _ctx.products = []

    customer_ctx = ""
    if customer:
        customer_ctx = "CONTEXTO DO CLIENTE:\n" + customer.context_summary()

    # Injeta o histórico direto no system prompt — funciona com qualquer provider
    history_ctx = ""
    if history_msgs:
        lines = ["\nHISTORICO DESTA CONVERSA (use para manter contexto e nao repetir):"]
        for m in history_msgs[-20:]:   # últimas 20 msgs
            role_label = "Cliente" if m["role"] == "user" else "Atendente"
            # trunca mensagens longas para não explodir o contexto
            text = m["content"][:300] + "..." if len(m["content"]) > 300 else m["content"]
            lines.append(f"[{role_label}]: {text}")
        history_ctx = "\n".join(lines)

    system = _SYSTEM.format(
        store=config.STORE_NAME,
        customer_context=customer_ctx + history_ctx,
    )

    import inspect as _inspect
    _agent_params = set(_inspect.signature(Agent.__init__).parameters.keys())

    def _has(k): return k in _agent_params or "kwargs" in _agent_params

    kwargs: dict = dict(
        name="Atendente",
        model=build_model(),
        tools=[
            buscar_produtos,
            listar_categorias,
            listar_por_categoria,
            buscar_por_preco,
            verificar_estoque,
            detalhe_produto,
            registrar_preferencia,
        ],
        instructions=system,
    )

    if _has("markdown"):         kwargs["markdown"]         = True
    if _has("show_tool_calls"):  kwargs["show_tool_calls"]  = False
    if _has("debug_mode"):       kwargs["debug_mode"]       = False

    if _HAS_STORAGE:
        storage_extra = dict(
            storage=SqliteStorage(
                table_name="agent_sessions",
                db_file=str(BASE_DIR / "agent_sessions.db"),
            ),
            session_id=session_id,
            add_history_to_messages=True,
            num_history_responses=config.MAX_HISTORY,
        )
        for k, v in storage_extra.items():
            if _has(k):
                kwargs[k] = v

    return Agent(**kwargs)


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def run_agent(db: Session, session_id: str, user_message: str) -> tuple[str, list[dict]]:
    """
    Executa o agente e retorna (texto_resposta, produtos_encontrados).
    Salva mensagens no DB de clientes para histórico e perfil.
    """
    customer = get_or_create_customer(db, session_id)

    log.info("run_agent start: session=%s", session_id)

    # Carrega histórico do banco e injeta no system prompt via _make_agent
    history_msgs = [m.to_dict() for m in get_history(db, session_id, config.MAX_HISTORY)]
    agent = _make_agent(session_id, customer, db, history_msgs=history_msgs)
    log.info("Histórico: %d msgs injetadas no system prompt", len(history_msgs))

    response = agent.run(user_message, stream=False)

    text = _extract_text(response)
    log.info("run_agent ok: text_len=%d", len(text))

    if not text.strip():
        text = "Desculpe, nao consegui processar sua mensagem. Pode repetir?"

    # Salva no DB de clientes (perfil + histórico externo)
    save_message(db, session_id, "user", user_message)
    save_message(db, session_id, "assistant", text)

    return text, get_captured_products()


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from database import SessionLocal, init_db

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    init_db()

    print("\n" + "=" * 52)
    print(f"   Loja: {config.STORE_NAME}")
    print(f"   Provider: {config.LLM_PROVIDER.upper()} / {config.LLM_MODEL}")
    print("=" * 52)
    print("   'sair' para encerrar\n")

    db_sess  = SessionLocal()
    sess_id  = "cli_" + uuid.uuid4().hex[:8]

    try:
        while True:
            try:
                msg = input("Voce: ").strip()
                if not msg:
                    continue
                if msg.lower() in ("sair", "exit"):
                    print("\nAte logo!\n")
                    break
                resp, prods = run_agent(db_sess, sess_id, msg)
                print(f"\nAgente: {resp}")
                if prods:
                    print(f"[{len(prods)} produto(s) encontrado(s)]\n")
                else:
                    print()
            except KeyboardInterrupt:
                print("\n\nAte logo!\n")
                break
    finally:
        db_sess.close()
