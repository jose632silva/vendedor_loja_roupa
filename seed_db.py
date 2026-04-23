"""
Popula o banco de dados com produtos de exemplo.
Execute uma vez: python seed_db.py

Para resetar: python seed_db.py --reset
"""
import json
import sys
from pathlib import Path

from database import Product, SessionLocal, init_db

PRODUCTS: list[dict] = [
    # ── Calçados ──────────────────────────────────────────────────────────────
    {
        "id": "CAL001",
        "nome": "Tênis Runner Pro X",
        "categoria": "Calçados",
        "preco": 349.90,
        "descricao": "Tênis de corrida de alta performance com amortecimento reativo e cabedal em mesh respirável. Palmilha anatômica removível. Disponível nos números 37 ao 44.",
        "disponibilidade": True,
        "imagem_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=80",
        "imagem_local": "",
        "tags": ["tênis", "corrida", "esporte", "academia", "running"],
        "destaque": True,
    },
    {
        "id": "CAL002",
        "nome": "Tênis Casual Street Low",
        "categoria": "Calçados",
        "preco": 219.90,
        "descricao": "Tênis casual estilo streetwear em couro sintético premium. Solado vulcanizado, extremamente confortável para uso diário. Disponível em branco, preto e cinza.",
        "disponibilidade": True,
        "imagem_url": "https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?w=600&q=80",
        "imagem_local": "",
        "tags": ["tênis", "casual", "street", "urbano", "sneaker"],
        "destaque": True,
    },
    {
        "id": "CAL003",
        "nome": "Tênis Esportivo Training",
        "categoria": "Calçados",
        "preco": 179.90,
        "descricao": "Ideal para treinos funcionais e academia. Solado de borracha com tração multidirecional, cabedal reforçado nos pontos de estresse.",
        "disponibilidade": True,
        "imagem_url": "https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=600&q=80",
        "imagem_local": "",
        "tags": ["tênis", "treino", "academia", "funcional", "esporte"],
        "destaque": False,
    },
    {
        "id": "CAL004",
        "nome": "Chinelo Slide Premium",
        "categoria": "Calçados",
        "preco": 89.90,
        "descricao": "Chinelo slide com palmilha em EVA de alta densidade, tira dupla anti-torção. Ideal para praia, piscina e uso doméstico. Tamanho único ajustável.",
        "disponibilidade": True,
        "imagem_url": "https://images.unsplash.com/photo-1603487742131-4160ec999306?w=600&q=80",
        "imagem_local": "",
        "tags": ["chinelo", "slide", "praia", "piscina", "verão"],
        "destaque": False,
    },
    # ── Roupas ────────────────────────────────────────────────────────────────
    {
        "id": "ROU001",
        "nome": "Camiseta Básica Essential",
        "categoria": "Roupas",
        "preco": 59.90,
        "descricao": "Camiseta 100% algodão penteado, corte regular, costuras reforçadas. Não desbota. Disponível em preto, branco, cinza e azul marinho nos tamanhos P ao GG.",
        "disponibilidade": True,
        "imagem_url": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=600&q=80",
        "imagem_local": "",
        "tags": ["camiseta", "básica", "algodão", "clássica", "roupa"],
        "destaque": True,
    },
    {
        "id": "ROU002",
        "nome": "Camiseta Dry-Fit Performance",
        "categoria": "Roupas",
        "preco": 79.90,
        "descricao": "Camiseta tecnológica com tecido dry-fit que afasta a umidade do corpo. Proteção UV50+. Ideal para treinos, corrida e esportes ao ar livre.",
        "disponibilidade": True,
        "imagem_url": "https://images.unsplash.com/photo-1503341504253-dff4815485f1?w=600&q=80",
        "imagem_local": "",
        "tags": ["camiseta", "dry-fit", "esporte", "treino", "uv", "roupa"],
        "destaque": False,
    },
    {
        "id": "ROU003",
        "nome": "Calça Jeans Slim Premium",
        "categoria": "Roupas",
        "preco": 189.90,
        "descricao": "Calça jeans de corte slim com 2% de elastano para máximo conforto e mobilidade. Lavagem stonewash. Disponível do 36 ao 48.",
        "disponibilidade": True,
        "imagem_url": "https://images.unsplash.com/photo-1542272604-787c3835535d?w=600&q=80",
        "imagem_local": "",
        "tags": ["calça", "jeans", "slim", "premium", "roupa"],
        "destaque": True,
    },
    {
        "id": "ROU004",
        "nome": "Moletom Oversized Comfort",
        "categoria": "Roupas",
        "preco": 149.90,
        "descricao": "Moletom felpudo em modelo oversized, algodão 80% e poliéster 20%. Capuz com cordão, bolso canguru. Tamanhos P ao GGG.",
        "disponibilidade": True,
        "imagem_url": "https://images.unsplash.com/photo-1556821840-3a63f15732ce?w=600&q=80",
        "imagem_local": "",
        "tags": ["moletom", "oversized", "conforto", "inverno", "roupa"],
        "destaque": True,
    },
    {
        "id": "ROU005",
        "nome": "Jaqueta Corta-Vento Ultralight",
        "categoria": "Roupas",
        "preco": 279.90,
        "descricao": "Jaqueta corta-vento impermeável em nylon ripstop ultraleve. Capuz retrátil, bolsos com zíper. Dobra em si mesma formando uma bolsa compacta.",
        "disponibilidade": True,
        "imagem_url": "https://images.unsplash.com/photo-1544923246-77307dd654cb?w=600&q=80",
        "imagem_local": "",
        "tags": ["jaqueta", "corta-vento", "impermeável", "outdoor", "roupa"],
        "destaque": True,
    },
    {
        "id": "ROU006",
        "nome": "Shorts Treino Flex",
        "categoria": "Roupas",
        "preco": 79.90,
        "descricao": "Shorts de treino em tecido flex com 4 vias de elasticidade. Cós duplo com elástico e cordão, bolso lateral com zíper. Tamanhos P ao GG.",
        "disponibilidade": True,
        "imagem_url": "https://images.unsplash.com/photo-1591195853828-11db59a44f43?w=600&q=80",
        "imagem_local": "",
        "tags": ["shorts", "treino", "academia", "flex", "roupa"],
        "destaque": False,
    },
    # ── Acessórios ────────────────────────────────────────────────────────────
    {
        "id": "ACE001",
        "nome": "Mochila Urban Explorer 30L",
        "categoria": "Acessórios",
        "preco": 289.90,
        "descricao": "Mochila urbana de 30L com compartimento para notebook até 17\", porta USB externa, costas acolchoadas ergonômicas e material resistente à água.",
        "disponibilidade": True,
        "imagem_url": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=600&q=80",
        "imagem_local": "",
        "tags": ["mochila", "urbana", "notebook", "viagem", "acessório"],
        "destaque": True,
    },
    {
        "id": "ACE002",
        "nome": "Boné Structured Snapback",
        "categoria": "Acessórios",
        "preco": 69.90,
        "descricao": "Boné estruturado 6 painéis, aba reta ou curva, regulagem snapback metálica. Tecido premium com bordado 3D. Tamanho único.",
        "disponibilidade": True,
        "imagem_url": "https://images.unsplash.com/photo-1588850561407-ed78c282e89b?w=600&q=80",
        "imagem_local": "",
        "tags": ["boné", "cap", "snapback", "acessório", "streetwear"],
        "destaque": False,
    },
    {
        "id": "ACE003",
        "nome": "Kit Meias Esportivas 6 Pares",
        "categoria": "Acessórios",
        "preco": 59.90,
        "descricao": "Kit com 6 pares de meias esportivas cano médio. Tecnologia antibacteriana, almofada no calcanhar e na ponta, sem costura.",
        "disponibilidade": True,
        "imagem_url": "https://images.unsplash.com/photo-1586350977771-b3b0abd50c82?w=600&q=80",
        "imagem_local": "",
        "tags": ["meias", "esportivas", "kit", "acessório", "treino"],
        "destaque": False,
    },
    {
        "id": "ACE004",
        "nome": "Cinto Casual Couro Sintético",
        "categoria": "Acessórios",
        "preco": 49.90,
        "descricao": "Cinto em couro sintético premium, fivela metálica dourada ou prata. Disponível em preto e marrom. Tamanhos P, M, G.",
        "disponibilidade": True,
        "imagem_url": "https://images.unsplash.com/photo-1624623278313-a930126a11c3?w=600&q=80",
        "imagem_local": "",
        "tags": ["cinto", "couro", "casual", "acessório", "fivela"],
        "destaque": False,
    },
]


def seed(reset: bool = False):
    init_db()
    db = SessionLocal()
    try:
        if reset:
            deleted = db.query(Product).delete()
            db.commit()
            print(f"🗑️  {deleted} produto(s) removido(s).")

        existing = {p.id for p in db.query(Product.id).all()}
        added = 0

        for data in PRODUCTS:
            if data["id"] not in existing:
                p = Product(
                    id=data["id"],
                    nome=data["nome"],
                    categoria=data["categoria"],
                    preco=data["preco"],
                    descricao=data["descricao"],
                    disponibilidade=data["disponibilidade"],
                    imagem_url=data.get("imagem_url", ""),
                    imagem_local=data.get("imagem_local", ""),
                    tags=json.dumps(data.get("tags", []), ensure_ascii=False),
                    destaque=data.get("destaque", False),
                )
                db.add(p)
                added += 1

        db.commit()
        print(f"✅  {added} produto(s) inserido(s). Total no catálogo: {db.query(Product).count()}")

    finally:
        db.close()


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    seed(reset=reset)
