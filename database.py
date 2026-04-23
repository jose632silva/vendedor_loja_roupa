# """
# Modelos e helpers do banco de dados.

# Tabelas:
#   customers  — perfil e preferências dos clientes (memória persistente)
#   messages   — histórico completo de todas as conversas
#   products   — catálogo de produtos
# """
# from __future__ import annotations

# import json
# from datetime import datetime
# from typing import Optional

# from sqlalchemy import (
#     Boolean, Column, DateTime, Float, ForeignKey,
#     Integer, String, Text, create_engine, event,
# )
# from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

# from config import DATABASE_URL, API_BASE_URL


# # ── Engine & Session ──────────────────────────────────────────────────────────
# connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

# # Habilita WAL no SQLite para melhor concorrência
# @event.listens_for(engine, "connect")
# def _set_sqlite_pragma(conn, _):
#     if DATABASE_URL.startswith("sqlite"):
#         conn.execute("PRAGMA journal_mode=WAL")
#         conn.execute("PRAGMA foreign_keys=ON")

# SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# class Base(DeclarativeBase):
#     pass


# # ══════════════════════════════════════════════════════════════════════════════
# #  MODELS
# # ══════════════════════════════════════════════════════════════════════════════

# class Customer(Base):
#     __tablename__ = "customers"

#     id          = Column(Integer, primary_key=True, index=True)
#     session_id  = Column(String(128), unique=True, index=True, nullable=False)
#     name        = Column(String(120), nullable=True)
#     email       = Column(String(200), nullable=True, index=True)
#     phone       = Column(String(30), nullable=True)
#     # JSON — ex: {"favorite_categories": ["Calçados"], "budget_range": "100-300"}
#     preferences = Column(Text, default="{}")
#     created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
#     last_seen   = Column(DateTime, default=datetime.utcnow, nullable=False)

#     messages = relationship("Message", back_populates="customer",
#                             cascade="all, delete-orphan", order_by="Message.created_at")

#     # ── helpers ──────────────────────────────────────────────────────────────
#     @property
#     def prefs(self) -> dict:
#         try:
#             return json.loads(self.preferences or "{}")
#         except Exception:
#             return {}

#     @prefs.setter
#     def prefs(self, value: dict):
#         self.preferences = json.dumps(value, ensure_ascii=False)

#     @property
#     def is_returning(self) -> bool:
#         return len(self.messages) > 0

#     def display_name(self) -> str:
#         return self.name or f"Cliente #{self.id}"

#     def context_summary(self) -> str:
#         """Resumo para injetar no system prompt do agente."""
#         lines = []
#         if self.name:
#             lines.append(f"Nome do cliente: {self.name}")
#         if self.email:
#             lines.append(f"E-mail: {self.email}")
#         msg_count = len(self.messages)
#         if msg_count > 0:
#             lines.append(
#                 f"Cliente recorrente — {msg_count} mensagens no histórico. "
#                 "Lembre-se de mencioná-lo pelo nome e referenciar conversas anteriores."
#             )
#         else:
#             lines.append("Novo cliente — seja especialmente acolhedor.")
#         prefs = self.prefs
#         if prefs.get("favorite_categories"):
#             lines.append(f"Categorias favoritas: {', '.join(prefs['favorite_categories'])}")
#         return "\n".join(lines)

#     def __repr__(self):
#         return f"<Customer session={self.session_id!r} name={self.name!r}>"


# class Message(Base):
#     __tablename__ = "messages"

#     id         = Column(Integer, primary_key=True, index=True)
#     session_id = Column(String(128), ForeignKey("customers.session_id",
#                         ondelete="CASCADE"), index=True, nullable=False)
#     role       = Column(String(20), nullable=False)   # "user" | "assistant"
#     content    = Column(Text, nullable=False)
#     created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

#     customer = relationship("Customer", back_populates="messages")

#     def to_dict(self) -> dict:
#         return {"role": self.role, "content": self.content}


# class Product(Base):
#     __tablename__ = "products"

