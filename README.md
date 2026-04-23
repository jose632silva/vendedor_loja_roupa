# 🛍️ Agente de Vendas v2 — Produção

Atendente virtual de loja completo, construído com **[Agno](https://github.com/agno-agi/agno)**, suportando **Claude**, **GPT-4o** e **Groq**. Inclui banco de dados persistente, memória de clientes, vitrine de produtos com imagens e interface premium de e-commerce.

---

## ✨ Funcionalidades

| Feature | Descrição |
|---|---|
| 🤖 **Multi-Provider** | Claude (Anthropic), GPT-4o (OpenAI) ou Groq (Llama) — troque com 1 variável |
| 💾 **Banco de Dados** | SQLite (padrão) ou PostgreSQL — histórico completo de conversas |
| 🧠 **Memória de Clientes** | Reconhece clientes que voltam, lembra preferências e histórico |
| 🛒 **Vitrine com Imagens** | Pasta `products/images/` para fotos reais dos produtos |
| 🎨 **UI Luxury** | Interface de chat premium estilo boutique de alto padrão |
| 📦 **Cards de Produto** | Imagem + preço + disponibilidade + descrição no próprio chat |
| 🔌 **API REST** | Endpoints FastAPI documentados em `/docs` |
| 🚀 **Pronto para Produção** | CORS, WAL mode no SQLite, error handling, static files |

---

## 📁 Estrutura

```
loja_v2/
├── config.py            # ⚙️  Configurações centrais (provider, DB, server)
├── database.py          # 🗄️  Modelos SQLAlchemy + helpers de DB
├── agent.py             # 🤖  Agente Agno com multi-provider e 7 tools
├── app.py               # 🌐  Servidor FastAPI (API + static files)
├── seed_db.py           # 🌱  Popula o banco com produtos de exemplo
├── requirements.txt     # 📋  Dependências Python
├── .env.example         # 🔑  Template de variáveis de ambiente
│
├── products/
│   └── images/          # 📸  COLOQUE AS FOTOS DOS PRODUTOS AQUI
│       └── README.md    # Instruções de nomenclatura e especificações
│
└── static/
    └── index.html       # 💬  Interface de chat premium
```

---

## 🚀 Instalação & Execução

### 1. Instalar dependências

```bash
cd loja_v2
pip install -r requirements.txt
```

### 2. Configurar variáveis de ambiente

```bash
cp .env.example .env
# Edite .env — preencha LLM_PROVIDER e a chave API correspondente
```

### 3. Popular o banco de dados

```bash
python seed_db.py
# Para resetar: python seed_db.py --reset
```

### 4. Iniciar o servidor

```bash
python app.py
```

### 5. Acessar a interface

Abra **http://localhost:8000** no browser.

---

## 🔄 Trocar de Provider LLM

Edite o `.env`:

```env
# Para Claude (Anthropic):
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Para GPT-4o (OpenAI):
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Para Groq (Llama 3.3 70B):
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
```

Reinicie o servidor após alterar.

---

## 📸 Adicionando Imagens de Produtos

1. Coloque as fotos em `products/images/` (JPG, PNG, WebP)
2. No `seed_db.py`, preencha `imagem_local` com o nome do arquivo:

```python
{
    "id": "CAL001",
    "imagem_local": "cal001-tenis-runner.jpg",   # ← arquivo em products/images/
    "imagem_url": "https://fallback.url/img.jpg", # ← fallback se arquivo não existir
}
```

3. Rode `python seed_db.py --reset` para reinserir com as novas imagens.

---

## 🔌 Endpoints da API

| Método | Endpoint | Descrição |
|---|---|---|
| `POST` | `/chat` | Envia mensagem, recebe resposta + produtos |
| `GET` | `/products` | Lista todos os produtos |
| `GET` | `/products/featured` | Produtos em destaque (vitrine) |
| `GET` | `/products/{id}` | Detalhe de produto |
| `POST` | `/identify` | Identifica/atualiza perfil do cliente |
| `GET` | `/history/{session_id}` | Histórico da conversa |
| `GET` | `/health` | Status do servidor + provider ativo |
| `GET` | `/docs` | Documentação interativa (Swagger) |

### Exemplo de chat via API

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Quero um tênis para corrida até R$ 300",
    "session_id": "meu-cliente-123"
  }'
```

**Resposta:**
```json
{
  "session_id": "meu-cliente-123",
  "response": "Ótima escolha! Temos dois tênis perfeitos...",
  "products": [
    {
      "id": "CAL001",
      "nome": "Tênis Runner Pro X",
      "preco": 249.90,
      "image_url": "http://localhost:8000/products/images/cal001.jpg",
      "disponibilidade": true,
      ...
    }
  ],
  "customer_name": null,
  "is_returning": false
}
```

---

## 🛠️ Tools do Agente

| Tool | Descrição |
|---|---|
| `buscar_produtos` | Busca livre por texto no catálogo |
| `listar_categorias` | Lista categorias disponíveis |
| `listar_por_categoria` | Filtra por categoria |
| `buscar_por_preco` | Filtra por faixa de preço |
| `verificar_estoque` | Verifica disponibilidade em estoque |
| `detalhe_produto` | Detalhes completos por ID |
| `registrar_preferencia_cliente` | Salva preferências no perfil do cliente |

---

## 🗄️ Schema do Banco

```
customers    — session_id, name, email, phone, preferences (JSON), timestamps
messages     — session_id (FK), role, content, created_at
products     — id, nome, categoria, preco, descricao, disponibilidade,
               imagem_url, imagem_local, tags (JSON), destaque
```

---

## 🚢 Deploy em Produção

### Com PostgreSQL

```env
DATABASE_URL=postgresql+psycopg2://user:pass@db:5432/loja
pip install psycopg2-binary
```

### Com gunicorn + nginx

```bash
pip install gunicorn
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker (exemplo mínimo)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN python seed_db.py
CMD ["python", "app.py"]
```

---

## 🧩 Stack

- **[Agno](https://github.com/agno-agi/agno)** — Framework de agentes IA
- **[Anthropic Claude](https://anthropic.com)** / **[OpenAI](https://openai.com)** / **[Groq](https://groq.com)** — LLMs
- **[FastAPI](https://fastapi.tiangolo.com)** + **[Uvicorn](https://www.uvicorn.org)** — API REST
- **[SQLAlchemy](https://sqlalchemy.org)** — ORM (SQLite / PostgreSQL)
- HTML + CSS + JS Vanilla — Interface premium (sem framework extra)