#     id              = Column(String(20), primary_key=True)
#     nome            = Column(String(200), nullable=False, index=True)
#     categoria       = Column(String(80), nullable=False, index=True)
#     preco           = Column(Float, nullable=False)
#     descricao       = Column(Text)
#     disponibilidade = Column(Boolean, default=True)
#     # imagem_url: URL externa (fallback)
#     imagem_url      = Column(String(500), nullable=True)
#     # imagem_local: nome do arquivo em products/images/ (ex: "tenis-runner.jpg")
#     imagem_local    = Column(String(200), nullable=True)
#     tags            = Column(Text, default="[]")    # JSON array
#     destaque        = Column(Boolean, default=False)  # aparece na vitrine
#     created_at      = Column(DateTime, default=datetime.utcnow)
#     updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

#     @property
#     def tag_list(self) -> list[str]:
#         try:
#             return json.loads(self.tags or "[]")
#         except Exception:
#             return []

#     def image_url(self, api_base: str = API_BASE_URL) -> str:
#         """Retorna a URL da imagem mais apropriada."""
#         if self.imagem_local:
#             return f"{api_base}/products/images/{self.imagem_local}"
#         return self.imagem_url or ""

#     def to_dict(self, api_base: str = API_BASE_URL) -> dict:
#         return {
#             "id":              self.id,
#             "nome":            self.nome,
#             "categoria":       self.categoria,
#             "preco":           self.preco,
#             "descricao":       self.descricao,
#             "disponibilidade": self.disponibilidade,
#             "image_url":       self.image_url(api_base),
#             "destaque":        self.destaque,
#             "tags":            self.tag_list,
#         }

#     def __repr__(self):
#         return f"<Product {self.id!r} {self.nome!r} R${self.preco}>"


# # ══════════════════════════════════════════════════════════════════════════════
# #  DB HELPERS
# # ══════════════════════════════════════════════════════════════════════════════

# def get_db():
#     """FastAPI dependency — yields a scoped DB session."""
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# def init_db():
#     """Cria todas as tabelas (idempotente)."""
#     Base.metadata.create_all(bind=engine)


# # ── Customer ──────────────────────────────────────────────────────────────────

# def get_or_create_customer(db: Session, session_id: str) -> Customer:
#     customer = db.query(Customer).filter_by(session_id=session_id).first()
#     if not customer:
#         customer = Customer(session_id=session_id)
#         db.add(customer)
#         db.commit()
#         db.refresh(customer)
#     else:
#         customer.last_seen = datetime.utcnow()
#         db.commit()
#     return customer


# def identify_customer(
#     db: Session, session_id: str,
#     name: Optional[str] = None,
#     email: Optional[str] = None,
#     phone: Optional[str] = None,
# ) -> Customer:
#     """Atualiza dados de identificação do cliente."""
#     customer = get_or_create_customer(db, session_id)
#     if name:  customer.name  = name.strip()
#     if email: customer.email = email.strip().lower()
#     if phone: customer.phone = phone.strip()
#     db.commit()
#     db.refresh(customer)
#     return customer


# def update_preferences(db: Session, session_id: str, **kwargs) -> Customer:
#     customer = get_or_create_customer(db, session_id)
#     prefs = customer.prefs
#     prefs.update(kwargs)
#     customer.prefs = prefs
#     db.commit()
#     return customer


# # ── Messages ──────────────────────────────────────────────────────────────────

# def save_message(db: Session, session_id: str, role: str, content: str):
#     msg = Message(session_id=session_id, role=role, content=content)
#     db.add(msg)
#     db.commit()


# def get_history(db: Session, session_id: str, limit: int = 20) -> list[Message]:
#     """Retorna as últimas `limit` mensagens em ordem cronológica."""
#     return (
#         db.query(Message)
#         .filter_by(session_id=session_id)
#         .order_by(Message.created_at.desc())
#         .limit(limit)
#         .all()[::-1]
#     )


# # ── Products ──────────────────────────────────────────────────────────────────

# def search_products(db: Session, query: str, max_results: int = 3) -> list[Product]:
#     q = query.lower()
#     scored: list[tuple[int, Product]] = []
#     for p in db.query(Product).all():
#         score = 0
#         haystack = " ".join([
#             p.nome.lower(), p.categoria.lower(),
#             (p.descricao or "").lower(),
#             " ".join(p.tag_list),
#         ])
#         for word in q.split():
#             score += haystack.count(word)
#         if score:
#             scored.append((score, p))
#     scored.sort(key=lambda x: x[0], reverse=True)
#     return [p for _, p in scored[:max_results]]


# def get_products_by_category(db: Session, categoria: str) -> list[Product]:
#     return db.query(Product).filter(
#         Product.categoria.ilike(f"%{categoria}%")
#     ).all()


# def get_products_by_price(db: Session, pmin: float, pmax: float) -> list[Product]:
#     return (
#         db.query(Product)
#         .filter(Product.preco >= pmin, Product.preco <= pmax)
#         .order_by(Product.preco)
#         .all()
#     )


# def get_featured_products(db: Session, limit: int = 6) -> list[Product]:
#     return db.query(Product).filter_by(destaque=True).limit(limit).all()



########################################################

"""
Modelos e helpers do banco de dados.

Tabelas:
  customers  — perfil e preferências dos clientes (memória persistente)
  messages   — histórico completo de todas as conversas
  products   — catálogo de produtos
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, create_engine, event,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from config import DATABASE_URL, API_BASE_URL


# ── Engine & Session ──────────────────────────────────────────────────────────
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

# Habilita WAL no SQLite para melhor concorrência
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(conn, _):
    if DATABASE_URL.startswith("sqlite"):
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


# ══════════════════════════════════════════════════════════════════════════════
#  MODELS
# ══════════════════════════════════════════════════════════════════════════════

class Customer(Base):
    __tablename__ = "customers"

    id          = Column(Integer, primary_key=True, index=True)
    session_id  = Column(String(128), unique=True, index=True, nullable=False)
    name        = Column(String(120), nullable=True)
    email       = Column(String(200), nullable=True, index=True)
    phone       = Column(String(30), nullable=True)
    # JSON — ex: {"favorite_categories": ["Calçados"], "budget_range": "100-300"}
    preferences = Column(Text, default="{}")
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen   = Column(DateTime, default=datetime.utcnow, nullable=False)

    messages = relationship("Message", back_populates="customer",
                            cascade="all, delete-orphan", order_by="Message.created_at")

    # ── helpers ──────────────────────────────────────────────────────────────
    @property
    def prefs(self) -> dict:
        try:
            return json.loads(self.preferences or "{}")
        except Exception:
            return {}

    @prefs.setter
    def prefs(self, value: dict):
        self.preferences = json.dumps(value, ensure_ascii=False)

    @property
    def is_returning(self) -> bool:
        return len(self.messages) > 0

    def display_name(self) -> str:
        return self.name or f"Cliente #{self.id}"

    def context_summary(self) -> str:
        """Resumo para injetar no system prompt do agente."""
        lines = []
        if self.name:
            lines.append(f"Nome do cliente: {self.name}. Use este nome ao se dirigir a ele.")
        else:
            lines.append("Nome do cliente: desconhecido. NAO use nenhum placeholder como 'seu nome'.")
        if self.email:
            lines.append(f"E-mail: {self.email}")
        msg_count = len(self.messages)
        if msg_count > 0:
            lines.append(f"Cliente recorrente ({msg_count} mensagens anteriores). Seja caloroso no reencontro.")
        else:
            lines.append("Primeira visita do cliente.")
        prefs = self.prefs
        if prefs.get("favorite_categories"):
            lines.append(f"Categorias de interesse: {', '.join(prefs['favorite_categories'])}")
        if prefs.get("budget_range"):
            lines.append(f"Faixa de preco preferida: {prefs['budget_range']}")
        return "\n".join(lines)

    def __repr__(self):
        return f"<Customer session={self.session_id!r} name={self.name!r}>"


class Message(Base):
    __tablename__ = "messages"

    id         = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(128), ForeignKey("customers.session_id",
                        ondelete="CASCADE"), index=True, nullable=False)
    role       = Column(String(20), nullable=False)   # "user" | "assistant"
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    customer = relationship("Customer", back_populates="messages")

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class Product(Base):
    __tablename__ = "products"

    id              = Column(String(20), primary_key=True)
    nome            = Column(String(200), nullable=False, index=True)
    categoria       = Column(String(80), nullable=False, index=True)
    preco           = Column(Float, nullable=False)
    descricao       = Column(Text)
    disponibilidade = Column(Boolean, default=True)
    # imagem_url: URL externa (fallback)
    imagem_url      = Column(String(500), nullable=True)
    # imagem_local: nome do arquivo em products/images/ (ex: "tenis-runner.jpg")
    imagem_local    = Column(String(200), nullable=True)
    tags            = Column(Text, default="[]")    # JSON array
    destaque        = Column(Boolean, default=False)  # aparece na vitrine
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def tag_list(self) -> List[str]:
        try:
            return json.loads(self.tags or "[]")
        except Exception:
            return []

    def image_url(self, api_base: str = API_BASE_URL) -> str:
        """Retorna a URL da imagem mais apropriada."""
        if self.imagem_local:
            return f"{api_base}/products/images/{self.imagem_local}"
        return self.imagem_url or ""

    def to_dict(self, api_base: str = API_BASE_URL) -> dict:
        return {
            "id":              self.id,
            "nome":            self.nome,
            "categoria":       self.categoria,
            "preco":           self.preco,
            "descricao":       self.descricao,
            "disponibilidade": self.disponibilidade,
            "image_url":       self.image_url(api_base),
            "destaque":        self.destaque,
            "tags":            self.tag_list,
        }

    def __repr__(self):
        return f"<Product {self.id!r} {self.nome!r} R${self.preco}>"


# ══════════════════════════════════════════════════════════════════════════════
#  DB HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_db():
    """FastAPI dependency — yields a scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Cria todas as tabelas (idempotente)."""
    Base.metadata.create_all(bind=engine)


# ── Customer ──────────────────────────────────────────────────────────────────

def get_or_create_customer(db: Session, session_id: str) -> Customer:
    customer = db.query(Customer).filter_by(session_id=session_id).first()
    if not customer:
        customer = Customer(session_id=session_id)
        db.add(customer)
        db.commit()
        db.refresh(customer)
    else:
        customer.last_seen = datetime.utcnow()
        db.commit()
    return customer


def identify_customer(
    db: Session, session_id: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> Customer:
    """Atualiza dados de identificação do cliente."""
    customer = get_or_create_customer(db, session_id)
    if name:  customer.name  = name.strip()
    if email: customer.email = email.strip().lower()
    if phone: customer.phone = phone.strip()
    db.commit()
    db.refresh(customer)
    return customer


def update_preferences(db: Session, session_id: str, **kwargs) -> Customer:
    customer = get_or_create_customer(db, session_id)
    prefs = customer.prefs
    prefs.update(kwargs)
    customer.prefs = prefs
    db.commit()
    return customer


# ── Messages ──────────────────────────────────────────────────────────────────

def save_message(db: Session, session_id: str, role: str, content: str):
    msg = Message(session_id=session_id, role=role, content=content)
    db.add(msg)
    db.commit()


def get_history(db: Session, session_id: str, limit: int = 20) -> List[Message]:
    """Retorna as últimas `limit` mensagens em ordem cronológica."""
    return (
        db.query(Message)
        .filter_by(session_id=session_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()[::-1]
    )


# ── Products ──────────────────────────────────────────────────────────────────

def search_products(db: Session, query: str, max_results: int = 3) -> List[Product]:
    q = query.lower()
    scored: List[Tuple[int, Product]] = []
    for p in db.query(Product).all():
        score = 0
        haystack = " ".join([
            p.nome.lower(), p.categoria.lower(),
            (p.descricao or "").lower(),
            " ".join(p.tag_list),
        ])
        for word in q.split():
            score += haystack.count(word)
        if score:
            scored.append((score, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:max_results]]


def get_products_by_category(db: Session, categoria: str) -> List[Product]:
    return db.query(Product).filter(
        Product.categoria.ilike(f"%{categoria}%")
    ).all()


def get_products_by_price(db: Session, pmin: float, pmax: float) -> List[Product]:
    return (
        db.query(Product)
        .filter(Product.preco >= pmin, Product.preco <= pmax)
        .order_by(Product.preco)
        .all()
    )


def get_featured_products(db: Session, limit: int = 6) -> List[Product]:
    return db.query(Product).filter_by(destaque=True).limit(limit).all()

